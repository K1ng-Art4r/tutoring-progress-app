from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.config import settings
from app.database import SessionLocal, init_database
from app.diagnostics_data import seed_diagnostic_works
from app.routers import admin, cabinet, public
from app.seed import seed_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    with SessionLocal() as db:
        seed_diagnostic_works(db)
        if settings.seed_demo_data:
            seed_demo_data(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(public.router)
app.include_router(cabinet.router)
app.include_router(admin.router)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.middleware("http")
async def add_private_indexing_headers(request: Request, call_next):
    response: Response = await call_next(request)
    if request.url.path.startswith(("/admin", "/cabinet")):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
