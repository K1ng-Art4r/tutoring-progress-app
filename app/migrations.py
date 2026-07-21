from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def run_lightweight_migrations(engine: Engine) -> None:
    """Keep existing local Docker volumes compatible with small MVP schema changes."""
    statements = [
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS access_code VARCHAR(10)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS parent_name VARCHAR(120) DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS parent_contact VARCHAR(160) DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS target_date DATE",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS current_status TEXT DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS current_level TEXT DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS top_gaps TEXT DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS four_week_focus TEXT DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS planned_topics TEXT DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS next_checkpoint_date DATE",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS next_lesson_focus TEXT DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS status VARCHAR(40) DEFAULT 'active'",
        "UPDATE students SET parent_name = '' WHERE parent_name IS NULL",
        "UPDATE students SET parent_contact = '' WHERE parent_contact IS NULL",
        "UPDATE students SET current_status = '' WHERE current_status IS NULL",
        "UPDATE students SET current_level = '' WHERE current_level IS NULL",
        "UPDATE students SET top_gaps = '' WHERE top_gaps IS NULL",
        "UPDATE students SET four_week_focus = '' WHERE four_week_focus IS NULL",
        "UPDATE students SET planned_topics = '' WHERE planned_topics IS NULL",
        "UPDATE students SET next_lesson_focus = '' WHERE next_lesson_focus IS NULL",
        "UPDATE students SET status = 'active' WHERE status IS NULL OR status = ''",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS status VARCHAR(40) DEFAULT 'new'",
        "UPDATE leads SET status = 'new' WHERE status IS NULL OR status = ''",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS due_date DATE",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS is_completed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS attachment_filename VARCHAR(255)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS attachment_storage_path VARCHAR(500)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS attachment_content_type VARCHAR(120)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS solution_filename VARCHAR(255)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS solution_storage_path VARCHAR(500)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS solution_content_type VARCHAR(120)",
        "ALTER TABLE homework ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP",
        "UPDATE homework SET is_completed = FALSE WHERE is_completed IS NULL",
        "ALTER TABLE lesson_reports ADD COLUMN IF NOT EXISTS homework_completed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE lesson_reports ADD COLUMN IF NOT EXISTS materials_link VARCHAR(500) DEFAULT ''",
        "UPDATE lesson_reports SET homework_completed = FALSE WHERE homework_completed IS NULL",
        "UPDATE lesson_reports SET materials_link = '' WHERE materials_link IS NULL",
        "ALTER TABLE materials ADD COLUMN IF NOT EXISTS lesson_report_id INTEGER",
        "ALTER TABLE materials ADD COLUMN IF NOT EXISTS kind VARCHAR(80) DEFAULT 'Ссылка'",
        "UPDATE materials SET kind = 'Ссылка' WHERE kind IS NULL OR kind = ''",
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
        "ALTER TABLE diagnostic_works ADD COLUMN IF NOT EXISTS subject VARCHAR(120)",
        "ALTER TABLE diagnostic_works ADD COLUMN IF NOT EXISTS exam_type VARCHAR(80)",
        "ALTER TABLE diagnostic_works ADD COLUMN IF NOT EXISTS description TEXT DEFAULT ''",
        "ALTER TABLE diagnostic_works ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 40",
        "ALTER TABLE diagnostic_works ADD COLUMN IF NOT EXISTS max_score INTEGER DEFAULT 20",
        "ALTER TABLE diagnostic_works ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "UPDATE diagnostic_works SET description = '' WHERE description IS NULL",
        "UPDATE diagnostic_works SET duration_minutes = 40 WHERE duration_minutes IS NULL",
        "UPDATE diagnostic_works SET max_score = 20 WHERE max_score IS NULL",
        "UPDATE diagnostic_works SET is_active = TRUE WHERE is_active IS NULL",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS title VARCHAR(220) DEFAULT ''",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS skill VARCHAR(260) DEFAULT ''",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS prompt TEXT DEFAULT ''",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS correct_answer VARCHAR(260) DEFAULT ''",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS solution TEXT DEFAULT ''",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS image_path VARCHAR(500) DEFAULT ''",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS max_score INTEGER DEFAULT 1",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS requires_solution BOOLEAN DEFAULT FALSE",
        "ALTER TABLE diagnostic_tasks ADD COLUMN IF NOT EXISTS criteria TEXT DEFAULT ''",
        "UPDATE diagnostic_tasks SET title = '' WHERE title IS NULL",
        "UPDATE diagnostic_tasks SET skill = '' WHERE skill IS NULL",
        "UPDATE diagnostic_tasks SET prompt = '' WHERE prompt IS NULL",
        "UPDATE diagnostic_tasks SET correct_answer = '' WHERE correct_answer IS NULL",
        "UPDATE diagnostic_tasks SET solution = '' WHERE solution IS NULL",
        "UPDATE diagnostic_tasks SET image_path = '' WHERE image_path IS NULL",
        "UPDATE diagnostic_tasks SET max_score = 1 WHERE max_score IS NULL",
        "UPDATE diagnostic_tasks SET requires_solution = FALSE WHERE requires_solution IS NULL",
        "UPDATE diagnostic_tasks SET criteria = '' WHERE criteria IS NULL",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS status VARCHAR(40) DEFAULT 'in_progress'",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS started_at TIMESTAMP",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS auto_score INTEGER DEFAULT 0",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS manual_score INTEGER",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS conclusion TEXT DEFAULT ''",
        "ALTER TABLE diagnostic_attempts ADD COLUMN IF NOT EXISTS parent_message TEXT DEFAULT ''",
        "UPDATE diagnostic_attempts SET status = 'in_progress' WHERE status IS NULL OR status = ''",
        "UPDATE diagnostic_attempts SET started_at = created_at WHERE started_at IS NULL",
        "UPDATE diagnostic_attempts SET expires_at = COALESCE(started_at, created_at) + INTERVAL '40 minutes' WHERE expires_at IS NULL",
        "UPDATE diagnostic_attempts SET auto_score = 0 WHERE auto_score IS NULL",
        "UPDATE diagnostic_attempts SET conclusion = '' WHERE conclusion IS NULL",
        "UPDATE diagnostic_attempts SET parent_message = '' WHERE parent_message IS NULL",
        "ALTER TABLE diagnostic_answers ADD COLUMN IF NOT EXISTS answer_text TEXT DEFAULT ''",
        "ALTER TABLE diagnostic_answers ADD COLUMN IF NOT EXISTS is_correct BOOLEAN",
        "ALTER TABLE diagnostic_answers ADD COLUMN IF NOT EXISTS auto_score INTEGER DEFAULT 0",
        "ALTER TABLE diagnostic_answers ADD COLUMN IF NOT EXISTS solution_filename VARCHAR(255)",
        "ALTER TABLE diagnostic_answers ADD COLUMN IF NOT EXISTS solution_storage_path VARCHAR(500)",
        "ALTER TABLE diagnostic_answers ADD COLUMN IF NOT EXISTS solution_content_type VARCHAR(120)",
        "ALTER TABLE diagnostic_answers ADD COLUMN IF NOT EXISTS teacher_score INTEGER",
        "ALTER TABLE diagnostic_answers ADD COLUMN IF NOT EXISTS teacher_comment TEXT DEFAULT ''",
        "UPDATE diagnostic_answers SET answer_text = '' WHERE answer_text IS NULL",
        "UPDATE diagnostic_answers SET auto_score = 0 WHERE auto_score IS NULL",
        "UPDATE diagnostic_answers SET teacher_comment = '' WHERE teacher_comment IS NULL",
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
