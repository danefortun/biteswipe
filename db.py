from flask_sqlalchemy import SQLAlchemy


try:
    from flask_migrate import Migrate
except ImportError:  # pragma: no cover - lets old local envs still boot before deps are installed.
    Migrate = None


db = SQLAlchemy()
migrate = Migrate() if Migrate is not None else None
