"""Isolated local load tools. No operation implicitly resets a database."""

import argparse
import getpass
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import tomllib
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime

import httpx
import psycopg
from dotenv import dotenv_values
from psycopg import sql

from scripts.qa.manage import ALEMBIC, ROOT, activate
from scripts.qa.seed import save
from src.common.infra.db.postgres.alembic.load_guard import DB, HOST, PORT, ROLE, async_guard, require, verify


ENV = ROOT / ".env.load"
DIRECTORY = ROOT / ".codex-tmp/load"
STATE = DIRECTORY / "process.json"
BASE_URL = "http://127.0.0.1:8002"


def load():
    v = dict(dotenv_values(ENV))
    require(
        (v.get("POSTGRES_DB"), v.get("POSTGRES_USER"), v.get("POSTGRES_HOST"), v.get("POSTGRES_PORT"))
        == (DB, ROLE, HOST, str(PORT)),
        "Invalid load configuration",
    )
    require(v.get("LOAD_ALLOW") == "local-load-only" and v.get("LOAD_MARKER"), "Load marker required")
    for other in (".env", ".env.qa"):
        original = dotenv_values(ROOT / other)
        require(original.get("POSTGRES_DB") != DB, "Database conflicts with existing environment")
        for field in ("JWT_SECRET_KEY", "ADMIN_PASSWORD"):
            require(v.get(field) and v[field] != original.get(field), "Load secrets must be separate")
    return v


def connect(v):
    return psycopg.connect(
        host=HOST,
        port=PORT,
        dbname=v["POSTGRES_DB"],
        user=v["POSTGRES_USER"],
        password=v["POSTGRES_PASSWORD"],
        connect_timeout=5,
        autocommit=True,
    )


def initialize(confirmation):
    require(confirmation == DB, "init requires --confirm " + DB)
    require(not ENV.exists(), ".env.load exists; refusing overwrite or automatic recovery")
    require(
        all(dotenv_values(ROOT / path).get("POSTGRES_DB") != DB for path in (".env", ".env.qa")),
        "Load database name conflicts with an existing environment",
    )
    with socket.socket() as probe:
        probe.bind((HOST, 8002))
    password, marker = secrets.token_hex(24), secrets.token_hex(32)
    admin = os.environ.get("LOAD_PG_ADMIN_PASSWORD") or getpass.getpass("Local PostgreSQL admin password: ")
    with psycopg.connect(
        host=HOST, port=PORT, dbname="postgres", user="postgres", password=admin, autocommit=True
    ) as c:
        require(
            c.execute("SELECT current_database(),host(inet_server_addr()),inet_server_port(),current_user").fetchone()
            == ("postgres", HOST, PORT, "postgres"),
            "Bootstrap endpoint mismatch",
        )
        for query, name in (
            ("SELECT 1 FROM pg_database WHERE datname=%s", DB),
            ("SELECT 1 FROM pg_roles WHERE rolname=%s", ROLE),
        ):
            require(not c.execute(query, (name,)).fetchone(), "Resource exists; inspect partial initialization")
        c.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(ROLE), sql.Literal(password))
        )
        c.execute(
            sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'").format(
                sql.Identifier(DB), sql.Identifier(ROLE)
            )
        )
    # Bootstrap is the sole exception to app-role/marker checks: both are created here.
    # Existing databases are rejected above; no adoption or cleanup is attempted.
    v = dict(
        POSTGRES_HOST=HOST,
        POSTGRES_PORT=str(PORT),
        POSTGRES_DB=DB,
        POSTGRES_USER=ROLE,
        POSTGRES_PASSWORD=password,
        LOAD_ALLOW="local-load-only",
        LOAD_MARKER=marker,
        JWT_SECRET_KEY=secrets.token_hex(32),
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES="1440",
        REFRESH_TOKEN_EXPIRE_DAYS="1",
        ADMIN_USERNAME="load_admin",
        ADMIN_PASSWORD=secrets.token_hex(16),
        CONFIG_DIR=str(ROOT),
        SENTRY_DSN="",
        SENTRY_ENVIRONMENT="load",
        GEOAPIFY_API_KEY="",
        FLUTTER_MONITORING_ENABLED="false",
        APP_HOST=HOST,
        APP_PORT="8002",
    )
    with ENV.open("x", encoding="utf-8") as stream:
        stream.write("".join(f"{k}={value}\n" for k, value in v.items()))
    with psycopg.connect(host=HOST, port=PORT, dbname=DB, user="postgres", password=admin) as c:
        require(
            c.execute(
                "SELECT current_database(),host(inet_server_addr()),inet_server_port(),"
                "pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()"
            ).fetchone()
            == (DB, HOST, PORT, ROLE),
            "Bootstrap database mismatch",
        )
        c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DB)))
        c.execute("CREATE SCHEMA load_control AUTHORIZATION postgres")
        c.execute("REVOKE ALL ON SCHEMA load_control FROM PUBLIC")
        c.execute(
            "CREATE TABLE load_control.identity(singleton boolean PRIMARY KEY CHECK(singleton),token text NOT NULL)"
        )
        c.execute("INSERT INTO load_control.identity VALUES(true,%s)", (marker,))
        c.execute(sql.SQL("GRANT USAGE ON SCHEMA load_control TO {}").format(sql.Identifier(ROLE)))
        c.execute(sql.SQL("GRANT SELECT ON load_control.identity TO {}").format(sql.Identifier(ROLE)))
        for extension in ("pg_trgm", "uuid-ossp"):
            c.execute(sql.SQL("CREATE EXTENSION IF NOT EXISTS {}").format(sql.Identifier(extension)))
        require(c.execute("SELECT token FROM load_control.identity").fetchone() == (marker,), "Marker readback failed")
    with connect(v) as c:
        verify(c, v)
    print("Load database initialized; run migrate explicitly. Secrets: ignored .env.load")


