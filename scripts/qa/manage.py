"""Local QA management. Never imports the destructive pytest bootstrap."""

import argparse
import asyncio
import getpass
import json
import os
import secrets
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env.qa"
STATE = ROOT / ".codex-tmp" / "qa-process.json"
DB = "mountain_fairytale_qa"
ROLE = "mountain_fairytale_qa_app"
HOST = "127.0.0.1"
PORT = 5432
API_PORT = 8001
ALEMBIC = ROOT / "src/common/infra/db/postgres/alembic/alembic.ini"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load():
    v = dict(dotenv_values(ENV))
    dev = dotenv_values(ROOT / ".env")
    require(v.get("POSTGRES_DB") == DB and DB != dev.get("POSTGRES_DB"), "QA/development database conflict")
    require(v.get("POSTGRES_HOST") == HOST and v.get("POSTGRES_PORT") == str(PORT), "Unexpected PostgreSQL endpoint")
    require(v.get("POSTGRES_USER") == ROLE, "Unexpected QA role")
    require(v.get("QA_ALLOW") == "local-qa-only" and bool(v.get("QA_MARKER")), "Explicit QA authorization missing")
    require(
        bool(v.get("JWT_SECRET_KEY")) and v["JWT_SECRET_KEY"] != dev.get("JWT_SECRET_KEY"),
        "QA JWT secret must be separate",
    )
    require(
        bool(v.get("ADMIN_PASSWORD")) and v["ADMIN_PASSWORD"] != dev.get("ADMIN_PASSWORD"),
        "QA admin secret must be separate",
    )
    return v


def activate(v):
    # Do not inherit monitoring, map keys or any application secrets from the caller.
    for key in list(os.environ):
        if key.startswith(("POSTGRES_", "JWT_", "ADMIN_", "SENTRY_", "GEOAPIFY_", "FLUTTER_")):
            del os.environ[key]
    os.environ.update({k: str(value) for k, value in v.items()})


def connect(v):
    return psycopg.connect(
        host=HOST,
        port=PORT,
        dbname=v["POSTGRES_DB"],
        user=v["POSTGRES_USER"],
        password=v["POSTGRES_PASSWORD"],
        connect_timeout=5,
    )


def validate_identity(v, actual, marker):
    require(v.get("QA_ALLOW") == "local-qa-only", "QA operation not authorized")
    require(v.get("POSTGRES_DB") == DB and actual["db"] == DB, "Actual database mismatch")
    require(v.get("POSTGRES_HOST") == HOST and str(v.get("POSTGRES_PORT")) == str(PORT), "Configured server mismatch")
    require(actual["host"] == HOST and actual["port"] == PORT, "Actual PostgreSQL server mismatch")
    require(actual["role"] == ROLE and actual["session_role"] == ROLE, "Actual role mismatch")
    require(
        not any(
            actual[k]
            for k in ("super", "createdb", "createrole", "replication", "bypass", "memberships", "other_owned")
        ),
        "Unsafe role privileges",
    )
    require(actual["owner"] == ROLE and actual["marker_owner"] == "postgres", "Unexpected ownership")
    require(marker == v["QA_MARKER"], "QA marker missing or mismatched")


def verify(c, v):
    with c.cursor(row_factory=psycopg.rows.dict_row) as cur:
        actual = cur.execute("""SELECT current_database() AS db, host(inet_server_addr()) AS host,
          inet_server_port() AS port, current_user AS role, session_user AS session_role,
          r.rolsuper AS super, r.rolcreatedb AS createdb, r.rolcreaterole AS createrole,
          r.rolreplication AS replication, r.rolbypassrls AS bypass,
          EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid) AS memberships,
          EXISTS(SELECT 1 FROM pg_database WHERE datdba=r.oid AND datname<>current_database()) AS other_owned,
          pg_get_userbyid(d.datdba) AS owner,
          (SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='qa_control') AS marker_owner
          FROM pg_roles r, pg_database d WHERE r.rolname=current_user AND d.datname=current_database()""").fetchone()
        require(
            cur.execute(
                "SELECT NOT has_table_privilege(current_user,"
                "'qa_control.identity','INSERT,UPDATE,DELETE,TRUNCATE') AS safe"
            ).fetchone()["safe"],
            "QA marker must be read-only",
        )
        marker = cur.execute("SELECT token FROM qa_control.identity WHERE singleton").fetchone()
    validate_identity(v, actual, marker["token"] if marker else None)
    return actual


