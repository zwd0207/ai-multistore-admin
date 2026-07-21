"""encrypted inquiry answer conversation

Revision ID: 7e2a9c4f1b36
Revises: d4b7a91c2e6f
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e2a9c4f1b36"
down_revision: Union[str, None] = "d4b7a91c2e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pxg_naver_readonly_customer_inquiries",
        sa.Column("encrypted_customer_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "pxg_naver_readonly_customer_inquiries",
        sa.Column("customer_name_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "pxg_naver_readonly_customer_inquiries",
        sa.Column(
            "customer_name_length",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "pxg_naver_readonly_customer_inquiries",
        sa.Column("encrypted_answer_content", sa.Text(), nullable=True),
    )
    op.add_column(
        "pxg_naver_readonly_customer_inquiries",
        sa.Column("answer_content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "pxg_naver_readonly_customer_inquiries",
        sa.Column(
            "answer_content_length",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("pxg_naver_readonly_customer_inquiries", "answer_content_length")
    op.drop_column("pxg_naver_readonly_customer_inquiries", "answer_content_hash")
    op.drop_column("pxg_naver_readonly_customer_inquiries", "encrypted_answer_content")
    op.drop_column("pxg_naver_readonly_customer_inquiries", "customer_name_length")
    op.drop_column("pxg_naver_readonly_customer_inquiries", "customer_name_hash")
    op.drop_column("pxg_naver_readonly_customer_inquiries", "encrypted_customer_name")
