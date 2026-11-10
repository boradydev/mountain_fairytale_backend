"""Exercise the actual Alembic env.py in subprocesses against new disposable databases."""

import os
import secrets
import subprocess
import sys

import psycopg
import pytest
from alembic.config import Config
from psycopg import sql

from scripts.qa import manage as qa


pytestmark = pytest.mark.skipif(os.environ.get("QA_INFRA_LIVE") != "1", reason="Disposable PostgreSQL opt-in required")


def admin_connection(database="postgres", **kwargs):
    return psycopg.connect(
        host=qa.HOST,
        port=qa.PORT,
        user="postgres",
        password=os.environ["QA_PG_ADMIN_PASSWORD"],
        dbname=database,
        **kwargs,
    )


def run_alembic(resource, *, env=None, expected=None, guarded=True, offline=False, revision="head"):
    expected = resource["expected"] if expected is None else expected
    command = [sys.executable, "-m", "alembic", "-c", str(resource["config"])]
    if guarded:
        for key, value in {"qa_guard": "1", **expected}.items():
            command.extend(["-x", f"{key}={value}"])
    command.extend(["upgrade", revision])
    if offline:
        command.append("--sql")
    return subprocess.run(
        command,
        cwd=qa.ROOT,
        env=resource["env"] if env is None else env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def snapshot(resource, database=None):
    with admin_connection(database or resource["database"]) as c:
        assert c.execute("SELECT current_database(),host(inet_server_addr()),inet_server_port()").fetchone() == (
            database or resource["database"],
            qa.HOST,
            qa.PORT,
        )
        return (
            c.execute("SELECT version_num FROM alembic_version").fetchall(),
            c.execute("SELECT value FROM guard_sentinel ORDER BY value").fetchall(),
            c.execute("SELECT to_regclass('public.guard_applied')").fetchone(),
        )


@pytest.fixture
def migration_resource(tmp_path):
    name = "mf_guard_probe_" + secrets.token_hex(6)
    role = name + "_app"
    wrong_role = name + "_other"
    databases = [name, name + "_decoy"]
    password, wrong_password, marker = (secrets.token_hex(24) for _ in range(3))
    created_databases, created_roles = [], []
    resource = dict(
        database=name, role=role, marker=marker, password=password, wrong_role=wrong_role, wrong_password=wrong_password
    )
    try:
        with admin_connection(autocommit=True) as c:
            for new_role, secret in [(role, password), (wrong_role, wrong_password)]:
                assert not c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (new_role,)).fetchone()
                c.execute(
                    sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                        sql.Identifier(new_role), sql.Literal(secret)
                    )
                )
                created_roles.append(new_role)
            for database in databases:
                assert not c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone()
                owner = role if database == name else wrong_role
                c.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier(owner))
                )
                created_databases.append(database)
        for database in databases:
            with admin_connection(database) as c:
                assert c.execute("SELECT current_database()").fetchone() == (database,)
                c.execute(sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(sql.Identifier(role)))
                c.execute("CREATE SCHEMA qa_control AUTHORIZATION postgres")
                c.execute(
                    "CREATE TABLE qa_control.identity("
                    "singleton boolean PRIMARY KEY CHECK(singleton),token text NOT NULL)"
                )
                c.execute("INSERT INTO qa_control.identity VALUES(true,%s)", (marker,))
                c.execute(sql.SQL("GRANT USAGE ON SCHEMA qa_control TO {}").format(sql.Identifier(role)))
                c.execute(sql.SQL("GRANT SELECT ON qa_control.identity TO {}").format(sql.Identifier(role)))
        # Test-only revisions make any transition observably destructive to a sentinel.
        # The env.py being executed is the real project file, not a stub of its guard.
        (tmp_path / "versions").mkdir()
        real_env = qa.ALEMBIC.parent / "migrations/env.py"
        (tmp_path / "env.py").write_text(f"from runpy import run_path\nrun_path({str(real_env)!r})\n", encoding="utf-8")
        (tmp_path / "versions/base.py").write_text(
            """from alembic import op
revision = 'guard_base'
down_revision = None
def upgrade():
    op.execute('CREATE TABLE guard_sentinel(value text NOT NULL)')
    op.execute("INSERT INTO guard_sentinel VALUES('preserve-me')")
def downgrade():
    op.execute('DROP TABLE guard_sentinel')
""",
            encoding="utf-8",
        )
        (tmp_path / "versions/head.py").write_text(
            """from alembic import op
revision = 'guard_head'
down_revision = 'guard_base'
def upgrade():
    op.execute("UPDATE guard_sentinel SET value='transition-ran'")
    op.execute('CREATE TABLE guard_applied(id integer)')
def downgrade():
    op.execute('DROP TABLE guard_applied')
""",
            encoding="utf-8",
        )
        config = Config(str(qa.ALEMBIC))
        config.set_main_option("script_location", str(tmp_path))
        config.set_main_option("version_locations", str(tmp_path / "versions"))
        resource["config"] = tmp_path / "alembic.ini"
        with resource["config"].open("w", encoding="utf-8") as f:
            config.file_config.write(f)
        resource["expected"] = dict(qa_database=name, qa_role=role, qa_host=qa.HOST, qa_port=str(qa.PORT))
        env = {k: value for k, value in os.environ.items() if k != "QA_PG_ADMIN_PASSWORD"}
        env.update(
            POSTGRES_HOST=qa.HOST,
            POSTGRES_PORT=str(qa.PORT),
            POSTGRES_DB=name,
            POSTGRES_USER=role,
            POSTGRES_PASSWORD=password,
            QA_ALLOW="local-qa-only",
            QA_MARKER=marker,
        )
        resource["env"] = env
        for database in databases:
            result = run_alembic(resource, env={**env, "POSTGRES_DB": database}, guarded=False, revision="guard_base")
            assert result.returncode == 0, "Disposable baseline migration failed"
        resource["decoy"] = databases[1]
        yield resource
    finally:
        # Only resources successfully CREATEd by this fixture can enter this loop.
        # Validate actual server, DB ownership and secret marker before any DROP.
        for database in created_databases:
            with admin_connection(database) as c:
                assert c.execute(
                    "SELECT current_database(),host(inet_server_addr()),inet_server_port()"
                ).fetchone() == (database, qa.HOST, qa.PORT)
                assert c.execute("SELECT token FROM qa_control.identity WHERE singleton").fetchone() == (marker,)
            with admin_connection(autocommit=True) as c:
                assert c.execute(
                    "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s", (database,)
                ).fetchone() == (role if database == name else wrong_role,)
                c.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
        with admin_connection(autocommit=True) as c:
            for new_role in created_roles:
                c.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(new_role)))


