class Config:
    SECRET_KEY = "key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///users.db"
    SQLALCHEMY_BINDS = {"posts": "sqlite:///blogPosts.db"}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = "static/uploads"

