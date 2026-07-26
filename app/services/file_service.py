"""
OroGest Lex — File Upload Service
Local filesystem storage with S3 upgrade path.

Files stored at: UPLOAD_DIR/{user_id}/{year}/{month}/{filename}
Each file gets a SHA-256 hash for integrity verification.
"""

import asyncio
import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

logger = logging.getLogger("orogest.file_service")
settings = get_settings()

UPLOAD_DIR = Path("/data/orogest/uploads")  # Override via env in production
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".csv",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".txt",
    ".md",
    ".odt",
}


class FileUploadError(Exception):
    pass


def _validate_file(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> str:
    """Validate file extension and size. Returns the extension."""
    if not file.filename:
        raise FileUploadError("Archivo sin nombre")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileUploadError(
            f"Extensión no permitida: {ext}. Permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    return ext


def _compute_file_hash(content: bytes) -> str:
    """SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def _sanitize_filename(filename: str) -> str:
    """
    Strip directory components and traversal/control characters from a
    client-supplied filename before it is used to build a filesystem path.

    UploadFile.filename comes straight from the multipart request and is
    fully attacker-controlled (e.g. "../../../../etc/cron.d/evil" or
    "..\\..\\evil.txt"). Without this, _build_storage_path would embed it
    directly into a path joined onto UPLOAD_DIR, allowing writes (and later
    reads via get_file_full_path) outside the upload directory.
    """
    name = Path(filename).name  # drop any POSIX directory components
    name = name.replace("\x00", "")  # strip null bytes
    name = re.sub(r"[/\\]", "_", name)  # neutralize any remaining separators
    name = name.lstrip(".")  # avoid ".", ".." or hidden-dotfile reconstruction
    return name or "file"


def _build_storage_path(
    user_id: uuid.UUID,
    filename: str,
    ext: str,
) -> Path:
    """Build organized storage path: user_id/year/month/uuid_filename."""
    now = datetime.now(UTC)
    safe_filename = _sanitize_filename(filename)
    unique_name = f"{uuid.uuid4().hex[:12]}_{safe_filename}"
    return UPLOAD_DIR / str(user_id) / str(now.year) / f"{now.month:02d}" / unique_name


async def save_uploaded_file(
    file: UploadFile,
    user_id: uuid.UUID,
    max_size: int = MAX_FILE_SIZE,
) -> dict:
    """
    Save an uploaded file to local storage.

    Returns:
        {
            "file_path": str,      # relative path for DB storage
            "file_hash": str,      # SHA-256
            "file_size": int,      # bytes
            "file_name": str,      # original name
            "mime_type": str,      # content type
        }
    """
    ext = _validate_file(file, max_size)

    content = await file.read()
    if len(content) > max_size:
        raise FileUploadError(f"Archivo excede el límite de {max_size // (1024 * 1024)} MB")
    if len(content) == 0:
        raise FileUploadError("Archivo vacío")

    file_hash = _compute_file_hash(content)
    storage_path = _build_storage_path(user_id, file.filename or "unnamed", ext)

    # Create directories
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file (off the event loop — this is a sync/blocking disk write)
    await asyncio.to_thread(storage_path.write_bytes, content)

    # Return relative path (strip UPLOAD_DIR prefix for portability)
    relative_path = str(storage_path.relative_to(UPLOAD_DIR))

    return {
        "file_path": relative_path,
        "file_hash": file_hash,
        "file_size": len(content),
        "file_name": file.filename,
        "mime_type": file.content_type or "application/octet-stream",
    }


def get_file_full_path(relative_path: str) -> Path:
    """Get the full filesystem path from a relative DB path."""
    upload_root = UPLOAD_DIR.resolve()
    full = (UPLOAD_DIR / relative_path).resolve()
    # Defense in depth: refuse to serve anything that resolves outside
    # UPLOAD_DIR, even if a stored relative_path somehow contains "..".
    if full != upload_root and upload_root not in full.parents:
        raise FileNotFoundError(f"Archivo no encontrado: {relative_path}")
    if not full.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {relative_path}")
    return full


def delete_file(relative_path: str) -> bool:
    """Delete a file from storage. Returns True if deleted."""
    try:
        full = UPLOAD_DIR / relative_path
        if full.exists():
            full.unlink()
            return True
    except Exception as e:  # noqa: BLE001 — best-effort disk cleanup, must not raise into the caller
        logger.warning(f"delete_file failed for {relative_path}: {e}")
    return False
