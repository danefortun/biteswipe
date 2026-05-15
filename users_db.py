from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from db import db


INTEREST_FIELD_TO_CATEGORY = {
    "allergen_interests_json": "allergen",
    "food_preferences_json": "food",
    "hobby_interests_json": "hobby",
}


class Users(db.Model):
    id = db.Column("id", db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(32), unique=True, index=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verification_token = db.Column(db.String(128), index=True)
    email_verification_sent_at = db.Column(db.String(40))
    joined_at = db.Column(db.String(40))
    profile_stat_visibility_json = db.Column(db.Text, default="{}")
    profile_stat_enabled_json = db.Column(db.Text, default="{}")
    profile_stat_order_json = db.Column(db.Text, default="[]")
    profile_badge_visibility_json = db.Column(db.Text, default="{}")
    profile_badge_order_json = db.Column(db.Text, default="[]")
    bio = db.Column(db.String(256), default="this is a placeholder!")
    pfp_file_path = db.Column(db.String(255), default="transparentnewdefaultpicture.png")
    profile_banner_file_path = db.Column(db.String(255))
    profile_showcase_file_path = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    campus_theme_domain = db.Column(db.String(255))
    transportation_mode = db.Column(db.String(16))
    pronouns = db.Column(db.String(64))
    last_active_at = db.Column(db.String(40))
    allergen_interests_json = db.Column(db.Text, default="[]")
    food_preferences_json = db.Column(db.Text, default="[]")
    hobby_interests_json = db.Column(db.Text, default="[]")

    def __init__(
        self,
        name: str,
        password: str,
        email: str,
        username: str | None = None,
        bio: str = "this is a placeholder!",
        pfp_file_path: str = "transparentnewdefaultpicture.png",
    ) -> None:
        self.bio = bio
        self.name = name
        self.username = username
        self.email = email
        self.password = password
        self.pfp_file_path = pfp_file_path
        self.joined_at = datetime.now(timezone.utc).isoformat()

    def __repr__(self) -> str:
        return (
            f"<User id={self.id}, name={self.name}, email={self.email}, "
            f"location={self.latitude},{self.longitude}>"
        )

    def get_interest_list(self, field_name: str) -> list[str]:
        category = INTEREST_FIELD_TO_CATEGORY.get(field_name)
        if category and self.id:
            rows = (
                UserInterest.query.filter_by(user_id=self.id, category=category)
                .order_by(UserInterest.id.asc())
                .all()
            )
            if rows:
                return [row.value for row in rows]

        value = getattr(self, field_name, "[]") or "[]"
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return []

        if not isinstance(parsed, list):
            return []

        return [str(item) for item in parsed if str(item).strip()]

    def set_interest_list(self, field_name: str, values: list[Any]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()

        for value in values:
            text = str(value).strip()
            key = text.lower()

            if not text or key in seen:
                continue

            cleaned.append(text[:64])
            seen.add(key)

        cleaned = cleaned[:30]
        setattr(self, field_name, json.dumps(cleaned))

        category = INTEREST_FIELD_TO_CATEGORY.get(field_name)
        if not category or not self.id:
            return

        UserInterest.query.filter_by(user_id=self.id, category=category).delete()
        for value in cleaned:
            db.session.add(UserInterest(user_id=self.id, category=category, value=value))


class UserInterest(db.Model):
    __tablename__ = "user_interests"
    __table_args__ = (
        db.UniqueConstraint("user_id", "category", "value_key", name="uq_user_interest_category_value"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category = db.Column(db.String(32), nullable=False, index=True)
    value = db.Column(db.String(64), nullable=False)
    value_key = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.String(40), nullable=False, index=True)

    user = db.relationship("Users", backref=db.backref("interest_rows", lazy=True, cascade="all, delete-orphan"))

    def __init__(self, user_id: int, category: str, value: str) -> None:
        self.user_id = user_id
        self.category = category
        self.value = value[:64]
        self.value_key = value.strip().lower()[:64]
        self.created_at = datetime.now(timezone.utc).isoformat()


class SavedRestaurant(db.Model):
    __tablename__ = "saved_restaurants"
    __table_args__ = (
        db.UniqueConstraint("user_id", "place_id", name="uq_saved_restaurant_user_place"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    place_id = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    source = db.Column(db.String(64), default="openstreetmap")
    address = db.Column(db.String(512))
    photo = db.Column(db.String(512))
    distance_meters = db.Column(db.Float)
    cuisine = db.Column(db.String(255))
    price_text = db.Column(db.String(64))
    rating = db.Column(db.Float)
    review_count = db.Column(db.Integer)
    website = db.Column(db.String(512))
    created_at = db.Column(db.String(40), nullable=False, index=True)

    user = db.relationship("Users", backref=db.backref("saved_restaurants", lazy=True))

    def __init__(
        self,
        user_id: int,
        place_id: str,
        name: str,
        source: str = "openstreetmap",
        address: str | None = None,
        photo: str | None = None,
        distance_meters: float | None = None,
        cuisine: str | None = None,
        price_text: str | None = None,
        rating: float | None = None,
        review_count: int | None = None,
        website: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.place_id = place_id
        self.name = name
        self.source = source
        self.address = address
        self.photo = photo
        self.distance_meters = distance_meters
        self.cuisine = cuisine
        self.price_text = price_text
        self.rating = rating
        self.review_count = review_count
        self.website = website
        self.created_at = datetime.now(timezone.utc).isoformat()


class UserRestaurantRating(db.Model):
    __tablename__ = "user_restaurant_ratings"
    __table_args__ = (
        db.UniqueConstraint("user_id", "place_id", name="uq_user_restaurant_rating_place"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    place_id = db.Column(db.String(255), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.String(40), nullable=False, index=True)

    user = db.relationship("Users", backref=db.backref("restaurant_ratings", lazy=True, cascade="all, delete-orphan"))

    def __init__(self, user_id: int, place_id: str, rating: int) -> None:
        self.user_id = user_id
        self.place_id = place_id[:255]
        self.rating = min(max(int(rating), 1), 5)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def update_rating(self, rating: int) -> None:
        self.rating = min(max(int(rating), 1), 5)
        self.updated_at = datetime.now(timezone.utc).isoformat()


class UserFollow(db.Model):
    __tablename__ = "user_follows"
    __table_args__ = (
        db.UniqueConstraint("follower_id", "following_id", name="uq_user_follow_pair"),
    )

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    following_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(16), default="pending", nullable=False, index=True)
    created_at = db.Column(db.String(40), nullable=False, index=True)

    follower = db.relationship("Users", foreign_keys=[follower_id], backref=db.backref("following_rows", lazy=True))
    following = db.relationship("Users", foreign_keys=[following_id], backref=db.backref("follower_rows", lazy=True))

    def __init__(self, follower_id: int, following_id: int, status: str = "pending") -> None:
        self.follower_id = follower_id
        self.following_id = following_id
        self.status = status
        self.created_at = datetime.now(timezone.utc).isoformat()


class UserActivity(db.Model):
    __tablename__ = "user_activity"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(32), nullable=False, index=True)
    summary = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.String(40), nullable=False, index=True)

    user = db.relationship("Users", backref=db.backref("activity_rows", lazy=True, cascade="all, delete-orphan"))

    def __init__(self, user_id: int, action: str, summary: str) -> None:
        self.user_id = user_id
        self.action = action[:32]
        self.summary = summary[:255]
        self.created_at = datetime.now(timezone.utc).isoformat()


class UserNotification(db.Model):
    __tablename__ = "user_notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    kind = db.Column(db.String(32), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    link_url = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.String(40), nullable=False, index=True)

    user = db.relationship("Users", foreign_keys=[user_id], backref=db.backref("notifications", lazy=True))
    actor = db.relationship("Users", foreign_keys=[actor_user_id])

    def __init__(
        self,
        user_id: int,
        kind: str,
        message: str,
        actor_user_id: int | None = None,
        link_url: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.actor_user_id = actor_user_id
        self.kind = kind[:32]
        self.message = message[:255]
        self.link_url = link_url[:255] if link_url else None
        self.created_at = datetime.now(timezone.utc).isoformat()


class GroupSwipeSession(db.Model):
    __tablename__ = "group_swipe_sessions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), nullable=False, unique=True, index=True)
    host_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.String(40), nullable=False, index=True)
    expires_at = db.Column(db.String(40), index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    host = db.relationship("Users", backref=db.backref("hosted_group_sessions", lazy=True))

    def __init__(self, code: str, host_user_id: int) -> None:
        self.code = code
        self.host_user_id = host_user_id
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.expires_at = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)).isoformat()
        self.is_active = True


class GroupSwipeMember(db.Model):
    __tablename__ = "group_swipe_members"
    __table_args__ = (
        db.UniqueConstraint("session_id", "user_id", name="uq_group_swipe_member_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("group_swipe_sessions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    joined_at = db.Column(db.String(40), nullable=False, index=True)

    session = db.relationship("GroupSwipeSession", backref=db.backref("members", lazy=True))
    user = db.relationship("Users", backref=db.backref("group_swipe_memberships", lazy=True))

    def __init__(self, session_id: int, user_id: int) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.joined_at = datetime.now(timezone.utc).isoformat()


class GroupSwipeVote(db.Model):
    __tablename__ = "group_swipe_votes"
    __table_args__ = (
        db.UniqueConstraint("session_id", "user_id", "place_id", name="uq_group_swipe_vote_place"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("group_swipe_sessions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    place_id = db.Column(db.String(255), nullable=False, index=True)
    action = db.Column(db.String(16), nullable=False)
    restaurant_json = db.Column(db.Text, default="{}")
    updated_at = db.Column(db.String(40), nullable=False, index=True)

    session = db.relationship("GroupSwipeSession", backref=db.backref("votes", lazy=True))
    user = db.relationship("Users", backref=db.backref("group_swipe_votes", lazy=True))

    def __init__(
        self,
        session_id: int,
        user_id: int,
        place_id: str,
        action: str,
        restaurant: dict[str, Any],
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.place_id = place_id
        self.action = action
        self.restaurant_json = json.dumps(restaurant)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def set_vote(self, action: str, restaurant: dict[str, Any]) -> None:
        self.action = action
        self.restaurant_json = json.dumps(restaurant)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def restaurant_payload(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.restaurant_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}

        return payload if isinstance(payload, dict) else {}


class GroupSwipeMessage(db.Model):
    __tablename__ = "group_swipe_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("group_swipe_sessions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(160), nullable=False)
    created_at = db.Column(db.String(40), nullable=False, index=True)

    session = db.relationship("GroupSwipeSession", backref=db.backref("messages", lazy=True, cascade="all, delete-orphan"))
    user = db.relationship("Users", backref=db.backref("group_swipe_messages", lazy=True))

    def __init__(self, session_id: int, user_id: int, message: str) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.message = message[:160]
        self.created_at = datetime.now(timezone.utc).isoformat()
