"""add ops analytics tables

Revision ID: 0003_ops_analytics
Revises: 0002_engagement_tools
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_ops_analytics"
down_revision = "0002_engagement_tools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_filter_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )
    op.create_index("ix_user_filter_usage_user_id", "user_filter_usage", ["user_id"])
    op.create_index("ix_user_filter_usage_created_at", "user_filter_usage", ["created_at"])

    op.create_table(
        "user_deck_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )
    op.create_index("ix_user_deck_events_user_id", "user_deck_events", ["user_id"])
    op.create_index("ix_user_deck_events_event_type", "user_deck_events", ["event_type"])
    op.create_index("ix_user_deck_events_created_at", "user_deck_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_user_deck_events_created_at", table_name="user_deck_events")
    op.drop_index("ix_user_deck_events_event_type", table_name="user_deck_events")
    op.drop_index("ix_user_deck_events_user_id", table_name="user_deck_events")
    op.drop_table("user_deck_events")

    op.drop_index("ix_user_filter_usage_created_at", table_name="user_filter_usage")
    op.drop_index("ix_user_filter_usage_user_id", table_name="user_filter_usage")
    op.drop_table("user_filter_usage")
