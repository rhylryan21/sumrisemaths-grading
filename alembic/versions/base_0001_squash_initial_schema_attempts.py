import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "base_0001"
down_revision = None  # <-- new base of the tree
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_attempts_created_at", "attempts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_attempts_created_at", table_name="attempts")
    op.drop_table("attempts")
