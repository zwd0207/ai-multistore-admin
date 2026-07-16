from sqlalchemy import Engine, inspect, text

from app.core.exceptions import ApiError


def verify_production_schema(engine: Engine) -> None:
    """Fail startup when production migrations were not applied explicitly."""

    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        raise ApiError(
            "production database migrations are not applied",
            "database_migration_required",
            503,
        )
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    if not revision:
        raise ApiError(
            "production database migration version is missing",
            "database_migration_required",
            503,
        )
