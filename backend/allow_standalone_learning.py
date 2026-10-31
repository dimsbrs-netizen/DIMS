
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "dims.db"

connection = sqlite3.connect(DB_PATH)

try:
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("BEGIN")

    connection.execute("""
        CREATE TABLE learning_references_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intelligence_report_id INTEGER NULL,
            processed_report_id INTEGER NULL,
            report_category VARCHAR(100) NOT NULL,
            approved_final_text VARCHAR NOT NULL,
            submitted_by INTEGER NOT NULL,
            approved_by INTEGER NOT NULL,
            approved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            withdrawn_by INTEGER NULL,
            withdrawn_at DATETIME NULL,
            review_notes VARCHAR(1000) NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        INSERT INTO learning_references_new (
            id, intelligence_report_id, processed_report_id,
            report_category, approved_final_text, submitted_by,
            approved_by, approved_at, is_active, withdrawn_by,
            withdrawn_at, review_notes, created_at
        )
        SELECT
            id, intelligence_report_id, processed_report_id,
            report_category, approved_final_text, submitted_by,
            approved_by, approved_at, is_active, withdrawn_by,
            withdrawn_at, review_notes, created_at
        FROM learning_references
    """)

    connection.execute("DROP TABLE learning_references")
    connection.execute(
        "ALTER TABLE learning_references_new RENAME TO learning_references"
    )

    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_learning_references_id
        ON learning_references (id)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_learning_references_intelligence_report_id
        ON learning_references (intelligence_report_id)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_learning_references_processed_report_id
        ON learning_references (processed_report_id)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_learning_references_report_category
        ON learning_references (report_category)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_learning_references_is_active
        ON learning_references (is_active)
    """)

    connection.commit()
    print("SUCCESS: Learning References can now be saved independently.")

except Exception:
    connection.rollback()
    raise

finally:
    connection.close()
