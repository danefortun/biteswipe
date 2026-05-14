# LifeSwipe

LifeSwipe is a Flask app for location-based restaurant discovery, profile pages, and a simple shared chat.

## Tech Stack

- Python 3.12
- Flask
- Flask-SQLAlchemy
- Flask-Migrate / Alembic migrations
- SQLite for local development
- Optional PostgreSQL through `DATABASE_URL` for production scale
- Optional S3-compatible upload storage for profile media
- OpenStreetMap Overpass API for no-key restaurant search
- Optional Google Places API for richer restaurant cards

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a real `SECRET_KEY` in `.env`. Restaurant search works without a key through OpenStreetMap. Add `GOOGLE_PLACES_API_KEY` only if you want the app to use Google Places when `RESTAURANT_PROVIDER=auto`.

Run the app:

```powershell
$env:FLASK_APP="main"
flask run
```

Initialize the database manually when needed:

```powershell
flask --app main init-db
```

For production databases, use migrations instead of `init-db`:

```powershell
$env:AUTO_CREATE_DB="false"
flask --app main db upgrade
```

## Tests

```powershell
python -m unittest discover -s tests
```

GitHub Actions runs the same test suite on pushes and pull requests to `main`.

## Deploy

The production entry point is:

```text
gunicorn wsgi:app
```

Required environment variables:

- `SECRET_KEY`: long random string used to sign sessions
- `DATABASE_URL`: production database URL
- `GOOGLE_PLACES_API_KEY`: optional, used only when Google Places is enabled

Optional environment variables:

- `POSTS_DATABASE_URL`: separate database URL for chat posts
- `DATABASE_POOL_RECYCLE_SECONDS`: database connection pool recycle window
- `UPLOAD_STORAGE_PROVIDER`: `local` or `s3`; default is `local`
- `UPLOADS_PUBLIC_BASE_URL`: public CDN/bucket base URL for S3 uploads
- `UPLOADS_S3_BUCKET`: S3 bucket name when `UPLOAD_STORAGE_PROVIDER=s3`
- `UPLOADS_S3_PREFIX`: folder/prefix for profile uploads
- `RESTAURANT_PROVIDER`: `auto`, `osm`, or `google`; default is `auto`
- `AUTO_CREATE_DB`: defaults to `true`; set to `false` after adding real migrations
- `MAX_CONTENT_LENGTH`: upload size limit in bytes
- `RESTAURANT_SEARCH_RADIUS_METERS`: nearby restaurant search radius
- `OSM_OVERPASS_URL`: OpenStreetMap Overpass endpoint
- `OSM_OVERPASS_TIMEOUT`: Overpass query timeout in seconds
- `OSM_MAX_RESULTS`: maximum number of OpenStreetMap restaurants returned

OpenStreetMap does not require an API key, but public Overpass servers are shared infrastructure. For heavier production traffic, use your own Overpass instance, a paid hosted OSM provider, or Google Places with a private server-side key.

`render.yaml` and `Procfile` are included for common Python web hosts. If your host provides PostgreSQL URLs as `postgres://...`, the app normalizes them for SQLAlchemy.

Public profiles are available by user ID at `/userID=<id>` and `/user/<id>`, for example `/userID=1`.

## Repository Hygiene

Do not commit local databases, virtual environments, `.env`, API key files, Python caches, or user-uploaded profile images. The included `.gitignore` keeps those out while preserving the default profile image.
