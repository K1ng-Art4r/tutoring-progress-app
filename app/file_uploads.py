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
