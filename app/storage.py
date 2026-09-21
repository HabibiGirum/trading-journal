from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from .config import get_settings
from .models import FileAsset

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
PDF_SUFFIXES = {".pdf"}


class UploadError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def uploads_dir() -> Path:
    path = Path(get_settings().upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UploadError(f"File is too large. Max {max_bytes // (1024 * 1024)} MB.")
    if not data:
        raise UploadError("Empty file.")
    return data


def save_upload(upload: UploadFile, user_id: int, kind: str, db: Session) -> str:
    if not upload.filename:
        raise UploadError("Choose a file.")
    suffix = Path(upload.filename).suffix.lower()
    settings = get_settings()
    if kind == "image":
        if suffix not in IMAGE_SUFFIXES:
            raise UploadError("Images must be PNG, JPG, JPEG, or WEBP.")
        payload = _read_limited(upload, settings.max_image_mb * 1024 * 1024)
    elif kind == "pdf":
        if suffix not in PDF_SUFFIXES:
            raise UploadError("Only PDF files are allowed.")
        payload = _read_limited(upload, settings.max_pdf_mb * 1024 * 1024)
        if not payload.startswith(b"%PDF"):
            raise UploadError("That file does not look like a PDF.")
    else:
        raise UploadError("Unsupported file type.")

    filename = f"{uuid4().hex}{suffix}"
    destination = uploads_dir() / filename
    destination.write_bytes(payload)
    db.add(FileAsset(user_id=user_id, filename=filename, kind=kind))
    return filename


def delete_file(filename: str | None) -> None:
    if not filename:
        return
    path = uploads_dir() / filename
    if path.exists() and path.is_file():
        path.unlink()
