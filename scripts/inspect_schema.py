
import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "dims_migration_test.db"

with sqlite3.connect(db_path) as connection:
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
        print(f"\nTABLE: {table_name}")

        columns = connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()

        for column in columns:
            print(f"  COLUMN: {column}")

        foreign_keys = connection.execute(
            f'PRAGMA foreign_key_list("{table_name}")'
        ).fetchall()

        print(f"  FOREIGN KEYS: {foreign_keys}")


    print("\nSCHEMA SQL:")
schema_rows = connection.execute(
    """
    SELECT name, sql
    FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
    """.strip()
).fetchall()

for name, sql in schema_rows:
    print(f"\n{name}:\n{sql}")

    print("\nDATABASE INTEGRITY:")
    print(connection.execute("PRAGMA integrity_check").fetchone()[0])
