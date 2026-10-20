"""数据存档管理：列表、下载、删除、手动/自动导出。"""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import Archive
from ..schemas import ArchiveOut

router = APIRouter(prefix="/archives", tags=["archives"])

ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "archives")
os.makedirs(ARCHIVE_DIR, exist_ok=True)

EXPORT_ROUTES = {
    "people": "/people",
    "projects": "/projects",
    "papers": "/papers",
    "ip": "/ip",
}


def _build_archive_path(entity: str, filename: str) -> str:
    entity_dir = os.path.join(ARCHIVE_DIR, entity)
    os.makedirs(entity_dir, exist_ok=True)
    return os.path.join(entity_dir, filename)


@router.get("", response_model=list[ArchiveOut])
def list_archives(
    entity: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Archive)
    if entity:
        q = q.filter(Archive.entity == entity)
    return q.order_by(Archive.created_at.desc()).all()


@router.get("/{archive_id}")
def download_archive(archive_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    a = db.get(Archive, archive_id)
    if not a:
        raise HTTPException(status_code=404, detail="存档不存在")
    if not os.path.exists(a.file_path):
        raise HTTPException(status_code=404, detail="文件已丢失")
    return FileResponse(
        a.file_path,
        filename=a.filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.delete("/{archive_id}")
def delete_archive(archive_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    a = db.get(Archive, archive_id)
    if not a:
        raise HTTPException(status_code=404, detail="存档不存在")
    if os.path.exists(a.file_path):
        os.remove(a.file_path)
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.post("/{entity}/export")
def trigger_export(
    entity: str,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """手动触发导出：立即导出指定实体的当前数据并保存为存档。"""
    if entity not in EXPORT_ROUTES:
        raise HTTPException(status_code=400, detail="不支持的实体类型")
    record = _do_export(db, entity, user.username, is_auto=False)
    return record


def _do_export(db: Session, entity: str, username: str, is_auto: bool) -> ArchiveOut:
    """执行导出并写入 Archive 记录。"""
    from .. import export_builder as eb
    from .. import importexport as ie

    now = datetime.utcnow()
    ts = now.strftime("%Y-%m-%d_%H%M%S")
    filename = f"{ts}_{entity}.xlsx"
    file_path = _build_archive_path(entity, filename)

    # 使用现有的 build_*_rows + make_excel 生成完整 Excel
    # （与 /export/custom 一致：columns 传字符串 key 列表，再展平成值行，
    #   因为 _select/make_excel 都不接受 dict 列）
    cols = eb.export_columns_for(db, entity)
    keys = [c["key"] for c in cols]
    from ..models import Person, Project, Paper, IntellectualProperty
    model_map = {"people": Person, "projects": Project, "papers": Paper, "ip": IntellectualProperty}
    model_cls = model_map[entity]
    entities = db.query(model_cls).all()

    if entity == "people":
        built = eb.build_people_rows(db, entities, keys)
    elif entity == "projects":
        built = eb.build_project_rows(db, entities, keys)
    elif entity == "papers":
        built = eb.build_paper_rows(db, entities, keys)
    else:
        built = eb.build_ip_rows(db, entities, keys)

    header = [c["label"] for c in cols]
    data_rows = [[row.get(k) for k in keys] for row in built]
    data = ie.make_excel(header, data_rows)
    with open(file_path, "wb") as f:
        f.write(data)

    size = os.path.getsize(file_path)
    a = Archive(
        entity=entity,
        filename=filename,
        file_path=file_path,
        size_bytes=size,
        is_auto=is_auto,
        created_by=username,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return ArchiveOut.model_validate(a)
