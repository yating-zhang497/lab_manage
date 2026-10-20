from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import ai_extract, custom_fields as cf
from ..extraction_apply import apply_extraction_result
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import (
    AIExtraction,
    Attachment,
    Paper,
    PaperAuthor,
    PaperFunding,
    Person,
    Project,
    normalize_title,
)
from ..paper_query import filter_papers
from ..schemas import (
    PaperAuthorIn,
    PaperAuthorOut,
    PaperCreate,
    PaperFundingIn,
    PaperFundingOut,
    PaperListItem,
    PaperOut,
    PaperUpdate,
)

router = APIRouter(prefix="/papers", tags=["papers"])


def paper_to_out(p: Paper) -> PaperOut:
    data = PaperOut.model_validate(p)
    data.extra = cf.parse_extra(p)
    data.authors = [
        PaperAuthorOut(
            id=a.id,
            seq=a.seq,
            author_name=a.author_name,
            person_id=a.person_id,
            is_corresponding=a.is_corresponding,
            affiliation=a.affiliation,
            person_name=a.person.name if a.person else None,
        )
        for a in p.authors
    ]
    data.funding = [
        PaperFundingOut(
            id=f.id,
            project_id=f.project_id,
            funding_no=f.funding_no,
            seq=f.seq,
            source=f.source,
            confirmed=f.confirmed,
            project_name=f.project.name if f.project else None,
        )
        for f in p.funding
    ]
    return data


def paper_to_list_item(p: Paper) -> PaperListItem:
    """列表项：标量字段 + extra（自定义字段），不加载作者/基金子表。"""
    data = PaperListItem.model_validate(p)
    data.extra = cf.parse_extra(p)
    return data


def check_title_conflict(db: Session, title: str, exclude_id: Optional[int] = None):
    norm = normalize_title(title)
    q = db.query(Paper).filter(Paper.title_norm == norm)
    if exclude_id:
        q = q.filter(Paper.id != exclude_id)
    dup = q.first()
    if dup:
        raise HTTPException(status_code=409, detail=f"论文标题已存在（id={dup.id}）")


@router.get("", response_model=None)
def list_papers(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=200),
    year: Optional[int] = None,
    years: Optional[List[int]] = Query(default=None),
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    venue_type: Optional[str] = None,
    venue_types: Optional[List[str]] = Query(default=None),
    ccf_class: Optional[str] = None,
    person_id: Optional[int] = None,
    author_role: Optional[str] = None,
    project_id: Optional[int] = None,
    funding_seq: Optional[int] = None,
    include_ack_text: bool = False,
    keyword: Optional[str] = None,
    extract_status: Optional[str] = None,
):
    """论文列表。传 page/page_size 时返回 {total,page,page_size,rows}（分页），
    不传时返回 List[PaperListItem] 全量（兼容下拉框等场景，向后兼容）。
    """
    q = filter_papers(
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
        extract_status=extract_status,
    )
    if page and page_size:
        # 分页模式：返回对象。total 用 distinct 后的子查询计数
        total = q.count()
        rows = q.limit(page_size).offset((page - 1) * page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": [paper_to_list_item(p) for p in rows],
        }
    return [paper_to_list_item(p) for p in q.all()]


