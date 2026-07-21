from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.auth import (
    attach_login_cookie,
    attach_student_login_cookie,
    clear_student_login_cookie,
    student_access_token_from_cookie,
)
from app.config import settings
from app.database import get_db
from app.demo import DEMO_ACCESS_TOKEN
from app.diagnostic_logic import finalize_attempt, score_answer
from app.file_uploads import save_diagnostic_solution_upload, save_pdf_upload
from app.models import (
    DiagnosticAnswer,
    DiagnosticAttempt,
    DiagnosticTask,
    DiagnosticWork,
    Homework,
    Material,
    Student,
)
from app.progress_forecast import build_student_forecast, ensure_oge_competency_topics
from app.seed import seed_demo_data
from app.view_helpers import templates

router = APIRouter(prefix="/cabinet")


def _student_by_token(access_token: str, db: Session) -> Student | None:
    return db.scalar(
        select(Student).where(Student.access_token == access_token, Student.status != "archived")
    )


def _normalize_login(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _student_login_matches(student: Student, login_name: str) -> bool:
    normalized_login = _normalize_login(login_name)
    normalized_student_name = _normalize_login(student.name)
    first_name = normalized_student_name.split(" ", 1)[0]
    return normalized_login in {normalized_student_name, first_name}


def _remaining_seconds(attempt: DiagnosticAttempt) -> int:
    return max(0, int((attempt.expires_at - datetime.utcnow()).total_seconds()))


def _load_attempt(attempt_id: int, student_id: int, db: Session) -> DiagnosticAttempt | None:
    return db.scalar(
        select(DiagnosticAttempt)
        .where(DiagnosticAttempt.id == attempt_id, DiagnosticAttempt.student_id == student_id)
        .options(
            selectinload(DiagnosticAttempt.work).selectinload(DiagnosticWork.tasks),
            selectinload(DiagnosticAttempt.answers).selectinload(DiagnosticAnswer.task),
        )
    )


def _latest_attempt(student_id: int, work_id: int, db: Session) -> DiagnosticAttempt | None:
    return db.scalar(
        select(DiagnosticAttempt)
        .where(DiagnosticAttempt.student_id == student_id, DiagnosticAttempt.work_id == work_id)
        .options(
            selectinload(DiagnosticAttempt.work).selectinload(DiagnosticWork.tasks),
            selectinload(DiagnosticAttempt.answers).selectinload(DiagnosticAnswer.task),
        )
        .order_by(desc(DiagnosticAttempt.created_at))
        .limit(1)
    )


def _active_work_for_student(student: Student, work_slug: str, db: Session) -> DiagnosticWork | None:
    return db.scalar(
        select(DiagnosticWork)
        .where(
            DiagnosticWork.slug == work_slug,
            DiagnosticWork.subject == student.subject,
            DiagnosticWork.is_active.is_(True),
        )
        .options(selectinload(DiagnosticWork.tasks))
    )


def _finish_expired_attempt(attempt: DiagnosticAttempt) -> bool:
    if attempt.status == "in_progress" and _remaining_seconds(attempt) <= 0:
        finalize_attempt(attempt)
        return True
    return False


def _first_unsaved_task_position(
    tasks: list[DiagnosticTask],
    answers_by_task: dict[int, DiagnosticAnswer],
    fallback_position: int,
) -> int:
    for task in tasks:
        answer = answers_by_task.get(task.id)
        if answer is None or not answer.answer_text.strip():
            return task.position
    return fallback_position


@router.get("/login", response_class=HTMLResponse)
def cabinet_login_page(
    request: Request,
    error: int | None = None,
    db: Session = Depends(get_db),
):
    if not error:
        saved_access_token = student_access_token_from_cookie(request)
        if saved_access_token:
            student = _student_by_token(saved_access_token, db)
            if student is not None:
                return RedirectResponse(f"/cabinet/{student.access_token}", status_code=303)

    return templates.TemplateResponse(
        request,
        "cabinet_login.html",
        {
            "request": request,
            "error": error == 1,
            "is_admin": False,
            "noindex": True,
        },
    )


@router.post("/login")
def cabinet_login(
    username: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db),
):
    login_name = username.strip()
    if login_name == settings.teacher_login:
        if code != settings.teacher_password:
            return RedirectResponse("/cabinet/login?error=1", status_code=303)
        response = RedirectResponse("/admin", status_code=303)
        attach_login_cookie(response)
        return response

    normalized_code = "".join(char for char in code.strip() if char.isdigit())
    if len(normalized_code) != 10:
        return RedirectResponse("/cabinet/login?error=1", status_code=303)
    student = db.scalar(
        select(Student).where(
            Student.access_code == normalized_code,
            Student.status != "archived",
        )
    )
    if student is None or not _student_login_matches(student, login_name):
        return RedirectResponse("/cabinet/login?error=1", status_code=303)
    response = RedirectResponse(f"/cabinet/{student.access_token}", status_code=303)
    attach_student_login_cookie(response, student.access_token)
    return response


