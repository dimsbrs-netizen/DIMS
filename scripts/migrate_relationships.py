import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_DIR / "dims.db"

RELATIONSHIPS = {
    "cases": [
        ("created_by", "users", "id"),
    ],
    "intelligence_reports": [
        ("report_format_id", "report_formats", "id"),
        ("case_id", "cases", "id"),
        ("reporting_officer_id", "users", "id"),
        ("department_id", "departments", "id"),
    ],
    "raw_reports": [
        ("intelligence_report_id", "intelligence_reports", "id"),
        ("submitted_by", "users", "id"),
    ],
    "processed_reports": [
        ("intelligence_report_id", "intelligence_reports", "id"),
        ("processed_by", "users", "id"),
    ],
}

CREATE_TABLES = {
    "cases": """
        CREATE TABLE cases_new (
            id INTEGER NOT NULL PRIMARY KEY,
            case_reference VARCHAR(100) NOT NULL,
            title VARCHAR(255) NOT NULL,
            description VARCHAR(1000),
            status VARCHAR(50) NOT NULL,
            created_by INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """,
    "intelligence_reports": """
        CREATE TABLE intelligence_reports_new (
            id INTEGER NOT NULL PRIMARY KEY,
            report_reference VARCHAR(100) NOT NULL,
            title VARCHAR(255),
            heading VARCHAR(500),
            report_format_id INTEGER,
            case_id INTEGER,
            reporting_officer_id INTEGER NOT NULL,
            department_id INTEGER,
            incident_date DATETIME,
            incident_time VARCHAR(20),
            location VARCHAR(255),
            lga VARCHAR(100),
            state VARCHAR(100),
            status VARCHAR(50) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (report_format_id) REFERENCES report_formats(id),
            FOREIGN KEY (case_id) REFERENCES cases(id),
            FOREIGN KEY (reporting_officer_id) REFERENCES users(id),
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """,
    "raw_reports": """
        CREATE TABLE raw_reports_new (
            id INTEGER NOT NULL PRIMARY KEY,
            intelligence_report_id INTEGER NOT NULL,
            submitted_by INTEGER NOT NULL,
            raw_text VARCHAR NOT NULL,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (intelligence_report_id)
                REFERENCES intelligence_reports(id),
            FOREIGN KEY (submitted_by) REFERENCES users(id)
        )
    """,
    "processed_reports": """
        CREATE TABLE processed_reports_new (
            id INTEGER NOT NULL PRIMARY KEY,
            intelligence_report_id INTEGER NOT NULL,
            heading VARCHAR(500),
            body VARCHAR,
            comment VARCHAR,
            processed_by INTEGER NOT NULL,
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (intelligence_report_id)
                REFERENCES intelligence_reports(id),
            FOREIGN KEY (processed_by) REFERENCES users(id)
        )
    """,
}

COPY_COLUMNS = {
    "cases": """
        id, case_reference, title, description, status, created_by,
        created_at, updated_at
    """,
    "intelligence_reports": """
        id, report_reference, title, heading, report_format_id, case_id,
        reporting_officer_id, department_id, incident_date, incident_time,
        location, lga, state, status, created_at, updated_at
    """,
    "raw_reports": """
        id, intelligence_report_id, submitted_by, raw_text, submitted_at
    """,
    "processed_reports": """
        id, intelligence_report_id, heading, body, comment,
        processed_by, processed_at
    """,
}


def check_orphans(connection):
    for table, relationships in RELATIONSHIPS.items():
        for column, parent_table, parent_column in relationships:
            query = f"""
                SELECT COUNT(*)
                FROM "{table}" AS child
                LEFT JOIN "{parent_table}" AS parent
                    ON child."{column}" = parent."{parent_column}"
                WHERE child."{column}" IS NOT NULL
                  AND parent."{parent_column}" IS NULL
            """
            count = connection.execute(query).fetchone()[0]

            if count:
                raise RuntimeError(
                    f"Migration stopped: {table}.{column} contains "
                    f"{count} invalid reference(s) to "
                    f"{parent_table}.{parent_column}."
                )


def migrate():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Test database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = OFF")

        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        required_tables = {
            "users",
            "departments",
            "cases",
            "report_formats",
            "intelligence_reports",
            "raw_reports",
            "processed_reports",
        }

        missing = required_tables - tables

        if missing:
            raise RuntimeError(
                f"Required tables are missing: {sorted(missing)}"
            )

        check_orphans(connection)

        original_counts = {
            table: connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
            for table in required_tables
        }

        connection.execute("BEGIN IMMEDIATE")

        try:
            for table, create_sql in CREATE_TABLES.items():
                connection.execute(
                    f'DROP TABLE IF EXISTS "{table}_new"'
                )
                connection.execute(create_sql)

                columns = COPY_COLUMNS[table]

                connection.execute(
                    f"""
                    INSERT INTO "{table}_new" ({columns})
                    SELECT {columns}
                    FROM "{table}"
                    """
                )

            # Drop dependent tables before their parent tables.
            for table in (
                "raw_reports",
                "processed_reports",
                "intelligence_reports",
                "cases",
            ):
                connection.execute(f'DROP TABLE "{table}"')

            for table in (
                "cases",
                "intelligence_reports",
                "raw_reports",
                "processed_reports",
            ):
                connection.execute(
                    f'ALTER TABLE "{table}_new" RENAME TO "{table}"'
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        connection.execute("PRAGMA foreign_keys = ON")

        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        final_counts = {
            table: connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
            for table in required_tables
        }

        if violations:
            raise RuntimeError(
                f"Foreign-key violations detected: {violations}"
            )

        if integrity != "ok":
            raise RuntimeError(
                f"Database integrity check failed: {integrity}"
            )

        if original_counts != final_counts:
            raise RuntimeError(
                "Record counts changed during migration. "
                f"Before: {original_counts}; after: {final_counts}"
            )

        print("MIGRATION SUCCESSFUL")
        print(f"Database: {DATABASE_PATH.name}")
        print(f"Integrity: {integrity}")
        print(f"Foreign-key violations: {len(violations)}")
        print("\nRECORD COUNTS PRESERVED")

        for table in sorted(required_tables):
            print(f"{table}: {final_counts[table]}")

        print("\nFOREIGN KEYS")

        for table in sorted(required_tables):
            keys = connection.execute(
                f'PRAGMA foreign_key_list("{table}")'
            ).fetchall()

            if keys:
                for key in keys:
                    print(
                        f"{table}.{key[3]} -> "
                        f"{key[2]}.{key[4]}"
                    )

        print("\nTEST DATABASE VERIFIED.")

    finally:
        connection.close()


if __name__ == "__main__":
    migrate()