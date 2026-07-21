from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    TOPIC_STATUS_LABELS,
    TOPIC_STATUS_LEVELS,
    DiagnosticAttempt,
    Student,
    TopicProgress,
)


@dataclass(frozen=True)
class OgeCompetency:
    key: str
    title: str
    weight: int
    is_geometry: bool = False


OGE_COMPETENCIES = [
    OgeCompetency("practical", "Практико-ориентированные задачи", 5),
    OgeCompetency("numbers_formulas", "Числа, выражения и формулы", 3),
    OgeCompetency("number_line", "Координаты на прямой", 1),
    OgeCompetency("equations", "Уравнения", 1),
    OgeCompetency("probability_statistics", "Вероятность и статистика", 1),
    OgeCompetency("functions_graphs", "Функции и чтение графиков", 1),
    OgeCompetency("inequalities_systems", "Неравенства и системы", 1),
    OgeCompetency("sequences_progressions", "Последовательности и прогрессии", 1),
    OgeCompetency("geometry_first", "Геометрия первой части", 5, True),
    OgeCompetency("algebra_second", "Алгебра второй части", 2),
    OgeCompetency("word_problem_second", "Текстовая задача второй части", 2),
    OgeCompetency("graphs_second", "Графики второй части", 2),
    OgeCompetency("geometry_second_compute", "Геометрия второй части: вычисление", 2, True),
    OgeCompetency("geometry_second_proof", "Геометрия второй части: доказательство", 2, True),
    OgeCompetency("geometry_second_hard", "Геометрия второй части: сложная задача", 2, True),
]

OGE_TOTAL_POINTS = sum(item.weight for item in OGE_COMPETENCIES)
OGE_GEOMETRY_POINTS = sum(item.weight for item in OGE_COMPETENCIES if item.is_geometry)

OGE_TASK_COMPETENCY_MAP = {
    1: "practical",
    2: "practical",
    3: "practical",
    4: "numbers_formulas",
    5: "numbers_formulas",
    6: "equations",
    7: "geometry_first",
    8: "geometry_first",
    9: "functions_graphs",
    10: "word_problem_second",
    11: "inequalities_systems",
    12: "geometry_second_compute",
}


def is_oge_student(student: Student) -> bool:
    return "ОГЭ" in student.subject


def _clip_level(value: float | int | None) -> float:
    try:
        numeric = float(value if value is not None else 0)
    except (TypeError, ValueError):
        numeric = 0.0
    return min(max(numeric, 0.0), 1.0)


def status_for_level(level: float) -> str:
    level = _clip_level(level)
    if level < 0.13:
        return "not_started"
    if level < 0.38:
        return "explained"
    if level < 0.63:
        return "with_help"
    if level < 0.83:
        return "independent"
    if level < 0.96:
        return "ready_for_test"
    return "stable"


def _topic_level(topic: TopicProgress | None) -> float:
    if topic is None:
        return 0.0
    if topic.mastery_level is not None:
        return _clip_level(topic.mastery_level)
    return _clip_level(TOPIC_STATUS_LEVELS.get(topic.status, 0.0))


def _topics_by_competency(student: Student) -> dict[str, TopicProgress]:
    by_key = {
        topic.competency_key: topic
        for topic in student.topics
        if getattr(topic, "competency_key", "")
    }
    by_title = {topic.topic.strip().lower(): topic for topic in student.topics}
    result: dict[str, TopicProgress] = {}
    for competency in OGE_COMPETENCIES:
        topic = by_key.get(competency.key) or by_title.get(competency.title.lower())
        if topic is not None:
            result[competency.key] = topic
    return result


def ensure_oge_competency_topics(db: Session, student: Student, commit: bool = True) -> bool:
    if not is_oge_student(student):
        return False

    existing = _topics_by_competency(student)
    changed = False
    for competency in OGE_COMPETENCIES:
        topic = existing.get(competency.key)
        if topic is None:
            db.add(
                TopicProgress(
                    student_id=student.id,
                    topic=competency.title,
                    competency_key=competency.key,
                    weight=competency.weight,
                    mastery_level=0.0,
                    status="not_started",
                    insufficient_data=True,
                )
            )
            changed = True
            continue
        if not topic.competency_key:
            topic.competency_key = competency.key
            changed = True
        if topic.topic != competency.title:
            topic.topic = competency.title
            changed = True
        if topic.weight != competency.weight:
            topic.weight = competency.weight
            changed = True
    if changed and commit:
        db.commit()
    elif changed:
        db.flush()
    return changed


