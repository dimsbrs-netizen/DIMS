
import sqlite3
from pathlib import Path

project_dir = Path(__file__).resolve().parent.parent

files = [
    "dims.db",
    "dims_backup.db",
    "dims_pre_relationships_backup.db",
]

for filename in files:
    db_path = project_dir / filename

    print(f"\nDATABASE: {filename}")

    if not db_path.exists():
        print("FILE NOT FOUND")
        continue

    try:
        with sqlite3.connect(
            f"file:{db_path.as_posix()}?mode=ro",
            uri=True
        ) as connection:
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            print(f"Integrity: {integrity}")

            tables = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()

            for (table_name,) in tables:
                count = connection.execute(
                    f'SELECT COUNT(*) FROM "{table_name}"'
                ).fetchone()[0]

                print(f"  {table_name}: {count} records")

    except sqlite3.Error as error:
        print(f"Database error: {error}")

print("\nVerification complete. No database changes made.")
