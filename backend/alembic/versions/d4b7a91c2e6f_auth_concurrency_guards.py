"""auth concurrency guards

Revision ID: d4b7a91c2e6f
Revises: 608122e7c9e6
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4b7a91c2e6f"
down_revision: Union[str, None] = "608122e7c9e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        UPDATE tenant_invitations
        SET status='revoked',
            revoked_at=COALESCE(revoked_at, updated_at, created_at),
            updated_at=COALESCE(updated_at, created_at)
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY email_hash ORDER BY created_at DESC, id DESC
                ) AS duplicate_rank
                FROM tenant_invitations
                WHERE status IN ('pending', 'pending_mfa')
            ) ranked
            WHERE duplicate_rank > 1
        )
    """))
    op.create_index(
        "uq_tenant_invitations_active_email_hash",
        "tenant_invitations",
        ["email_hash"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending', 'pending_mfa')"),
        postgresql_where=sa.text("status IN ('pending', 'pending_mfa')"),
    )
    op.create_index(
        "uq_erp_users_login_identifier_hash",
        "erp_users",
        ["login_identifier_hash"],
        unique=True,
        sqlite_where=sa.text("login_identifier_hash IS NOT NULL"),
        postgresql_where=sa.text("login_identifier_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_erp_users_login_identifier_hash", table_name="erp_users")
    op.drop_index("uq_tenant_invitations_active_email_hash", table_name="tenant_invitations")
