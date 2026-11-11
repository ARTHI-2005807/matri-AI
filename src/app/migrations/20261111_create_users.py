"""create users

Revision ID: 20261111_create_users
"""
from alembic import op
import sqlalchemy as sa

revision = "20261111_create_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
    )
    op.create_table(
        "tokens",
        sa.Column("token", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
    )
    op.create_table(
        "threads",
        sa.Column("thread_id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
    )


def downgrade():
    op.drop_table("threads")
    op.drop_table("tokens")
    op.drop_table("users")
