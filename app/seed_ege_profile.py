from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exam_config import EGE_PROFILE_COMPETENCIES
from app.models import (
    Checkpoint,
    DiagnosticAnswer,
    DiagnosticAttempt,
    DiagnosticWork,
    Homework,
    LessonReport,
    Material,
    Student,
    TopicProgress,
    make_access_code,
)
from app.progress_forecast import status_for_level


EGE_PROFILE_DEMO_ACCESS_TOKEN = "demo-anna-ege-profile-progress"
EGE_PROFILE_DEMO_ACCESS_CODE = "1234598760"
EGE_PROFILE_DEMO_SUBJECT = "Математика, ЕГЭ профиль"


def _day(offset: int) -> date:
    return date.today() + timedelta(days=offset)


def seed_ege_profile_demo_data(db: Session) -> Student:
    conflict = db.scalar(
        select(Student).where(
            Student.access_code == EGE_PROFILE_DEMO_ACCESS_CODE,
            Student.access_token != EGE_PROFILE_DEMO_ACCESS_TOKEN,
        )
    )
    if conflict is not None:
        conflict.access_code = make_access_code()
        db.flush()

    student = db.scalar(select(Student).where(Student.access_token == EGE_PROFILE_DEMO_ACCESS_TOKEN))
    if student is None:
        student = Student(access_token=EGE_PROFILE_DEMO_ACCESS_TOKEN, access_code=EGE_PROFILE_DEMO_ACCESS_CODE)
        db.add(student)

    student.access_code = EGE_PROFILE_DEMO_ACCESS_CODE
    student.name = "Анна К."
    student.parent_name = "Мария"
    student.parent_contact = "@demo_ege_profile"
    student.subject = EGE_PROFILE_DEMO_SUBJECT
    student.goal = "Подготовиться к профильному ЕГЭ по математике и выйти на 80 баллов."
    student.target_date = _day(118)
    student.current_status = (
        "Первая часть и уравнения уже дают устойчивую основу. Для роста к 80+ нужно добрать "
        "баллы в стереометрии, финансовых задачах и заданиях с параметром."
    )
    student.current_level = "Текущий прогноз находится около 78 тестовых баллов при средней уверенности."
    student.top_gaps = "1. Стереометрия\n2. Финансовые задачи\n3. Параметры\n4. Теория чисел"
    student.four_week_focus = "Укрепить задания 14–16 и сохранить стабильность первой части."
    student.planned_topics = (
        "Неделя 1: сложные уравнения и отбор корней\n"
        "Неделя 2: стереометрия\n"
        "Неделя 3: неравенства и финансовые задачи\n"
        "Неделя 4: пробный вариант и анализ результата"
    )
    student.next_checkpoint_date = _day(18)
    student.next_lesson_focus = "Стереометрия: построение сечения и вычислительная часть."
    student.status = "active"

    student.topics.clear()
    student.reports.clear()
    student.homework_items.clear()
    student.materials.clear()
    student.checkpoints.clear()
    student.diagnostic_attempts.clear()
    db.flush()

    levels = {
        "profile_planimetry_basic": 0.90,
        "profile_vectors": 0.82,
        "profile_stereometry_basic": 0.72,
        "profile_probability_simple": 0.88,
        "profile_probability_advanced": 0.74,
        "profile_equations_short": 0.90,
        "profile_transformations": 0.86,
        "profile_derivative_graph": 0.80,
        "profile_applied_formula": 0.84,
        "profile_word_problems": 0.76,
        "profile_functions_graphs": 0.78,
        "profile_extrema": 0.72,
        "profile_equation_detailed": 0.65,
        "profile_stereometry_detailed": 0.30,
        "profile_inequalities": 0.60,
        "profile_finance": 0.30,
        "profile_planimetry_proof": 0.40,
        "profile_parameter": 0.20,
        "profile_number_theory": 0.10,
    }
    checked_lines = {1, 4, 7, 8, 9, 11, 13, 14, 15, 18}
    db.add_all(
        TopicProgress(
            student_id=student.id,
            topic=item.title,
            competency_key=item.key,
            weight=item.weight,
            mastery_level=levels[item.key],
            status=status_for_level(levels[item.key]),
            insufficient_data=not any(line in checked_lines for line in item.task_lines),
            comment=(
                "Уровень подтверждён стартовой диагностикой."
                if any(line in checked_lines for line in item.task_lines)
                else "В стартовой диагностике данных недостаточно; уточним на полном варианте."
            ),
        )
        for item in EGE_PROFILE_COMPETENCIES
    )

    reports = [
        LessonReport(
            student_id=student.id,
            lesson_date=_day(-2),
            lesson_topic="Сложные уравнения и отбор корней",
            covered="Повторили ограничения, общий метод решения и отбор корней.",
            worked="Основное уравнение решается уверенно, отбор корней стал аккуратнее.",
            weak="В тригонометрических ограничениях иногда пропускается граница.",
            homework="Решить 4 задания №13 с полным отбором корней.",
            homework_completed=True,
            parent_comment="Это одна из сильных зон, которая уже даёт вклад в прогноз.",
            materials_link="https://example.com/ege-profile-equations",
        ),
        LessonReport(
            student_id=student.id,
            lesson_date=_day(-9),
            lesson_topic="Стартовая диагностика профильного ЕГЭ",
            covered="Проверили первую часть и несколько задач с развёрнутым решением.",
            worked="Уверенно выполнены вычисления, вероятность, функции и базовая планиметрия.",
            weak="Стереометрия, финансовая задача и параметр требуют отдельного плана.",
            homework="Перерешать ошибки стартовой диагностики.",
            homework_completed=True,
            parent_comment="Текущий уровень близок к 80 баллам, но прогноз пока средней уверенности.",
            materials_link="https://example.com/ege-profile-start",
        ),
    ]
    db.add_all(reports)
    db.flush()
    db.add_all(
        [
            Homework(student_id=student.id, title="4 задания №13", description="Решить уравнения и отдельно записать отбор корней.", due_date=_day(3)),
            Homework(student_id=student.id, title="Стереометрия: сечения", description="Решить 3 задачи с рисунком и обоснованием построения.", due_date=_day(6)),
            Homework(student_id=student.id, title="Разбор стартовой диагностики", description="Перерешать задания с потерянными баллами.", due_date=_day(-5), is_completed=True, completed_at=datetime.utcnow() - timedelta(days=5)),
        ]
    )
    db.add_all(
        [
            Material(student_id=student.id, lesson_report_id=reports[0].id, title="Чек-лист отбора корней", kind="Конспект", url="https://example.com/ege-profile-equations"),
            Material(student_id=student.id, lesson_report_id=reports[1].id, title="Разбор стартовой диагностики", kind="Доска урока", url="https://example.com/ege-profile-start"),
        ]
    )
    db.add(
        Checkpoint(
            student_id=student.id,
            checkpoint_date=_day(-3),
            before="Баллы второй части были нестабильны.",
            after="Уравнения и неравенства дают более предсказуемый результат.",
            improved="Отбор корней и оформление решения.",
            blockers="Стереометрия и параметр пока требуют подсказки.",
            next_month_plan="Закрепить №13–16 и пройти полный пробный вариант.",
        )
    )

    work = db.scalar(select(DiagnosticWork).where(DiagnosticWork.slug == "ege-profile-start"))
    if work is not None:
        started = datetime.utcnow() - timedelta(days=9, minutes=38)
        attempt = DiagnosticAttempt(
            student_id=student.id,
            work_id=work.id,
            status="reviewed",
            started_at=started,
            expires_at=started + timedelta(minutes=40),
            submitted_at=started + timedelta(minutes=36),
            reviewed_at=started + timedelta(hours=2),
            auto_score=10,
            manual_score=13,
            conclusion="Первая часть выполнена уверенно. Основной резерв — задачи с развёрнутым решением.",
            parent_message="Прогноз близок к цели 80 баллов. Следующий фокус — стереометрия, финансовые задачи и параметр.",
        )
        db.add(attempt)
        db.flush()
        for task in sorted(work.tasks, key=lambda item: item.position):
            score = task.max_score if task.position <= 9 else max(task.max_score - 1, 0)
            db.add(
                DiagnosticAnswer(
                    attempt_id=attempt.id,
                    task_id=task.id,
                    answer_text=task.correct_answer if score else "Нет ответа",
                    is_correct=score == task.max_score,
                    auto_score=task.max_score if score == task.max_score else 0,
                    teacher_score=score,
                    teacher_comment="Верно." if score == task.max_score else "Есть рабочий ход, но потерян один балл.",
                )
            )

    db.commit()
    db.refresh(student)
    return student

