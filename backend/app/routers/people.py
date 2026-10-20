from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from .. import custom_fields as cf
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import (
    AwardRecord,
    AwardRecipient,
    IPInventor,
    Paper,
    PaperAuthor,
    Person,
    PersonNameVariant,
    Project,
    ProjectMember,
)
from ..schemas import (
    NameVariantIn,
    PersonCreate,
    PersonOut,
    PersonUpdate,
)

router = APIRouter(prefix="/people", tags=["people"])


def person_to_out(p: Person) -> PersonOut:
    data = PersonOut.model_validate(p)
    data.extra = cf.parse_extra(p)
    return data


@router.get("", response_model=None)
def list_people(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=200),
    status: Optional[List[str]] = None,
    degree_type: Optional[List[str]] = None,
    project_id: Optional[int] = None,
    keyword: Optional[str] = None,
):
    """人员列表。传 page/page_size 时返回 {total,page,page_size,rows}，否则返回 List 全量。"""
    q = db.query(Person).options(selectinload(Person.name_variants))
    if status:
        vals = [v for v in status if v]
        if vals:
            q = q.filter(Person.status.in_(vals))
    if degree_type:
        vals = [v for v in degree_type if v]
        if vals:
            q = q.filter(Person.degree_type.in_(vals))
    if project_id:
        member_ids = db.query(ProjectMember.person_id).filter(
            ProjectMember.project_id == project_id
        )
        q = q.filter(Person.id.in_(member_ids))
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            Person.name.like(like)
            | Person.english_name.like(like)
            | Person.uid.like(like)
        )
    q = q.order_by(Person.id)
    if page and page_size:
        total = q.count()
        rows = q.limit(page_size).offset((page - 1) * page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": [person_to_out(p) for p in rows],
        }
    return [person_to_out(p) for p in q.all()]


@router.post("", response_model=PersonOut, status_code=201)
def create_person(
    body: PersonCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    if body.uid:
        dup = db.query(Person).filter(Person.uid == body.uid).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"学号/工号 {body.uid} 已存在")
    p = Person(**body.model_dump(exclude={"name_variants", "extra"}))
    db.add(p)
    db.flush()
    cf.save_extra(p, body.extra, db, "people")
    for v in body.name_variants:
        db.add(PersonNameVariant(person_id=p.id, **v.model_dump()))
    db.commit()
    db.refresh(p)
    return person_to_out(p)


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="人员不存在")
    db.query(Person).options(selectinload(Person.name_variants)).filter(Person.id == person_id).first()
    return person_to_out(p)


@router.put("/{person_id}", response_model=PersonOut)
def update_person(
    person_id: int,
    body: PersonUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="人员不存在")
    payload = body.model_dump(exclude_unset=True)
    variants = payload.pop("name_variants", None)
    extra = payload.pop("extra", None)
    new_uid = payload.get("uid")
    if new_uid and new_uid != p.uid:
        dup = db.query(Person).filter(Person.uid == new_uid).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"学号/工号 {new_uid} 已存在")
    for k, v in payload.items():
        setattr(p, k, v)
    if extra is not None:
        cf.save_extra(p, extra, db, "people")
    if variants is not None:
        for old in list(p.name_variants):
            db.delete(old)
        db.flush()
        for v in variants:
            db.add(
                PersonNameVariant(
                    person_id=p.id,
                    name_text=v["name_text"],
                    kind=v.get("kind"),
                )
            )
    db.commit()
    db.refresh(p)
    return person_to_out(p)


@router.delete("/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="人员不存在")
    # 清理关联：作者/发明人记录保留名字但解除关联，成员记录删除，获奖人解除关联
    for a in db.query(PaperAuthor).filter(PaperAuthor.person_id == person_id).all():
        a.person_id = None
    for v in db.query(IPInventor).filter(IPInventor.person_id == person_id).all():
        v.person_id = None
    for m in db.query(ProjectMember).filter(ProjectMember.person_id == person_id).all():
        db.delete(m)
    for r in db.query(AwardRecipient).filter(AwardRecipient.person_id == person_id).all():
        r.person_id = None
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/batch-delete")
def batch_delete_people(body: list[int], db: Session = Depends(get_db), _=Depends(require_admin)):
    """批量删除人员。"""
    if not body:
        raise HTTPException(status_code=400, detail="未选择要删除的记录")
    deleted = 0
    for person_id in body:
        p = db.get(Person, person_id)
        if p:
            for a in db.query(PaperAuthor).filter(PaperAuthor.person_id == person_id).all():
                a.person_id = None
            for v in db.query(IPInventor).filter(IPInventor.person_id == person_id).all():
                v.person_id = None
            for m in db.query(ProjectMember).filter(ProjectMember.person_id == person_id).all():
                db.delete(m)
            for r in db.query(AwardRecipient).filter(AwardRecipient.person_id == person_id).all():
                r.person_id = None
            db.delete(p)
            deleted += 1
    db.commit()
    return {"deleted": deleted}


@router.get("/{person_id}/projects")
def person_projects(person_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """人员参与的项目列表，供 Drawer 调用。"""
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="人员不存在")
    rows = (
        db.query(ProjectMember, Project)
        .join(Project, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.person_id == person_id)
        .all()
    )
    return [
        {
            "project_id": pm.project_id,
            "project_no": proj.project_no,
            "name": proj.name,
            "category": proj.category,
            "duration": proj.duration,
            "role": pm.role,
        }
        for pm, proj in rows
    ]


@router.get("/{person_id}/papers")
def person_papers(person_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="人员不存在")
    rows = (
        db.query(Paper, PaperAuthor)
        .join(PaperAuthor, PaperAuthor.paper_id == Paper.id)
        .filter(PaperAuthor.person_id == person_id)
        .order_by(Paper.year.desc().nullslast(), PaperAuthor.seq)
        .all()
    )
    return [
        {
            "id": paper.id,
            "title": paper.title,
            "venue": paper.venue,
            "year": paper.year,
            "ccf_class": paper.ccf_class,
            "seq": pa.seq,
            "is_corresponding": pa.is_corresponding,
        }
        for paper, pa in rows
    ]


@router.get("/{person_id}/awards")
def person_awards(person_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """人员的获奖列表（通过 AwardRecipient 关系表关联）。"""
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="人员不存在")
    from sqlalchemy.orm import selectinload
    links = (
        db.query(AwardRecipient)
        .join(AwardRecord, AwardRecipient.award_id == AwardRecord.id)
        .options(selectinload(AwardRecipient.award))
        .filter(AwardRecipient.person_id == person_id)
        .order_by(AwardRecord.id.desc())
        .all()
    )
    return [
        {
            "recipient_id": r.id,
            "award_id": r.award_id,
            "award_name": r.award.award_name if r.award else None,
            "level": r.award.level if r.award else None,
            "award_date": r.award.award_date.isoformat() if r.award and r.award.award_date else None,
            "issuer": r.award.issuer if r.award else None,
            "rank": r.rank,
            "recipient_name": r.recipient_name,
        }
        for r in links
    ]
