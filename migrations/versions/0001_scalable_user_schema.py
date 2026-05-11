"""scalable user schema

Revision ID: 0001_scalable_user_schema
Revises:
Create Date: 2026-05-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_scalable_user_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("bio", sa.String(length=256), nullable=True),
        sa.Column("pfp_file_path", sa.String(length=255), nullable=True),
        sa.Column("profile_banner_file_path", sa.String(length=255), nullable=True),
        sa.Column("profile_showcase_file_path", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("campus_theme_domain", sa.String(length=255), nullable=True),
        sa.Column("allergen_interests_json", sa.Text(), nullable=True),
        sa.Column("food_preferences_json", sa.Text(), nullable=True),
        sa.Column("hobby_interests_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_interests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column("value_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("user_id", "category", "value_key", name="uq_user_interest_category_value"),
    )
    op.create_index("ix_user_interests_user_id", "user_interests", ["user_id"])
    op.create_index("ix_user_interests_category", "user_interests", ["category"])
    op.create_index("ix_user_interests_created_at", "user_interests", ["created_at"])

    op.create_table(
        "saved_restaurants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("place_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("photo", sa.String(length=512), nullable=True),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("cuisine", sa.String(length=255), nullable=True),
        sa.Column("price_text", sa.String(length=64), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("user_id", "place_id", name="uq_saved_restaurant_user_place"),
    )
    op.create_index("ix_saved_restaurants_user_id", "saved_restaurants", ["user_id"])
    op.create_index("ix_saved_restaurants_created_at", "saved_restaurants", ["created_at"])

    op.create_table(
        "group_swipe_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("host_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_group_swipe_sessions_code", "group_swipe_sessions", ["code"], unique=True)
    op.create_index("ix_group_swipe_sessions_host_user_id", "group_swipe_sessions", ["host_user_id"])
    op.create_index("ix_group_swipe_sessions_created_at", "group_swipe_sessions", ["created_at"])

    op.create_table(
        "group_swipe_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("group_swipe_sessions.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("joined_at", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("session_id", "user_id", name="uq_group_swipe_member_user"),
    )
    op.create_index("ix_group_swipe_members_session_id", "group_swipe_members", ["session_id"])
    op.create_index("ix_group_swipe_members_user_id", "group_swipe_members", ["user_id"])
    op.create_index("ix_group_swipe_members_joined_at", "group_swipe_members", ["joined_at"])

    op.create_table(
        "group_swipe_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("group_swipe_sessions.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("place_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("restaurant_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("session_id", "user_id", "place_id", name="uq_group_swipe_vote_place"),
    )
    op.create_index("ix_group_swipe_votes_session_id", "group_swipe_votes", ["session_id"])
    op.create_index("ix_group_swipe_votes_user_id", "group_swipe_votes", ["user_id"])
    op.create_index("ix_group_swipe_votes_place_id", "group_swipe_votes", ["place_id"])
    op.create_index("ix_group_swipe_votes_updated_at", "group_swipe_votes", ["updated_at"])


def downgrade():
    op.drop_table("group_swipe_votes")
    op.drop_table("group_swipe_members")
    op.drop_table("group_swipe_sessions")
    op.drop_table("saved_restaurants")
    op.drop_table("user_interests")
    op.drop_table("users")
