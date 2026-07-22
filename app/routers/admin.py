from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.auth import admin_redirect, attach_login_cookie, clear_login_cookie, is_admin
from app.config import settings
from app.database import get_db
from app.diagnostic_logic import answer_score, build_parent_message, get_scale_band
from app.file_uploads import save_diagnostic_task_image, save_pdf_upload
from app.models import (
    STUDENT_STATUSES,
    Checkpoint,
    CompetencyAdjustment,
    DiagnosticAnswer,
    DiagnosticAttempt,
    DiagnosticTask,
    DiagnosticWork,
    Homework,
    LEAD_STATUSES,
    LessonReport,
    Material,
    Student,
    TopicProgress,
    Lead,
    TOPIC_STATUS_LEVELS,
    TOPIC_STATUSES,
    make_access_code,
)
from app.options import (
    GOAL_OPTIONS,
    HOMEWORK_FORMAT_OPTIONS,
    MATERIAL_KIND_OPTIONS,
    SUBJECT_OPTIONS,
)
from app.progress_forecast import (
    build_student_forecast,
    calibrate_oge_competencies_from_attempt,
    ensure_oge_competency_topics,
)
from app.view_helpers import templates

router = APIRouter(prefix="/admin")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _require_admin(request: Request):
    if not is_admin(request):
        return admin_redirect()
    return None


def _student_or_redirect(student_id: int, db: Session) -> Student | None:
    return db.get(Student, student_id)


def _redirect_to_student(student_id: int) -> RedirectResponse:
    return RedirectResponse(f"/admin/students/{student_id}", status_code=303)


def _save_homework_pdf(student_id: int, upload: UploadFile | None) -> tuple[str, str, str] | None:
    return save_pdf_upload(student_id, upload, "homework", "homework_pdf_only")


def _lead_or_redirect(lead_id: int, db: Session) -> Lead | None:
    return db.get(Lead, lead_id)


def _make_unique_access_code(db: Session) -> str:
    while True:
        code = make_access_code()
        exists = db.scalar(select(Student.id).where(Student.access_code == code).limit(1))
        if exists is None:
            return code


def _parse_mastery_level(value: str, status: str) -> float:
    if value.strip():
        try:
            return min(max(float(value.replace(",", ".")), 0.0), 1.0)
        except ValueError:
            pass
    return float(TOPIC_STATUS_LEVELS.get(status, 0.0))


def _parse_weight(value: str, fallback: int = 1) -> int:
    try:
        return min(max(int(value), 1), 31)
    except ValueError:
        return fallback


def _load_diagnostic_attempt(attempt_id: int, db: Session) -> DiagnosticAttempt | None:
    return db.scalar(
        select(DiagnosticAttempt)
        .where(DiagnosticAttempt.id == attempt_id)
        .options(
            selectinload(DiagnosticAttempt.student),
            selectinload(DiagnosticAttempt.work).selectinload(DiagnosticWork.tasks),
            selectinload(DiagnosticAttempt.answers).selectinload(DiagnosticAnswer.task),
        )
    )


@router.get("/login")
def login_page(request: Request, error: int | None = None):
    if is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {
            "request": request,
            "error": error == 1,
            "is_admin": False,
            "noindex": True,
        },
    )


@router.post("/login")
def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    if username.strip() != settings.teacher_login or password != settings.teacher_password:
        return RedirectResponse("/admin/login?error=1", status_code=303)
    response = RedirectResponse("/admin", status_code=303)
    attach_login_cookie(response)
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    clear_login_cookie(response)
    return response


