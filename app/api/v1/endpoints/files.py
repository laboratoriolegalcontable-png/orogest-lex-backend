"""
OroGest Lex — File Upload Endpoints
Upload, download, and manage file attachments.
"""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission, get_current_user
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import Document, User
from app.services.audit_service import create_audit_entry
from app.services.file_service import (
    FileUploadError,
    delete_file,
    get_file_full_path,
    save_uploaded_file,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    case_id: str | None = None,
    doc_type: str = "otro",
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_WRITE)),
):
    """
    Upload a file and optionally associate it with a case.
    Creates a Document record pointing to the file.
    Max size: 50 MB.
    """
    try:
        file_info = await save_uploaded_file(file, user.id)
    except FileUploadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create Document record
    case_uuid = uuid.UUID(case_id) if case_id else None

    doc = Document(
        title=file_info["file_name"],
        doc_type=doc_type,
        file_path=file_info["file_path"],
        file_hash=file_info["file_hash"],
        created_by=user.id,
        case_id=case_uuid,
        version=1,
    )
    db.add(doc)
    await db.flush()

    if request:
        await create_audit_entry(
            db, action="file.upload", user_id=user.id,
            resource_type="document", resource_id=str(doc.id),
            details={
                "filename": file_info["file_name"],
                "size_bytes": file_info["file_size"],
                "mime": file_info["mime_type"],
            },
            ip_address=request.client.host if request.client else None,
        )

    return {
        "document_id": str(doc.id),
        "filename": file_info["file_name"],
        "size_bytes": file_info["file_size"],
        "file_hash": file_info["file_hash"],
        "mime_type": file_info["mime_type"],
    }


@router.get("/download/{document_id}")
async def download_file(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_READ)),
):
    """Download a file by its Document ID."""
    doc = await db.get(Document, document_id)
    if not doc or doc.is_deleted or not doc.file_path:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    try:
        full_path = get_file_full_path(doc.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en storage")

    return FileResponse(
        path=str(full_path),
        filename=doc.title,
        media_type="application/octet-stream",
    )