@router.post("", response_model=PaperOut, status_code=201)
def create_paper(body: PaperCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    check_title_conflict(db, body.title)
    payload = body.model_dump(exclude={"authors", "funding", "extra"})
    p = Paper(**payload)
    p.title_norm = normalize_title(p.title)
    db.add(p)
    db.flush()
    cf.save_extra(p, body.extra, db, "papers")
    for i, a in enumerate(body.authors):
        db.add(PaperAuthor(paper_id=p.id, seq=a.seq or i + 1, **a.model_dump(exclude={"seq"})))
    for f in body.funding:
        db.add(PaperFunding(paper_id=p.id, **f.model_dump()))
    db.commit()
    db.refresh(p)
    return paper_to_out(p)


@router.get("/{paper_id}", response_model=PaperOut)
def get_paper(paper_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = (
        db.query(Paper)
        .options(
            joinedload(Paper.authors).joinedload(PaperAuthor.person),
            joinedload(Paper.funding).joinedload(PaperFunding.project),
        )
        .filter(Paper.id == paper_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="论文不存在")
    return paper_to_out(p)


@router.put("/{paper_id}", response_model=PaperOut)
def update_paper(
    paper_id: int,
    body: PaperUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    p = db.get(Paper, paper_id)
    if not p:
        raise HTTPException(status_code=404, detail="论文不存在")
    payload = body.model_dump(exclude_unset=True)
    extra = payload.pop("extra", None)
    new_title = payload.get("title")
    if new_title is not None and new_title != p.title:
        check_title_conflict(db, new_title, exclude_id=paper_id)
        p.title_norm = normalize_title(new_title)
    elif "title" in payload and payload["title"] is None:
        raise HTTPException(status_code=422, detail="论文标题不能为空")
    new_doi = payload.get("doi")
    if new_doi and new_doi != p.doi:
        dup = db.query(Paper).filter(Paper.doi == new_doi, Paper.id != paper_id).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"DOI {new_doi} 已存在")
    for k, v in payload.items():
        setattr(p, k, v)
    if extra is not None:
        cf.save_extra(p, extra, db, "papers")
    db.commit()
    db.refresh(p)
    return paper_to_out(p)


@router.delete("/{paper_id}")
def delete_paper(paper_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    p = db.get(Paper, paper_id)
    if not p:
        raise HTTPException(status_code=404, detail="论文不存在")
    # 附件保留在文献库中，仅解除关联
    for att in db.query(Attachment).filter(Attachment.paper_id == paper_id).all():
        att.paper_id = None
    db.delete(p)
    db.commit()
    return {"ok": True}


def _apply_extraction_result(db: Session, extraction: AIExtraction, paper: Paper, user_id: int):
    """已废弃：保留为统一函数的薄壳，供批量提取路径直接调用。

    新代码请直接使用 ``extraction_apply.apply_extraction_result``。
    """
    return apply_extraction_result(db, extraction, paper, user_id, set_confirmed=True)


@router.post("/batch-extract")
def batch_extract_from_papers(
    paper_ids: List[int],
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """
    从论文列表触发 AI 提取：根据论文 ID 找到关联的 PDF（如无关联 PDF 则跳过），
    提取后自动应用结果（写入基金标注 + 标记通讯作者），同步执行（最多前 50 条）。
    """
    import io
    import json
    import time
    from pathlib import Path

    settings = ai_extract.get_llm_settings()
    if not settings["api_key"]:
        raise HTTPException(status_code=400, detail="未配置 IM_LLM_API_KEY 环境变量")

    processed = 0
    skipped = 0
    errors = []
    applied_funding = 0
    applied_corresponding = 0
    for paper_id in paper_ids[:50]:
        paper = db.get(Paper, paper_id)
        if not paper:
            errors.append(f"论文不存在(id={paper_id})")
            continue
        # 找该论文关联的 PDF
        att = db.query(Attachment).filter(Attachment.paper_id == paper_id, Attachment.att_type == "pdf").first()
        if not att:
            skipped += 1
            continue
        # 每次提取都创建新记录，不跳过已提取的
        extraction = db.query(AIExtraction).filter(AIExtraction.attachment_id == att.id).first()
        if extraction and extraction.status == "pending":
            created_at = extraction.created_at
            if created_at and (time.time() - created_at.timestamp() > 600):
                db.delete(extraction)
            else:
                skipped += 1
                continue

        try:
            pdf_path = Path(att.store_path)
            if not pdf_path.exists():
                errors.append(f"{att.filename}: 文件不存在")
                continue
            text = ai_extract.extract_text(io.BytesIO(pdf_path.read_bytes()))
        except Exception as e:
            errors.append(f"{att.filename}: PDF解析失败({e})")
            continue
        if not text.strip():
            errors.append(f"{att.filename}: 未提取到文本（可能是扫描件）")
            continue
        try:
            llm_result = ai_extract.call_llm(ai_extract.build_prompt(text), settings)
        except Exception as e:
            errors.append(f"{att.filename}: AI接口调用失败({e})")
            continue

        funding_matches = ai_extract.match_funding_projects(
            llm_result.get("funding_nos", []), db.query(Project).all()
        )
        corresponding_match = ai_extract.match_corresponding(
            llm_result.get("author", ""), db.query(Person).all()
        )
        extraction = AIExtraction(
            attachment_id=att.id,
            result_json=json.dumps(
                {
                    "author": llm_result.get("author"),
                    "funding_text": llm_result.get("funding_text", ""),
                    "funding_nos": llm_result.get("funding_nos", []),
                    "corresponding_match": corresponding_match,
                    "funding_matches": funding_matches,
                },
                ensure_ascii=False,
            ),
            model=settings["model"],
            status="pending",
        )
        db.add(extraction)
        db.flush()
        # 自动应用提取结果（写入基金标注 + 标记通讯作者）
        added, marked = _apply_extraction_result(db, extraction, paper, user.id)
        applied_funding += added
        if marked:
            applied_corresponding += 1
        processed += 1

    db.commit()
    parts = []
    if processed:
        parts.append(f"已提取并应用 {processed} 篇")
    if applied_funding:
        parts.append(f"写入基金标注 {applied_funding} 条")
    if applied_corresponding:
        parts.append(f"标记通讯作者 {applied_corresponding} 篇")
    if skipped:
        parts.append(f"跳过 {skipped} 个（无PDF或已提取）")
    if errors:
        parts.append(f"失败 {len(errors)} 个：{'；'.join(errors[:5])}")
    return {"message": " ".join(parts), "processed": processed, "skipped": skipped, "errors": errors}


@router.post("/batch-delete")
def batch_delete_papers(body: list[int], db: Session = Depends(get_db), _=Depends(require_admin)):
    """批量删除论文。"""
    if not body:
        raise HTTPException(status_code=400, detail="未选择要删除的记录")
    deleted = 0
    for paper_id in body:
        p = db.get(Paper, paper_id)
        if p:
            for att in db.query(Attachment).filter(Attachment.paper_id == paper_id).all():
                att.paper_id = None
            db.delete(p)
            deleted += 1
    db.commit()
    return {"deleted": deleted}


@router.post("/rematch-authors")
def rematch_authors(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
    full: bool = Query(True, description="清空全部旧关联后重新精确匹配"),
):
    """按姓名/英文名（含姓名变体）精确匹配人员库。

    默认 full=True：清空所有作者旧关联（含历史上模糊匹配的错误绑定），用精确
    匹配重新绑定；full=False 时仅回填 person_id 为空的记录，不动已有关联。
    """
    from .imports import _build_person_lookup, _match_person_in_lookup

    lookup = _build_person_lookup(db)
    q = db.query(PaperAuthor)
    cleared = 0
    if full:
        cleared = q.update({PaperAuthor.person_id: None})
        q = db.query(PaperAuthor)
    matched = 0
    for a in q.all():
        person = _match_person_in_lookup(lookup, a.author_name)
        if person:
            a.person_id = person.id
            matched += 1
    db.commit()
    return {"ok": True, "matched": matched, "cleared": cleared}


@router.post("/{paper_id}/authors", status_code=201)
def add_author(
    paper_id: int, body: PaperAuthorIn, db: Session = Depends(get_db), _=Depends(require_admin)
):
    if not db.get(Paper, paper_id):
        raise HTTPException(status_code=404, detail="论文不存在")
    if body.person_id and not db.get(Person, body.person_id):
        raise HTTPException(status_code=404, detail="人员不存在")
    db.add(PaperAuthor(paper_id=paper_id, **body.model_dump()))
    db.commit()
    return {"ok": True}


@router.delete("/{paper_id}/authors/{author_id}")
def remove_author(
    paper_id: int, author_id: int, db: Session = Depends(get_db), _=Depends(require_admin)
):
    a = db.get(PaperAuthor, author_id)
    if not a or a.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="作者记录不存在")
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.put("/{paper_id}/authors/{author_id}")
def update_author(
    paper_id: int,
    author_id: int,
    body: PaperAuthorIn,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    a = db.get(PaperAuthor, author_id)
    if not a or a.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="作者记录不存在")
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    db.commit()
    return {"ok": True}


@router.post("/{paper_id}/funding", status_code=201)
def add_funding(
    paper_id: int,
    body: PaperFundingIn,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    if not db.get(Paper, paper_id):
        raise HTTPException(status_code=404, detail="论文不存在")
    if body.project_id and not db.get(Project, body.project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    db.add(PaperFunding(paper_id=paper_id, **body.model_dump()))
    db.commit()
    return {"ok": True}


@router.delete("/{paper_id}/funding/{funding_id}")
def remove_funding(
    paper_id: int, funding_id: int, db: Session = Depends(get_db), _=Depends(require_admin)
):
    f = db.get(PaperFunding, funding_id)
    if not f or f.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="基金标注记录不存在")
    db.delete(f)
    db.commit()
    return {"ok": True}


@router.put("/{paper_id}/funding/{funding_id}")
def update_funding(
    paper_id: int,
    funding_id: int,
    body: PaperFundingIn,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    f = db.get(PaperFunding, funding_id)
    if not f or f.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="基金标注记录不存在")
    if body.project_id and not db.get(Project, body.project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    # 选了项目后 funding_no 自动用项目编号（统一事实来源）
    if f.project_id:
        proj = db.get(Project, f.project_id)
        if proj:
            f.funding_no = proj.project_no
    db.commit()
    return {"ok": True}