@router.get("")
def dashboard(
    request: Request,
    lead_status: list[str] | None = Query(None),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    students = list(db.scalars(select(Student).order_by(Student.status, Student.name)))
    all_leads = list(db.scalars(select(Lead).order_by(desc(Lead.created_at))))
    selected_lead_statuses = [
        status for status in (lead_status or ["new", "contacted"]) if status in LEAD_STATUSES
    ]
    if not selected_lead_statuses:
        selected_lead_statuses = ["new", "contacted"]
    leads = [lead for lead in all_leads if lead.status in selected_lead_statuses]
    lead_counts = {
        status: sum(1 for lead in all_leads if lead.status == status)
        for status in LEAD_STATUSES
    }
    diagnostic_review_count = len(
        list(
            db.scalars(
                select(DiagnosticAttempt)
                .join(Student)
                .where(
                    DiagnosticAttempt.status == "submitted",
                    Student.status != "archived",
                )
            )
        )
    )
    latest_reports: dict[int, LessonReport | None] = {}
    stale_student_ids: set[int] = set()

    for student in students:
        report = db.scalar(
            select(LessonReport)
            .where(LessonReport.student_id == student.id)
            .order_by(desc(LessonReport.lesson_date), desc(LessonReport.created_at))
            .limit(1)
        )
        latest_reports[student.id] = report
        if student.status == "active":
            if report is None or report.lesson_date < date.today() - timedelta(days=7):
                stale_student_ids.add(student.id)

    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            "request": request,
            "students": students,
            "leads": leads,
            "lead_statuses": LEAD_STATUSES,
            "selected_lead_statuses": selected_lead_statuses,
            "lead_counts": lead_counts,
            "selected_leads_count": len(leads),
            "latest_reports": latest_reports,
            "stale_student_ids": stale_student_ids,
            "active_count": sum(1 for student in students if student.status == "active"),
            "diagnostic_review_count": diagnostic_review_count,
            "is_admin": True,
            "noindex": True,
        },
    )


