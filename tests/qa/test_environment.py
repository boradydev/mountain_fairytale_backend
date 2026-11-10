"""QA guards: these tests never import repository/API autouse fixtures."""

import os
import secrets

import psycopg
import pytest
from psycopg import sql

from scripts.qa import manage as qa


def identity():
    return dict(
        db=qa.DB,
        host=qa.HOST,
        port=qa.PORT,
        role=qa.ROLE,
        session_role=qa.ROLE,
        super=False,
        createdb=False,
        createrole=False,
        replication=False,
        bypass=False,
        memberships=False,
        other_owned=False,
        owner=qa.ROLE,
        marker_owner="postgres",
    )


def config():
    return dict(
        QA_ALLOW="local-qa-only",
        QA_MARKER="marker",
        POSTGRES_DB=qa.DB,
        POSTGRES_HOST=qa.HOST,
        POSTGRES_PORT=str(qa.PORT),
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("db", "mountain_fairytale_sales_live_20261101"),
        ("db", "mountain_fairytale_api_test"),
        ("host", "192.168.0.25"),
        ("port", 5433),
        ("role", "postgres"),
        ("session_role", "postgres"),
        ("super", True),
        ("createdb", True),
        ("createrole", True),
        ("replication", True),
        ("bypass", True),
        ("memberships", True),
        ("other_owned", True),
        ("marker_owner", qa.ROLE),
    ],
)
def test_identity_refuses_mismatch(key, value):
    actual = identity()
    actual[key] = value
    with pytest.raises(RuntimeError):
        qa.validate_identity(config(), actual, "marker")


@pytest.mark.parametrize("marker", [None, "", "another-marker"])
def test_marker_required(marker):
    with pytest.raises(RuntimeError, match="marker"):
        qa.validate_identity(config(), identity(), marker)


def test_explicit_permission_required():
    v = config()
    v["QA_ALLOW"] = ""
    with pytest.raises(RuntimeError, match="authorized"):
        qa.validate_identity(v, identity(), "marker")


def test_missing_confirmation_never_connects(monkeypatch):
    def forbidden(*args):
        pytest.fail("Must refuse before connection")

    monkeypatch.setattr(qa, "connect", forbidden)
    with pytest.raises(RuntimeError, match="confirmation"):
        qa.reset(config(), "")


def test_ordinary_database_configuration_rejected(monkeypatch, tmp_path):
    env = tmp_path / ".env.qa"
    env.write_text("POSTGRES_DB=mountain_fairytale_sales_live_20261101\n")
    monkeypatch.setattr(qa, "ENV", env)
    with pytest.raises(RuntimeError, match="conflict"):
        qa.load()


@pytest.mark.skipif(
    os.environ.get("QA_INFRA_LIVE") != "1", reason="Explicit disposable QA infrastructure opt-in required"
)
def test_disposable_database_migrations_reset_and_persistence(monkeypatch, tmp_path, request):
    # New resources only. Never target the permanent QA or existing pytest DBs.
    name = "mf_qa_probe_" + secrets.token_hex(6)
    role = name + "_app"
    monkeypatch.setattr(qa, "DB", name)
    monkeypatch.setattr(qa, "ROLE", role)
    monkeypatch.setattr(qa, "ENV", tmp_path / ".env.qa")
    monkeypatch.setattr(qa, "STATE", tmp_path / "process.json")
    # initialize() only probes a bind here; no HTTP server subsequently reuses the port.
    # Port zero lets the kernel allocate a free port atomically, including parallel runs.
    monkeypatch.setattr(qa, "API_PORT", 0)
    saved_env = os.environ.copy()

    def restore_environment():
        os.environ.clear()
        os.environ.update(saved_env)

    request.addfinalizer(restore_environment)
    qa.initialize()
    v = qa.load()
    verified = False
    try:
        with qa.connect(v) as c:
            qa.verify(c, v)
            c.execute("CREATE TABLE public.qa_persistence(value text)")
            c.execute("INSERT INTO public.qa_persistence VALUES('synthetic-infrastructure-only')")
        with pytest.raises(RuntimeError, match="already exists"):
            qa.initialize()
        # Temporarily hide the marker only in this freshly-created disposable DB.
        with psycopg.connect(
            host=qa.HOST, port=qa.PORT, user="postgres", password=os.environ["QA_PG_ADMIN_PASSWORD"], dbname=name
        ) as admin:
            assert admin.execute("SELECT current_database()").fetchone() == (name,)
            admin.execute("ALTER TABLE qa_control.identity RENAME TO hidden_identity")
        try:
            with pytest.raises(psycopg.errors.UndefinedTable):
                qa.reset(v, "RESET " + name)
            with qa.connect(v) as c:
                assert c.execute("SELECT count(*) FROM qa_persistence").fetchone()[0] == 1
        finally:
            with psycopg.connect(
                host=qa.HOST, port=qa.PORT, user="postgres", password=os.environ["QA_PG_ADMIN_PASSWORD"], dbname=name
            ) as admin:
                admin.execute("ALTER TABLE qa_control.hidden_identity RENAME TO identity")
        # Migrate/check twice must preserve existing contents.
        qa.migrate(v)
        qa.migrate(v)
        with qa.connect(v) as c:
            qa.verify(c, v)
            assert c.execute("SELECT value FROM qa_persistence").fetchone()[0] == "synthetic-infrastructure-only"
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            assert (
                c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                == ScriptDirectory.from_config(Config(str(qa.ALEMBIC))).get_current_head()
            )
            bad = dict(v, QA_MARKER="missing")
            with pytest.raises(RuntimeError, match="marker"):
                qa.verify(c, bad)
        import asyncio

        from src.common.infra.db.postgres.database import Postgres

        async def verify_async_engine():
            db = Postgres()
            try:
                await qa.check_engine(db, v)
                with pytest.raises(RuntimeError, match="marker"):
                    await qa.check_engine(db, dict(v, QA_MARKER="wrong"))
            finally:
                await db.dispose()

        asyncio.run(verify_async_engine())
        qa.reset(v, "RESET " + name)
        with qa.connect(v) as c:
            qa.verify(c, v)
            assert c.execute("SELECT to_regclass('public.qa_persistence')").fetchone()[0] is None
            assert c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            verified = True
    finally:
        # Cleanup is allowed only after real identity was verified, even on failure.
        with qa.connect(v) as c:
            qa.verify(c, v)
            verified = True
        if verified:
            with psycopg.connect(
                host=qa.HOST,
                port=qa.PORT,
                user="postgres",
                password=os.environ["QA_PG_ADMIN_PASSWORD"],
                dbname="postgres",
                autocommit=True,
            ) as c:
                assert c.execute("SELECT host(inet_server_addr()),inet_server_port()").fetchone() == (qa.HOST, qa.PORT)
                assert c.execute(
                    "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s", (name,)
                ).fetchone() == (role,)
                c.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
                c.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