def migrate(v):
    with connect(v) as c:
        verify(c, v)
    activate_load(v)
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC), "-x", "load_guard=1", "upgrade", "head"],
        cwd=ROOT,
        check=True,
        env={k: val for k, val in os.environ.items() if k != "LOAD_PG_ADMIN_PASSWORD"},
    )


def reset(v, confirmation):
    """Explicit load-data reset, retaining schema, revision and protected identity."""
    from scripts.qa.seed import exclusive

    require(confirmation == DB, "reset requires --confirm " + DB)
    require(not STATE.exists(), "Stop only load API before reset")
    with exclusive(DIRECTORY), connect(v) as c:
        verify(c, v)
        require(
            c.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"
            ).fetchone()[0]
            == 0,
            "Other load sessions exist",
        )
        tables = c.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version'"
        ).fetchall()
        require(bool(tables), "No migrated load tables")
        intent = DIRECTORY / "reset-pending.json"
        save(intent, {"status": "reset pending; rerun reset with exact confirmation if interrupted"})
        with c.transaction():
            verify(c, v)
            c.execute(
                sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(",").join(sql.Identifier("public", table) for (table,) in tables)
                )
            )
            for (table,) in tables:
                require(
                    c.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("public", table))).fetchone()[0]
                    == 0,
                    "Reset readback failed",
                )
        archive = DIRECTORY / "archives" / str(time.time_ns())
        archive.mkdir(parents=True)
        for path in [DIRECTORY / "objects", *DIRECTORY.glob("*.json")]:
            if path.exists() and path != intent:
                require(path.resolve().parent == DIRECTORY.resolve(), "Unsafe journal archive path")
                path.rename(archive / path.name)
        intent.unlink()
    print("Only load business data reset; schema/marker retained; previous journal archived locally")


def activate_load(v):
    for key in list(os.environ):
        if key.startswith(("QA_", "LOAD_")):
            del os.environ[key]
    activate(v)


def check_revision(c):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    require(
        c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == ScriptDirectory.from_config(Config(str(ALEMBIC))).get_current_head(),
        "Migrations not at head",
    )


def attest(client):
    require(STATE.exists(), "Managed load API absent; run start")
    nonce = json.loads(STATE.read_text(encoding="utf-8"))["run_id"]
    response = client.get("/health/ready")
    require(response.status_code == 200 and response.headers.get("X-Load-Run") == nonce, "Load API attestation failed")
    return nonce


def readonly_token(v):
    """Authenticate the existing LOAD administrator without recording a login event."""
    from src.common.infra.services.password_service import PasswordService
    from src.common.infra.services.token.jwt_service import JwtTokenService
    from src.common.infra.services.token.settings import JwtSettings

    with connect(v) as c:
        verify(c, v)
        with c.transaction():
            c.execute("SET TRANSACTION READ ONLY")
            row = c.execute(
                "SELECT employee_id,password_hash FROM employees WHERE username=%s AND role='admin' AND is_active",
                (v["ADMIN_USERNAME"],),
            ).fetchone()
    require(
        row is not None
        and PasswordService().verify_password(plain_password=v["ADMIN_PASSWORD"], hashed_password=row[1]),
        "Existing active LOAD admin credentials required for read-only authentication",
    )
    settings = JwtSettings(
        **{key: v[key] for key in ("JWT_SECRET_KEY", "JWT_ALGORITHM")},
        ACCESS_TOKEN_EXPIRE_MINUTES=int(v["ACCESS_TOKEN_EXPIRE_MINUTES"]),
        REFRESH_TOKEN_EXPIRE_DAYS=int(v["REFRESH_TOKEN_EXPIRE_DAYS"]),
    )
    return JwtTokenService(settings).create_access_token(employee_id=str(row[0]), role="admin")


