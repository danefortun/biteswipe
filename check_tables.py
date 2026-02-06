import sqlite3
import os

# ------------------------------
# CONFIG: Match your Flask app
# ------------------------------

# Path to your SQLite database file
DB_FILE = r'instance\users.sqlite3'

# Folder where uploaded images are stored
UPLOAD_FOLDER = os.path.join("static", "uploads")

# Make paths absolute
DB_FILE = os.path.abspath(DB_FILE)
UPLOAD_FOLDER = os.path.abspath(UPLOAD_FOLDER)

print(f"Using database file: {DB_FILE}")
print(f"Looking for profile pictures in: {UPLOAD_FOLDER}")
print("-" * 60)

# ------------------------------
# CONNECT TO DATABASE
# ------------------------------

conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row  # allows accessing columns by name
cursor = conn.cursor()

# ------------------------------
# FETCH COLUMN NAMES
# ------------------------------
cursor.execute("PRAGMA table_info(users);")
columns = [col["name"] for col in cursor.fetchall()]
print("Columns in users table:", columns)
print("-" * 60)

# ------------------------------
# FETCH ALL USERS
# ------------------------------

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
                # Check if the profile picture file exists
                if value:
                    file_path = os.path.join(UPLOAD_FOLDER, value)
                    if os.path.exists(file_path):
                        status = "✅ File exists"
                    else:
                        status = "❌ File missing"
                    value = f"{value} | {status}"
                else:
                    value = "❌ No file assigned"
            output.append(f"{col}: {value}")
        print(" | ".join(output))
        print("-" * 60)

# ------------------------------
# CLOSE CONNECTION
# ------------------------------
conn.close()
print("\nDone.")