def build_competency_rows(student: Student) -> list[dict[str, object]]:
    existing = _topics_by_competency(student)
    rows: list[dict[str, object]] = []
    for competency in OGE_COMPETENCIES:
        topic = existing.get(competency.key)
        level = _topic_level(topic)
        status = topic.status if topic is not None else "not_started"
        rows.append(
            {
                "key": competency.key,
                "title": competency.title,
                "weight": competency.weight,
                "level": level,
                "percent": round(level * 100),
                "weighted_points": competency.weight * level,
                "weighted_points_display": f"{competency.weight * level:.1f}".replace(".", ","),
                "status": status,
                "status_label": TOPIC_STATUS_LABELS.get(status, status),
                "comment": topic.comment if topic is not None else "",
                "updated_at": topic.updated_at if topic is not None else None,
                "is_geometry": competency.is_geometry,
                "insufficient_data": topic.insufficient_data if topic is not None else True,
            }
        )
    return rows


def _answer_score(answer) -> int:
    if answer is None:
        return 0
    if answer.teacher_score is not None:
        return answer.teacher_score
    return answer.auto_score


def _diagnostic_points(attempt: DiagnosticAttempt) -> float:
    if not attempt.work or not attempt.work.max_score:
        return 0.0
    score = attempt.manual_score if attempt.manual_score is not None else attempt.auto_score
    return _clip_level(score / attempt.work.max_score) * OGE_TOTAL_POINTS


def _reviewed_oge_attempts(attempts: list[DiagnosticAttempt]) -> list[DiagnosticAttempt]:
    return [
        attempt
        for attempt in attempts
        if attempt.status == "reviewed"
        and attempt.work is not None
        and attempt.work.exam_type == "ОГЭ"
        and attempt.work.max_score > 0
    ]


def _oge_grade(points: int, geometry_points: float) -> int:
    if points < 8 or geometry_points < 2:
        return 2
    if points <= 14:
        return 3
    if points <= 21:
        return 4
    return 5


def _grade_zone(grade: int) -> str:
    return {
        2: "Зона риска",
        3: "Сдача уже видна, но нестабильно",
        4: "Рабочая оценка 4",
        5: "Зона оценки 5",
    }.get(grade, "Текущий прогноз")


def _history_from_activity(student: Student, forecast_points: int) -> list[dict[str, object]]:
    activity_dates = sorted(
        {
            report.lesson_date
            for report in student.reports
        }
        | {
            checkpoint.checkpoint_date
            for checkpoint in student.checkpoints
        }
    )
    if not activity_dates:
        return [{"date": date.today(), "label": "Текущий прогноз", "points": forecast_points}]

    selected_dates = activity_dates[-4:]
    history: list[dict[str, object]] = []
    steps_before_now = len(selected_dates)
    for index, item_date in enumerate(selected_dates):
        points = max(0, forecast_points - (steps_before_now - index) * 2)
        history.append({"date": item_date, "label": "После занятия", "points": points})
    if history[-1]["date"] != date.today():
        history.append({"date": date.today(), "label": "Сейчас", "points": forecast_points})
    return history


def _build_chart(history: list[dict[str, object]]) -> dict[str, object]:
    width = 720
    left = 54
    right = 682
    top = 22
    bottom = 238
    plot_width = right - left
    plot_height = bottom - top

    def y_for(score: float) -> float:
        return bottom - _clip_level(score / OGE_TOTAL_POINTS) * plot_height

    point_count = len(history)
    points = []
    for index, item in enumerate(history):
        x = left + (plot_width / max(point_count - 1, 1)) * index if point_count > 1 else left + plot_width / 2
        y = y_for(float(item["points"]))
        points.append(
            {
                "x": round(x, 1),
                "y": round(y, 1),
                "points": int(item["points"]),
                "label": item["label"],
                "date": item["date"],
            }
        )

    zones = [
        {"grade": "5", "from": 22, "to": 31, "class": "zone-5"},
        {"grade": "4", "from": 15, "to": 22, "class": "zone-4"},
        {"grade": "3", "from": 8, "to": 15, "class": "zone-3"},
        {"grade": "2", "from": 0, "to": 8, "class": "zone-2"},
    ]
    zone_rects = []
    for zone in zones:
        y_top = y_for(zone["to"])
        y_bottom = y_for(zone["from"])
        zone_rects.append(
            {
                "grade": zone["grade"],
                "class": zone["class"],
                "x": left,
                "y": round(y_top, 1),
                "width": plot_width,
                "height": round(y_bottom - y_top, 1),
                "label_y": round(y_top + (y_bottom - y_top) / 2 + 4, 1),
            }
        )

    ticks = [
        {"score": score, "y": round(y_for(score), 1)}
        for score in [0, 8, 15, 22, 31]
    ]
    return {
        "width": width,
        "height": 280,
        "left": left,
        "right": right,
        "top": top,
        "bottom": bottom,
        "zones": zone_rects,
        "ticks": ticks,
        "points": points,
        "polyline": " ".join(f"{point['x']},{point['y']}" for point in points),
    }


