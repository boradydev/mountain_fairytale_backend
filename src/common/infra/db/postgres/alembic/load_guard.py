"""Independent load guard on the real connection; no configurable database allowlist."""

from hmac import compare_digest

from sqlalchemy import text


DB = "mountain_fairytale_load"
ROLE = "mountain_fairytale_load_app"
HOST = "127.0.0.1"
PORT = 5432
IDENTITY = """SELECT current_database(),host(inet_server_addr()),inet_server_port(),
 current_user,session_user, r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
 OR r.rolreplication OR r.rolbypassrls
 OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid),
 pg_get_userbyid(d.datdba),
 (SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='load_control')
 FROM pg_roles r,pg_database d WHERE r.rolname=current_user AND d.datname=current_database()"""
TOKEN = "SELECT token FROM load_control.identity WHERE singleton"
READ_ONLY = """SELECT NOT has_table_privilege(current_user,
 'load_control.identity','INSERT,UPDATE,DELETE,TRUNCATE')"""


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def validate(config, row, tokens, readonly):
    require(config.get("LOAD_ALLOW") == "local-load-only", "Load authorization missing")
    require(
        tuple(row) == (DB, HOST, PORT, ROLE, ROLE, False, ROLE, "postgres"),
        "Load database/endpoint/role/ownership mismatch",
    )
    marker = config.get("LOAD_MARKER", "")
    require(
        readonly
        and len(tokens) == 1
        and bool(marker)
        and isinstance(tokens[0], str)
        and compare_digest(tokens[0].encode(), marker.encode()),
        "Load marker absent, writable or mismatched",
    )


def verify(connection, config):
    row = connection.execute(IDENTITY).fetchone()
    tokens = [r[0] for r in connection.execute(TOKEN).fetchall()]
    readonly = connection.execute(READ_ONLY).fetchone()[0]
    validate(config, row or (), tokens, readonly)


def migration_guard(connection, config):
    row = connection.execute(text(IDENTITY)).one()
    tokens = connection.execute(text(TOKEN)).scalars().all()
    readonly = connection.execute(text(READ_ONLY)).scalar_one()
    validate(config, row, tokens, readonly)


async def async_guard(connection, config):
    row = (await connection.execute(text(IDENTITY))).one()
    tokens = (await connection.execute(text(TOKEN))).scalars().all()
    readonly = (await connection.execute(text(READ_ONLY))).scalar_one()
    validate(config, row, tokens, readonly)


def statement_guard(config):
    """Check each actual API DBAPI connection before allowing its SQL statement."""

    def before_statement(conn, _cursor, _statement, _parameters, _context, _executemany):
        with conn.connection.cursor() as probe:
            probe.execute(IDENTITY)
            row = probe.fetchone()
            probe.execute(TOKEN)
            tokens = [r[0] for r in probe.fetchall()]
            probe.execute(READ_ONLY)
            validate(config, row, tokens, probe.fetchone()[0])

    return before_statement