def migrate(v):
    with connect(v) as c:
        verify(c, v)
    activate(v)
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC), "upgrade", "head"],
        cwd=ROOT,
        env={k: value for k, value in os.environ.items() if k != "QA_PG_ADMIN_PASSWORD"},
        check=True,
    )


def initialize():
    require(not ENV.exists(), ".env.qa already exists; inspect origin, never overwrite")
    with socket.socket() as s:
        s.bind((HOST, API_PORT))
    password = secrets.token_hex(24)
    marker = secrets.token_hex(32)
    admin_password = os.environ.get("QA_PG_ADMIN_PASSWORD") or getpass.getpass(
        "Local PostgreSQL administrator password: "
    )
    with psycopg.connect(
        host=HOST, port=PORT, user="postgres", password=admin_password, dbname="postgres", autocommit=True
    ) as c:
        require(
            not c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB,)).fetchone(),
            "QA database already exists; owner approval required",
        )
        require(
            not c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (ROLE,)).fetchone(),
            "QA role already exists; owner approval required",
        )
        c.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(ROLE), sql.Literal(password))
        )
        c.execute(
            sql.SQL(
                "CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8' "
                "LC_COLLATE 'Russian_Russia.utf8' LC_CTYPE 'Russian_Russia.utf8'"
            ).format(sql.Identifier(DB), sql.Identifier(ROLE))
        )
    v = dict(
        POSTGRES_HOST=HOST,
        POSTGRES_PORT=str(PORT),
        POSTGRES_DB=DB,
        POSTGRES_USER=ROLE,
        POSTGRES_PASSWORD=password,
        JWT_SECRET_KEY=secrets.token_hex(32),
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES="15",
        REFRESH_TOKEN_EXPIRE_DAYS="1",
        ADMIN_USERNAME="qa_admin",
        ADMIN_PASSWORD=secrets.token_hex(16),
        QA_ALLOW="local-qa-only",
        QA_MARKER=marker,
        CONFIG_DIR=str(ROOT),
        SENTRY_DSN="",
        SENTRY_ENVIRONMENT="qa",
        GEOAPIFY_API_KEY="",
        FLUTTER_MONITORING_ENABLED="false",
        APP_HOST=HOST,
        APP_PORT=str(API_PORT),
    )
    # Save immediately so a partial initialization can be diagnosed without replacing resources.
    with ENV.open("x", encoding="utf-8") as f:
        f.write("".join(f"{k}={value}\n" for k, value in v.items()))
    with psycopg.connect(host=HOST, port=PORT, user="postgres", password=admin_password, dbname=DB) as c:
        require(
            c.execute("SELECT current_database(),host(inet_server_addr()),inet_server_port()").fetchone()
            == (DB, HOST, PORT),
            "Initialization target mismatch",
        )
        c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DB)))
        c.execute("CREATE SCHEMA qa_control AUTHORIZATION postgres")
        c.execute("REVOKE ALL ON SCHEMA qa_control FROM PUBLIC")
        c.execute(
            "CREATE TABLE qa_control.identity(singleton boolean PRIMARY KEY CHECK(singleton), token text NOT NULL)"
        )
        c.execute("INSERT INTO qa_control.identity VALUES(true,%s)", (marker,))
        c.execute(sql.SQL("GRANT USAGE ON SCHEMA qa_control TO {}").format(sql.Identifier(ROLE)))
        c.execute(sql.SQL("GRANT SELECT ON qa_control.identity TO {}").format(sql.Identifier(ROLE)))
    with connect(v) as c:
        verify(c, v)
    migrate(v)
    print("Created isolated QA database and configuration; secrets are in ignored .env.qa")


def reset(v, confirmation):
    require(confirmation == "RESET " + DB, "Explicit confirmation missing: type RESET " + DB)
    require(not STATE.exists(), "Stop QA backend before reset; process state exists")
    with connect(v) as c:
        verify(c, v)
        require(
            c.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"
            ).fetchone()[0]
            == 0,
            "Other QA sessions exist",
        )
        # Same checked connection/transaction; marker lives outside public and survives.
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
    migrate(v)
    with connect(v) as c:
        verify(c, v)
    print("QA schema reset and migrated. Administrator is recreated on next start.")


