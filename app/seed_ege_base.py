from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exam_config import EGE_BASE_COMPETENCIES
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


EGE_BASE_DEMO_ACCESS_TOKEN = "demo-anna-ege-base-progress"
EGE_BASE_DEMO_ACCESS_CODE = "1234509876"
EGE_BASE_DEMO_SUBJECT = "Математика, ЕГЭ база"


def _day(offset: int) -> date:
    return date.today() + timedelta(days=offset)


def seed_ege_base_demo_data(db: Session) -> Student:
    conflict = db.scalar(
        select(Student).where(
            Student.access_code == EGE_BASE_DEMO_ACCESS_CODE,
            Student.access_token != EGE_BASE_DEMO_ACCESS_TOKEN,
        )
    )
    if conflict is not None:
        conflict.access_code = make_access_code()
        db.flush()

    student = db.scalar(select(Student).where(Student.access_token == EGE_BASE_DEMO_ACCESS_TOKEN))
    if student is None:
        student = Student(access_token=EGE_BASE_DEMO_ACCESS_TOKEN, access_code=EGE_BASE_DEMO_ACCESS_CODE)
        db.add(student)

    student.access_code = EGE_BASE_DEMO_ACCESS_CODE
    student.name = "Анна К."
    student.parent_name = "Мария"
    student.parent_contact = "@demo_ege_base"
    student.subject = EGE_BASE_DEMO_SUBJECT
    student.goal = "Уверенно сдать базовый ЕГЭ по математике на оценку 4 и приблизиться к стабильной 5."
    student.target_date = _day(118)
    student.current_status = (
        "После стартовой диагностики уверенно получаются практические расчёты, таблицы и проценты. "
        "Основной резерв сейчас — планиметрия, стереометрия и задачи на свойства чисел."
    )
    student.current_level = "Прогноз находится в зоне оценки 4; часть компетенций ещё требует проверки полным вариантом."
    student.top_gaps = "1. Планиметрия\n2. Объёмные фигуры\n3. Неравенства\n4. Нестандартные задачи"
    student.four_week_focus = "Закрепить геометрию и алгебраическое ядро, затем пройти полный вариант из 21 задания."
    student.planned_topics = (
        "Неделя 1: практические расчёты и проценты\n"
        "Неделя 2: планиметрия и стереометрия\n"
        "Неделя 3: уравнения и неравенства\n"
        "Неделя 4: полный пробный вариант и корректировка плана"
    )
    student.next_checkpoint_date = _day(17)
    student.next_lesson_focus = "Планиметрия: площади, углы и выбор нужной формулы."
    student.status = "active"

    student.topics.clear()
    student.reports.clear()
    student.homework_items.clear()
    student.materials.clear()
    student.checkpoints.clear()
    student.diagnostic_attempts.clear()
    db.flush()

    levels = {
        "practical_calculations_rounding": 0.90,
        "text_problems_units_estimation": 0.76,
        "tables_charts_graphs": 0.84,
        "formulas_dependencies_calculations": 0.78,
        "basic_probability": 0.70,
        "functions_graphs_derivative": 0.68,
        "logical_reasoning": 0.72,
        "planimetry": 0.58,
        "stereometry": 0.48,
        "arithmetic_fractions_decimals": 0.86,
        "percentages_financial_math": 0.88,
        "powers_roots_logs_trigonometry": 0.66,
        "equations": 0.73,
        "inequalities": 0.52,
        "number_properties_method_selection": 0.40,
        "word_problems_equations": 0.56,
        "nonstandard_logic_modeling": 0.35,
    }
    checked_keys = {
        "arithmetic_fractions_decimals",
        "percentages_financial_math",
        "powers_roots_logs_trigonometry",
        "practical_calculations_rounding",
        "tables_charts_graphs",
        "equations",
        "functions_graphs_derivative",
        "planimetry",
        "stereometry",
        "formulas_dependencies_calculations",
    }
    db.add_all(
        TopicProgress(
            student_id=student.id,
            topic=item.title,
            competency_key=item.key,
            weight=item.weight,
            mastery_level=levels[item.key],
            status=status_for_level(levels[item.key]),
            insufficient_data=item.key not in checked_keys,
            comment=(
                "Уровень подтверждён стартовой диагностикой."
                if item.key in checked_keys
                else "В короткой диагностике данных недостаточно; уточним на полном варианте."
            ),
        )
        for item in EGE_BASE_COMPETENCIES
    )

    reports = [
        LessonReport(
            student_id=student.id,
            lesson_date=_day(-2),
            lesson_topic="Проценты и финансовые расчёты",
            covered="Разобрали скидки, наценки и последовательные изменения величины.",
            worked="Практические расчёты выполняются самостоятельно и с проверкой ответа.",
            weak="В длинном условии иногда пропускается промежуточная величина.",
            homework="Решить 8 задач на проценты и тарифы.",
            homework_completed=True,
            parent_comment="Навык уже близок к устойчивому экзаменационному уровню.",
            materials_link="https://example.com/ege-base-percent",
        ),
        LessonReport(
            student_id=student.id,
            lesson_date=_day(-8),
            lesson_topic="Стартовая диагностика базового ЕГЭ",
            covered="Проверили 12 ключевых типов заданий за 40 минут.",
            worked="Сильнее всего — вычисления, таблицы, проценты и формулы.",
            weak="Геометрия и часть алгебраических заданий пока нестабильны.",
            homework="Перерешать ошибки стартового среза.",
            homework_completed=True,
            parent_comment="Текущий прогноз рабочий, но для высокой уверенности нужен полный вариант.",
            materials_link="https://example.com/ege-base-start",
        ),
    ]
    db.add_all(reports)
    db.flush()
    db.add_all(
        [
            Homework(student_id=student.id, title="8 задач на проценты и тарифы", description="Решить и проверить реалистичность каждого ответа.", due_date=_day(3)),
            Homework(student_id=student.id, title="Планиметрия: площади", description="Решить 6 задач на треугольники и четырёхугольники.", due_date=_day(6)),
            Homework(student_id=student.id, title="Разбор стартовой диагностики", description="Перерешать задания с ошибками.", due_date=_day(-5), is_completed=True, completed_at=datetime.utcnow() - timedelta(days=5)),
        ]
    )
    db.add_all(
        [
            Material(student_id=student.id, lesson_report_id=reports[0].id, title="Памятка по процентам", kind="Конспект", url="https://example.com/ege-base-percent"),
            Material(student_id=student.id, lesson_report_id=reports[1].id, title="Разбор стартовой диагностики", kind="Доска урока", url="https://example.com/ege-base-start"),
        ]
    )
    db.add(
        Checkpoint(
            student_id=student.id,
            checkpoint_date=_day(-3),
            before="Не было единой картины готовности по линиям базового ЕГЭ.",
            after="Определены сильные компетенции и ближайшие зоны роста.",
            improved="Практические расчёты, таблицы и проценты.",
            blockers="Не все 21 тип задания ещё проверены.",
            next_month_plan="Закрепить геометрию и пройти полный пробный вариант.",
        )
    )

    work = db.scalar(select(DiagnosticWork).where(DiagnosticWork.slug == "ege-base-start"))
    if work is not None:
        started = datetime.utcnow() - timedelta(days=8, minutes=35)
        attempt = DiagnosticAttempt(
            student_id=student.id,
            work_id=work.id,
            status="reviewed",
            started_at=started,
            expires_at=started + timedelta(minutes=40),
            submitted_at=started + timedelta(minutes=34),
            reviewed_at=started + timedelta(hours=2),
            auto_score=9,
            manual_score=9,
            conclusion="9 из 12 заданий стартового среза выполнены верно. База для оценки 4 уже видна.",
            parent_message="Стартовая диагностика показала сильные практические навыки. Следующий фокус — геометрия и полный вариант из 21 задания.",
        )
        db.add(attempt)
        db.flush()
        for task in sorted(work.tasks, key=lambda item: item.position):
            correct = task.position not in {9, 10, 12}
            db.add(
                DiagnosticAnswer(
                    attempt_id=attempt.id,
                    task_id=task.id,
                    answer_text=task.correct_answer if correct else "Нет ответа",
                    is_correct=correct,
                    auto_score=1 if correct else 0,
                    teacher_score=1 if correct else 0,
                    teacher_comment="Верно." if correct else "Вернёмся к этому типу после разбора темы.",
                )
            )

    db.commit()
    db.refresh(student)
    return student
