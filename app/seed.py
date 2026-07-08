from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.demo import DEMO_ACCESS_CODE, DEMO_ACCESS_TOKEN, DEMO_DIAGNOSTIC_SLUG, DEMO_SUBJECT
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


def _demo_date(days_from_today: int) -> date:
    return date.today() + timedelta(days=days_from_today)


def _clear_demo_collections(student: Student) -> None:
    student.topics.clear()
    student.reports.clear()
    student.homework_items.clear()
    student.materials.clear()
    student.checkpoints.clear()
    student.diagnostic_attempts.clear()


def _reviewed_demo_attempt(db: Session, student: Student) -> None:
    work = db.scalar(select(DiagnosticWork).where(DiagnosticWork.slug == DEMO_DIAGNOSTIC_SLUG))
    if work is None:
        return

    started_at = datetime.utcnow() - timedelta(days=6, minutes=28)
    submitted_at = started_at + timedelta(minutes=24)
    reviewed_at = submitted_at + timedelta(hours=2)
    attempt = DiagnosticAttempt(
        student_id=student.id,
        work_id=work.id,
        status="reviewed",
        started_at=started_at,
        expires_at=started_at + timedelta(minutes=25),
        submitted_at=submitted_at,
        reviewed_at=reviewed_at,
        auto_score=6,
        manual_score=8,
        conclusion=(
            "Демо-диагностика показывает формат проверки: краткие ответы, задания с ходом "
            "решения, баллы по каждому номеру и понятный вывод для родителя."
        ),
        parent_message=(
            "Здравствуйте!\n\n"
            "### Итог демо-диагностики\n"
            "- **Работа:** короткий тестовый срез на 6 заданий.\n"
            "- **Результат:** 8/10.\n"
            "- **Что видно в кабинете:** баллы по заданиям, комментарии преподавателя, "
            "правильные ответы и краткие решения.\n\n"
            "### Как это используется на реальных занятиях\n"
            "После настоящей диагностики я фиксирую текущий уровень, главные пробелы, ближайший "
            "фокус и план на 2-4 недели. Дальше прогресс обновляется после уроков, домашних "
            "заданий и контрольных чекпоинтов."
        ),
    )
    db.add(attempt)
    db.flush()

    demo_answers = {
        1: ("7", True, 1, "Верно: порядок действий сохранен."),
        2: ("15", True, 1, "Верно найдены 25% от 60."),
        3: ("3", True, 1, "Уравнение решено правильно."),
        4: ("4", False, 1, "Идея верная, но потерян коэффициент при графике."),
        5: ("40", True, 2, "Верно составлена пропорция и найден ответ."),
        6: ("Провела высоту, получила 48", False, 2, "Ход решения правильный, не дописан радиус."),
    }

    for task in sorted(work.tasks, key=lambda item: item.position):
        answer_data = demo_answers.get(task.position)
        if answer_data is None:
            continue
        answer_text, is_correct, teacher_score, teacher_comment = answer_data
        db.add(
            DiagnosticAnswer(
                attempt_id=attempt.id,
                task_id=task.id,
                answer_text=answer_text,
                is_correct=is_correct,
                auto_score=task.max_score if is_correct else 0,
                teacher_score=teacher_score,
                teacher_comment=teacher_comment,
            )
        )


