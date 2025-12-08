"""baseline

Revision ID: 1eb7884120f0
Revises: 858ce7f30108
Create Date: 2025-12-08 19:40:16.250527

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1eb7884120f0"
down_revision: Union[str, Sequence[str], None] = "858ce7f30108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
    )
    op.create_index("ix_attempts_created_at", "attempts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_attempts_created_at", table_name="attempts")
    op.drop_table("attempts")
