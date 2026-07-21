from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import attach_student_login_cookie
from app.database import get_db
from app.models import Lead
from app.notifications import notify_new_lead
from app.options import CLASS_OPTIONS, GOAL_OPTIONS, SUBJECT_OPTIONS
from app.seed import seed_demo_data
from app.view_helpers import templates

router = APIRouter()


@router.get("/")
def landing(request: Request, sent: int | None = None):
    return templates.TemplateResponse(
        request,
        "public.html",
        {
            "request": request,
            "sent": sent == 1,
            "class_options": CLASS_OPTIONS,
            "subject_options": SUBJECT_OPTIONS,
            "goal_options": GOAL_OPTIONS,
            "is_admin": False,
            "noindex": False,
        },
    )


@router.get("/demo")
def demo_cabinet(db: Session = Depends(get_db)):
    student = seed_demo_data(db)
    response = RedirectResponse(f"/cabinet/{student.access_token}", status_code=303)
    attach_student_login_cookie(response, student.access_token)
    return response


@router.get("/about")
def about_teacher(request: Request):
    return templates.TemplateResponse(
        request,
        "about.html",
        {
            "request": request,
            "is_admin": False,
            "noindex": False,
        },
    )


@router.get("/format")
def format_page(request: Request):
    return templates.TemplateResponse(
        request,
        "format.html",
        {
            "request": request,
            "is_admin": False,
            "noindex": False,
        },
    )


@router.get("/methodology")
def methodology_page(request: Request):
    return format_page(request)


@router.get("/pricing")
def pricing(request: Request):
    return templates.TemplateResponse(
        request,
        "pricing.html",
        {
            "request": request,
            "is_admin": False,
            "noindex": False,
        },
    )


@router.post("/request")
def create_request(
    parent_name: str = Form(...),
    student_class: str = Form(...),
    subject: str = Form(...),
    goal: str = Form(...),
    goal_details: str = Form(""),
    contact: str = Form(...),
    db: Session = Depends(get_db),
):
    full_goal = goal.strip()
    if goal_details.strip():
        full_goal = f"{full_goal}. Детали: {goal_details.strip()}"
    lead = Lead(
        parent_name=parent_name.strip(),
        student_class=student_class.strip(),
        subject=subject.strip(),
        goal=full_goal,
        contact=contact.strip(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    notify_new_lead(lead)
    return RedirectResponse("/?sent=1#contact", status_code=303)


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return "User-agent: *\nDisallow: /admin\nDisallow: /cabinet\n"