@router.get("/homework")
def homework_overview(
    request: Request,
    view: str = Query("active"),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    all_homework = list(
        db.scalars(
            select(Homework)
            .join(Student)
            .where(Student.status != "archived")
            .options(selectinload(Homework.student))
            .order_by(
                Homework.is_completed.asc(),
                Homework.due_date.asc().nullslast(),
                desc(Homework.created_at),
            )
        )
    )
    homework_counts = {
        "all": len(all_homework),
        "active": sum(1 for item in all_homework if not item.is_completed),
        "completed": sum(1 for item in all_homework if item.is_completed),
        "with_solution": sum(1 for item in all_homework if item.solution_filename),
    }
    if view == "completed":
        homework_items = [item for item in all_homework if item.is_completed]
    elif view == "with_solution":
        homework_items = [item for item in all_homework if item.solution_filename]
    elif view == "all":
        homework_items = all_homework
    else:
        view = "active"
        homework_items = [item for item in all_homework if not item.is_completed]

    return templates.TemplateResponse(
        request,
        "admin_homework.html",
        {
            "request": request,
            "homework_items": homework_items,
            "homework_counts": homework_counts,
            "selected_view": view,
            "is_admin": True,
            "noindex": True,
        },
    )


@router.get("/diagnostics")
def diagnostics_overview(
    request: Request,
    view: str = Query("needs_review"),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    all_attempts = list(
        db.scalars(
            select(DiagnosticAttempt)
            .join(Student)
            .where(Student.status != "archived")
            .options(
                selectinload(DiagnosticAttempt.student),
                selectinload(DiagnosticAttempt.work),
            )
            .order_by(
                DiagnosticAttempt.status.asc(),
                desc(DiagnosticAttempt.submitted_at).nullslast(),
                desc(DiagnosticAttempt.created_at),
            )
        )
    )

    diagnostic_counts = {
        "all": len(all_attempts),
        "needs_review": sum(1 for attempt in all_attempts if attempt.status == "submitted"),
        "in_progress": sum(1 for attempt in all_attempts if attempt.status == "in_progress"),
        "reviewed": sum(1 for attempt in all_attempts if attempt.status == "reviewed"),
    }
    if view == "all":
        attempts = all_attempts
    elif view == "in_progress":
        attempts = [attempt for attempt in all_attempts if attempt.status == "in_progress"]
    elif view == "reviewed":
        attempts = [attempt for attempt in all_attempts if attempt.status == "reviewed"]
    else:
        view = "needs_review"
        attempts = [attempt for attempt in all_attempts if attempt.status == "submitted"]

    return templates.TemplateResponse(
        request,
        "admin_diagnostics.html",
        {
            "request": request,
            "attempts": attempts,
            "diagnostic_counts": diagnostic_counts,
            "selected_view": view,
            "is_admin": True,
            "noindex": True,
        },
    )


@router.get("/diagnostics/new")
def new_diagnostic_work_page(
    request: Request,
    created: int | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    created_work = db.get(DiagnosticWork, created) if created is not None else None
    return templates.TemplateResponse(
        request,
        "admin_diagnostic_builder.html",
        {
            "request": request,
            "subject_options": SUBJECT_OPTIONS,
            "created_work": created_work,
            "error": error,
            "is_admin": True,
            "noindex": True,
        },
    )


@router.post("/diagnostics/new")
async def create_diagnostic_work(
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    form = await request.form()
    title = str(form.get("title", "")).strip()
    subject = str(form.get("subject", "")).strip()
    exam_type = str(form.get("exam_type", "")).strip()
    description = str(form.get("description", "")).strip()
    try:
        duration_minutes = min(max(int(str(form.get("duration_minutes", "40"))), 5), 300)
        task_count = min(max(int(str(form.get("task_count", "1"))), 1), 30)
    except ValueError:
        return RedirectResponse("/admin/diagnostics/new?error=invalid_fields", status_code=303)

    if not title or subject not in SUBJECT_OPTIONS or not exam_type or not description:
        return RedirectResponse("/admin/diagnostics/new?error=invalid_fields", status_code=303)

    task_rows: list[dict] = []
    for index in range(task_count):
        prompt = str(form.get(f"task_prompt_{index}", "")).strip()
        correct_answer = str(form.get(f"task_correct_answer_{index}", "")).strip()
        if not prompt or not correct_answer:
            return RedirectResponse("/admin/diagnostics/new?error=invalid_tasks", status_code=303)
        try:
            task_max_score = min(max(int(str(form.get(f"task_max_score_{index}", "1"))), 1), 20)
            raw_exam_line = str(form.get(f"task_exam_line_{index}", "")).strip()
            exam_line = min(max(int(raw_exam_line), 1), 31) if raw_exam_line else None
        except ValueError:
            return RedirectResponse("/admin/diagnostics/new?error=invalid_tasks", status_code=303)

        image_upload = form.get(f"task_image_{index}")
        image_filename = str(getattr(image_upload, "filename", "") or "")
        if image_filename:
            if Path(image_filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                return RedirectResponse("/admin/diagnostics/new?error=image_type", status_code=303)
            image_size = getattr(image_upload, "size", None)
            if image_size is not None and image_size > 8 * 1024 * 1024:
                return RedirectResponse("/admin/diagnostics/new?error=image_size", status_code=303)

        task_rows.append(
            {
                "title": str(form.get(f"task_title_{index}", "")).strip() or f"Задание {index + 1}",
                "skill": str(form.get(f"task_skill_{index}", "")).strip(),
                "prompt": prompt,
                "correct_answer": correct_answer,
                "solution": str(form.get(f"task_solution_{index}", "")).strip(),
                "criteria": str(form.get(f"task_criteria_{index}", "")).strip(),
                "max_score": task_max_score,
                "exam_line": exam_line,
                "requires_solution": str(form.get(f"task_requires_solution_{index}", "")) == "1",
                "image_upload": image_upload if image_filename else None,
            }
        )

    work = DiagnosticWork(
        slug=f"custom-{secrets.token_hex(8)}",
        title=title,
        subject=subject,
        exam_type=exam_type,
        description=description,
        duration_minutes=duration_minutes,
        max_score=sum(row["max_score"] for row in task_rows),
        is_active=True,
    )
    db.add(work)
    db.flush()
    for position, row in enumerate(task_rows, start=1):
        task = DiagnosticTask(
            work_id=work.id,
            position=position,
            exam_line=row["exam_line"],
            title=row["title"],
            skill=row["skill"],
            prompt=row["prompt"],
            correct_answer=row["correct_answer"],
            solution=row["solution"],
            max_score=row["max_score"],
            requires_solution=row["requires_solution"],
            criteria=row["criteria"],
            image_path="",
        )
        db.add(task)
        db.flush()
        if row["image_upload"] is not None:
            task.image_path = save_diagnostic_task_image(task.id, row["image_upload"])
    db.commit()
    return RedirectResponse(f"/admin/diagnostics/new?created={work.id}", status_code=303)


@router.get("/diagnostic-solutions/{answer_id}")
def diagnostic_solution_file(answer_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    answer = db.get(DiagnosticAnswer, answer_id)
    if (
        answer is None
        or not answer.solution_storage_path
        or not answer.solution_filename
        or not Path(answer.solution_storage_path).exists()
    ):
        raise HTTPException(status_code=404)
    return FileResponse(
        answer.solution_storage_path,
        media_type=answer.solution_content_type or "application/octet-stream",
        filename=answer.solution_filename,
    )


@router.get("/diagnostics/{attempt_id}")
def diagnostic_review_page(
    attempt_id: int,
    request: Request,
    reviewed: int | None = None,
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    attempt = _load_diagnostic_attempt(attempt_id, db)
    if attempt is None:
        return RedirectResponse("/admin/diagnostics", status_code=303)

    answers_by_task = {answer.task_id: answer for answer in attempt.answers}
    current_score = (
        attempt.manual_score
        if attempt.manual_score is not None
        else sum(answer_score(answers_by_task.get(task.id)) for task in attempt.work.tasks)
    )
    return templates.TemplateResponse(
        request,
        "admin_diagnostic_review.html",
        {
            "request": request,
            "attempt": attempt,
            "student": attempt.student,
            "work": attempt.work,
            "tasks": attempt.work.tasks,
            "answers_by_task": answers_by_task,
            "current_score": current_score,
            "scale_band": get_scale_band(current_score, attempt.work.exam_type),
            "reviewed": reviewed == 1,
            "is_admin": True,
            "noindex": True,
            "enable_mathjax": True,
        },
    )


@router.post("/diagnostics/{attempt_id}/review")
async def review_diagnostic_attempt(
    attempt_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    attempt = _load_diagnostic_attempt(attempt_id, db)
    if attempt is None:
        return RedirectResponse("/admin/diagnostics", status_code=303)

    form = await request.form()
    answers_by_task = {answer.task_id: answer for answer in attempt.answers}
    total_score = 0
    for task in attempt.work.tasks:
        answer = answers_by_task.get(task.id)
        if answer is None:
            answer = DiagnosticAnswer(attempt_id=attempt.id, task_id=task.id)
            db.add(answer)
            answers_by_task[task.id] = answer

        raw_score = str(form.get(f"score_{task.id}", "0"))
        try:
            teacher_score = int(raw_score)
        except ValueError:
            teacher_score = 0
        teacher_score = min(max(teacher_score, 0), task.max_score)
        answer.teacher_score = teacher_score
        answer.teacher_comment = str(form.get(f"comment_{task.id}", "")).strip()
        total_score += teacher_score

    band = get_scale_band(total_score, attempt.work.exam_type)
    generated_conclusion = (
        f"{band['level']}. {band['conclusion']} "
        f"Первый фокус: {band['focus']} Ориентир: {band['target']}"
    )
    generated_parent_message = build_parent_message(
        attempt.work,
        list(attempt.work.tasks),
        answers_by_task,
        total_score,
    )
    custom_conclusion = str(form.get("conclusion", "")).strip()
    custom_parent_message = str(form.get("parent_message", "")).strip()
    attempt.status = "reviewed"
    attempt.reviewed_at = datetime.utcnow()
    attempt.manual_score = total_score
    attempt.conclusion = custom_conclusion or generated_conclusion
    attempt.parent_message = custom_parent_message or generated_parent_message
    calibrate_oge_competencies_from_attempt(db, attempt)
    db.commit()
    return RedirectResponse(f"/admin/diagnostics/{attempt.id}?reviewed=1", status_code=303)


@router.post("/leads/{lead_id}/status")
def update_lead_status(
    lead_id: int,
    request: Request,
    status: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    lead = db.get(Lead, lead_id)
    if lead:
        lead.status = status if status in LEAD_STATUSES else lead.status
        db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/leads/{lead_id}/reject")
def reject_lead(lead_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    lead = _lead_or_redirect(lead_id, db)
    if lead:
        lead.status = "rejected"
        db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/leads/{lead_id}/contacted")
def mark_lead_contacted(lead_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    lead = _lead_or_redirect(lead_id, db)
    if lead and lead.status == "new":
        lead.status = "contacted"
        db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/leads/{lead_id}/approve")
def approve_lead(lead_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    lead = _lead_or_redirect(lead_id, db)
    if lead:
        return RedirectResponse(f"/admin/students/new?lead_id={lead.id}", status_code=303)
    return RedirectResponse("/admin", status_code=303)


@router.get("/students/new")
def new_student_page(
    request: Request,
    lead_id: int | None = None,
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    prefill = {}
    if lead_id:
        lead = db.get(Lead, lead_id)
        if lead:
            prefill = {
                "lead_id": str(lead.id),
                "parent_name": lead.parent_name,
                "parent_contact": lead.contact,
                "subject": lead.subject,
                "goal": lead.goal,
            }
    return templates.TemplateResponse(
        request,
        "student_form.html",
        {
            "request": request,
            "student": None,
            "action": "/admin/students/new",
            "title": "Новый ученик",
            "submit_label": "Создать кабинет",
            "prefill": prefill,
            "student_statuses": STUDENT_STATUSES,
            "subject_options": SUBJECT_OPTIONS,
            "goal_options": GOAL_OPTIONS,
            "is_admin": True,
            "noindex": True,
        },
    )


@router.post("/students/new")
def create_student(
    request: Request,
    name: Annotated[str, Form()],
    parent_name: Annotated[str, Form()] = "",
    parent_contact: Annotated[str, Form()] = "",
    subject: Annotated[str, Form()] = "",
    goal: Annotated[str, Form()] = "",
    target_date: Annotated[str, Form()] = "",
    current_status: Annotated[str, Form()] = "",
    current_level: Annotated[str, Form()] = "",
    top_gaps: Annotated[str, Form()] = "",
    four_week_focus: Annotated[str, Form()] = "",
    planned_topics: Annotated[str, Form()] = "",
    next_checkpoint_date: Annotated[str, Form()] = "",
    next_lesson_focus: Annotated[str, Form()] = "",
    status: Annotated[str, Form()] = "active",
    lead_id: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    student = Student(
        access_code=_make_unique_access_code(db),
        name=name.strip(),
        parent_name=parent_name.strip(),
        parent_contact=parent_contact.strip(),
        subject=subject.strip(),
        goal=goal.strip(),
        target_date=_parse_date(target_date),
        current_status=current_status.strip(),
        current_level=current_level.strip(),
        top_gaps=top_gaps.strip(),
        four_week_focus=four_week_focus.strip(),
        planned_topics=planned_topics.strip(),
        next_checkpoint_date=_parse_date(next_checkpoint_date),
        next_lesson_focus=next_lesson_focus.strip(),
        status=status if status in STUDENT_STATUSES else "active",
    )
    db.add(student)
    if lead_id.strip().isdigit():
        lead = db.get(Lead, int(lead_id))
        if lead:
            lead.status = "approved"
    db.commit()
    db.refresh(student)
    ensure_oge_competency_topics(db, student)
    return RedirectResponse(f"/admin/students/{student.id}?created=1", status_code=303)


@router.get("/students/{student_id}")
def student_detail(
    student_id: int,
    request: Request,
    created: int | None = None,
    diagnostic_assigned: int | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    student_query = (
        select(Student)
        .where(Student.id == student_id)
        .options(
            selectinload(Student.topics),
            selectinload(Student.reports),
            selectinload(Student.homework_items),
            selectinload(Student.materials).selectinload(Material.lesson_report),
            selectinload(Student.checkpoints),
            selectinload(Student.diagnostic_attempts).selectinload(DiagnosticAttempt.work),
        )
    )
    student = db.scalar(student_query)
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    if ensure_oge_competency_topics(db, student):
        student = db.scalar(student_query)
    diagnostic_attempts = list(student.diagnostic_attempts)
    forecast = build_student_forecast(student, diagnostic_attempts)
    unavailable_work_ids = {
        attempt.work_id
        for attempt in diagnostic_attempts
        if attempt.status in {"assigned", "in_progress", "submitted"}
    }
    available_diagnostic_works = list(
        db.scalars(
            select(DiagnosticWork)
            .where(
                DiagnosticWork.subject == student.subject,
                DiagnosticWork.is_active.is_(True),
                DiagnosticWork.id.not_in(unavailable_work_ids),
            )
            .order_by(DiagnosticWork.exam_type.asc(), DiagnosticWork.title.asc())
        )
    )

    return templates.TemplateResponse(
        request,
        "admin_student_detail.html",
        {
            "request": request,
            "student": student,
            "topic_statuses": TOPIC_STATUSES,
            "topic_status_levels": TOPIC_STATUS_LEVELS,
            "forecast": forecast,
            "available_diagnostic_works": available_diagnostic_works,
            "student_statuses": STUDENT_STATUSES,
            "created": created == 1,
            "diagnostic_assigned": diagnostic_assigned == 1,
            "error": error,
            "today": date.today(),
            "material_kind_options": MATERIAL_KIND_OPTIONS,
            "homework_format_options": HOMEWORK_FORMAT_OPTIONS,
            "is_admin": True,
            "noindex": True,
        },
    )


@router.post("/students/{student_id}/diagnostics/assign")
def assign_diagnostic_to_student(
    student_id: int,
    request: Request,
    work_id: Annotated[int, Form()],
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    student = db.get(Student, student_id)
    work = db.scalar(
        select(DiagnosticWork).where(
            DiagnosticWork.id == work_id,
            DiagnosticWork.is_active.is_(True),
        )
    )
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    if work is None or work.subject != student.subject:
        return RedirectResponse(
            f"/admin/students/{student.id}?error=diagnostic_unavailable",
            status_code=303,
        )

    existing = db.scalar(
        select(DiagnosticAttempt.id).where(
            DiagnosticAttempt.student_id == student.id,
            DiagnosticAttempt.work_id == work.id,
            DiagnosticAttempt.status.in_(["assigned", "in_progress", "submitted"]),
        ).limit(1)
    )
    if existing is not None:
        return RedirectResponse(
            f"/admin/students/{student.id}?error=diagnostic_unavailable",
            status_code=303,
        )

    now = datetime.utcnow()
    db.add(
        DiagnosticAttempt(
            student_id=student.id,
            work_id=work.id,
            status="assigned",
            started_at=now,
            expires_at=now + timedelta(minutes=work.duration_minutes),
        )
    )
    db.commit()
    return RedirectResponse(
        f"/admin/students/{student.id}?diagnostic_assigned=1",
        status_code=303,
    )


@router.get("/students/{student_id}/edit")
def edit_student_page(student_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    student = db.get(Student, student_id)
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request,
        "student_form.html",
        {
            "request": request,
            "student": student,
            "action": f"/admin/students/{student.id}/edit",
            "title": "Редактировать кабинет",
            "submit_label": "Сохранить",
            "prefill": {},
            "student_statuses": STUDENT_STATUSES,
            "subject_options": SUBJECT_OPTIONS,
            "goal_options": GOAL_OPTIONS,
            "is_admin": True,
            "noindex": True,
        },
    )


@router.post("/students/{student_id}/edit")
def update_student(
    student_id: int,
    request: Request,
    name: Annotated[str, Form()],
    parent_name: Annotated[str, Form()] = "",
    parent_contact: Annotated[str, Form()] = "",
    subject: Annotated[str, Form()] = "",
    goal: Annotated[str, Form()] = "",
    target_date: Annotated[str, Form()] = "",
    current_status: Annotated[str, Form()] = "",
    current_level: Annotated[str, Form()] = "",
    top_gaps: Annotated[str, Form()] = "",
    four_week_focus: Annotated[str, Form()] = "",
    planned_topics: Annotated[str, Form()] = "",
    next_checkpoint_date: Annotated[str, Form()] = "",
    next_lesson_focus: Annotated[str, Form()] = "",
    status: Annotated[str, Form()] = "active",
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    student = db.get(Student, student_id)
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    student.name = name.strip()
    student.parent_name = parent_name.strip()
    student.parent_contact = parent_contact.strip()
    student.subject = subject.strip()
    student.goal = goal.strip()
    student.target_date = _parse_date(target_date)
    student.current_status = current_status.strip()
    student.current_level = current_level.strip()
    student.top_gaps = top_gaps.strip()
    student.four_week_focus = four_week_focus.strip()
    student.planned_topics = planned_topics.strip()
    student.next_checkpoint_date = _parse_date(next_checkpoint_date)
    student.next_lesson_focus = next_lesson_focus.strip()
    student.status = status if status in STUDENT_STATUSES else "active"
    db.commit()
    ensure_oge_competency_topics(db, student)
    return _redirect_to_student(student.id)


@router.post("/students/{student_id}/topics")
def add_topic(
    student_id: int,
    request: Request,
    topic: Annotated[str, Form()],
    status: Annotated[str, Form()] = "not_started",
    comment: Annotated[str, Form()] = "",
    competency_key: Annotated[str, Form()] = "",
    weight: Annotated[str, Form()] = "1",
    mastery_level: Annotated[str, Form()] = "",
    insufficient_data: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    student = _student_or_redirect(student_id, db)
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    selected_status = status if status in TOPIC_STATUSES else "not_started"
    db.add(
        TopicProgress(
            student_id=student.id,
            topic=topic.strip(),
            competency_key=competency_key.strip(),
            weight=_parse_weight(weight),
            mastery_level=_parse_mastery_level(mastery_level, selected_status),
            status=selected_status,
            comment=comment.strip(),
            insufficient_data=insufficient_data == "on",
        )
    )
    db.commit()
    return _redirect_to_student(student.id)


@router.post("/topics/{topic_id}/update")
def update_topic(
    topic_id: int,
    request: Request,
    topic: Annotated[str, Form()],
    status: Annotated[str, Form()] = "not_started",
    comment: Annotated[str, Form()] = "",
    competency_key: Annotated[str, Form()] = "",
    weight: Annotated[str, Form()] = "1",
    mastery_level: Annotated[str, Form()] = "",
    insufficient_data: Annotated[str | None, Form()] = None,
    adjustment_reason: Annotated[str, Form()] = "Ручная корректировка преподавателя",
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    item = db.get(TopicProgress, topic_id)
    if item is None:
        return RedirectResponse("/admin", status_code=303)
    selected_status = status if status in TOPIC_STATUSES else item.status
    previous_level = float(item.mastery_level or 0.0)
    new_level = _parse_mastery_level(mastery_level, selected_status)
    item.topic = topic.strip()
    item.competency_key = competency_key.strip()
    item.weight = _parse_weight(weight, item.weight)
    item.mastery_level = new_level
    item.status = selected_status
    item.comment = comment.strip()
    item.insufficient_data = insufficient_data == "on"
    if abs(new_level - previous_level) > 0.0001:
        db.add(
            CompetencyAdjustment(
                topic_id=item.id,
                previous_level=previous_level,
                new_level=new_level,
                teacher="Преподаватель",
                reason=adjustment_reason.strip() or "Ручная корректировка преподавателя",
                comment=comment.strip(),
            )
        )
    db.commit()
    return _redirect_to_student(item.student_id)


@router.post("/students/{student_id}/reports")
def add_report(
    student_id: int,
    request: Request,
    lesson_date: Annotated[str, Form()],
    lesson_topic: Annotated[str, Form()],
    covered: Annotated[str, Form()],
    worked: Annotated[str, Form()],
    weak: Annotated[str, Form()],
    homework: Annotated[str, Form()],
    parent_comment: Annotated[str, Form()],
    homework_completed: Annotated[str | None, Form()] = None,
    materials_link: Annotated[str, Form()] = "",
    homework_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    student = _student_or_redirect(student_id, db)
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    required_values = [lesson_date, lesson_topic, covered, worked, weak, homework, parent_comment]
    if any(not value.strip() for value in required_values):
        return RedirectResponse(f"/admin/students/{student.id}?error=empty_report", status_code=303)

    report = LessonReport(
        student_id=student.id,
        lesson_date=date.fromisoformat(lesson_date),
        lesson_topic=lesson_topic.strip(),
        covered=covered.strip(),
        worked=worked.strip(),
        weak=weak.strip(),
        homework=homework.strip(),
        homework_completed=homework_completed == "on",
        parent_comment=parent_comment.strip(),
        materials_link=materials_link.strip(),
    )
    db.add(report)
    homework_attachment = None
    try:
        homework_attachment = _save_homework_pdf(student.id, homework_file)
    except ValueError:
        return RedirectResponse(f"/admin/students/{student.id}?error=homework_pdf_only", status_code=303)

    if homework.strip():
        homework_item = Homework(
            student_id=student.id,
            title=f"Домашнее задание: {lesson_topic.strip()}",
            description=homework.strip(),
        )
        if homework_attachment:
            (
                homework_item.attachment_filename,
                homework_item.attachment_storage_path,
                homework_item.attachment_content_type,
            ) = homework_attachment
        db.add(
            homework_item
        )
    db.flush()
    if materials_link.strip():
        db.add(
            Material(
                student_id=student.id,
                lesson_report_id=report.id,
                title=f"{date.fromisoformat(lesson_date).strftime('%d.%m.%Y')} · {lesson_topic.strip()}",
                kind="Онлайн-доска / конспект",
                url=materials_link.strip(),
            )
        )
    db.commit()
    return _redirect_to_student(student.id)


@router.post("/students/{student_id}/homework")
def add_homework(
    student_id: int,
    request: Request,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    due_date: Annotated[str, Form()] = "",
    homework_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    student = _student_or_redirect(student_id, db)
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    homework_item = Homework(
        student_id=student.id,
        title=title.strip(),
        description=description.strip(),
        due_date=_parse_date(due_date),
    )
    try:
        homework_attachment = _save_homework_pdf(student.id, homework_file)
    except ValueError:
        return RedirectResponse(f"/admin/students/{student.id}?error=homework_pdf_only", status_code=303)
    if homework_attachment:
        (
            homework_item.attachment_filename,
            homework_item.attachment_storage_path,
            homework_item.attachment_content_type,
        ) = homework_attachment
    db.add(homework_item)
    db.commit()
    return _redirect_to_student(student.id)


@router.post("/homework/{homework_id}/edit")
def edit_homework(
    homework_id: int,
    request: Request,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    due_date: Annotated[str, Form()] = "",
    is_completed: Annotated[str | None, Form()] = None,
    homework_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    item = db.get(Homework, homework_id)
    if item is None:
        return RedirectResponse("/admin", status_code=303)
    item.title = title.strip()
    item.description = description.strip()
    item.due_date = _parse_date(due_date)
    item.is_completed = is_completed == "on"
    item.completed_at = datetime.utcnow() if item.is_completed else None
    try:
        homework_attachment = _save_homework_pdf(item.student_id, homework_file)
    except ValueError:
        return RedirectResponse(f"/admin/students/{item.student_id}?error=homework_pdf_only", status_code=303)
    if homework_attachment:
        (
            item.attachment_filename,
            item.attachment_storage_path,
            item.attachment_content_type,
        ) = homework_attachment
    db.commit()
    return _redirect_to_student(item.student_id)


@router.get("/homework/{homework_id}/solution")
def homework_solution_file(homework_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    item = db.get(Homework, homework_id)
    if (
        item is None
        or not item.solution_storage_path
        or not item.solution_filename
        or not Path(item.solution_storage_path).exists()
    ):
        raise HTTPException(status_code=404)
    return FileResponse(
        item.solution_storage_path,
        media_type=item.solution_content_type or "application/pdf",
        filename=item.solution_filename,
    )


@router.post("/homework/{homework_id}/toggle")
def toggle_homework(homework_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    item = db.get(Homework, homework_id)
    if item is None:
        return RedirectResponse("/admin", status_code=303)
    item.is_completed = not item.is_completed
    item.completed_at = datetime.utcnow() if item.is_completed else None
    db.commit()
    return _redirect_to_student(item.student_id)


@router.post("/students/{student_id}/materials")
def add_material(
    student_id: int,
    request: Request,
    title: Annotated[str, Form()],
    url: Annotated[str, Form()],
    kind: Annotated[str, Form()] = "Ссылка",
    material_date: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    student = _student_or_redirect(student_id, db)
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    display_title = title.strip()
    if material_date:
        display_title = f"{date.fromisoformat(material_date).strftime('%d.%m.%Y')} · {display_title}"
    db.add(
        Material(
            student_id=student.id,
            title=display_title,
            kind=kind.strip() or "Ссылка",
            url=url.strip(),
        )
    )
    db.commit()
    return _redirect_to_student(student.id)


@router.post("/students/{student_id}/checkpoints")
def add_checkpoint(
    student_id: int,
    request: Request,
    checkpoint_date: Annotated[str, Form()],
    before: Annotated[str, Form()],
    after: Annotated[str, Form()],
    improved: Annotated[str, Form()],
    blockers: Annotated[str, Form()],
    next_month_plan: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    student = _student_or_redirect(student_id, db)
    if student is None:
        return RedirectResponse("/admin", status_code=303)
    db.add(
        Checkpoint(
            student_id=student.id,
            checkpoint_date=date.fromisoformat(checkpoint_date),
            before=before.strip(),
            after=after.strip(),
            improved=improved.strip(),
            blockers=blockers.strip(),
            next_month_plan=next_month_plan.strip(),
        )
    )
    db.commit()
    return _redirect_to_student(student.id)
