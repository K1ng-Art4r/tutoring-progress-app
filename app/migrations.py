from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def run_lightweight_migrations(engine: Engine) -> None:
    """Keep existing local Docker volumes compatible with small MVP schema changes."""
    statements = [
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS attachment_filename VARCHAR(255)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS attachment_storage_path VARCHAR(500)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS attachment_content_type VARCHAR(120)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS solution_filename VARCHAR(255)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS solution_storage_path VARCHAR(500)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS solution_content_type VARCHAR(120)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS access_code VARCHAR(10)",
        "ALTER TABLE students DROP COLUMN IF EXISTS view_count",
        "ALTER TABLE students DROP COLUMN IF EXISTS last_viewed_at",
        """
        UPDATE students
        SET access_code = '1234567890'
        WHERE access_token = 'demo-anna-oge-progress'
          AND (access_code IS NULL OR access_code = '')
        """,
        """
        UPDATE students
        SET access_code = lpad(((id::bigint * 7919 + 104729) % 10000000000)::text, 10, '0')
        WHERE access_code IS NULL OR access_code = ''
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_students_access_code ON students(access_code)",
        "UPDATE leads SET status = 'rejected' WHERE status = 'closed'",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
