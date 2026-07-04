from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.file_uploads import save_pdf_upload
from app.models import Homework, Material, Student
from app.view_helpers import templates

router = APIRouter(prefix="/cabinet")


@router.get("/login", response_class=HTMLResponse)
def cabinet_login_page(request: Request, error: int | None = None):
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
def cabinet_login(code: str = Form(...), db: Session = Depends(get_db)):
    normalized_code = "".join(char for char in code.strip() if char.isdigit())
    if len(normalized_code) != 10:
        return RedirectResponse("/cabinet/login?error=1", status_code=303)
    student = db.scalar(
        select(Student).where(
            Student.access_code == normalized_code,
            Student.status != "archived",
        )
    )
    if student is None:
        return RedirectResponse("/cabinet/login?error=1", status_code=303)
    return RedirectResponse(f"/cabinet/{student.access_token}", status_code=303)


@router.get("/{access_token}", response_class=HTMLResponse)
def student_cabinet(
    access_token: str,
    request: Request,
    uploaded: int | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    student = db.scalar(
        select(Student)
        .where(Student.access_token == access_token, Student.status != "archived")
        .options(
            selectinload(Student.topics),
            selectinload(Student.reports),
            selectinload(Student.homework_items),
            selectinload(Student.materials).selectinload(Material.lesson_report),
            selectinload(Student.checkpoints),
        )
    )
    if student is None:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {"request": request, "is_admin": False, "noindex": True},
            status_code=404,
        )

    current_homework = [item for item in student.homework_items if not item.is_completed]
    completed_homework = [item for item in student.homework_items if item.is_completed]
    latest_report = student.reports[0] if student.reports else None

    return templates.TemplateResponse(
        request,
        "cabinet.html",
        {
            "request": request,
            "student": student,
            "current_homework": current_homework,
            "completed_homework": completed_homework,
            "latest_report": latest_report,
            "uploaded": uploaded == 1,
            "error": error,
            "is_admin": False,
            "noindex": True,
        },
    )


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
