"""add session_id to attempts

Revision ID: 62c61d12010e
Revises: base_0001
Create Date: 2025-12-23 21:09:39.870279

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "62c61d12010e"
down_revision: Union[str, Sequence[str], None] = "base_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("attempts", sa.Column("session_id", sa.String(length=64), nullable=True))
    op.create_index("ix_attempts_session_id", "attempts", ["session_id"])


def downgrade():
    op.drop_index("ix_attempts_session_id", table_name="attempts")
    op.drop_column("attempts", "session_id")


def downgrade() -> None:
    """Downgrade schema."""
    pass
