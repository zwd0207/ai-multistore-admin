from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_options = {} if is_sqlite else {
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 5,
    "pool_recycle": 1800,
}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    future=True,
    **engine_options,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401

    if settings.app_env == "production" and not is_sqlite:
        from app.services.schema_version_service import verify_production_schema

        verify_production_schema(engine)
        return
    Base.metadata.create_all(bind=engine)
    if is_sqlite:
        from scripts.upgrade_sync_schema import upgrade as upgrade_sync_schema
        from scripts.upgrade_order_status_events_schema import upgrade as upgrade_order_status_events_schema
        from scripts.upgrade_operation_audit_logs_schema import upgrade as upgrade_operation_audit_logs_schema
        from scripts.upgrade_auth_schema import upgrade as upgrade_auth_schema
        from scripts.upgrade_pxg_naver_readonly_schema import upgrade as upgrade_pxg_naver_readonly_schema
        from scripts.upgrade_shipping_schema import upgrade as upgrade_shipping_schema
        from scripts.upgrade_store_browser_schema import upgrade as upgrade_store_browser_schema
        from scripts.upgrade_store_onboarding_schema import upgrade as upgrade_store_onboarding_schema
        from scripts.upgrade_tenant_schema import upgrade as upgrade_tenant_schema
        from scripts.upgrade_ziniao_directory_schema import upgrade as upgrade_ziniao_directory_schema

        upgrade_sync_schema(run_create_all=False)
        upgrade_order_status_events_schema(run_create_all=False)
        upgrade_operation_audit_logs_schema(run_create_all=False)
        upgrade_auth_schema(run_create_all=False)
        upgrade_shipping_schema(run_create_all=False)
        upgrade_pxg_naver_readonly_schema(run_create_all=False)
        upgrade_store_browser_schema()
        upgrade_store_onboarding_schema()
        upgrade_tenant_schema()
        upgrade_ziniao_directory_schema()
