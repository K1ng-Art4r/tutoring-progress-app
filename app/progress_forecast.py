from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    TOPIC_STATUS_LABELS,
    TOPIC_STATUS_LEVELS,
    DiagnosticAttempt,
    Student,
    TopicProgress,
)
from app.exam_config import (
    EGE_BASE_CONFIG,
    EGE_PROFILE_CONFIG,
    OGE_COMPETENCIES,
    OGE_CONFIG,
    ExamConfig,
    get_exam_config,
    grade_for_score,
    grade_label,
    ege_profile_test_score,
)


OGE_TOTAL_POINTS = OGE_CONFIG.max_primary_score
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
    return get_exam_config(student.subject) == OGE_CONFIG


def is_ege_base_student(student: Student) -> bool:
    return get_exam_config(student.subject) == EGE_BASE_CONFIG


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


def _topics_by_competency(student: Student, config: ExamConfig) -> dict[str, TopicProgress]:
    by_key = {
        topic.competency_key: topic
        for topic in student.topics
        if getattr(topic, "competency_key", "")
    }
    by_title = {topic.topic.strip().lower(): topic for topic in student.topics}
    result: dict[str, TopicProgress] = {}
    for competency in config.competencies:
        topic = by_key.get(competency.key) or by_title.get(competency.title.lower())
        if topic is not None:
            result[competency.key] = topic
    return result


def ensure_oge_competency_topics(db: Session, student: Student, commit: bool = True) -> bool:
    return ensure_exam_competency_topics(db, student, commit)


