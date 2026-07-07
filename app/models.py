from __future__ import annotations

import secrets
import string
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


TOPIC_STATUSES = [
    "not_started",
    "explained",
    "with_help",
    "independent",
    "ready_for_test",
]

TOPIC_STATUS_LABELS = {
    "not_started": "Не начали",
    "explained": "Объяснено",
    "with_help": "Решает с помощью",
    "independent": "Решает самостоятельно",
    "ready_for_test": "Готово к проверке",
}

STUDENT_STATUSES = ["active", "paused", "archived"]
STUDENT_STATUS_LABELS = {
    "active": "Активен",
    "paused": "Пауза",
    "archived": "Архив",
}

LEAD_STATUSES = ["new", "contacted", "approved", "rejected"]
LEAD_STATUS_LABELS = {
    "new": "Новая",
    "contacted": "Связались",
    "approved": "Одобрено",
    "rejected": "Отклонено",
}

DIAGNOSTIC_ATTEMPT_STATUSES = ["in_progress", "submitted", "reviewed"]
DIAGNOSTIC_ATTEMPT_STATUS_LABELS = {
    "in_progress": "В процессе",
    "submitted": "Нужна проверка",
    "reviewed": "Проверено",
}


def make_access_token() -> str:
    return secrets.token_urlsafe(32)


def make_access_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(10))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_name: Mapped[str] = mapped_column(String(120))
    student_class: Mapped[str] = mapped_column(String(80))
    subject: Mapped[str] = mapped_column(String(120))
    goal: Mapped[str] = mapped_column(Text)
    contact: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="new")


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        default=make_access_token,
    )
    access_code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        index=True,
        default=make_access_code,
    )
    name: Mapped[str] = mapped_column(String(120))
    parent_name: Mapped[str] = mapped_column(String(120), default="")
    parent_contact: Mapped[str] = mapped_column(String(160), default="")
    subject: Mapped[str] = mapped_column(String(120))
    goal: Mapped[str] = mapped_column(Text)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_status: Mapped[str] = mapped_column(Text, default="")
    current_level: Mapped[str] = mapped_column(Text, default="")
    top_gaps: Mapped[str] = mapped_column(Text, default="")
    four_week_focus: Mapped[str] = mapped_column(Text, default="")
    planned_topics: Mapped[str] = mapped_column(Text, default="")
    next_checkpoint_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_lesson_focus: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="active")

    topics: Mapped[list["TopicProgress"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="TopicProgress.updated_at.desc()",
    )
    reports: Mapped[list["LessonReport"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="LessonReport.lesson_date.desc()",
    )
    homework_items: Mapped[list["Homework"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="Homework.created_at.desc()",
    )
    materials: Mapped[list["Material"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="Material.created_at.desc()",
    )
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="Checkpoint.checkpoint_date.desc()",
    )
    diagnostic_attempts: Mapped[list["DiagnosticAttempt"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="DiagnosticAttempt.created_at.desc()",
    )


class TopicProgress(Base, TimestampMixin):
    __tablename__ = "topic_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(40), default="not_started")
    comment: Mapped[str] = mapped_column(Text, default="")

    student: Mapped[Student] = relationship(back_populates="topics")


class LessonReport(Base, TimestampMixin):
    __tablename__ = "lesson_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_date: Mapped[date] = mapped_column(Date)
    lesson_topic: Mapped[str] = mapped_column(String(220))
    covered: Mapped[str] = mapped_column(Text)
    worked: Mapped[str] = mapped_column(Text)
    weak: Mapped[str] = mapped_column(Text)
    homework: Mapped[str] = mapped_column(Text)
    homework_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_comment: Mapped[str] = mapped_column(Text)
    materials_link: Mapped[str] = mapped_column(String(500), default="")

    student: Mapped[Student] = relationship(back_populates="reports")
    materials: Mapped[list["Material"]] = relationship(back_populates="lesson_report")


class Homework(Base, TimestampMixin):
    __tablename__ = "homework"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attachment_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attachment_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    solution_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    solution_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    solution_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)

    student: Mapped[Student] = relationship(back_populates="homework_items")


class Material(Base, TimestampMixin):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("lesson_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(220))
    kind: Mapped[str] = mapped_column(String(80), default="Ссылка")
    url: Mapped[str] = mapped_column(String(500))

    student: Mapped[Student] = relationship(back_populates="materials")
    lesson_report: Mapped[LessonReport | None] = relationship(back_populates="materials")


class Checkpoint(Base, TimestampMixin):
    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    checkpoint_date: Mapped[date] = mapped_column(Date)
    before: Mapped[str] = mapped_column(Text)
    after: Mapped[str] = mapped_column(Text)
    improved: Mapped[str] = mapped_column(Text)
    blockers: Mapped[str] = mapped_column(Text)
    next_month_plan: Mapped[str] = mapped_column(Text)

    student: Mapped[Student] = relationship(back_populates="checkpoints")


class DiagnosticWork(Base, TimestampMixin):
    __tablename__ = "diagnostic_works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(260))
    subject: Mapped[str] = mapped_column(String(120), index=True)
    exam_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=40)
    max_score: Mapped[int] = mapped_column(Integer, default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tasks: Mapped[list["DiagnosticTask"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
        order_by="DiagnosticTask.position.asc()",
    )
    attempts: Mapped[list["DiagnosticAttempt"]] = relationship(back_populates="work")


class DiagnosticTask(Base, TimestampMixin):
    __tablename__ = "diagnostic_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_works.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(220))
    skill: Mapped[str] = mapped_column(String(260), default="")
    prompt: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(String(260))
    solution: Mapped[str] = mapped_column(Text, default="")
    max_score: Mapped[int] = mapped_column(Integer, default=1)
    requires_solution: Mapped[bool] = mapped_column(Boolean, default=False)
    criteria: Mapped[str] = mapped_column(Text, default="")

    work: Mapped[DiagnosticWork] = relationship(back_populates="tasks")
    answers: Mapped[list["DiagnosticAnswer"]] = relationship(back_populates="task")


class DiagnosticAttempt(Base, TimestampMixin):
    __tablename__ = "diagnostic_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    work_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_works.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(40), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    auto_score: Mapped[int] = mapped_column(Integer, default=0)
    manual_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conclusion: Mapped[str] = mapped_column(Text, default="")
    parent_message: Mapped[str] = mapped_column(Text, default="")

    student: Mapped[Student] = relationship(back_populates="diagnostic_attempts")
    work: Mapped[DiagnosticWork] = relationship(back_populates="attempts")
    answers: Mapped[list["DiagnosticAnswer"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class DiagnosticAnswer(Base, TimestampMixin):
    __tablename__ = "diagnostic_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_attempts.id", ondelete="CASCADE"))
    task_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"))
    answer_text: Mapped[str] = mapped_column(Text, default="")
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    auto_score: Mapped[int] = mapped_column(Integer, default=0)
    teacher_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    teacher_comment: Mapped[str] = mapped_column(Text, default="")
    solution_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    solution_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    solution_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)

    attempt: Mapped[DiagnosticAttempt] = relationship(back_populates="answers")
    task: Mapped[DiagnosticTask] = relationship(back_populates="answers")