@pytest.mark.parametrize(
    "failure",
    [
        "database",
        "role",
        "host",
        "port",
        "missing_marker_table",
        "wrong_marker",
        "missing_marker_secret",
        "missing_permission",
        "missing_expected_database",
        "unreadable_marker",
        "inherited_other_database",
        "offline",
    ],
)
def test_guard_refuses_before_real_transitions(migration_resource, failure):
    r = migration_resource
    env, expected = dict(r["env"]), dict(r["expected"])
    before = {database: snapshot(r, database) for database in [r["database"], r["decoy"]]}
    if failure in ("database", "host", "port"):
        expected["qa_" + failure] = {"database": r["decoy"], "host": "127.0.0.2", "port": "5433"}[failure]
    elif failure == "role":
        env.update(POSTGRES_USER=r["wrong_role"], POSTGRES_PASSWORD=r["wrong_password"])
    elif failure == "wrong_marker":
        env["QA_MARKER"] = secrets.token_hex(24)
    elif failure == "missing_marker_secret":
        env.pop("QA_MARKER")
    elif failure == "missing_permission":
        env.pop("QA_ALLOW")
    elif failure == "missing_expected_database":
        expected.pop("qa_database")
    elif failure == "inherited_other_database":
        # Correct -x identity remains in argv while connection env targets another NEW DB.
        # Decoy even has the same readable secret marker, so its name must stop migration.
        env["POSTGRES_DB"] = r["decoy"]
    with admin_connection(r["database"]) as c:
        if failure == "missing_marker_table":
            c.execute("ALTER TABLE qa_control.identity RENAME TO hidden_identity")
        elif failure == "unreadable_marker":
            c.execute(sql.SQL("REVOKE SELECT ON qa_control.identity FROM {}").format(sql.Identifier(r["role"])))
    try:
        result = run_alembic(r, env=env, expected=expected, offline=failure == "offline")
        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "QA migration guard:" in output
        assert "Running upgrade" not in output
        for secret in [r["marker"], r["password"], r["wrong_password"], env.get("QA_MARKER", "")]:
            if secret:
                assert secret not in output
        for database, state in before.items():
            assert snapshot(r, database) == state
    finally:
        with admin_connection(r["database"]) as c:
            if failure == "missing_marker_table":
                c.execute("ALTER TABLE qa_control.hidden_identity RENAME TO identity")
            elif failure == "unreadable_marker":
                c.execute(sql.SQL("GRANT SELECT ON qa_control.identity TO {}").format(sql.Identifier(r["role"])))