@contextmanager
def http_client(v, *, readonly=False):
    with httpx.Client(base_url=BASE_URL, timeout=60, trust_env=False, follow_redirects=False) as client:
        policy = tomllib.loads((ROOT / "client_compatibility.toml").read_text(encoding="utf-8"))
        client.headers["X-Client-Version"] = policy["flutter"]["min_version"]
        attest(client)
        if readonly:
            client.headers["Authorization"] = "Bearer " + readonly_token(v)
            yield client
            return
        response = client.post(
            "/public/auth/login", json={"username": v["ADMIN_USERNAME"], "password": v["ADMIN_PASSWORD"]}
        )
        require(response.status_code == 200, "Load admin login failed")
        client.headers["Authorization"] = "Bearer " + response.json()["data"]["accessToken"]
        yield client


def serve(v):
    import uvicorn
    from sqlalchemy import event

    from src.common.api.app import fastapi_app
    from src.common.infra.db.postgres.alembic.load_guard import statement_guard
    from src.common.infra.db.postgres.database import Postgres

    require(not STATE.exists(), "Load process state exists; inspect/stop first")
    nonce = secrets.token_hex(16)
    original = fastapi_app.router.lifespan_context

    async def protect(postgres):
        async with postgres._engine.connect() as c:
            await async_guard(c, v)

    before_statement = statement_guard(v)

    # Install on all Postgres engines, including bootstrap's engine before its first write.
    from sqlalchemy.engine import Engine

    event.listen(Engine, "before_cursor_execute", before_statement)

    @asynccontextmanager
    async def guarded(app):
        probe = Postgres()
        try:
            await protect(probe)
        finally:
            await probe.dispose()
        async with original(app):
            await protect(app.state.postgres)
            yield

    @fastapi_app.middleware("http")
    async def attestation(request, call_next):
        if request.url.path == "/health/ready":
            await protect(request.app.state.postgres)
        response = await call_next(request)
        response.headers["X-Load-Run"] = nonce
        return response

    fastapi_app.router.lifespan_context = guarded
    with socket.socket() as probe:
        probe.bind((HOST, 8002))
    created = subprocess.check_output(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-Process -Id {os.getpid()}).StartTime.ToUniversalTime().Ticks.ToString()",
        ],
        text=True,
    ).strip()
    save(STATE, {"pid": os.getpid(), "created": created, "run_id": nonce})
    try:
        uvicorn.run(fastapi_app, host=HOST, port=8002, workers=1)
    finally:
        STATE.unlink(missing_ok=True)
        event.remove(Engine, "before_cursor_execute", before_statement)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["init", "check", "serve", "migrate", "reset", "seed", "seed-status", "verify", "benchmark", "report"],
    )
    parser.add_argument("--confirm", help="Required exact database name for init")
    parser.add_argument("--profile", choices=["main", "high"], default="main")
    parser.add_argument("--seed", type=int, default=20261110)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--rate", type=float, default=5, help="Maximum seed HTTP requests/second (0 < rate <= 10)")
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--concurrency", type=int, choices=[1, 2, 3, 4], default=1)
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "init":
        initialize(args.confirm)
        return
    if args.command == "report":
        for name in ("verification.json", "benchmark.json"):
            path = DIRECTORY / name
            print(name, path.read_text(encoding="utf-8") if path.exists() else "NOT RUN")
        return
    v = load()
    activate_load(v)
    require(
        args.command == "reset" or not (DIRECTORY / "reset-pending.json").exists(),
        "Interrupted reset; inspect archive and rerun explicit reset",
    )
    with connect(v) as c:
        verify(c, v)
    if args.command == "migrate":
        migrate(v)
    elif args.command == "reset":
        reset(v, args.confirm)
    elif args.command == "serve":
        serve(v)
    else:
        from scripts.load.seed import LoadSeed
        from scripts.qa.seed import exclusive

        with exclusive(DIRECTORY), connect(v) as c, http_client(v, readonly=args.command != "seed") as client:
            check_revision(c)
            seed = LoadSeed(v, c, client, args)
            if args.command == "seed":
                seed.run()
            elif args.command == "seed-status":
                print(json.dumps(seed.summary(), ensure_ascii=False))
            elif args.command == "check":
                print("Actual load connection, marker, schema and API verified")
            elif args.command == "verify":
                from scripts.load.verify import verify_all

                save(DIRECTORY / "verification.json", {"result": "RUNNING", "timestamp": datetime.now(UTC).isoformat()})
                try:
                    verify_all(seed)
                except Exception as exc:
                    save(
                        DIRECTORY / "verification.json",
                        {
                            "result": "FAIL",
                            "timestamp": datetime.now(UTC).isoformat(),
                            "diagnostic": str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__,
                        },
                    )
                    raise
            elif args.command == "benchmark":
                from scripts.load.benchmark import benchmark

                benchmark(seed, args.requests, args.concurrency)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "Load operation refused/failed:",
            str(error) if isinstance(error, RuntimeError) else type(error).__name__,
            file=sys.stderr,
        )
        sys.exit(1)
