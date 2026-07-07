from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Checkpoint,
    Homework,
    LessonReport,
    Lead,
    Material,
    Student,
    TopicProgress,
)


def seed_demo_data(db: Session) -> None:
    existing = db.scalar(select(Student).limit(1))
    if existing:
        return

    student = Student(
        access_token="demo-anna-oge-progress",
        access_code="1234567890",
        name="Анна К.",
        parent_name="Мария",
        parent_contact="@parent_demo",
        subject="Математика, ОГЭ",
        goal="Подтянуть алгебру и выйти на уверенное решение второй части ОГЭ.",
        target_date=date.today() + timedelta(days=120),
        current_status="После диагностики: базовые вычисления нормальные, слабее всего текстовые задачи и квадратные уравнения.",
        current_level="Средний школьный уровень, задания 1-12 решает с подсказками.",
        top_gaps="1. Квадратные уравнения\n2. Текстовые задачи на проценты\n3. Ошибки в оформлении решений",
        four_week_focus="Закрываем квадратные уравнения и базовые текстовые задачи, затем делаем мини-проверку.",
        planned_topics="Неделя 1: дискриминант и корни\nНеделя 2: задачи на проценты\nНеделя 3: смешанные задачи\nНеделя 4: мини-тест и разбор ошибок",
        next_checkpoint_date=date.today() + timedelta(days=28),
        next_lesson_focus="Квадратные уравнения: довести решение до самостоятельного алгоритма.",
    )
    db.add(student)
    db.flush()

    db.add_all(
        [
            TopicProgress(
                student_id=student.id,
                topic="Квадратные уравнения",
                status="with_help",
                comment="Алгоритм понятен, но пока путается в знаках.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Проценты и текстовые задачи",
                status="explained",
                comment="Разобрали схему условия, нужна тренировка.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Оформление второй части",
                status="not_started",
                comment="Запланировано после стабилизации базы.",
            ),
        ]
    )

    report = LessonReport(
        student_id=student.id,
        lesson_date=date.today(),
        lesson_topic="Диагностика и квадратные уравнения",
        covered="Проверили базовые вычисления, разобрали 4 примера на дискриминант и записали общий алгоритм.",
        worked="Анна быстро поняла, как находить дискриминант, и верно решила два примера после подсказки.",
        weak="Пока теряется знак перед коэффициентом b и не всегда проверяет подстановкой.",
        homework="Решить 8 уравнений из подборки и отметить, где возникла ошибка.",
        homework_completed=False,
        parent_comment="Первый фокус: убрать ошибки в знаках, затем перейти к текстовым задачам.",
        materials_link="https://example.com/demo-material",
    )
    db.add(report)
    db.flush()

    db.add_all(
        [
            Homework(
                student_id=student.id,
                title="8 квадратных уравнений",
                description="Решить подборку и подписать, где возникли сомнения.",
                due_date=date.today() + timedelta(days=3),
            ),
            Material(
                student_id=student.id,
                lesson_report_id=report.id,
                title="Памятка: квадратные уравнения",
                kind="Google Docs",
                url="https://example.com/demo-material",
            ),
            Checkpoint(
                student_id=student.id,
                checkpoint_date=date.today(),
                before="На диагностике решала квадратные уравнения только с подсказками.",
                after="Появился общий алгоритм, первые примеры решены с меньшим количеством подсказок.",
                improved="Понимание структуры решения и запись дискриминанта.",
                blockers="Знаки и привычка не проверять ответ.",
                next_month_plan="Довести квадратные уравнения до самостоятельного решения и перейти к процентам.",
            ),
            Lead(
                parent_name="Елена",
                student_class="8 класс",
                subject="Математика, ОГЭ",
                goal="Подготовка к ОГЭ по математике. Детали: подтянуть оценки и убрать страх перед контрольными.",
                contact="@lead_demo",
                status="new",
            ),
        ]
    )
    db.commit()