@router.post("/logout")
def cabinet_logout():
    response = RedirectResponse("/cabinet/login", status_code=303)
    clear_student_login_cookie(response)
    return response


@router.get("/{access_token}", response_class=HTMLResponse)
def student_cabinet(
    access_token: str,
    request: Request,
    uploaded: int | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    student_query = (
        select(Student)
        .where(Student.access_token == access_token, Student.status != "archived")
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
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {"request": request, "is_admin": False, "noindex": True},
            status_code=404,
        )
    if access_token == DEMO_ACCESS_TOKEN:
        seed_demo_data(db)
        student = db.scalar(student_query)
    if ensure_oge_competency_topics(db, student):
        student = db.scalar(student_query)

    current_homework = [item for item in student.homework_items if not item.is_completed]
    completed_homework = [item for item in student.homework_items if item.is_completed]
    latest_report = student.reports[0] if student.reports else None
    diagnostic_works = list(
        db.scalars(
            select(DiagnosticWork)
            .where(DiagnosticWork.subject == student.subject, DiagnosticWork.is_active.is_(True))
            .options(selectinload(DiagnosticWork.tasks))
            .order_by(DiagnosticWork.created_at.asc())
        )
    )
    diagnostic_attempts = list(
        db.scalars(
            select(DiagnosticAttempt)
            .where(DiagnosticAttempt.student_id == student.id)
            .options(selectinload(DiagnosticAttempt.work))
            .order_by(desc(DiagnosticAttempt.created_at))
        )
    )
    latest_diagnostic_attempts = {}
    for attempt in diagnostic_attempts:
        latest_diagnostic_attempts.setdefault(attempt.work_id, attempt)
    forecast = build_student_forecast(student, diagnostic_attempts)

    response = templates.TemplateResponse(
        request,
        "cabinet.html",
        {
            "request": request,
            "student": student,
            "current_homework": current_homework,
            "completed_homework": completed_homework,
            "latest_report": latest_report,
            "diagnostic_works": diagnostic_works,
            "latest_diagnostic_attempts": latest_diagnostic_attempts,
            "forecast": forecast,
            "uploaded": uploaded == 1,
            "error": error,
            "is_admin": False,
            "noindex": True,
        },
    )
    attach_student_login_cookie(response, student.access_token)
    return response


@router.get("/{access_token}/homework/{homework_id}/file")
def homework_file(access_token: str, homework_id: int, db: Session = Depends(get_db)):
    student = db.scalar(
        select(Student).where(Student.access_token == access_token, Student.status != "archived")
    )
    if student is None:
        raise HTTPException(status_code=404)
    homework = db.scalar(
        select(Homework).where(Homework.id == homework_id, Homework.student_id == student.id)
    )
    if homework is None or not homework.attachment_storage_path or not homework.attachment_filename:
        raise HTTPException(status_code=404)
    return FileResponse(
        homework.attachment_storage_path,
        media_type=homework.attachment_content_type or "application/pdf",
        filename=homework.attachment_filename,
    )


@router.post("/{access_token}/homework/{homework_id}/solution")
def upload_homework_solution(
    access_token: str,
    homework_id: int,
    solution_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    student = db.scalar(
        select(Student).where(Student.access_token == access_token, Student.status != "archived")
    )
    if student is None:
        raise HTTPException(status_code=404)
    homework = db.scalar(
        select(Homework).where(Homework.id == homework_id, Homework.student_id == student.id)
    )
    if homework is None:
        raise HTTPException(status_code=404)
    try:
        solution_attachment = save_pdf_upload(
            student.id,
            solution_file,
            "homework_solutions",
            "solution_pdf_only",
        )
    except ValueError:
        return RedirectResponse(f"/cabinet/{access_token}?error=solution_pdf_only", status_code=303)
    if not solution_attachment:
        return RedirectResponse(f"/cabinet/{access_token}?error=solution_pdf_only", status_code=303)
    (
        homework.solution_filename,
        homework.solution_storage_path,
        homework.solution_content_type,
    ) = solution_attachment
    db.commit()
    return RedirectResponse(f"/cabinet/{access_token}?uploaded=1", status_code=303)


@router.get("/{access_token}/diagnostics/{work_slug}", response_class=HTMLResponse)
def diagnostic_work_page(
    access_token: str,
    work_slug: str,
    request: Request,
    saved_task: int | None = None,
    active_task: int | None = None,
    finished: int | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    student = _student_by_token(access_token, db)
    if student is None:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {"request": request, "is_admin": False, "noindex": True},
            status_code=404,
        )

    work = _active_work_for_student(student, work_slug, db)
    if work is None:
        raise HTTPException(status_code=404)

    attempt = _latest_attempt(student.id, work.id, db)
    if attempt is None:
        response = templates.TemplateResponse(
            request,
            "diagnostic_intro.html",
            {
                "request": request,
                "student": student,
                "work": work,
                "tasks": work.tasks,
                "is_admin": False,
                "noindex": True,
                "enable_mathjax": True,
            },
        )
        attach_student_login_cookie(response, student.access_token)
        return response

    if _finish_expired_attempt(attempt):
        db.commit()
        finished = 1

    if attempt.status != "in_progress":
        answers_by_task = {answer.task_id: answer for answer in attempt.answers}
        response = templates.TemplateResponse(
            request,
            "diagnostic_complete.html",
            {
                "request": request,
                "student": student,
                "work": attempt.work,
                "attempt": attempt,
                "tasks": attempt.work.tasks,
                "answers_by_task": answers_by_task,
                "finished": finished == 1,
                "is_admin": False,
                "noindex": True,
                "enable_mathjax": True,
            },
        )
        attach_student_login_cookie(response, student.access_token)
        return response

    answers_by_task = {answer.task_id: answer for answer in attempt.answers}
    response = templates.TemplateResponse(
        request,
        "diagnostic_work.html",
        {
            "request": request,
            "student": student,
            "work": work,
            "attempt": attempt,
            "tasks": work.tasks,
            "answers_by_task": answers_by_task,
            "remaining_seconds": _remaining_seconds(attempt),
            "saved_task": saved_task,
            "active_task": active_task,
            "error": error,
            "is_admin": False,
            "noindex": True,
            "enable_mathjax": True,
        },
    )
    attach_student_login_cookie(response, student.access_token)
    return response


@router.post("/{access_token}/diagnostics/{work_slug}/start")
def start_diagnostic_work(
    access_token: str,
    work_slug: str,
    db: Session = Depends(get_db),
):
    student = _student_by_token(access_token, db)
    if student is None:
        raise HTTPException(status_code=404)

    work = _active_work_for_student(student, work_slug, db)
    if work is None:
        raise HTTPException(status_code=404)

    attempt = _latest_attempt(student.id, work.id, db)
    if attempt is not None:
        if _finish_expired_attempt(attempt):
            db.commit()
        return RedirectResponse(
            f"/cabinet/{access_token}/diagnostics/{work.slug}",
            status_code=303,
        )

    now = datetime.utcnow()
    attempt = DiagnosticAttempt(
        student_id=student.id,
        work_id=work.id,
        started_at=now,
        expires_at=now + timedelta(minutes=work.duration_minutes),
        status="in_progress",
    )
    db.add(attempt)
    db.commit()
    return RedirectResponse(
        f"/cabinet/{access_token}/diagnostics/{work.slug}",
        status_code=303,
    )


@router.post("/{access_token}/diagnostics/attempts/{attempt_id}/answers/{task_id}")
def save_diagnostic_answer(
    access_token: str,
    attempt_id: int,
    task_id: int,
    answer_text: str = Form(""),
    solution_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    student = _student_by_token(access_token, db)
    if student is None:
        raise HTTPException(status_code=404)

    attempt = _load_attempt(attempt_id, student.id, db)
    if attempt is None:
        raise HTTPException(status_code=404)
    if attempt.status != "in_progress":
        return RedirectResponse(
            f"/cabinet/{access_token}/diagnostics/{attempt.work.slug}", status_code=303
        )
    if _finish_expired_attempt(attempt):
        db.commit()
        return RedirectResponse(
            f"/cabinet/{access_token}/diagnostics/{attempt.work.slug}?finished=1", status_code=303
        )

    task = db.scalar(
        select(DiagnosticTask).where(
            DiagnosticTask.id == task_id,
            DiagnosticTask.work_id == attempt.work_id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404)

    answer = db.scalar(
        select(DiagnosticAnswer).where(
            DiagnosticAnswer.attempt_id == attempt.id,
            DiagnosticAnswer.task_id == task.id,
        )
    )
    if answer is None:
        answer = DiagnosticAnswer(attempt_id=attempt.id, task_id=task.id)
        db.add(answer)

    answer.answer_text = answer_text.strip()
    answer.is_correct, answer.auto_score = score_answer(task, answer.answer_text)

    try:
        solution_attachment = save_diagnostic_solution_upload(
            student.id,
            attempt.id,
            solution_file,
        )
    except ValueError:
        return RedirectResponse(
            f"/cabinet/{access_token}/diagnostics/{attempt.work.slug}"
            f"?saved_task={task.position}&active_task={task.position}&error=diagnostic_solution_file_type",
            status_code=303,
        )
    if solution_attachment:
        (
            answer.solution_filename,
            answer.solution_storage_path,
            answer.solution_content_type,
        ) = solution_attachment

    answers_by_task = {item.task_id: item for item in attempt.answers}
    answers_by_task[task.id] = answer
    active_task_position = _first_unsaved_task_position(
        list(attempt.work.tasks),
        answers_by_task,
        task.position,
    )
    db.commit()
    return RedirectResponse(
        f"/cabinet/{access_token}/diagnostics/{attempt.work.slug}"
        f"?saved_task={task.position}&active_task={active_task_position}",
        status_code=303,
    )


@router.post("/{access_token}/diagnostics/attempts/{attempt_id}/finish")
def finish_diagnostic_attempt(
    access_token: str,
    attempt_id: int,
    db: Session = Depends(get_db),
):
    student = _student_by_token(access_token, db)
    if student is None:
        raise HTTPException(status_code=404)

    attempt = _load_attempt(attempt_id, student.id, db)
    if attempt is None:
        raise HTTPException(status_code=404)
    finalize_attempt(attempt)
    db.commit()
    return RedirectResponse(
        f"/cabinet/{access_token}/diagnostics/{attempt.work.slug}?finished=1",
        status_code=303,
    )
