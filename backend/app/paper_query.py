"""论文筛选唯一实现：列表页与各导出端点共用，避免多处逻辑漂移。

所有人员/项目关联筛选都走关系表（paper_authors / paper_funding），
与"唯一标识 + 关系表贯通"的数据模型保持一致。
"""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import Paper, PaperAuthor, PaperFunding, Project


def _author_role_condition(author_role: Optional[str]):
    if author_role == "first":
        return PaperAuthor.seq == 1
    if author_role == "corresponding":
        return PaperAuthor.is_corresponding.is_(True)
    if author_role == "first_or_corresponding":
        return or_(PaperAuthor.seq == 1, PaperAuthor.is_corresponding.is_(True))
    return None


def filter_papers(
    db: Session,
    *,
    year: Optional[int] = None,
    years: Optional[List[int]] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    venue_type: Optional[str] = None,
    venue_types: Optional[List[str]] = None,
    ccf_class: Optional[str] = None,
    person_id: Optional[int] = None,
    author_role: Optional[str] = None,
    project_id: Optional[int] = None,
    funding_seq: Optional[int] = None,
    include_ack_text: bool = False,
    keyword: Optional[str] = None,
    extract_status: Optional[str] = None,
):
    q = db.query(Paper)

    author_conditions = []
    if person_id:
        author_conditions.append(PaperAuthor.person_id == person_id)
    role_cond = _author_role_condition(author_role)
    if role_cond is not None:
        author_conditions.append(role_cond)
    if author_conditions:
        q = q.join(PaperAuthor).filter(*author_conditions)

    if project_id:
        funding = db.query(PaperFunding.paper_id).filter(
            PaperFunding.project_id == project_id
        )
        if funding_seq:
            funding = funding.filter(PaperFunding.seq == funding_seq)
        cond = Paper.id.in_(funding)
        if include_ack_text:
            proj = db.get(Project, project_id)
            if proj and proj.project_no:
                cond = or_(cond, Paper.acknowledgements.like(f"%{proj.project_no}%"))
        q = q.filter(cond)

    if year:
        q = q.filter(Paper.year == year)
    if years:
        q = q.filter(Paper.year.in_(years))
    if year_min:
        q = q.filter(Paper.year >= year_min)
    if year_max:
        q = q.filter(Paper.year <= year_max)
    if venue_type:
        q = q.filter(Paper.venue_type == venue_type)
    if venue_types:
        q = q.filter(Paper.venue_type.in_(venue_types))
    if ccf_class:
        q = q.filter(Paper.ccf_class == ccf_class)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            Paper.title.like(like)
            | Paper.venue.like(like)
            | Paper.authors_raw.like(like)
            | Paper.acknowledgements.like(like)
        )
    if extract_status:
        q = q.filter(Paper.extract_status == extract_status)
    return q.distinct().order_by(Paper.year.desc().nullslast(), Paper.id.desc())


def papers_by_ids(db: Session, ids: List[int]) -> List[Paper]:
    """按给定 id 列表取论文，保留传入顺序（勾选导出用）。"""
    rows = db.query(Paper).filter(Paper.id.in_(ids)).all()
    order = {pid: i for i, pid in enumerate(ids)}
    return sorted(rows, key=lambda p: order[p.id])
