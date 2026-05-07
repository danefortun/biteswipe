from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from db import db


class Users(db.Model):
    id = db.Column("id", db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    bio = db.Column(db.String(256), default="this is a placeholder!")
    pfp_file_path = db.Column(db.String(255), default="transparentnewdefaultpicture.png")
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
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

        setattr(self, field_name, json.dumps(cleaned[:30]))


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
    ) -> None:
        self.user_id = user_id
        self.place_id = place_id
        self.name = name
        self.source = source
        self.address = address
        self.photo = photo
        self.distance_meters = distance_meters
        self.created_at = datetime.now(timezone.utc).isoformat()
