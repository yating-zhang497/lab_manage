"""行内附件管理：为 projects/people/ip/awards 四类实体上传、列表、下载、删除 PDF。

与论文 PDF 库（routers/pdfs.py）隔离：论文附件用 paper_id + entity_type IS NULL；
本路由的附件用 entity_type/entity_id。pdfs.py 列表查询已加 entity_type.is_(None) 守卫，
互不干扰。
"""

import hashlib
import io
import mimetypes
import re
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import Attachment, AwardRecord, IntellectualProperty, Person, Project
from ..schemas import (
    AttachmentOut,
    BatchByIdsIn,
    BatchByRecordsIn,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])

# 实体白名单：entity -> (模型, 主名称字段, 备选名称字段)。用于校验记录存在 + zip 文件夹命名。
ENTITY_REGISTRY = {
    "projects": (Project, "name", "project_no"),
    "people": (Person, "name", "uid"),
    "ip": (IntellectualProperty, "title", None),
    "awards": (AwardRecord, "award_name", None),
}

# 行内附件允许的文件类型：PDF / Word / Excel / 常见图片
ALLOWED_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
}

# 扩展名 -> att_type 桶（用于归档分类；论文 PDF 库仍固定 "pdf"，此处只影响行内附件）
_EXT_ATT_TYPE = {
    ".pdf": "pdf",
    ".doc": "word", ".docx": "word",
    ".xls": "excel", ".xlsx": "excel",
    ".jpg": "image", ".jpeg": "image", ".png": "image",
    ".gif": "image", ".bmp": "image", ".webp": "image", ".svg": "image",
}

# 显式 content-type 表（mimetypes 在精简系统上可能不识别 .docx/.svg 等）
_EXPLICIT_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".bmp": "image/bmp", ".webp": "image/webp", ".svg": "image/svg+xml",
}


def _att_type(filename: str) -> str:
    return _EXT_ATT_TYPE.get(Path(filename or "").suffix.lower(), "other")


