from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import IntellectualProperty, Paper, Person, Project

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    q: str = Query(..., min_length=1),
    type: str = Query("all", pattern="^(people|projects|papers|ip|all)$"),
    limit: int = Query(5, ge=1, le=20),
):
    """
    全局跨表搜索，支持 Ctrl+K 一次性查询四类实体。
    - people: name / english_name / uid
    - projects: name / project_no
    - papers:   title / venue
    - ip:       title
    """
    like = f"%{q}%"
    result = {"people": [], "projects": [], "papers": [], "ip": []}

    if type in ("all", "people"):
        rows = (
            db.query(Person)
            .filter(
                Person.name.like(like)
                | Person.english_name.like(like)
                | Person.uid.like(like)
            )
            .limit(limit)
            .all()
        )
        result["people"] = [
            {"id": p.id, "name": p.name, "uid": p.uid, "degree_type": p.degree_type, "status": p.status}
            for p in rows
        ]

    if type in ("all", "projects"):
        rows = (
            db.query(Project)
            .filter(Project.name.like(like) | Project.project_no.like(like))
            .limit(limit)
            .all()
        )
        result["projects"] = [
            {"id": p.id, "name": p.name, "project_no": p.project_no}
            for p in rows
        ]

    if type in ("all", "papers"):
        rows = (
            db.query(Paper)
            .filter(Paper.title.like(like) | Paper.venue.like(like))
            .limit(limit)
            .all()
        )
        result["papers"] = [
            {"id": p.id, "title": p.title, "venue": p.venue, "year": p.year}
            for p in rows
        ]

    if type in ("all", "ip"):
        rows = (
            db.query(IntellectualProperty)
            .filter(IntellectualProperty.title.like(like))
            .limit(limit)
            .all()
        )
        result["ip"] = [
            {"id": p.id, "title": p.title, "ip_type": p.ip_type}
            for p in rows
        ]

    return result
