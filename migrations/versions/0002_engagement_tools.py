"""add engagement tools

Revision ID: 0002_engagement_tools
Revises: 0001_profile_notifications_email_verification
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_engagement_tools"
down_revision = "0001_profile_notifications_email_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("deck_streak_count", sa.Integer(), server_default="0"))
        batch_op.add_column(sa.Column("deck_last_opened_on", sa.String(length=10)))
        batch_op.add_column(sa.Column("dare_points", sa.Integer(), server_default="0"))

    with op.batch_alter_table("saved_restaurants") as batch_op:
        batch_op.add_column(sa.Column("student_discount", sa.Boolean(), server_default=sa.false()))

    op.create_table(
        "avoided_restaurants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("place_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("user_id", "place_id", name="uq_avoided_restaurant_user_place"),
    )
    op.create_index("ix_avoided_restaurants_user_id", "avoided_restaurants", ["user_id"])
    op.create_index("ix_avoided_restaurants_place_id", "avoided_restaurants", ["place_id"])


def downgrade() -> None:
    op.drop_index("ix_avoided_restaurants_place_id", table_name="avoided_restaurants")
    op.drop_index("ix_avoided_restaurants_user_id", table_name="avoided_restaurants")
    op.drop_table("avoided_restaurants")

    with op.batch_alter_table("saved_restaurants") as batch_op:
        batch_op.drop_column("student_discount")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("dare_points")
        batch_op.drop_column("deck_last_opened_on")
        batch_op.drop_column("deck_streak_count")
