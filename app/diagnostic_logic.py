from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models import DiagnosticAnswer, DiagnosticAttempt, DiagnosticTask, DiagnosticWork


SCALE_BANDS = [
    {
        "min": 0,
        "max": 7,
        "level": "База нестабильна",
        "conclusion": (
            "Ученик пока теряет баллы на базовых темах, поэтому рано системно идти во вторую часть."
        ),
        "focus": "Алгебра, вычисления, функции, базовая геометрия и типовые задания первой части.",
        "target": "Сначала стабилизировать базу; ближайший ориентир - 50-60+, затем пересмотр цели.",
    },
    {
        "min": 8,
        "max": 12,
        "level": "Первая часть частично собрана, но есть системные пробелы",
        "conclusion": (
            "Можно готовиться к 60-70+, но сначала нужно стабилизировать типовые темы."
        ),
        "focus": "Уравнения, неравенства, производная, геометрия и регулярные мини-срезы.",
        "target": "60-70+ при регулярной работе и снижении ошибок в первой части.",
    },
    {
        "min": 13,
        "max": 16,
        "level": "Хорошая база, потенциал 70-80+",
        "conclusion": (
            "Основные баллы можно добирать через профильное ядро и аккуратную работу со второй частью."
        ),
        "focus": (
            "Сложные уравнения и неравенства, геометрия, экономическая задача, "
            "задания с развернутым решением."
        ),
        "target": "70-80+ при системной тренировке второй части.",
    },
    {
        "min": 17,
        "max": 20,
        "level": "Сильный ученик, потенциал 80+",
        "conclusion": "Базовые темы в целом рабочие, нужно строить стратегию высокого балла.",
        "focus": (
            "Параметры, сложная геометрия, экономические задачи, номер 19/логика/делимость, "
            "оформление решений."
        ),
        "target": "80+; при точечной работе возможна стратегия 85-90+.",
    },
]

OGE_SCALE_BANDS = [
    {
        "min": 0,
        "max": 7,
        "level": "Высокий риск",
        "conclusion": (
            "Ученик теряет баллы на базовых темах. Сначала нужно стабилизировать арифметику, "
            "простую алгебру и практические задачи."
        ),
        "focus": "Базовые вычисления, проценты, простые уравнения, практические задачи, минимальная геометрия.",
        "target": "Снизить риск несдачи и перейти к стабильному решению базовых заданий.",
    },
    {
        "min": 8,
        "max": 11,
        "level": "Сдать можно, но нестабильно",
        "conclusion": (
            "Часть базы есть, но ошибки могут стоить оценки. Нужно закрывать системные пробелы "
            "и тренировать типовые задания."
        ),
        "focus": "Алгебра 7-9 класса, функции, текстовые задачи, геометрия первой части.",
        "target": "Сделать сдачу устойчивой и начать движение к оценке 4.",
    },
    {
        "min": 12,
        "max": 15,
        "level": "База на 4 формируется",
        "conclusion": (
            "Ученик может решать значительную часть первой части, но для уверенной 4/5 нужно "
            "добирать геометрию, функции и развернутые задания."
        ),
        "focus": "Задания повышенной сложности, текстовые задачи, графики, геометрия, оформление решений.",
        "target": "Закрепить уровень 4 и подготовить основу для выхода на 5.",
    },
    {
        "min": 16,
        "max": 20,
        "level": "Сильная база, потенциал на 5",
        "conclusion": (
            "Базовые темы в целом рабочие, нужно тренировать скорость, аккуратность и вторую часть."
        ),
        "focus": "Сложные текстовые задачи, геометрические доказательства, задания второй части, стратегия экзамена.",
        "target": "Вывести ученика на стратегию оценки 5.",
    },
]


def normalize_answer(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    replacements = {
        "\u00a0": "",
        " ": "",
        ",": ".",
        "−": "-",
        "–": "-",
        "—": "-",
        "∞": "inf",
        "∪": "u",
        "≤": "<=",
        "≥": ">=",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = normalized.replace("рублей", "").replace("руб.", "").replace("р.", "")
    return normalized


def _as_decimal(value: str) -> Decimal | None:
    if not re.fullmatch(r"[+-]?\d+(\.\d+)?", value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def answers_match(student_answer: str | None, correct_answer: str) -> bool:
    student_normalized = normalize_answer(student_answer)
    correct_normalized = normalize_answer(correct_answer)
    if not student_normalized:
        return False

    student_decimal = _as_decimal(student_normalized)
    correct_decimal = _as_decimal(correct_normalized)
    if student_decimal is not None and correct_decimal is not None:
        return student_decimal == correct_decimal
    return student_normalized == correct_normalized


def score_answer(task: DiagnosticTask, answer_text: str | None) -> tuple[bool, int]:
    is_correct = answers_match(answer_text, task.correct_answer)
    return is_correct, task.max_score if is_correct else 0


def finalize_attempt(attempt: DiagnosticAttempt) -> None:
    if attempt.status != "in_progress":
        return

    answers_by_task = {answer.task_id: answer for answer in attempt.answers}
    total = 0
    for task in attempt.work.tasks:
        answer = answers_by_task.get(task.id)
        if answer is None:
            continue
        is_correct, score = score_answer(task, answer.answer_text)
        answer.is_correct = is_correct
        answer.auto_score = score
        total += score

    attempt.auto_score = total
    attempt.status = "submitted"
    attempt.submitted_at = datetime.utcnow()


def get_scale_band(score: int, exam_type: str | None = None) -> dict[str, str | int]:
    scale_bands = OGE_SCALE_BANDS if exam_type == "ОГЭ" else SCALE_BANDS
    for band in scale_bands:
        if band["min"] <= score <= band["max"]:
            return band
    return scale_bands[-1] if score > 20 else scale_bands[0]


def answer_score(answer: DiagnosticAnswer | None) -> int:
    if answer is None:
        return 0
    if answer.teacher_score is not None:
        return answer.teacher_score
    return answer.auto_score


def build_parent_message(
    work: DiagnosticWork,
    tasks: list[DiagnosticTask],
    answers_by_task: dict[int, DiagnosticAnswer],
    total_score: int,
) -> str:
    band = get_scale_band(total_score, work.exam_type)
    solved = []
    partial = []
    weak = []
    for task in tasks:
        score = answer_score(answers_by_task.get(task.id))
        label = f"№{task.position} ({task.title})"
        if score >= task.max_score:
            solved.append(label)
        elif score > 0:
            partial.append(label)
            weak.append(task.skill or task.title)
        else:
            weak.append(task.skill or task.title)

    solved_text = ", ".join(solved) if solved else "пока нет полностью закрытых заданий"
    partial_text = ", ".join(partial) if partial else "частичных решений нет"
    weak_unique = []
    for item in weak:
        if item not in weak_unique:
            weak_unique.append(item)
    weak_text = ", ".join(weak_unique[:5]) if weak_unique else "точечные ошибки, без системного провала"

    return (
        f"Ученик прошел диагностику «{work.exam_type}» и набрал {total_score}/{work.max_score}.\n\n"
        f"Текущий уровень: {band['level']}.\n"
        f"Вывод: {band['conclusion']}\n\n"
        f"Что получилось хорошо: {solved_text}.\n"
        f"Частично получилось: {partial_text}.\n"
        f"Основные зоны роста: {weak_text}.\n\n"
        f"Первый фокус подготовки: {band['focus']}\n"
        f"Ориентир: {band['target']}\n\n"
        "На ближайших занятиях я разберу ошибки, закреплю слабые темы и буду фиксировать прогресс "
        "в личном кабинете после уроков и мини-срезов."
    )
