"""Add viewing confirmation email delivery state.

Revision ID: b84f61ad82c0
Revises: ed11587940a9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b84f61ad82c0"
down_revision: str | None = "ed11587940a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "viewings",
        sa.Column(
            "confirmation_email_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "viewings",
        sa.Column("confirmation_email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("viewings", "confirmation_email_sent_at")
    op.drop_column("viewings", "confirmation_email_status")
