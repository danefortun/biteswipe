"""profile notifications and email verification

Revision ID: 0001_profile_notifications_email_verification
Revises:
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_profile_notifications_email_verification"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("email_verification_token", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("email_verification_sent_at", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("joined_at", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("profile_stat_visibility_json", sa.Text(), nullable=True, server_default="{}"))
        batch_op.add_column(sa.Column("profile_stat_enabled_json", sa.Text(), nullable=True, server_default="{}"))
        batch_op.add_column(sa.Column("profile_stat_order_json", sa.Text(), nullable=True, server_default="[]"))
        batch_op.add_column(sa.Column("profile_badge_visibility_json", sa.Text(), nullable=True, server_default="{}"))
        batch_op.add_column(sa.Column("profile_badge_order_json", sa.Text(), nullable=True, server_default="[]"))
        batch_op.create_index("ix_users_username", ["username"], unique=True)
        batch_op.create_index("ix_users_email_verification_token", ["email_verification_token"], unique=False)

    op.create_table(
        "user_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("link_url", sa.String(length=255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_notifications_user_id", "user_notifications", ["user_id"], unique=False)
    op.create_index("ix_user_notifications_kind", "user_notifications", ["kind"], unique=False)
    op.create_index("ix_user_notifications_is_read", "user_notifications", ["is_read"], unique=False)
    op.create_index("ix_user_notifications_created_at", "user_notifications", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_user_notifications_created_at", table_name="user_notifications")
    op.drop_index("ix_user_notifications_is_read", table_name="user_notifications")
    op.drop_index("ix_user_notifications_kind", table_name="user_notifications")
    op.drop_index("ix_user_notifications_user_id", table_name="user_notifications")
    op.drop_table("user_notifications")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_email_verification_token")
        batch_op.drop_index("ix_users_username")
        batch_op.drop_column("email_verification_sent_at")
        batch_op.drop_column("email_verification_token")
        batch_op.drop_column("email_verified")
        batch_op.drop_column("profile_stat_enabled_json")
        batch_op.drop_column("profile_stat_visibility_json")
        batch_op.drop_column("profile_badge_order_json")
        batch_op.drop_column("profile_badge_visibility_json")
        batch_op.drop_column("profile_stat_order_json")
        batch_op.drop_column("joined_at")
        batch_op.drop_column("username")
