from logging.config import fileConfig
from os import environ

import dotenv
from alembic import context
from alembic.util import CommandError
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import SQLAlchemyError

from src.common.domain.base_model import BaseModel
from src.common.infra.db.postgres.alembic.qa_guard import verify_qa_migration_connection
from src.common.infra.db.postgres.settings import PostgresSettings


config = context.config
qa_arguments = context.get_x_argument(as_dictionary=True)
qa_guard = "qa_guard" in qa_arguments
if qa_guard and qa_arguments["qa_guard"] != "1":
    raise CommandError("QA migration guard: qa_guard must be 1; migrations refused.")

dotenv.load_dotenv(encoding="utf-8")
try:
    postgres_settings = PostgresSettings()
except KeyError:
    if qa_guard:
        raise CommandError("QA migration guard: connection configuration missing; migrations refused.") from None
    raise
config.set_main_option(
    "sqlalchemy.url",
    f"{postgres_settings.DB_URL_SYNC}",
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BaseModel.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    if qa_guard:
        raise CommandError("QA migration guard: an online connection is required; offline migrations refused.")
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            if qa_guard:
                # Explicit outer transaction owns both the guard SELECTs and migration writes.
                # Otherwise SQLAlchemy autobegin from SELECT could leave migrations uncommitted.
                with connection.begin():
                    verify_qa_migration_connection(connection, qa_arguments, environ)
                    context.configure(connection=connection, target_metadata=target_metadata)
                    with context.begin_transaction():
                        context.run_migrations()
            else:
                context.configure(connection=connection, target_metadata=target_metadata)
                with context.begin_transaction():
                    context.run_migrations()
    except SQLAlchemyError:
        if qa_guard:
            raise CommandError("QA migration guard: database operation failed; migrations stopped.") from None
        raise
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