async def check_engine(postgres, v):
    from sqlalchemy import text

    async with postgres._engine.connect() as c:
        row = (
            await c.execute(text("SELECT current_database(),host(inet_server_addr()),inet_server_port(),current_user"))
        ).one()
        require(tuple(row) == (DB, HOST, PORT, ROLE), "FastAPI actual connection mismatch")
        token = (await c.execute(text("SELECT token FROM qa_control.identity WHERE singleton"))).scalar_one()
        require(token == v["QA_MARKER"], "FastAPI marker mismatch")


def serve(v):
    import uvicorn

    from src.common.api.app import fastapi_app
    from src.common.infra.db.postgres.database import Postgres

    original = fastapi_app.router.lifespan_context
    run_id = secrets.token_hex(16)

    @fastapi_app.middleware("http")
    async def qa_attestation(request, call_next):
        if request.url.path == "/health/ready":
            await check_engine(request.app.state.postgres, v)
        response = await call_next(request)
        response.headers["X-QA-Run"] = run_id
        return response

    @asynccontextmanager
    async def guarded(app):
        # Validate the real async engine before bootstrap can write anything.
        probe = Postgres()
        try:
            await check_engine(probe, v)
        finally:
            await probe.dispose()
        async with original(app):
            await check_engine(app.state.postgres, v)
            yield

    fastapi_app.router.lifespan_context = guarded
    with socket.socket() as port_probe:
        port_probe.bind((HOST, API_PORT))
    require(not STATE.exists(), "QA process state exists; run stop/inspect first")
    STATE.parent.mkdir(exist_ok=True)
    # Creation time is independently verified by the stop script to avoid recycled PIDs.
    result = subprocess.check_output(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-Process -Id {os.getpid()}).StartTime.ToUniversalTime().Ticks.ToString()",
        ],
        text=True,
    ).strip()
    STATE.write_text(json.dumps({"pid": os.getpid(), "created": result, "run_id": run_id}), encoding="utf-8")
    print(f"Flutter QA server: http://{HOST}:{API_PORT}", flush=True)
    try:
        uvicorn.run(fastapi_app, host=HOST, port=API_PORT, workers=1)
    finally:
        STATE.unlink(missing_ok=True)


def status(v):
    import httpx
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    with connect(v) as c:
        identity = verify(c, v)
        revision = c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        require(
            revision == ScriptDirectory.from_config(Config(str(ALEMBIC))).get_current_head(),
            "Migration revision is behind head",
        )
        extensions = c.execute("SELECT extname FROM pg_extension").fetchall()
        require(("pg_trgm",) in extensions and ("uuid-ossp",) in extensions, "Required extension missing")
        print("Database:", identity["db"], "server:", HOST, PORT, "role:", ROLE, "marker: verified")
        print("Alembic:", revision, "extensions:", extensions)
    with httpx.Client(base_url=f"http://{HOST}:{API_PORT}", timeout=5, trust_env=False) as client:
        for path in ["/health/live", "/health/ready"]:
            response = client.get(path)
            response.raise_for_status()
            require(
                response.headers.get("X-QA-Run") == json.loads(STATE.read_text(encoding="utf-8"))["run_id"],
                "API is not the managed QA process",
            )
            print(path, response.json()["data"]["status"])
    print("API DB identity: actual engine and marker verified at startup AND /health/ready; run attestation matched")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "serve", "check", "migrate", "reset", "admin-password"])
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "init":
        initialize()
        return
    v = load()
    activate(v)
    with connect(v) as c:
        verify(c, v)
    if args.command == "serve":
        serve(v)
    elif args.command == "check":
        status(v)
    elif args.command == "migrate":
        migrate(v)
    elif args.command == "reset":
        reset(v, input("Destructive operation. Type RESET " + DB + ": "))
    elif args.command == "admin-password":
        from src.common.cli.main import change_admin_password

        asyncio.run(change_admin_password())


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # DB exceptions may embed credentials/SQL; do not dump them to logs.
        print(
            "QA operation refused/failed:",
            str(error) if isinstance(error, RuntimeError) else type(error).__name__,
            file=sys.stderr,
        )
        sys.exit(1)
