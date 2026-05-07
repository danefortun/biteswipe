from __future__ import annotations

from datetime import datetime, timezone

from db import db
from users_db import Users


class BlogPosts(db.Model):
    __bind_key__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, index=True)
    time = db.Column(db.String(40), nullable=False, index=True)

    def __init__(self, message: str, user_id: int | None = None) -> None:
        self.message = message
        self.user_id = user_id
        self.time = datetime.now(timezone.utc).isoformat()

    def __repr__(self) -> str:
        return (
            f"message_id={self.id}, user_id={self.user_id}, "
            f"message={self.message}, time={self.time}"
        )

    def message_content(self) -> str:
        user = Users.query.filter_by(id=self.user_id).first()
        user_name = user.name if user else "Unknown"
        return f"{user_name}: {self.message}"