def ensure_exam_competency_topics(db: Session, student: Student, commit: bool = True) -> bool:
    config = get_exam_config(student.subject)
    if config is None:
        return False

    existing = _topics_by_competency(student, config)
    changed = False
    for competency in config.competencies:
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
    config = get_exam_config(student.subject)
    if config is None:
        return []
    existing = _topics_by_competency(student, config)
    rows: list[dict[str, object]] = []
    base_status_labels = {
        "not_started": "Не начали",
        "explained": "Объяснено",
        "with_help": "Решает с подсказкой",
        "independent": "Решает самостоятельно",
        "ready_for_test": "Готово к проверке",
        "stable": "Закреплено",
    }
    for competency in config.competencies:
        topic = existing.get(competency.key)
        level = _topic_level(topic)
        status = topic.status if topic is not None else "not_started"
        rows.append(
            {
                "key": competency.key,
                "title": competency.title,
                "description": competency.description,
                "task_lines": competency.task_lines,
                "weight": competency.weight,
                "level": level,
                "percent": round(level * 100),
                "weighted_points": competency.weight * level,
                "weighted_points_display": f"{competency.weight * level:.1f}".replace(".", ","),
                "status": status,
                "status_label": (
                    base_status_labels.get(status, status)
                    if config in {EGE_BASE_CONFIG, EGE_PROFILE_CONFIG}
                    else TOPIC_STATUS_LABELS.get(status, status)
                ),
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


def _forecast_points_from_diagnostics(
    mastery_points: float,
    diagnostic_records: list[DiagnosticAttempt],
) -> int:
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
    return min(max(round(forecast_float), 0), OGE_TOTAL_POINTS)


def _attempt_date(attempt: DiagnosticAttempt) -> date:
    if attempt.reviewed_at:
        return attempt.reviewed_at.date()
    if attempt.submitted_at:
        return attempt.submitted_at.date()
    return attempt.created_at.date()


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


def _build_chart(
    history: list[dict[str, object]],
    config: ExamConfig = OGE_CONFIG,
    one_decimal: bool = False,
) -> dict[str, object]:
    width = 720
    left = 54
    right = 682
    top = 22
    bottom = 238
    plot_width = right - left
    plot_height = bottom - top

    def y_for(score: float) -> float:
        chart_max = config.chart_max_score or config.max_primary_score
        return bottom - _clip_level(score / chart_max) * plot_height

    point_count = len(history)
    points = []
    for index, item in enumerate(history):
        x = left + (plot_width / max(point_count - 1, 1)) * index if point_count > 1 else left + plot_width / 2
        y = y_for(float(item["points"]))
        points.append(
            {
                "x": round(x, 1),
                "y": round(y, 1),
                "points": round(float(item["points"]), 1) if one_decimal else int(item["points"]),
                "grade": grade_for_score(config, float(item["points"])) if config.grade_bands else None,
                "primary_points": item.get("primary_points"),
                "change": round(float(item.get("change", 0.0)), 1),
                "influence": item.get("influence", "Обновились данные по занятиям и проверкам."),
                "label": item["label"],
                "date": item["date"],
            }
        )

    zone_labels = (
        {5: "ЦЕЛЬ", 4: "ВЫШЕ ПОРОГА", 2: "НИЖЕ ПОРОГА"}
        if config == EGE_PROFILE_CONFIG
        else {}
    )
    zones = [
        {
            "grade": str(grade),
            "label": zone_labels.get(grade, f"ОЦЕНКА {grade}"),
            "from": lower,
            "to": upper,
            "class": f"zone-{grade}",
        }
        for grade, lower, upper in config.chart_zones
    ]
    zone_rects = []
    for zone in zones:
        y_top = y_for(zone["to"])
        y_bottom = y_for(zone["from"])
        zone_rects.append(
            {
                "grade": zone["grade"],
                "label": zone["label"],
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
        for score in config.chart_ticks
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


EGE_BASE_SMOOTHING = {
    "homework": (0.15, 0.3),
    "lesson": (0.25, 0.6),
    "mini_diagnostic": (0.40, 1.0),
    "checkpoint": (0.60, 1.5),
    "full_mock": (0.80, 3.0),
    "manual": (0.70, 21.0),
}

EGE_BASE_LEARNING_RATES = {
    "homework": 0.12,
    "lesson": 0.20,
    "mini_diagnostic": 0.35,
    "checkpoint": 0.50,
    "full_mock": 0.65,
    "manual": 1.0,
}


def update_ege_base_mastery(old_level: float, observation_level: float, event_type: str) -> float:
    old = _clip_level(old_level)
    observation = _clip_level(observation_level)
    rate = EGE_BASE_LEARNING_RATES[event_type]
    return _clip_level(old + rate * (observation - old))


def calculate_ege_base_model_score(competencies: list[dict[str, object]]) -> float:
    score = sum(
        float(item["weight"]) * _clip_level(float(item["level"]))
        for item in competencies
    )
    return min(max(score, 0.0), float(EGE_BASE_CONFIG.max_primary_score))


def smooth_ege_base_score(
    previous_score: float,
    model_score: float,
    event_type: str,
) -> float:
    alpha, max_delta = EGE_BASE_SMOOTHING[event_type]
    previous = min(max(float(previous_score), 0.0), 21.0)
    model = min(max(float(model_score), 0.0), 21.0)
    calculated_delta = alpha * (model - previous)
    delta = min(max(calculated_delta, -max_delta), max_delta)
    return min(max(previous + delta, 0.0), 21.0)


def _ege_base_history(student: Student, model_score: float) -> list[dict[str, object]]:
    events = sorted(
        [(report.lesson_date, "lesson", f"Урок: {report.lesson_topic}", report.worked) for report in student.reports]
        + [
            (checkpoint.checkpoint_date, "checkpoint", "Месячный чекпоинт", checkpoint.improved)
            for checkpoint in student.checkpoints
        ],
        key=lambda item: item[0],
    )[-5:]
    if not events:
        return [{"date": date.today(), "label": "Текущий прогноз", "points": round(model_score, 1)}]

    display = max(0.0, model_score - min(2.0, len(events) * 0.45))
    history: list[dict[str, object]] = []
    for event_date, event_type, label, influence in events:
        updated = smooth_ege_base_score(display, model_score, event_type)
        history.append(
            {
                "date": event_date,
                "label": label,
                "points": round(updated, 1),
                "change": updated - display,
                "influence": influence,
            }
        )
        display = updated
    if history[-1]["date"] != date.today():
        history.append(
            {
                "date": date.today(),
                "label": "Текущий прогноз",
                "points": round(model_score, 1),
                "change": model_score - display,
                "influence": "Учтены текущие уровни всех проверенных компетенций.",
            }
        )
    return history


def _build_ege_base_forecast(
    student: Student,
    diagnostic_attempts: list[DiagnosticAttempt],
) -> dict[str, object]:
    competencies = build_competency_rows(student)
    model_score = calculate_ege_base_model_score(competencies)
    forecast_score = round(model_score, 1)
    grade = grade_for_score(EGE_BASE_CONFIG, forecast_score)
    next_threshold = next(
        (band.minimum for band in EGE_BASE_CONFIG.grade_bands if band.grade > grade),
        None,
    )
    if next_threshold is None:
        distance_text = "Результат уже находится в зоне оценки 5."
    else:
        distance = max(next_threshold - forecast_score, 0.0)
        if distance < 0.7:
            distance_text = (
                f"Прогноз находится рядом с границей оценки {grade + 1}. "
                f"Для стабильной оценки {grade + 1} нужно закрепить ещё несколько типов заданий."
            )
        else:
            distance_text = f"До оценки {grade + 1} осталось {str(round(distance, 1)).replace('.', ',')} балла."

    checked = sum(1 for item in competencies if not item["insufficient_data"])
    coverage = checked / max(len(competencies), 1)
    confidence = "высокая" if coverage >= 0.8 else "средняя" if coverage >= 0.45 else "низкая"
    incomplete = coverage < 1.0
    explanation = (
        f"Если бы базовый ЕГЭ был сегодня, прогноз — "
        f"{str(forecast_score).replace('.', ',')} из 21, оценка {grade}. {distance_text} "
        f"Уверенность прогноза: {confidence}."
    )
    if incomplete:
        explanation += " Для более точного прогноза нужен полный пробный вариант из 21 задания."

    return {
        "is_available": True,
        "exam_id": EGE_BASE_CONFIG.id,
        "exam_title": EGE_BASE_CONFIG.title,
        "competencies_title": "Компетенции базового ЕГЭ",
        "competencies": competencies,
        "mastery_points": model_score,
        "forecast_points": forecast_score,
        "forecast_label": f"Прогноз: {str(forecast_score).replace('.', ',')} из 21 — оценка {grade}",
        "grade": grade,
        "grade_zone": grade_label(EGE_BASE_CONFIG, forecast_score),
        "has_geometry_threshold": False,
        "geometry_points": 0,
        "geometry_total": 0,
        "geometry_ok": True,
        "max_primary_score": 21,
        "score_range_label": "0-21 балл",
        "chart_title": "Первичные баллы базового ЕГЭ по времени",
        "explanation": explanation,
        "confidence": confidence,
        "confidence_incomplete": incomplete,
        "chart": _build_chart(_ege_base_history(student, model_score), EGE_BASE_CONFIG, True),
        "diagnostic_points": None,
        "diagnostic_summaries": [],
    }


def calculate_ege_profile_primary_score(competencies: list[dict[str, object]]) -> float:
    score = sum(
        float(item["weight"]) * _clip_level(float(item["level"]))
        for item in competencies
    )
    return min(max(score, 0.0), 32.0)


def _ege_profile_history(student: Student, primary_score: float) -> list[dict[str, object]]:
    test_score = ege_profile_test_score(primary_score)
    activity = sorted(
        [(report.lesson_date, f"Урок: {report.lesson_topic}", report.worked) for report in student.reports]
        + [(item.checkpoint_date, "Месячный чекпоинт", item.improved) for item in student.checkpoints],
        key=lambda item: item[0],
    )[-4:]
    if not activity:
        return [{"date": date.today(), "label": "Текущий прогноз", "points": test_score, "primary_points": primary_score}]
    history: list[dict[str, object]] = []
    start = max(0.0, test_score - min(9.0, len(activity) * 2.2))
    previous = start
    for index, (event_date, label, influence) in enumerate(activity, start=1):
        fraction = index / len(activity)
        current = start + fraction * (test_score - start)
        current_primary = primary_score * (0.88 + 0.12 * fraction)
        history.append(
            {
                "date": event_date,
                "label": label,
                "points": round(current, 1),
                "primary_points": round(current_primary, 1),
                "change": current - previous,
                "influence": influence,
            }
        )
        previous = current
    if history[-1]["date"] != date.today():
        history.append(
            {
                "date": date.today(),
                "label": "Текущий прогноз",
                "points": round(test_score, 1),
                "primary_points": round(primary_score, 1),
                "change": test_score - previous,
                "influence": "Учтены текущие уровни компетенций профильного ЕГЭ.",
            }
        )
    return history


def _build_ege_profile_forecast(
    student: Student,
    diagnostic_attempts: list[DiagnosticAttempt],
) -> dict[str, object]:
    competencies = build_competency_rows(student)
    primary_score = calculate_ege_profile_primary_score(competencies)
    test_score_float = ege_profile_test_score(primary_score)
    test_score = round(test_score_float)
    target_score = 80
    for token in student.goal.replace("/", " ").split():
        if token.rstrip(".,").isdigit():
            candidate = int(token.rstrip(".,"))
            if 60 <= candidate <= 100:
                target_score = candidate

    checked = sum(1 for item in competencies if not item["insufficient_data"])
    coverage = checked / max(len(competencies), 1)
    confidence = "высокая" if coverage >= 0.8 else "средняя" if coverage >= 0.45 else "низкая"
    ranked = sorted(competencies, key=lambda item: float(item["level"]), reverse=True)
    strengths = ", ".join(str(item["title"]).lower() for item in ranked[:2])
    growth = ", ".join(str(item["title"]).lower() for item in ranked[-2:])
    threshold_reserve = test_score - 27
    target_delta = target_score - test_score
    threshold_text = (
        f"Экзамен сдан с запасом: {threshold_reserve} тестовых баллов."
        if threshold_reserve >= 0
        else f"До минимального порога: {abs(threshold_reserve)} тестовых баллов."
    )
    target_text = (
        f"До цели {target_score}: {target_delta} тестовых баллов."
        if target_delta > 0
        else f"Цель {target_score} баллов уже достигнута."
    )
    explanation = (
        f"Текущий прогноз — {test_score} баллов. {threshold_text} {target_text} "
        f"Сильные стороны — {strengths}. Основные зоны роста — {growth}. "
        f"Уверенность прогноза: {confidence}."
    )
    if coverage < 1:
        explanation += " Для уточнения прогноза нужен полный пробный вариант."

    return {
        "is_available": True,
        "exam_id": EGE_PROFILE_CONFIG.id,
        "exam_title": EGE_PROFILE_CONFIG.title,
        "competencies_title": "Компетенции профильного ЕГЭ",
        "competencies": competencies,
        "mastery_points": primary_score,
        "forecast_points": test_score,
        "forecast_label": f"Прогноз: {test_score} баллов",
        "primary_score_label": f"≈ {str(round(primary_score, 1)).replace('.', ',')} первичных из 32",
        "grade": None,
        "grade_zone": f"Цель: {target_score} баллов",
        "has_geometry_threshold": False,
        "geometry_points": 0,
        "geometry_total": 0,
        "geometry_ok": True,
        "max_primary_score": 100,
        "score_range_label": "0-100 баллов",
        "chart_title": "Тестовые баллы профильного ЕГЭ по времени",
        "explanation": explanation,
        "confidence": confidence,
        "confidence_incomplete": coverage < 1,
        "chart": _build_chart(_ege_profile_history(student, primary_score), EGE_PROFILE_CONFIG, True),
        "diagnostic_points": None,
        "diagnostic_summaries": [],
    }


def build_student_forecast(
    student: Student,
    diagnostic_attempts: list[DiagnosticAttempt],
) -> dict[str, object]:
    config = get_exam_config(student.subject)
    if config == EGE_BASE_CONFIG:
        return _build_ege_base_forecast(student, diagnostic_attempts)
    if config == EGE_PROFILE_CONFIG:
        return _build_ege_profile_forecast(student, diagnostic_attempts)
    if config != OGE_CONFIG:
        return {"is_available": False, "competencies": []}

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
    forecast_points = _forecast_points_from_diagnostics(mastery_points, diagnostic_records)
    grade = _oge_grade(forecast_points, geometry_points)
    geometry_display = min(max(round(geometry_points), 0), OGE_GEOMETRY_POINTS)

    if diagnostic_records:
        diagnostic_history = []
        for index, attempt in enumerate(diagnostic_records):
            diagnostic_history.append(
                {
                    "date": _attempt_date(attempt),
                    "label": f"Прогноз после диагностики: {attempt.work.title}",
                    "points": _forecast_points_from_diagnostics(
                        mastery_points,
                        diagnostic_records[: index + 1],
                    ),
                }
            )
        history = diagnostic_history[-4:]
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
        "exam_id": OGE_CONFIG.id,
        "exam_title": OGE_CONFIG.title,
        "competencies_title": "Компетенции ОГЭ",
        "competencies": competencies,
        "mastery_points": mastery_points,
        "forecast_points": forecast_points,
        "forecast_label": f"{forecast_points} из {OGE_TOTAL_POINTS} → оценка {grade}",
        "grade": grade,
        "grade_zone": _grade_zone(grade),
        "geometry_points": geometry_display,
        "geometry_total": OGE_GEOMETRY_POINTS,
        "geometry_ok": geometry_points >= 2,
        "has_geometry_threshold": True,
        "max_primary_score": OGE_TOTAL_POINTS,
        "score_range_label": "0-31 балл",
        "chart_title": "Первичные баллы ОГЭ по времени",
        "explanation": explanation,
        "chart": _build_chart(history),
        "diagnostic_points": diagnostic_points,
        "diagnostic_summaries": diagnostic_summaries,
    }


def calibrate_oge_competencies_from_attempt(db: Session, attempt: DiagnosticAttempt) -> None:
    if attempt.work is None or attempt.student is None:
        return

    config = get_exam_config(attempt.student.subject)
    if config is None or attempt.work.exam_type != config.exam_type:
        return

    ensure_exam_competency_topics(db, attempt.student, commit=False)
    existing = _topics_by_competency(attempt.student, config)
    answers_by_task = {answer.task_id: answer for answer in attempt.answers}
    aggregates: dict[str, dict[str, float]] = {}

    task_map = OGE_TASK_COMPETENCY_MAP if config == OGE_CONFIG else {
        line: competency.key
        for competency in config.competencies
        for line in competency.task_lines
    }

    for task in attempt.work.tasks:
        competency_key = task_map.get(task.exam_line or task.position)
        if competency_key is None:
            continue
        bucket = aggregates.setdefault(competency_key, {"score": 0.0, "max_score": 0.0})
        bucket["score"] += _answer_score(answers_by_task.get(task.id))
        bucket["max_score"] += task.max_score

    for competency in config.competencies:
        topic = existing.get(competency.key)
        if topic is None:
            continue

        bucket = aggregates.get(competency.key)
        if bucket and bucket["max_score"] > 0:
            level = _clip_level(bucket["score"] / bucket["max_score"])
            if config in {EGE_BASE_CONFIG, EGE_PROFILE_CONFIG} and not topic.insufficient_data:
                level = update_ege_base_mastery(topic.mastery_level, level, "mini_diagnostic")
            topic.mastery_level = level
            topic.status = status_for_level(level)
            topic.insufficient_data = False
            if not topic.comment.strip():
                topic.comment = "Стартовый уровень выставлен по проверенной диагностике."
            continue

        if config == OGE_CONFIG and not topic.comment.strip() and topic.status == "not_started":
            topic.mastery_level = 0.25
            topic.status = "explained"
            topic.insufficient_data = True
            topic.comment = "В диагностике мало данных по этой компетенции; стартовое значение рабочее."
