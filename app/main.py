from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.responses import FileResponse, Response

from app.config import settings
from app.database import SessionLocal, init_database
from app.diagnostics_data import seed_diagnostic_works
from app.models import Student
from app.progress_forecast import ensure_oge_competency_topics
from app.routers import admin, cabinet, public
from app.seed import seed_demo_data
from app.seed_ege_base import seed_ege_base_demo_data
from app.seed_ege_profile import seed_ege_profile_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    with SessionLocal() as db:
        seed_diagnostic_works(db)
        for student in db.scalars(select(Student)).all():
            ensure_oge_competency_topics(db, student, commit=False)
        db.commit()
        if settings.seed_demo_data:
            seed_demo_data(db)
            seed_ege_base_demo_data(db)
            seed_ege_profile_demo_data(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(public.router)
app.include_router(cabinet.router)
app.include_router(admin.router)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse("app/static/favicon.png", media_type="image/png")


@app.middleware("http")
async def add_private_indexing_headers(request: Request, call_next):
    response: Response = await call_next(request)
    if request.url.path.startswith(("/admin", "/cabinet")):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
