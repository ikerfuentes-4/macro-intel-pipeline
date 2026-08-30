import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Permite `from persistence.db import Base` aunque alembic se invoque desde otro cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from persistence.db import Base  # noqa: E402  -- todos los modelos (import registra las tablas)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# La URL real viene de settings (que a su vez lee .env), NO de alembic.ini -- asi Alembic
# siempre apunta a la misma base de datos que el resto de la aplicacion, sin duplicar config.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata real de la aplicacion (persistence/db.py) -- esto es lo que habilita
# `alembic revision --autogenerate` a detectar cambios de verdad en los modelos.
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # render_as_batch: SQLite no soporta ALTER TABLE para muchas operaciones (borrar
        # columna, cambiar tipo/constraint); Alembic las emula recreando la tabla cuando esto
        # esta activo. En Postgres (Fase 2) esto no tiene efecto -- se ignora automaticamente.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connectable.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