def seed_demo_data(db: Session) -> Student:
    conflicting_code_owner = db.scalar(
        select(Student).where(
            Student.access_code == DEMO_ACCESS_CODE,
            Student.access_token != DEMO_ACCESS_TOKEN,
        )
    )
    if conflicting_code_owner is not None:
        conflicting_code_owner.access_code = make_access_code()
        db.flush()

    student = db.scalar(select(Student).where(Student.access_token == DEMO_ACCESS_TOKEN))
    if student is None:
        student = Student(access_token=DEMO_ACCESS_TOKEN)
        db.add(student)
        db.flush()

    student.access_code = DEMO_ACCESS_CODE
    student.name = "Анна К."
    student.parent_name = "Мария"
    student.parent_contact = "@demo_parent"
    student.subject = DEMO_SUBJECT
    student.goal = "Уверенно подготовиться к ОГЭ по математике и выйти на стабильную оценку 4/5."
    student.target_date = _demo_date(118)
    student.current_status = (
        "После стартового среза база стала стабильнее: Анна уверенно решает простые уравнения "
        "и проценты, но еще теряет баллы на текстовых задачах и геометрии с оформлением."
    )
    student.current_level = (
        "Рабочая база первой части: быстрые задания решает самостоятельно, в задачах с несколькими "
        "шагами иногда нужна подсказка по плану решения."
    )
    student.top_gaps = (
        "1. Текстовые задачи на проценты и движение\n"
        "2. Геометрия: площади, окружности, доказательства\n"
        "3. Оформление второй части без пропусков в рассуждении\n"
        "4. Проверка ответа после вычислений"
    )
    student.four_week_focus = (
        "Стабилизировать текстовые задачи и геометрию первой части, затем перейти к двум заданиям "
        "с развернутым решением и мини-срезу."
    )
    student.planned_topics = (
        "Неделя 1: проценты, пропорции, практические задачи\n"
        "Неделя 2: квадратные уравнения и функции\n"
        "Неделя 3: геометрия треугольников и окружностей\n"
        "Неделя 4: пробный мини-вариант, разбор ошибок, корректировка плана"
    )
    student.next_checkpoint_date = _demo_date(17)
    student.next_lesson_focus = "Текстовые задачи: перевод условия в схему и проверка ответа."
    student.status = "active"

    _clear_demo_collections(student)
    db.flush()

    db.add_all(
        [
            TopicProgress(
                student_id=student.id,
                topic="Линейные уравнения",
                status="ready_for_test",
                comment="Решает самостоятельно, осталось закрепить скорость и аккуратность.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Проценты и пропорции",
                status="independent",
                comment="Базовые задачи решает без помощи, в сложных условиях проверяем схему.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Квадратные уравнения",
                status="with_help",
                comment="Алгоритм понятен, ошибки чаще всего в знаках и проверке корней.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Функции и графики",
                status="explained",
                comment="Разобрали линейную функцию, следующий шаг - чтение графиков.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Геометрия: треугольники",
                status="with_help",
                comment="Нужна тренировка высот, медиан, площадей и связи с окружностью.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Текстовые задачи",
                status="explained",
                comment="Учимся выделять величины, связь между ними и проверять смысл ответа.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Оформление второй части",
                status="not_started",
                comment="Запланировано после стабилизации базовой геометрии.",
            ),
            TopicProgress(
                student_id=student.id,
                topic="Стратегия экзамена",
                status="independent",
                comment="Есть порядок решения варианта и правило, когда переходить дальше.",
            ),
        ]
    )

    reports = [
        LessonReport(
            student_id=student.id,
            lesson_date=_demo_date(-1),
            lesson_topic="Текстовые задачи на проценты",
            covered="Разобрали перевод условия в таблицу: было, стало, изменение, итоговая величина.",
            worked="Анна быстро нашла процент от числа и сама исправила одну вычислительную ошибку.",
            weak="Пока сложнее удерживать два последовательных изменения в одной задаче.",
            homework="Решить 6 задач на проценты и подписать схему к каждой.",
            homework_completed=False,
            parent_comment=(
                "Есть хороший прогресс в базовых процентах. На следующем уроке закрепим задачи "
                "с двумя действиями и добавим проверку смысла ответа."
            ),
            materials_link="https://example.com/demo-percent-plan",
        ),
        LessonReport(
            student_id=student.id,
            lesson_date=_demo_date(-5),
            lesson_topic="Квадратные уравнения и проверка корней",
            covered="Повторили дискриминант, формулу корней, проверку подстановкой и типовые ошибки со знаками.",
            worked="3 из 5 уравнений решены самостоятельно, в двух Анна нашла ошибку после проверки.",
            weak="Иногда забывает проверить, что найденный корень подходит к исходному уравнению.",
            homework="Дорешать подборку из 8 уравнений и выделить корни, где была ошибка.",
            homework_completed=True,
            parent_comment="Тема стала заметно увереннее: теперь цель - скорость и меньше ошибок в записи.",
            materials_link="https://example.com/demo-quadratic-notes",
        ),
        LessonReport(
            student_id=student.id,
            lesson_date=_demo_date(-11),
            lesson_topic="Стартовая диагностика и план подготовки",
            covered="Провели короткий срез, отметили сильные стороны и главные пробелы.",
            worked="Базовые вычисления, простые уравнения и проценты получились лучше всего.",
            weak="Геометрия и текстовые задачи требуют отдельного блока занятий.",
            homework="Посмотреть разбор диагностики и решить 5 похожих заданий.",
            homework_completed=True,
            parent_comment="План на первый месяц: проценты, уравнения, геометрия и мини-срез в конце блока.",
            materials_link="https://example.com/demo-start-diagnostic",
        ),
    ]
    db.add_all(reports)
    db.flush()

    db.add_all(
        [
            Homework(
                student_id=student.id,
                title="6 задач на проценты",
                description="К каждой задаче записать схему: исходное число, процент, новая величина.",
                due_date=_demo_date(2),
            ),
            Homework(
                student_id=student.id,
                title="Мини-тренировка по графикам",
                description="Определить коэффициент наклона и точку пересечения с осью y в 5 примерах.",
                due_date=_demo_date(5),
            ),
            Homework(
                student_id=student.id,
                title="Геометрия: площади треугольников",
                description="Решить 4 задачи, в каждой подписать, какая высота или сторона используется.",
                due_date=_demo_date(7),
            ),
            Homework(
                student_id=student.id,
                title="8 квадратных уравнений",
                description="Решить подборку, проверить корни подстановкой.",
                due_date=_demo_date(-2),
                is_completed=True,
                completed_at=datetime.utcnow() - timedelta(days=2, hours=3),
            ),
            Homework(
                student_id=student.id,
                title="Разбор стартовой диагностики",
                description="Перерешать задания, где были ошибки, и выписать правило для каждого типа.",
                due_date=_demo_date(-8),
                is_completed=True,
                completed_at=datetime.utcnow() - timedelta(days=8, hours=2),
            ),
        ]
    )

    db.add_all(
        [
            Material(
                student_id=student.id,
                lesson_report_id=reports[0].id,
                title="Памятка: проценты и последовательные изменения",
                kind="Конспект",
                url="https://example.com/demo-percent-plan",
            ),
            Material(
                student_id=student.id,
                lesson_report_id=reports[1].id,
                title="Алгоритм решения квадратного уравнения",
                kind="Google Docs",
                url="https://example.com/demo-quadratic-notes",
            ),
            Material(
                student_id=student.id,
                lesson_report_id=reports[2].id,
                title="Разбор стартовой диагностики",
                kind="Доска урока",
                url="https://example.com/demo-start-diagnostic",
            ),
            Material(
                student_id=student.id,
                lesson_report_id=None,
                title="Таблица прогресса по темам ОГЭ",
                kind="Таблица",
                url="https://example.com/demo-progress-table",
            ),
            Material(
                student_id=student.id,
                lesson_report_id=None,
                title="План подготовки на 4 недели",
                kind="PDF",
                url="https://example.com/demo-four-week-plan",
            ),
        ]
    )

    db.add_all(
        [
            Checkpoint(
                student_id=student.id,
                checkpoint_date=_demo_date(-10),
                before="На стартовом срезе Анна теряла баллы в процентах, геометрии и оформлении.",
                after="Появился план, выделены 4 главных пробела, первые задачи на проценты решены увереннее.",
                improved="Стало понятнее, какие темы дают быстрый прирост и как проверять ответ.",
                blockers="Геометрия пока требует пошагового разбора и визуальной схемы.",
                next_month_plan="Закрыть проценты, стабилизировать уравнения, начать геометрию первой части.",
            ),
            Checkpoint(
                student_id=student.id,
                checkpoint_date=_demo_date(-3),
                before="Квадратные уравнения решались только с подсказками.",
                after="Большинство базовых уравнений решает самостоятельно, ошибки видит при проверке.",
                improved="Алгоритм решения, проверка корней, аккуратность записи.",
                blockers="В задачах с текстовым условием пока сложно составить уравнение без схемы.",
                next_month_plan="Перейти к текстовым задачам и связать их с уравнениями.",
            ),
        ]
    )

    _reviewed_demo_attempt(db, student)

    db.commit()
    db.refresh(student)
    return student


def ensure_demo_data(db: Session) -> Student:
    student = db.scalar(select(Student).where(Student.access_token == DEMO_ACCESS_TOKEN))
    if student is None or student.access_code != DEMO_ACCESS_CODE or student.subject != DEMO_SUBJECT:
        return seed_demo_data(db)

    work = db.scalar(select(DiagnosticWork).where(DiagnosticWork.slug == DEMO_DIAGNOSTIC_SLUG))
    reviewed_attempt = None
    if work is not None:
        reviewed_attempt = db.scalar(
            select(DiagnosticAttempt.id).where(
                DiagnosticAttempt.student_id == student.id,
                DiagnosticAttempt.work_id == work.id,
                DiagnosticAttempt.status == "reviewed",
            )
        )
    if work is None or reviewed_attempt is None:
        return seed_demo_data(db)

    return student
