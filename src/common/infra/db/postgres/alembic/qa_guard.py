"""Opt-in verification on Alembic's actual connection, independent of the QA CLI."""

from collections.abc import Mapping
from hmac import compare_digest

from alembic.util import CommandError
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError


def verify_qa_migration_connection(
    connection: Connection, arguments: Mapping[str, str], environ: Mapping[str, str]
) -> None:
    expected = tuple(arguments.get(key, "") for key in ("qa_database", "qa_host", "qa_port", "qa_role"))
    marker = environ.get("QA_MARKER", "")
    if not all(expected) or not marker or environ.get("QA_ALLOW") != "local-qa-only":
        raise CommandError("QA migration guard: required QA configuration is missing; migrations refused.")
    try:
        port = int(expected[2])
    except ValueError:
        raise CommandError("QA migration guard: invalid expected port; migrations refused.") from None

    try:
        actual = connection.execute(
            text("SELECT current_database(), host(inet_server_addr()), inet_server_port(), current_user, session_user")
        ).one()
        if tuple(actual) != (expected[0], expected[1], port, expected[3], expected[3]):
            raise CommandError("QA migration guard: actual database/server/role mismatch; migrations refused.")
        tokens = connection.execute(text("SELECT token FROM qa_control.identity WHERE singleton")).scalars().all()
    except SQLAlchemyError:
        raise CommandError("QA migration guard: identity or marker unavailable; migrations refused.") from None
    if len(tokens) != 1 or not isinstance(tokens[0], str) or not compare_digest(tokens[0].encode(), marker.encode()):
        raise CommandError("QA migration guard: marker mismatch; migrations refused.")
