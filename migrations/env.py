import os
from alembic import context
from sqlalchemy import create_engine
from logging.config import fileConfig

from App.Database.models import Base

# Alembic Config
config = context.config

# ==============================================
# ✅ ДИНАМИЧЕСКОЕ ОПРЕДЕЛЕНИЕ DATABASE URL
# ==============================================
# 1️⃣ Берём URL из переменной окружения (Heroku, .env, и т.п.)
database_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

# 2️⃣ Исправляем старый формат Heroku (postgres:// → postgresql://)
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# 3️⃣ Устанавливаем URL для Alembic
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
else:
    raise RuntimeError("❌ DATABASE_URL / DB_URL не найдена в окружении!")

# ==============================================
# Настройка логирования и метаданных
# ==============================================
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()