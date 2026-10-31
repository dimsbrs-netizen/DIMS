
import sqlite3
import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
BACKUP_DB = PROJECT_DIR / "dims_pre_migration_backup.db"
TEST_DB = PROJECT_DIR / "dims_migration_test.db"

if not BACKUP_DB.exists():
    raise FileNotFoundError(f"Backup not found: {BACKUP_DB}")

# Start from a fresh copy of the verified backup.
shutil.copy2(BACKUP_DB, TEST_DB)

connection = sqlite3.connect(TEST_DB)

try:
    connection.execute("PRAGMA foreign_keys = ON")

    # Confirm the test copy is healthy before proceeding.
    integrity = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    if integrity != "ok":
        raise RuntimeError(f"Database integrity check failed: {integrity}")

    user_count = connection.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    print(f"Test database: {TEST_DB.name}")
    print(f"Integrity: {integrity}")
    print(f"Users preserved: {user_count}")

    print(
        "\nTEST COPY CREATED. "
        "No schema migration has been applied yet."
    )

finally:
    connection.close()
