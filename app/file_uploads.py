from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings


def save_pdf_upload(
    student_id: int,
    upload: UploadFile | None,
    folder: str,
    error_code: str,
) -> tuple[str, str, str] | None:
    if upload is None or not upload.filename:
        return None

    filename = Path(upload.filename).name
    if not filename.lower().endswith(".pdf"):
        raise ValueError(error_code)

    student_dir = settings.upload_dir / folder / str(student_id)
    student_dir.mkdir(parents=True, exist_ok=True)
    storage_path = student_dir / f"{uuid.uuid4().hex}.pdf"
    with storage_path.open("wb") as destination:
        shutil.copyfileobj(upload.file, destination)
    return filename, str(storage_path), upload.content_type or "application/pdf"


def save_diagnostic_solution_upload(
    student_id: int,
    attempt_id: int,
    upload: UploadFile | None,
) -> tuple[str, str, str] | None:
    if upload is None or not upload.filename:
        return None

    filename = Path(upload.filename).name
    suffix = Path(filename).suffix.lower()
    allowed_suffixes = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }
    if suffix not in allowed_suffixes:
        raise ValueError("diagnostic_solution_file_type")

    student_dir = settings.upload_dir / "diagnostic_solutions" / str(student_id) / str(attempt_id)
    student_dir.mkdir(parents=True, exist_ok=True)
    storage_path = student_dir / f"{uuid.uuid4().hex}{suffix}"
    with storage_path.open("wb") as destination:
        shutil.copyfileobj(upload.file, destination)
    return filename, str(storage_path), upload.content_type or allowed_suffixes[suffix]


def save_diagnostic_task_image(task_id: int, upload: UploadFile | None) -> str:
    if upload is None or not upload.filename:
        return ""

    filename = Path(upload.filename).name
    suffix = Path(filename).suffix.lower()
    allowed_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    if suffix not in allowed_suffixes:
        raise ValueError("diagnostic_task_image_type")

    task_dir = settings.upload_dir / "diagnostic_task_images" / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    storage_path = task_dir / f"{uuid.uuid4().hex}{suffix}"
    with storage_path.open("wb") as destination:
        shutil.copyfileobj(upload.file, destination)
    return f"/diagnostic-task-images/{task_id}"
