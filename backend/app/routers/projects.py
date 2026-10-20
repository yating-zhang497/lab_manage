from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import custom_fields as cf
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import IPFunding, Paper, PaperFunding, Person, Project, ProjectMember
from ..schemas import ProjectCreate, ProjectMemberIn, ProjectMemberOut, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


def project_to_out(p: Project) -> ProjectOut:
    data = ProjectOut.model_validate(p)
    data.extra = cf.parse_extra(p)
    data.members = [
        ProjectMemberOut(
            id=m.id,
            person_id=m.person_id,
            role=m.role,
            note=m.note,
            person_name=m.person.name if m.person else None,
        )
        for m in p.members
    ]
    return data


@router.get("", response_model=None)
def list_projects(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=200),
    status: Optional[List[str]] = None,
    category: Optional[List[str]] = None,
    person_id: Optional[int] = None,
    keyword: Optional[str] = None,
):
    """项目列表。传 page/page_size 时返回 {total,page,page_size,rows}，否则返回 List 全量。"""
    q = db.query(Project).options(joinedload(Project.members).joinedload(ProjectMember.person))
    if status:
        vals = [v for v in status if v]
        if vals:
            q = q.filter(Project.status.in_(vals))
    if category:
        vals = [v for v in category if v]
        if vals:
            q = q.filter(Project.category.in_(vals))
    if person_id:
        proj_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.person_id == person_id
        )
        q = q.filter(Project.id.in_(proj_ids))
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(Project.name.like(like) | Project.project_no.like(like))
    q = q.order_by(Project.id)
    if page and page_size:
        total = q.count()
        rows = q.limit(page_size).offset((page - 1) * page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": [project_to_out(p) for p in rows],
        }
    return [project_to_out(p) for p in q.all()]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectCreate, db: Session = Depends(get_db), _=Depends(require_admin)
):
    if body.project_no:
        dup = db.query(Project).filter(Project.project_no == body.project_no).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"项目编号 {body.project_no} 已存在")
    p = Project(**body.model_dump(exclude={"members", "extra"}))
    db.add(p)
    db.flush()
    cf.save_extra(p, body.extra, db, "projects")
    for m in body.members:
        db.add(ProjectMember(project_id=p.id, **m.model_dump()))
    db.commit()
    db.refresh(p)
    return project_to_out(p)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = (
        db.query(Project)
        .options(joinedload(Project.members).joinedload(ProjectMember.person))
        .filter(Project.id == project_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project_to_out(p)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    payload = body.model_dump(exclude_unset=True)
    extra = payload.pop("extra", None)
    new_no = payload.get("project_no")
    if new_no and new_no != p.project_no:
        dup = db.query(Project).filter(Project.project_no == new_no).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"项目编号 {new_no} 已存在")
    for k, v in payload.items():
        setattr(p, k, v)
    if extra is not None:
        cf.save_extra(p, extra, db, "projects")
    db.commit()
    db.refresh(p)
    return project_to_out(p)


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 清理基金标注引用，避免导出时悬空引用
    for f in db.query(PaperFunding).filter(PaperFunding.project_id == project_id).all():
        f.project_id = None
    for f in db.query(IPFunding).filter(IPFunding.project_id == project_id).all():
        f.project_id = None
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/batch-delete")
def batch_delete_projects(body: list[int], db: Session = Depends(get_db), _=Depends(require_admin)):
    """批量删除项目。"""
    if not body:
        raise HTTPException(status_code=400, detail="未选择要删除的记录")
    deleted = 0
    for project_id in body:
        p = db.get(Project, project_id)
        if p:
            for f in db.query(PaperFunding).filter(PaperFunding.project_id == project_id).all():
                f.project_id = None
            for f in db.query(IPFunding).filter(IPFunding.project_id == project_id).all():
                f.project_id = None
            db.delete(p)
            deleted += 1
    db.commit()
    return {"deleted": deleted}


@router.post("/{project_id}/members", status_code=201)
def add_member(
    project_id: int,
    body: ProjectMemberIn,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    if not db.get(Person, body.person_id):
        raise HTTPException(status_code=404, detail="人员不存在")
    dup = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.person_id == body.person_id,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="该人员已在项目成员中")
    db.add(ProjectMember(project_id=project_id, **body.model_dump()))
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/members/{member_id}")
def remove_member(
    project_id: int, member_id: int, db: Session = Depends(get_db), _=Depends(require_admin)
):
    m = db.get(ProjectMember, member_id)
    if not m or m.project_id != project_id:
        raise HTTPException(status_code=404, detail="成员记录不存在")
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.get("/{project_id}/papers")
def project_papers(
    project_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    rows = (
        db.query(Paper, PaperFunding)
        .join(PaperFunding, PaperFunding.paper_id == Paper.id)
        .filter(PaperFunding.project_id == project_id)
        .order_by(PaperFunding.seq, Paper.year.desc().nullslast())
        .all()
    )
    return [
        {
            "id": paper.id,
            "title": paper.title,
            "venue": paper.venue,
            "year": paper.year,
            "funding_seq": pf.seq,
            "funding_no": pf.funding_no,
            "confirmed": pf.confirmed,
        }
        for paper, pf in rows
    ]
