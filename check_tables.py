from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

from config import Config


def sqlite_path_from_uri(database_uri: str) -> Path:
    parsed = urlparse(database_uri)
    if parsed.scheme != "sqlite":
        raise RuntimeError(f"check_tables.py only supports SQLite databases, got {parsed.scheme or 'unknown'}")

    if parsed.path in {"", "/:memory:"}:
        raise RuntimeError("In-memory SQLite databases cannot be inspected from check_tables.py")

    if parsed.netloc:
        raw_path = f"//{parsed.netloc}{parsed.path}"
    else:
        raw_path = parsed.path

    if raw_path.startswith("/") and len(raw_path) > 3 and raw_path[2] == ":":
        raw_path = raw_path[1:]

    return Path(unquote(raw_path)).resolve()


DB_FILE = sqlite_path_from_uri(Config.SQLALCHEMY_DATABASE_URI)
UPLOAD_FOLDER = Path(Config.UPLOAD_FOLDER).resolve()

print(f"Using database file: {DB_FILE}")
print(f"Looking for profile pictures in: {UPLOAD_FOLDER}")
print("-" * 60)

conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(users);")
columns = [col["name"] for col in cursor.fetchall()]
print("Columns in users table:", columns)
print("-" * 60)

cursor.execute("SELECT * FROM users")
rows = cursor.fetchall()

if not rows:
    print("No users found in the database.")
else:
    print(f"Found {len(rows)} users:\n")
    for row in rows:
        output = []
        for col in columns:
            value = row[col]
            if col == "pfp_file_path":
                if value:
                    file_path = UPLOAD_FOLDER / str(value)
                    status = "File exists" if file_path.exists() else "File missing"
                    value = f"{value} | {status}"
                else:
                    value = "No file assigned"
            output.append(f"{col}: {value}")
        print(" | ".join(output))
        print("-" * 60)

conn.close()
print("\nDone.")
