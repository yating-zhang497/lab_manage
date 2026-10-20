from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import custom_fields as cf
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import (
    IntellectualProperty,
    IPFunding,
    IPInventor,
    Person,
    Project,
)
from ..schemas import (
    IPCreate,
    IPFundingIn,
    IPFundingOut,
    IPInventorIn,
    IPInventorOut,
    IPOut,
    IPUpdate,
)

router = APIRouter(prefix="/ip", tags=["intellectual_property"])


def _auto_match_person(db: Session, name) -> Optional[int]:
    """按姓名/英文名（含变体）自动匹配人员，返回 person_id 或 None。"""
    if not (name or "").strip():
        return None
    from .imports import _build_person_lookup, _match_person_in_lookup

    person = _match_person_in_lookup(_build_person_lookup(db), name)
    return person.id if person else None


def ip_to_out(ip: IntellectualProperty) -> IPOut:
    data = IPOut.model_validate(ip)
    data.extra = cf.parse_extra(ip)
    data.inventors = [
        IPInventorOut(
            id=v.id,
            seq=v.seq,
            inventor_name=v.inventor_name,
            person_id=v.person_id,
            is_first=v.is_first,
            person_name=v.person.name if v.person else None,
        )
        for v in ip.inventors
    ]
    data.funding = [
        IPFundingOut(
            id=f.id,
            project_id=f.project_id,
            funding_no=f.funding_no,
            project_name=f.project.name if f.project else None,
        )
        for f in ip.funding
    ]
    return data


@router.get("", response_model=None)
def list_ip(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=200),
    ip_types: Optional[List[str]] = None,
    keyword: Optional[str] = None,
):
    """知识产权列表。传 page/page_size 时返回 {total,page,page_size,rows}，否则返回 List 全量。"""
    q = db.query(IntellectualProperty).options(
        joinedload(IntellectualProperty.inventors),
        joinedload(IntellectualProperty.funding).joinedload(IPFunding.project),
    )
    if ip_types:
        vals = [v for v in ip_types if v]
        if vals:
            q = q.filter(IntellectualProperty.ip_type.in_(vals))
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(IntellectualProperty.title.like(like))
    q = q.order_by(IntellectualProperty.id)
    if page and page_size:
        total = q.count()
        rows = q.limit(page_size).offset((page - 1) * page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": [ip_to_out(ip) for ip in rows],
        }
    return [ip_to_out(ip) for ip in q.all()]


def check_title_conflict(db: Session, title: str, exclude_id: Optional[int] = None):
    """产权名称为唯一标识（去空白后精确比对）。"""
    key = (title or "").strip()
    q = db.query(IntellectualProperty).filter(IntellectualProperty.title == key)
    if exclude_id:
        q = q.filter(IntellectualProperty.id != exclude_id)
    dup = q.first()
    if dup:
        raise HTTPException(status_code=409, detail=f"产权名称已存在（id={dup.id}）")


def _valid_ip_types(db: Session) -> list:
    """从当前字段定义获取 ip_type 的有效选项。"""
    for f in cf.defs_for(db, "ip", enabled_only=True):
        if f["key"] == "ip_type":
            return f.get("options", [])
    return []


@router.post("", response_model=IPOut, status_code=201)
def create_ip(body: IPCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    valid_types = _valid_ip_types(db)
    if valid_types and body.ip_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"ip_type 必须为 {'/'.join(valid_types)}")
    check_title_conflict(db, body.title)
    ip = IntellectualProperty(**body.model_dump(exclude={"inventors", "funding", "extra"}))
    db.add(ip)
    db.flush()
    cf.save_extra(ip, body.extra, db, "ip")
    for i, v in enumerate(body.inventors):
        person_id = v.person_id or _auto_match_person(db, v.inventor_name)
        db.add(
            IPInventor(
                ip_id=ip.id,
                seq=v.seq or i + 1,
                inventor_name=v.inventor_name,
                person_id=person_id,
                is_first=v.is_first,
            )
        )
    for f in body.funding:
        db.add(IPFunding(ip_id=ip.id, **f.model_dump()))
    db.commit()
    db.refresh(ip)
    return ip_to_out(ip)


