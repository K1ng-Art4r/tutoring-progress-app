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
        "ALTER TABLE topic_progress ADD COLUMN IF NOT EXISTS competency_key VARCHAR(120)",
        "ALTER TABLE topic_progress ADD COLUMN IF NOT EXISTS weight INTEGER",
        "ALTER TABLE topic_progress ADD COLUMN IF NOT EXISTS mastery_level DOUBLE PRECISION",
        "ALTER TABLE topic_progress ADD COLUMN IF NOT EXISTS insufficient_data BOOLEAN",
        "UPDATE topic_progress SET competency_key = '' WHERE competency_key IS NULL",
        "UPDATE topic_progress SET weight = 1 WHERE weight IS NULL",
        """
        UPDATE topic_progress
        SET mastery_level = CASE status
          WHEN 'not_started' THEN 0
          WHEN 'explained' THEN 0.25
          WHEN 'with_help' THEN 0.5
          WHEN 'independent' THEN 0.75
          WHEN 'ready_for_test' THEN 0.9
          WHEN 'stable' THEN 1
          ELSE 0
        END
        WHERE mastery_level IS NULL
        """,
        "UPDATE topic_progress SET insufficient_data = FALSE WHERE insufficient_data IS NULL",
        "ALTER TABLE topic_progress ALTER COLUMN competency_key SET DEFAULT ''",
        "ALTER TABLE topic_progress ALTER COLUMN weight SET DEFAULT 1",
        "ALTER TABLE topic_progress ALTER COLUMN mastery_level SET DEFAULT 0",
        "ALTER TABLE topic_progress ALTER COLUMN insufficient_data SET DEFAULT FALSE",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS solution TEXT DEFAULT ''",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS image_path VARCHAR(500) DEFAULT ''",
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