def _content_type(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in _EXPLICIT_TYPES:
        return _EXPLICIT_TYPES[ext]
    return mimetypes.guess_type(filename or "")[0] or "application/octet-stream"


# ─── Helpers ────────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_entity(entity: str):
    if entity not in ENTITY_REGISTRY:
        raise HTTPException(status_code=400, detail="不支持的实体类型")
    return ENTITY_REGISTRY[entity]


def _record_name(db: Session, entity: str, entity_id: int) -> str:
    """取记录名做 zip 内文件夹名；取不到就用 id。"""
    model, name_attr, fallback_attr = ENTITY_REGISTRY[entity]
    rec = db.get(model, entity_id)
    if not rec:
        return str(entity_id)
    name = getattr(rec, name_attr, None) or (
        getattr(rec, fallback_attr, None) if fallback_attr else None
    )
    name = _sanitize(str(name)) if name else ""
    return name or str(entity_id)


def _sanitize(name: str) -> str:
    """清理文件夹/文件名中的非法字符。"""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip()
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _unique_entry(entry: str, used: set) -> str:
    """zip 内重名文件追加序号。"""
    if entry not in used:
        return entry
    if "." in entry:
        stem, _, ext = entry.rpartition(".")
        i = 2
        while f"{stem}_{i}.{ext}" in used:
            i += 1
        return f"{stem}_{i}.{ext}"
    i = 2
    while f"{entry}_{i}" in used:
        i += 1
    return f"{entry}_{i}"


def _zip_attachments(
    atts: List[Attachment],
    db: Session,
    group_by_record: bool = False,
    entity: Optional[str] = None,
) -> StreamingResponse:
    zip_buf = io.BytesIO()
    used: set = set()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for att in atts:
            p = Path(att.store_path)
            if not p.exists():
                continue
            base = Path(att.filename or f"{att.id}.pdf").name
            if group_by_record and entity and att.entity_id is not None:
                folder = _record_name(db, entity, att.entity_id)
                entry = f"{folder}/{base}"
            else:
                entry = base
            entry = _unique_entry(entry, used)
            used.add(entry)
            zf.write(p, entry)
    zip_buf.seek(0)
    fname = f"{entity}_attachments.zip" if entity else "attachments.zip"
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ─── Routes ─────────────────────────────────────────────────────────────────
# 注意：带 {att_id} 的单段/双段字面路由声明在 {entity}/{entity_id} 之前，避免路径误匹配。

@router.post("/batch-download")
def batch_download_by_ids(
    body: BatchByIdsIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """按附件 id 批量下载（抽屉内多选下载用）。"""
    ids = body.attachment_ids
    if not ids:
        raise HTTPException(status_code=400, detail="未指定要下载的文件")
    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="单次最多下载 50 个文件")
    atts = (
        db.query(Attachment)
        .filter(Attachment.id.in_(ids), Attachment.entity_type.isnot(None))
        .all()
    )
    return _zip_attachments(atts, db)


@router.post("/download-by-records")
def download_by_records(
    body: BatchByRecordsIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """按记录 id 批量下载某实体的全部附件，zip 内按记录名分文件夹（列表页批量下载用）。"""
    _require_entity(body.entity)
    if not body.ids:
        raise HTTPException(status_code=400, detail="未选择记录")
    if len(body.ids) > 200:
        raise HTTPException(status_code=400, detail="单次最多 200 条记录")
    atts = (
        db.query(Attachment)
        .filter(
            Attachment.entity_type == body.entity,
            Attachment.entity_id.in_(body.ids),
        )
        .order_by(Attachment.entity_id, Attachment.id)
        .all()
    )
    if len(atts) > 50:
        raise HTTPException(status_code=400, detail="单次最多下载 50 个文件")
    return _zip_attachments(atts, db, group_by_record=True, entity=body.entity)


@router.get("/{att_id}/file")
def serve_attachment(
    att_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    att = db.get(Attachment, att_id)
    if not att or not att.entity_type:
        raise HTTPException(status_code=404, detail="附件不存在")
    p = Path(att.store_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(p, media_type=_content_type(att.filename), filename=att.filename)


@router.delete("/{att_id}")
def delete_attachment(
    att_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    att = db.get(Attachment, att_id)
    if not att or not att.entity_type:
        raise HTTPException(status_code=404, detail="附件不存在")
    p = Path(att.store_path)
    if p.exists():
        p.unlink()
    db.delete(att)
    db.commit()
    return {"ok": True}


@router.get("/{entity}/{entity_id}", response_model=List[AttachmentOut])
def list_attachments(
    entity: str,
    entity_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    _require_entity(entity)
    return (
        db.query(Attachment)
        .filter(
            Attachment.entity_type == entity,
            Attachment.entity_id == entity_id,
        )
        .order_by(Attachment.id.desc())
        .all()
    )


@router.post("/{entity}/{entity_id}")
def upload_attachments(
    entity: str,
    entity_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """批量上传附件到指定记录，支持 PDF / Word / Excel / 图片。"""
    model, _, _ = _require_entity(entity)
    if not db.get(model, entity_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    results = []
    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTS:
            results.append({"filename": file.filename, "status": "skipped", "reason": "不支持的文件类型"})
            continue
        data = file.file.read()
        if not data:
            results.append({"filename": file.filename, "status": "skipped", "reason": "文件为空"})
            continue
        sha = _sha256(data)
        suffix = ext or ".bin"
        store_name = f"att_{uuid.uuid4().hex[:12]}{suffix}"
        store_path = UPLOAD_DIR / store_name
        store_path.write_bytes(data)
        att = Attachment(
            att_type=_att_type(file.filename),
            filename=file.filename,
            store_path=str(store_path),
            sha256=sha,
            size=len(data),
            uploader_id=user.id,
            entity_type=entity,
            entity_id=entity_id,
        )
        db.add(att)
        db.flush()
        results.append({"filename": file.filename, "status": "ok", "attachment_id": att.id})
    db.commit()
    return {"files": results}