def build_student_forecast(
    student: Student,
    diagnostic_attempts: list[DiagnosticAttempt],
) -> dict[str, object]:
    competencies = build_competency_rows(student)
    mastery_points = sum(float(item["weighted_points"]) for item in competencies)
    geometry_points = sum(
        float(item["weighted_points"]) for item in competencies if item["is_geometry"]
    )

    reviewed_attempts = _reviewed_oge_attempts(diagnostic_attempts)
    diagnostic_records = sorted(
        reviewed_attempts,
        key=lambda attempt: attempt.reviewed_at or attempt.submitted_at or attempt.created_at,
    )
    recent_diagnostic_points = [_diagnostic_points(attempt) for attempt in diagnostic_records[-3:]]
    diagnostic_points = (
        sum(recent_diagnostic_points) / len(recent_diagnostic_points)
        if recent_diagnostic_points
        else None
    )
    forecast_float = (
        mastery_points * 0.8 + diagnostic_points * 0.2
        if diagnostic_points is not None
        else mastery_points
    )
    forecast_points = min(max(round(forecast_float), 0), OGE_TOTAL_POINTS)
    grade = _oge_grade(forecast_points, geometry_points)
    geometry_display = min(max(round(geometry_points), 0), OGE_GEOMETRY_POINTS)

    if diagnostic_records:
        history = [
            {
                "date": attempt.reviewed_at.date()
                if attempt.reviewed_at
                else (attempt.submitted_at.date() if attempt.submitted_at else attempt.created_at.date()),
                "label": attempt.work.title,
                "points": round(_diagnostic_points(attempt)),
            }
            for attempt in diagnostic_records[-4:]
        ]
        if history[-1]["date"] != date.today() or history[-1]["points"] != forecast_points:
            history.append({"date": date.today(), "label": "Текущий прогноз", "points": forecast_points})
    else:
        history = _history_from_activity(student, forecast_points)

    geometry_text = (
        "геометрия выше минимального порога"
        if geometry_points >= 2
        else "по геометрии пока не хватает минимального порога"
    )
    explanation = (
        f"Если бы ОГЭ был сегодня, прогноз — {forecast_points} из {OGE_TOTAL_POINTS}, "
        f"это {('оценка ' + str(grade)) if grade > 2 else 'зона риска'}. "
        "Прогноз строится по пройденным компетенциям"
        + (" и последним проверенным диагностикам. " if diagnostic_points is not None else ". ")
        + f"Отдельно следим за геометрией: сейчас {geometry_text}."
    )

    diagnostic_summaries = []
    for attempt in diagnostic_records:
        projected = round(_diagnostic_points(attempt))
        score = attempt.manual_score if attempt.manual_score is not None else attempt.auto_score
        diagnostic_summaries.append(
            {
                "attempt": attempt,
                "score": score,
                "projected_points": projected,
                "influence": (
                    f"В пересчете на шкалу ОГЭ это примерно {projected} из {OGE_TOTAL_POINTS}. "
                    "Последние диагностики дают 20% текущего прогноза."
                ),
            }
        )

    return {
        "is_available": is_oge_student(student),
        "competencies": competencies,
        "mastery_points": mastery_points,
        "forecast_points": forecast_points,
        "forecast_label": f"{forecast_points} из {OGE_TOTAL_POINTS} → оценка {grade}",
        "grade": grade,
        "grade_zone": _grade_zone(grade),
        "geometry_points": geometry_display,
        "geometry_total": OGE_GEOMETRY_POINTS,
        "geometry_ok": geometry_points >= 2,
        "explanation": explanation,
        "chart": _build_chart(history),
        "diagnostic_points": diagnostic_points,
        "diagnostic_summaries": diagnostic_summaries,
    }


def calibrate_oge_competencies_from_attempt(db: Session, attempt: DiagnosticAttempt) -> None:
    if attempt.work is None or attempt.student is None or attempt.work.exam_type != "ОГЭ":
        return

    ensure_oge_competency_topics(db, attempt.student, commit=False)
    existing = _topics_by_competency(attempt.student)
    answers_by_task = {answer.task_id: answer for answer in attempt.answers}
    aggregates: dict[str, dict[str, float]] = {}

    for task in attempt.work.tasks:
        competency_key = OGE_TASK_COMPETENCY_MAP.get(task.position)
        if competency_key is None:
            continue
        bucket = aggregates.setdefault(competency_key, {"score": 0.0, "max_score": 0.0})
        bucket["score"] += _answer_score(answers_by_task.get(task.id))
        bucket["max_score"] += task.max_score

    for competency in OGE_COMPETENCIES:
        topic = existing.get(competency.key)
        if topic is None:
            continue

        bucket = aggregates.get(competency.key)
        if bucket and bucket["max_score"] > 0:
            level = _clip_level(bucket["score"] / bucket["max_score"])
            topic.mastery_level = level
            topic.status = status_for_level(level)
            topic.insufficient_data = bucket["max_score"] < 2
            if not topic.comment.strip():
                topic.comment = "Стартовый уровень выставлен по проверенной диагностике."
            continue

        if not topic.comment.strip() and topic.status == "not_started":
            topic.mastery_level = 0.25
            topic.status = "explained"
            topic.insufficient_data = True
            topic.comment = "В диагностике мало данных по этой компетенции; стартовое значение рабочее."
