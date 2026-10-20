from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user, require_admin
from .. import custom_fields as cf
from ..models import AwardRecord, AwardRecipient, Person
from ..schemas import (
    AwardCreate, AwardDetailOut, AwardUpdate,
    AwardRecipientIn, AwardRecipientOut,
)

router = APIRouter(prefix="/awards", tags=["awards"])


def award_to_out(a: AwardRecord) -> AwardDetailOut:
    data = AwardDetailOut.model_validate(a)
    data.extra = cf.parse_extra(a)
    data.recipients = [
        AwardRecipientOut(
            id=r.id,
            seq=r.seq,
            recipient_name=r.recipient_name,
            person_id=r.person_id,
            rank=r.rank,
            person_name=r.person.name if r.person else None,
        )
        for r in a.recipients
    ]
    return data


def _build_recipient(db: Session, r: AwardRecipientIn) -> AwardRecipient:
    person_id = r.person_id
    if not person_id and r.recipient_name:
        from .imports import _build_person_lookup, _match_person_in_lookup
        lookup = _build_person_lookup(db)
        person = _match_person_in_lookup(lookup, r.recipient_name)
        if person:
            person_id = person.id
    return AwardRecipient(
        seq=r.seq,
        recipient_name=r.recipient_name,
        person_id=person_id,
        rank=r.rank,
    )


def check_award_conflict(db: Session, name: str, exclude_id: Optional[int] = None):
    q = db.query(AwardRecord).filter(AwardRecord.award_name == name.strip())
    if exclude_id:
        q = q.filter(AwardRecord.id != exclude_id)
    dup = q.first()
    if dup:
        raise HTTPException(status_code=409, detail=f"奖项名称已存在（id={dup.id}）")


@router.get("", response_model=None)
def list_awards(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=200),
    person_id: Optional[int] = None,
    level: Optional[str] = None,
    keyword: Optional[str] = None,
):
    """奖励荣誉列表。传 page/page_size 时返回 {total,page,page_size,rows}，否则返回 List 全量。"""
    q = db.query(AwardRecord).options(selectinload(AwardRecord.recipients))
    if person_id:
        q = q.join(AwardRecipient).filter(AwardRecipient.person_id == person_id)
    if level:
        q = q.filter(AwardRecord.level == level)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            AwardRecord.award_name.like(like)
            | AwardRecord.issuer.like(like)
            | AwardRecord.summary.like(like)
        )
    q = q.order_by(AwardRecord.id.desc())
    if page and page_size:
        total = q.count()
        rows = q.limit(page_size).offset((page - 1) * page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": [award_to_out(a) for a in rows],
        }
    return [award_to_out(a) for a in q.all()]


@router.post("", response_model=AwardDetailOut, status_code=201)
def create_award(body: AwardCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    check_award_conflict(db, body.award_name)
    a = AwardRecord(**body.model_dump(exclude={"recipients", "extra"}))
    db.add(a)
    db.flush()
    cf.save_extra(a, body.extra, db, "awards")
    for r in body.recipients:
        rec = _build_recipient(db, r)
        rec.award_id = a.id
        db.add(rec)
    db.commit()
    db.refresh(a)
    return award_to_out(a)


@router.get("/{award_id}", response_model=AwardDetailOut)
def get_award(award_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    a = db.query(AwardRecord).options(
        selectinload(AwardRecord.recipients)
    ).filter(AwardRecord.id == award_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="获奖记录不存在")
    return award_to_out(a)


@router.put("/{award_id}", response_model=AwardDetailOut)
def update_award(
    award_id: int, body: AwardUpdate, db: Session = Depends(get_db), _=Depends(require_admin)
):
    a = db.query(AwardRecord).options(
        selectinload(AwardRecord.recipients)
    ).filter(AwardRecord.id == award_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="获奖记录不存在")
    payload = body.model_dump(exclude_unset=True)
    recipients = payload.pop("recipients", None)
    extra = payload.pop("extra", None)
    if payload.get("award_name") and payload["award_name"] != a.award_name:
        check_award_conflict(db, payload["award_name"], exclude_id=award_id)
    for k, v in payload.items():
        setattr(a, k, v)
    if extra is not None:
        cf.save_extra(a, extra, db, "awards")
    if recipients is not None:
        for old in list(a.recipients):
            db.delete(old)
        db.flush()
        for r in recipients:
            rec = _build_recipient(db, AwardRecipientIn(**r))
            rec.award_id = a.id
            db.add(rec)
    db.commit()
    db.refresh(a)
    return award_to_out(a)


@router.delete("/{award_id}")
def delete_award(award_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    a = db.get(AwardRecord, award_id)
    if not a:
        raise HTTPException(status_code=404, detail="获奖记录不存在")
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.post("/batch-delete")
def batch_delete_awards(body: list[int], db: Session = Depends(get_db), _=Depends(require_admin)):
    if not body:
        raise HTTPException(status_code=400, detail="未选择要删除的记录")
    deleted = 0
    for award_id in body:
        a = db.get(AwardRecord, award_id)
        if a:
            db.delete(a)
            deleted += 1
    db.commit()
    return {"deleted": deleted}


@router.post("/rematch-recipients")
def rematch_recipients(db: Session = Depends(get_db), _=Depends(require_admin)):
    """对未关联人员的获奖人，按姓名重新匹配人员库。"""
    from .imports import _build_person_lookup, _match_person_in_lookup
    lookup = _build_person_lookup(db)
    matched = 0
    for r in db.query(AwardRecipient).filter(AwardRecipient.person_id.is_(None)).all():
        person = _match_person_in_lookup(lookup, r.recipient_name)
        if person:
            r.person_id = person.id
            matched += 1
    db.commit()
    return {"ok": True, "matched": matched}
