from __future__ import annotations

from datetime import datetime, timezone
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
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    bio = db.Column(db.String(256), default="this is a placeholder!")
    pfp_file_path = db.Column(db.String(255), default="transparentnewdefaultpicture.png")
    profile_banner_file_path = db.Column(db.String(255))
    profile_showcase_file_path = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    campus_theme_domain = db.Column(db.String(255))
    allergen_interests_json = db.Column(db.Text, default="[]")
    food_preferences_json = db.Column(db.Text, default="[]")
    hobby_interests_json = db.Column(db.Text, default="[]")

    def __init__(
        self,
        name: str,
        password: str,
        email: str,
        bio: str = "this is a placeholder!",
        pfp_file_path: str = "transparentnewdefaultpicture.png",
    ) -> None:
        self.bio = bio
        self.name = name
        self.email = email
        self.password = password
        self.pfp_file_path = pfp_file_path

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


class GroupSwipeSession(db.Model):
    __tablename__ = "group_swipe_sessions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), nullable=False, unique=True, index=True)
    host_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.String(40), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    host = db.relationship("Users", backref=db.backref("hosted_group_sessions", lazy=True))

    def __init__(self, code: str, host_user_id: int) -> None:
        self.code = code
        self.host_user_id = host_user_id
        self.created_at = datetime.now(timezone.utc).isoformat()
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