@router.get("/{ip_id}", response_model=IPOut)
def get_ip(ip_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ip = (
        db.query(IntellectualProperty)
        .options(
            joinedload(IntellectualProperty.inventors),
            joinedload(IntellectualProperty.funding).joinedload(IPFunding.project),
        )
        .filter(IntellectualProperty.id == ip_id)
        .first()
    )
    if not ip:
        raise HTTPException(status_code=404, detail="知识产权不存在")
    return ip_to_out(ip)


@router.put("/{ip_id}", response_model=IPOut)
def update_ip(
    ip_id: int, body: IPUpdate, db: Session = Depends(get_db), _=Depends(require_admin)
):
    valid_types = _valid_ip_types(db)
    if valid_types and body.ip_type and body.ip_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"ip_type 必须为 {'/'.join(valid_types)}")
    ip = db.get(IntellectualProperty, ip_id)
    if not ip:
        raise HTTPException(status_code=404, detail="知识产权不存在")
    payload = body.model_dump(exclude_unset=True)
    extra = payload.pop("extra", None)
    new_title = payload.get("title")
    if new_title is not None and new_title != ip.title:
        check_title_conflict(db, new_title, exclude_id=ip_id)
    for k, v in payload.items():
        setattr(ip, k, v)
    if extra is not None:
        cf.save_extra(ip, extra, db, "ip")
    db.commit()
    db.refresh(ip)
    return ip_to_out(ip)


@router.delete("/{ip_id}")
def delete_ip(ip_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    ip = db.get(IntellectualProperty, ip_id)
    if not ip:
        raise HTTPException(status_code=404, detail="知识产权不存在")
    db.delete(ip)
    db.commit()
    return {"ok": True}


@router.post("/batch-delete")
def batch_delete_ip(body: list[int], db: Session = Depends(get_db), _=Depends(require_admin)):
    """批量删除知识产权。"""
    if not body:
        raise HTTPException(status_code=400, detail="未选择要删除的记录")
    deleted = 0
    for ip_id in body:
        ip = db.get(IntellectualProperty, ip_id)
        if ip:
            db.delete(ip)
            deleted += 1
    db.commit()
    return {"deleted": deleted}


@router.post("/{ip_id}/inventors", status_code=201)
def add_inventor(
    ip_id: int, body: IPInventorIn, db: Session = Depends(get_db), _=Depends(require_admin)
):
    if not db.get(IntellectualProperty, ip_id):
        raise HTTPException(status_code=404, detail="知识产权不存在")
    if body.person_id and not db.get(Person, body.person_id):
        raise HTTPException(status_code=404, detail="人员不存在")
    person_id = body.person_id or _auto_match_person(db, body.inventor_name)
    db.add(
        IPInventor(
            ip_id=ip_id,
            inventor_name=body.inventor_name,
            person_id=person_id,
            seq=body.seq,
            is_first=body.is_first,
        )
    )
    db.commit()
    return {"ok": True}


@router.delete("/{ip_id}/inventors/{inventor_id}")
def remove_inventor(
    ip_id: int, inventor_id: int, db: Session = Depends(get_db), _=Depends(require_admin)
):
    v = db.get(IPInventor, inventor_id)
    if not v or v.ip_id != ip_id:
        raise HTTPException(status_code=404, detail="发明人记录不存在")
    db.delete(v)
    db.commit()
    return {"ok": True}


@router.put("/{ip_id}/inventors/{inventor_id}")
def update_inventor(
    ip_id: int,
    inventor_id: int,
    body: IPInventorIn,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    v = db.get(IPInventor, inventor_id)
    if not v or v.ip_id != ip_id:
        raise HTTPException(status_code=404, detail="发明人记录不存在")
    v.inventor_name = body.inventor_name
    v.seq = body.seq
    v.is_first = body.is_first
    v.person_id = body.person_id or _auto_match_person(db, body.inventor_name)
    db.commit()
    return {"ok": True}


@router.post("/rematch-inventors")
def rematch_inventors(db: Session = Depends(get_db), _=Depends(require_admin)):
    """对未关联人员的发明人，按姓名/英文名（含变体）重新匹配人员库。"""
    from .imports import _build_person_lookup, _match_person_in_lookup

    lookup = _build_person_lookup(db)
    matched = 0
    for v in db.query(IPInventor).filter(IPInventor.person_id.is_(None)).all():
        person = _match_person_in_lookup(lookup, v.inventor_name)
        if person:
            v.person_id = person.id
            matched += 1
    db.commit()
    return {"ok": True, "matched": matched}


@router.post("/{ip_id}/funding", status_code=201)
def add_ip_funding(
    ip_id: int, body: IPFundingIn, db: Session = Depends(get_db), _=Depends(require_admin)
):
    if not db.get(IntellectualProperty, ip_id):
        raise HTTPException(status_code=404, detail="知识产权不存在")
    if body.project_id and not db.get(Project, body.project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    db.add(IPFunding(ip_id=ip_id, **body.model_dump()))
    db.commit()
    return {"ok": True}


@router.delete("/{ip_id}/funding/{funding_id}")
def remove_ip_funding(
    ip_id: int, funding_id: int, db: Session = Depends(get_db), _=Depends(require_admin)
):
    f = db.get(IPFunding, funding_id)
    if not f or f.ip_id != ip_id:
        raise HTTPException(status_code=404, detail="基金标注记录不存在")
    db.delete(f)
    db.commit()
    return {"ok": True}
