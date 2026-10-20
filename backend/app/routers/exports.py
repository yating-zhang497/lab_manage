from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import export_builder as eb
from .. import importexport as ie
from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AwardRecord, AwardRecipient,
    IntellectualProperty, IPInventor, IPFunding,
    Paper, PaperAuthor,
    Person, Project, ProjectMember,
)
from ..paper_query import filter_papers, papers_by_ids

router = APIRouter(prefix="/export", tags=["export"])

XLSX_MT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type=XLSX_MT,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _text(data: str, filename: str) -> Response:
    return Response(
        content=data.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _selected_papers(
    db: Session,
    ids: Optional[str],
    year: Optional[int],
    years: Optional[List[int]],
    year_min: Optional[int],
    year_max: Optional[int],
    venue_type: Optional[str],
    venue_types: Optional[List[str]],
    ccf_class: Optional[str],
    person_id: Optional[int],
    author_role: Optional[str],
    project_id: Optional[int],
    funding_seq: Optional[int],
    include_ack_text: bool,
    keyword: Optional[str],
):
    """ids（勾选导出）优先于筛选条件。"""
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if not id_list:
            raise HTTPException(status_code=422, detail="ids 格式错误")
        return papers_by_ids(db, id_list)
    return filter_papers(
        db,
        year=year,
        years=years,
        year_min=year_min,
        year_max=year_max,
        venue_type=venue_type,
        venue_types=venue_types,
        ccf_class=ccf_class,
        person_id=person_id,
        author_role=author_role,
        project_id=project_id,
        funding_seq=funding_seq,
        include_ack_text=include_ack_text,
        keyword=keyword,
    ).all()


@router.get("/papers.bib")
def export_papers_bib(
    ids: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[List[int]] = Query(default=None),
    year_min: Optional[int] = Query(None),
    year_max: Optional[int] = Query(None),
    venue_type: Optional[str] = None,
    venue_types: Optional[List[str]] = Query(default=None),
    ccf_class: Optional[str] = None,
    person_id: Optional[int] = None,
    author_role: Optional[str] = None,
    project_id: Optional[int] = None,
    funding_seq: Optional[int] = None,
    include_ack_text: bool = False,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    entries = []
    for p in _selected_papers(
        db, ids, year, years, year_min, year_max, venue_type, venue_types, ccf_class,
        person_id, author_role, project_id, funding_seq, include_ack_text, keyword,
    ):
        entries.append(ie.build_paper_bib(p))
    return _text("\n\n".join(entries) + "\n", "papers_export.bib")


class CustomExportRequest(BaseModel):
    type: str
    columns: List[str] = []
    filters: dict = {}
    ids: Optional[List[int]] = None


def export_columns(db: Session, type_: str) -> List[dict]:
    """导出字段目录 = 模块字段定义（含启用的自定义字段）+ 关联派生列。"""
    return eb.export_columns_for(db, type_)


def _valid_columns(db: Session, type_: str, requested: List[str]) -> List[str]:
    cols = export_columns(db, type_)
    if not requested:
        # 默认导出 = 模块字段 + 标量派生列（不含多值关联列，避免维度混乱）
        return [c["key"] for c in cols if not c["dim"]]
    valid = {c["key"] for c in cols}
    unknown = [c for c in requested if c not in valid]
    if unknown:
        raise HTTPException(status_code=422, detail=f"未知字段: {unknown}")
    return requested


def _check_dims(type_: str, columns: List[str]) -> None:
    """所选字段若跨多个"多值维度"，无法在同一张二维表中同时按两个维度展开 → 拒绝导出。"""
    dims = eb.conflict_dims(type_, columns)
    if len(dims) > 1:
        dim_text = "、".join(f"「{d}」" for d in dims)
        raise HTTPException(
            status_code=422,
            detail=(
                f"无法导出：所选字段同时包含 {dim_text} 等多个「多值关联」维度，"
                f"同一张二维表无法同时按两个维度展开（每行只能属于一个维度的某条记录）。"
                f"请每次只保留一个维度的关联字段，分多次导出。"
            ),
        )


def _ordered_by_ids(db: Session, model, ids: List[int]) -> list:
    rows = db.query(model).filter(model.id.in_(ids)).all()
    order = {pid: i for i, pid in enumerate(ids)}
    return sorted(rows, key=lambda r: order[r.id])


def _query_entities(db: Session, type_: str, filters: dict, ids: Optional[List[int]] = None):
    if ids is not None:
        model = {
            "papers": Paper,
            "people": Person,
            "projects": Project,
            "ip": IntellectualProperty,
            "awards": AwardRecord,
        }.get(type_)
        if not model:
            raise HTTPException(status_code=422, detail="type 必须为 papers/people/projects/ip/awards")
        return papers_by_ids(db, ids) if type_ == "papers" else _ordered_by_ids(db, model, ids)

    if type_ == "papers":
        return filter_papers(
            db,
            year=filters.get("year"),
            years=filters.get("years"),
            year_min=filters.get("year_min"),
            year_max=filters.get("year_max"),
            venue_type=filters.get("venue_type") or None,
            venue_types=filters.get("venue_types"),
            ccf_class=filters.get("ccf_class") or None,
            person_id=filters.get("person_id") or None,
            author_role=filters.get("author_role") or None,
            project_id=filters.get("project_id") or None,
            funding_seq=filters.get("funding_seq") or None,
            include_ack_text=bool(filters.get("include_ack_text")),
            keyword=filters.get("keyword") or None,
        ).all()

    if type_ == "people":
        q = db.query(Person)
        if filters.get("status"):
            q = q.filter(Person.status == filters["status"])
        if filters.get("degree_type"):
            q = q.filter(Person.degree_type == filters["degree_type"])
        if filters.get("project_id"):
            member_ids = db.query(ProjectMember.person_id).filter(
                ProjectMember.project_id == filters["project_id"]
            )
            q = q.filter(Person.id.in_(member_ids))
        if filters.get("year"):
            person_ids = db.query(PaperAuthor.person_id).join(Paper).filter(
                PaperAuthor.paper_id == Paper.id, Paper.year == filters["year"]
            )
            q = q.filter(Person.id.in_(person_ids))
        if filters.get("keyword"):
            like = f"%{filters['keyword']}%"
            q = q.filter(
                Person.name.like(like)
                | Person.uid.like(like)
                | Person.english_name.like(like)
            )
        return q.order_by(Person.id).all()

    if type_ == "projects":
        q = db.query(Project)
        if filters.get("status"):
            q = q.filter(Project.status == filters["status"])
        if filters.get("category"):
            q = q.filter(Project.category == filters["category"])
        if filters.get("person_id"):
            proj_ids = db.query(ProjectMember.project_id).filter(
                ProjectMember.person_id == filters["person_id"]
            )
            q = q.filter(Project.id.in_(proj_ids))
        if filters.get("year"):
            from ..models import PaperFunding
            proj_ids = db.query(PaperFunding.project_id).join(Paper).filter(
                PaperFunding.paper_id == Paper.id, Paper.year == filters["year"]
            )
            q = q.filter(Project.id.in_(proj_ids))
        if filters.get("keyword"):
            like = f"%{filters['keyword']}%"
            q = q.filter(
                Project.name.like(like) | Project.project_no.like(like)
            )
        return q.order_by(Project.id).all()

    if type_ == "ip":
        q = db.query(IntellectualProperty)
        if filters.get("ip_type"):
            q = q.filter(IntellectualProperty.ip_type == filters["ip_type"])
        if filters.get("person_id"):
            ip_ids = db.query(IPInventor.ip_id).filter(
                IPInventor.person_id == filters["person_id"]
            )
            q = q.filter(IntellectualProperty.id.in_(ip_ids))
        if filters.get("project_id"):
            ip_ids = db.query(IPFunding.ip_id).filter(
                IPFunding.project_id == filters["project_id"]
            )
            q = q.filter(IntellectualProperty.id.in_(ip_ids))
        if filters.get("keyword"):
            like = f"%{filters['keyword']}%"
            q = q.filter(
                IntellectualProperty.title.like(like)
                | IntellectualProperty.applicant.like(like)
            )
        return q.order_by(IntellectualProperty.id).all()

    if type_ == "awards":
        q = db.query(AwardRecord)
        if filters.get("level"):
            q = q.filter(AwardRecord.level == filters["level"])
        if filters.get("person_id"):
            award_ids = db.query(AwardRecipient.award_id).filter(
                AwardRecipient.person_id == filters["person_id"]
            )
            q = q.filter(AwardRecord.id.in_(award_ids))
        if filters.get("keyword"):
            like = f"%{filters['keyword']}%"
            q = q.filter(
                AwardRecord.award_name.like(like)
                | AwardRecord.issuer.like(like)
                | AwardRecord.summary.like(like)
            )
        return q.order_by(AwardRecord.id.desc()).all()

    raise HTTPException(status_code=422, detail="type 必须为 papers/people/projects/ip/awards")


def _build_rows(db: Session, type_: str, entities: list, columns: List[str]) -> list:
    if type_ == "papers":
        return eb.build_paper_rows(db, entities, columns)
    if type_ == "people":
        return eb.build_people_rows(db, entities, columns)
    if type_ == "ip":
        return eb.build_ip_rows(db, entities, columns)
    if type_ == "awards":
        return eb.build_award_rows(db, entities, columns)
    return eb.build_project_rows(db, entities, columns)


@router.get("/columns")
def list_export_columns(type: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    cols = export_columns(db, type)
    if not cols:
        raise HTTPException(status_code=422, detail="type 必须为 papers/people/projects/ip")
    return cols


@router.post("/preview")
def export_preview(body: CustomExportRequest, db: Session = Depends(get_db), _=Depends(get_current_user)):
    columns = _valid_columns(db, body.type, body.columns)
    _check_dims(body.type, columns)
    entities = _query_entities(db, body.type, body.filters, body.ids)
    rows = _build_rows(db, body.type, entities, columns)[:100]
    return {
        "columns": [c for c in export_columns(db, body.type) if c["key"] in columns],
        "rows": rows,
        "total": len(entities),
    }


@router.post("/custom")
def export_custom(body: CustomExportRequest, db: Session = Depends(get_db), _=Depends(get_current_user)):
    columns = _valid_columns(db, body.type, body.columns)
    _check_dims(body.type, columns)
    entities = _query_entities(db, body.type, body.filters, body.ids)
    rows = _build_rows(db, body.type, entities, columns)
    labels = {c["key"]: c["label"] for c in export_columns(db, body.type)}
    header = [labels[c] for c in columns]
    data_rows = [[row.get(c) for c in columns] for row in rows]
    data = ie.make_excel(header, data_rows)
    return _xlsx(data, f"{body.type}_custom_export.xlsx")