def test_guarded_migration_commits_and_repeat_preserves_data(migration_resource):
    r = migration_resource
    result = run_alembic(r)
    assert result.returncode == 0, "Guarded migration failed"
    state = snapshot(r)
    assert state == ([("guard_head",)], [("transition-ran",)], ("guard_applied",))
    assert run_alembic(r).returncode == 0
    assert snapshot(r) == state


def test_ordinary_alembic_requires_no_qa_configuration(migration_resource):
    r = migration_resource
    env = {k: value for k, value in r["env"].items() if not k.startswith("QA_")}
    with admin_connection(r["database"]) as c:
        c.execute("ALTER TABLE qa_control.identity RENAME TO hidden_identity")
    try:
        assert run_alembic(r, env=env, guarded=False).returncode == 0
        assert snapshot(r)[0] == [("guard_head",)]
    finally:
        with admin_connection(r["database"]) as c:
            c.execute("ALTER TABLE qa_control.hidden_identity RENAME TO identity")


def test_cli_wrong_child_environment_still_activates_guard(migration_resource, monkeypatch):
    r = migration_resource
    for key, value in [("DB", r["database"]), ("ROLE", r["role"]), ("ALEMBIC", r["config"])]:
        monkeypatch.setattr(qa, key, value)
    # Restore caller environment after qa.activate(), including keys it removes.
    original = os.environ.copy()
    actual_run = subprocess.run
    before = snapshot(r, r["decoy"])

    def corrupt_environment(command, **kwargs):
        assert "-x" in command
        assert "qa_guard=1" in command
        assert f"qa_database={r['database']}" in command
        assert r["marker"] not in " ".join(command)
        assert r["password"] not in " ".join(command)
        kwargs["env"]["POSTGRES_DB"] = r["decoy"]
        kwargs.update(capture_output=True, text=True)
        return actual_run(command, **kwargs)

    monkeypatch.setattr(qa.subprocess, "run", corrupt_environment)
    try:
        with pytest.raises(subprocess.CalledProcessError) as failure:
            qa.migrate(r["env"])
        assert "QA migration guard: actual database/server/role mismatch" in failure.value.stderr
        assert "Running upgrade" not in failure.value.stderr
        assert snapshot(r, r["decoy"]) == before
        assert snapshot(r)[0] == [("guard_base",)]
    finally:
        os.environ.clear()
        os.environ.update(original)
