from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"


def sqlite_uri(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def normalize_database_url(value: str | None, fallback: str) -> str:
    database_url = value or fallback

    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")

    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")

    return database_url


def env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError:
        return default


def env_csv(name: str, default: str = "") -> list[str]:
    raw_value = os.environ.get(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get("DATABASE_URL"),
        sqlite_uri(INSTANCE_DIR / "users.db"),
    )
    SQLALCHEMY_BINDS = {
        "posts": normalize_database_url(
            os.environ.get("POSTS_DATABASE_URL") or os.environ.get("DATABASE_URL"),
            sqlite_uri(INSTANCE_DIR / "blogPosts.db"),
        )
    }
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.environ.get("DATABASE_POOL_RECYCLE_SECONDS", 1800)),
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "static" / "uploads"))
    UPLOAD_STORAGE_PROVIDER = os.environ.get("UPLOAD_STORAGE_PROVIDER", "local").strip().lower()
    UPLOADS_PUBLIC_BASE_URL = os.environ.get("UPLOADS_PUBLIC_BASE_URL", "").strip()
    UPLOADS_S3_BUCKET = os.environ.get("UPLOADS_S3_BUCKET", "").strip()
    UPLOADS_S3_PREFIX = os.environ.get("UPLOADS_S3_PREFIX", "profile-uploads").strip().strip("/")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 2 * 1024 * 1024))
    GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    GOOGLE_PLACES_MONTHLY_CREDIT_USD = env_float("GOOGLE_PLACES_MONTHLY_CREDIT_USD", 200.0)
    GOOGLE_PLACES_MONTHLY_SPEND_USD = env_float("GOOGLE_PLACES_MONTHLY_SPEND_USD", 0.0)
    GOOGLE_PLACES_USAGE_RATIO = env_float("GOOGLE_PLACES_USAGE_RATIO", -1.0)
    GOOGLE_PLACES_DISABLE_AT_USAGE_RATIO = env_float("GOOGLE_PLACES_DISABLE_AT_USAGE_RATIO", 0.6)
    RESTAURANT_PROVIDER = os.environ.get("RESTAURANT_PROVIDER", "auto")
    RESTAURANT_SEARCH_RADIUS_METERS = int(os.environ.get("RESTAURANT_SEARCH_RADIUS_METERS", 2000))
    OSM_OVERPASS_URL = os.environ.get("OSM_OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    OSM_OVERPASS_TIMEOUT = int(os.environ.get("OSM_OVERPASS_TIMEOUT", 12))
    OSM_MAX_RESULTS = int(os.environ.get("OSM_MAX_RESULTS", 25))
    RESTAURANT_SEARCH_RATE_LIMIT_COUNT = int(os.environ.get("RESTAURANT_SEARCH_RATE_LIMIT_COUNT", 20))
    RESTAURANT_SEARCH_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RESTAURANT_SEARCH_RATE_LIMIT_WINDOW_SECONDS", 60))
    RESTAURANT_SAVE_RATE_LIMIT_COUNT = int(os.environ.get("RESTAURANT_SAVE_RATE_LIMIT_COUNT", 30))
    RESTAURANT_SAVE_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RESTAURANT_SAVE_RATE_LIMIT_WINDOW_SECONDS", 60))
    RESTAURANT_CACHE_TTL_SECONDS = int(os.environ.get("RESTAURANT_CACHE_TTL_SECONDS", 300))
    RESTAURANT_CACHE_MAX_ENTRIES = int(os.environ.get("RESTAURANT_CACHE_MAX_ENTRIES", 250))
    BITESWIPE_FOUNDER_USER_IDS = env_csv("BITESWIPE_FOUNDER_USER_IDS", "1")
    BITESWIPE_FOUNDER_HANDLES = env_csv("BITESWIPE_FOUNDER_HANDLES")
    ADMIN_EMAILS = env_csv("ADMIN_EMAILS")
    AUTO_CREATE_DB = env_bool("AUTO_CREATE_DB", True)
    DEBUG = env_bool("FLASK_DEBUG", False)
