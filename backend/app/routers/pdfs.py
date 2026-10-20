"""PDF 库管理：列表、上传、匹配、删除。"""

import hashlib
import io
import re
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, aliased

from ..config import UPLOAD_DIR
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import AIExtraction, Attachment, Paper

router = APIRouter(prefix="/pdfs", tags=["pdfs"])


# ─── Helpers ────────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm_text(s: str) -> str:
    """归一化文本用于匹配：去除 LaTeX 公式/命令、统一小写、非字母数字替换为空格。"""
    s = re.sub(r"\$[^$]*\$", " ", s)        # 去除行内数学 $...$（如 $^\circ$）
    s = re.sub(r"\\[a-zA-Z]+", " ", s)       # 去除 LaTeX 命令（如 \textbf）
    s = re.sub(r"[\W_]+", " ", s).strip()     # 非字母数字 → 空格
    return s.lower()


def _match_paper_by_filename(db: Session, filename: str, papers: list = None) -> Optional[Paper]:
    """用清理后的文件名匹配论文标题（大小写/标点/连字符不敏感，含模糊兜底）。

    三级策略（2/3 取最高分再返回，避免通用词首匹配误命中）：
    1. 标题去标点后完整包含在文件名中 → 高置信，直接命中
    2. 词级交集：标题显著词 ≥60% 出现在文件名中（词级匹配，非子串）
    3. 模糊兜底：fuzz.token_set_ratio ≥ 80

    papers: 预加载的候选论文列表（批量匹配时传入避免逐条查库）；缺省则现场查库。
    """
    fn = re.sub(r"\.(pdf|PDF)$", "", filename)
    fn_norm = _norm_text(fn)
    if len(fn_norm) < 4:
        return None
    from thefuzz import fuzz

    fn_compact = re.sub(r"\s+", "", fn_norm)
    fn_words = {w for w in fn_norm.split() if len(w) >= 3}
    candidates = papers if papers is not None else db.query(Paper).all()

    best_match = None
    best_score = 0
    for p in candidates:
        p_title = (p.title or "").strip()
        if not p_title:
            continue
        p_norm = _norm_text(p_title)

        # 1. 标题去标点后完整包含在文件名中（高置信，直接返回）
        p_compact = re.sub(r"\s+", "", p_norm)
        if p_compact and len(p_compact) >= 8 and p_compact in fn_compact:
            return p

        # 2. 词级交集：标题显著词在文件名中出现的比例
        p_words = {w for w in p_norm.split() if len(w) >= 3}
        if p_words:
            overlap = len(p_words & fn_words)
            ratio = overlap / len(p_words)
            # 标题词数 <3 时要求全部命中；≥3 时至少命中 3 个且比例 ≥60%
            min_overlap = len(p_words) if len(p_words) < 3 else 3
            if ratio >= 0.6 and overlap >= min_overlap:
                score = int(ratio * 100)
                if score > best_score:
                    best_score = score
                    best_match = p

        # 3. 模糊兜底：容忍大小写、标点、词序差异
        if p_norm:
            score = fuzz.token_set_ratio(fn_norm, p_norm)
            if score >= 80 and score > best_score:
                best_score = score
                best_match = p

    return best_match


def _attachment_out_with_db(db: Session, att: Attachment) -> dict:
    extraction = (
        db.query(AIExtraction)
        .filter(AIExtraction.attachment_id == att.id)
        .order_by(AIExtraction.id.desc())
        .first()
    )
    out = {
        "id": att.id,
        "filename": att.filename,
        "size": att.size,
        "sha256": att.sha256,
        "paper_id": att.paper_id,
        "paper_title": None,
        "uploader_id": att.uploader_id,
        "created_at": att.created_at.isoformat() if att.created_at else None,
        "extraction_status": None,
        "extraction_id": None,
    }
    if att.paper_id:
        paper = db.get(Paper, att.paper_id)
        if paper:
            out["paper_title"] = paper.title
    if extraction:
        out["extraction_status"] = extraction.status
        out["extraction_id"] = extraction.id
    return out


# ─── Routes ─────────────────────────────────────────────────────────────────

def ensure_one_pdf_per_paper(db: Session, paper_id: int, keep_id: Optional[int] = None) -> int:
    """一篇论文最多关联一个 PDF：把该论文已关联的其它 PDF 解除关联（paper_id=None）。

    keep_id 指定保留的那条（新关联的）；被解除的 PDF 仍在文献库中，不删文件。
    返回被解除关联的数量。
    """
    q = db.query(Attachment).filter(
        Attachment.att_type == "pdf",
        Attachment.entity_type.is_(None),
        Attachment.paper_id == paper_id,
    )
    if keep_id is not None:
        q = q.filter(Attachment.id != keep_id)
    removed = 0
    for att in q.all():
        att.paper_id = None
        removed += 1
    return removed


@router.get("")
def list_pdfs(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    paper_id: Optional[int] = None,
    statuses: Optional[List[str]] = Query(default=None),
    filename: Optional[str] = Query(None, description="按文件名模糊搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    """
    PDF 列表，支持筛选和分页。

    - paper_id: 只显示关联到某论文的 PDF
    - statuses: 状态列表，未关联(unmatched)/已关联(matched)/提取中(pending)/已提取(extracted)
    - filename: 按文件名模糊搜索

    实现用一条 JOIN 查询同时带 Attachment + 最新 AIExtraction，避免原 N+1
    （每条 attachment 单独查 AIExtraction 与 Paper）。Paper 标题最后批量查一次。
    """
    # 子查询：每条 attachment 对应的最新 AIExtraction id
    latest_ext_subq = (
        db.query(
            AIExtraction.attachment_id.label("aid"),
            func.max(AIExtraction.id).label("max_ext_id"),
        )
        .group_by(AIExtraction.attachment_id)
        .subquery()
    )
    LatestExt = aliased(AIExtraction)

    q = (
        db.query(Attachment, LatestExt)
        .outerjoin(latest_ext_subq, Attachment.id == latest_ext_subq.c.aid)
        .outerjoin(LatestExt, LatestExt.id == latest_ext_subq.c.max_ext_id)
        .filter(
            Attachment.att_type == "pdf",
            Attachment.entity_type.is_(None),
        )
    )
    if paper_id is not None:
        q = q.filter(Attachment.paper_id == paper_id)
    if filename:
        q = q.filter(Attachment.filename.ilike(f"%{filename}%"))

    # statuses 筛选：转成 SQL 条件，避免取回全部 Python 端再过滤
    if statuses:
        conds = []
        for st in statuses:
            if st == "unmatched":
                conds.append(Attachment.paper_id.is_(None))
            elif st == "matched":
                conds.append(
                    and_(Attachment.paper_id.isnot(None), LatestExt.id.is_(None))
                )
            elif st == "extracted":
                conds.append(LatestExt.status == "confirmed")
            elif st == "pending":
                conds.append(LatestExt.status == "pending")
        if conds:
            q = q.filter(or_(*conds))

    total = q.count()
    rows = (
        q.order_by(Attachment.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
        .all()
    )

    # 批量取 paper_title（同 paper_id 集合一次 IN 查询）
    paper_ids = {att.paper_id for att, _ in rows if att.paper_id}
    paper_map = {}
    if paper_ids:
        for p in db.query(Paper).filter(Paper.id.in_(paper_ids)).all():
            paper_map[p.id] = p.title

    out = []
    for att, ext in rows:
        out.append({
            "id": att.id,
            "filename": att.filename,
            "size": att.size,
            "sha256": att.sha256,
            "paper_id": att.paper_id,
            "paper_title": paper_map.get(att.paper_id) if att.paper_id else None,
            "uploader_id": att.uploader_id,
            "created_at": att.created_at.isoformat() if att.created_at else None,
            "extraction_status": ext.status if ext else None,
            "extraction_id": ext.id if ext else None,
        })

    return {"total": total, "page": page, "page_size": page_size, "rows": out}


@router.post("")
def upload_pdfs(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """
    批量上传 PDF，自动按文件名匹配论文，返回匹配结果列表。
    文件名去重：同名文件直接跳过，不重复上传。
    """
    results = []
    for file in files:
        if not (file.filename or "").lower().endswith(".pdf"):
            results.append({"filename": file.filename, "status": "skipped", "reason": "非 PDF 文件"})
            continue
        data = file.file.read()
        if not data:
            results.append({"filename": file.filename, "status": "skipped", "reason": "文件为空"})
            continue

        # 文件名去重：同名文件直接跳过，不重复上传
        existing_by_name = (
            db.query(Attachment)
            .filter(
                Attachment.att_type == "pdf",
                Attachment.entity_type.is_(None),
                Attachment.filename == file.filename,
            )
            .first()
        )
        if existing_by_name:
            dup_paper = db.get(Paper, existing_by_name.paper_id) if existing_by_name.paper_id else None
            results.append({
                "filename": file.filename,
                "status": "duplicate",
                "attachment_id": existing_by_name.id,
                "paper_id": existing_by_name.paper_id,
                "paper_title": dup_paper.title if dup_paper else None,
            })
            continue

        sha = _sha256(data)

        # 内容去重：同 sha256 的 PDF（即使文件名不同）视为重复，不重复入库
        existing_by_sha = (
            db.query(Attachment)
            .filter(
                Attachment.att_type == "pdf",
                Attachment.entity_type.is_(None),
                Attachment.sha256 == sha,
            )
            .first()
        )
        if existing_by_sha:
            dup_paper = db.get(Paper, existing_by_sha.paper_id) if existing_by_sha.paper_id else None
            results.append({
                "filename": file.filename,
                "status": "duplicate",
                "reason": "内容已存在",
                "attachment_id": existing_by_sha.id,
                "paper_id": existing_by_sha.paper_id,
                "paper_title": dup_paper.title if dup_paper else None,
            })
            continue

        # auto-match paper
        paper = _match_paper_by_filename(db, file.filename)
        if paper:
            # 一篇论文最多一个 PDF：已有关联 PDF 的论文不自动绑定
            existing = db.query(Attachment).filter(
                Attachment.att_type == "pdf",
                Attachment.entity_type.is_(None),
                Attachment.paper_id == paper.id,
            ).first()
            if existing:
                paper = None

        # 服务端生成安全文件名，避免原始文件名中的路径穿越/非法字符
        suffix = Path(file.filename or "f.pdf").suffix.lower() or ".pdf"
        store_name = f"pdf_{uuid.uuid4().hex[:12]}{suffix}"
        store_path = UPLOAD_DIR / store_name
        store_path.write_bytes(data)

        att = Attachment(
            att_type="pdf",
            filename=file.filename,
            store_path=str(store_path),
            sha256=sha,
            size=len(data),
            paper_id=paper.id if paper else None,
            uploader_id=user.id,
        )
        db.add(att)
        db.flush()

        results.append({
            "filename": file.filename,
            "status": "ok",
            "attachment_id": att.id,
            "paper_id": paper.id if paper else None,
            "paper_title": paper.title if paper else None,
            "matched": paper is not None,
        })

    db.commit()
    return {"files": results}


@router.get("/batch-download")
def batch_download_pdfs(
    ids: str = Query(..., description="逗号分隔的 attachment_id"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """批量下载多个 PDF（返回 zip 包）。"""
    id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="未指定要下载的文件")
    if len(id_list) > 50:
        raise HTTPException(status_code=400, detail="单次最多下载 50 个文件")

    # 创建内存 zip
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for att_id in id_list:
            att = db.get(Attachment, att_id)
            if not att or att.att_type != "pdf":
                continue
            p = Path(att.store_path)
            if not p.exists():
                continue
            # 重名文件加序号区分；取 basename 防止路径穿越
            base_name = Path(att.filename or f"{att_id}.pdf").name
            zf.write(p, base_name)
    zip_buf.seek(0)
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=pdfs.zip"},
    )


@router.get("/{attachment_id}")
def get_pdf(
    attachment_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    att = db.get(Attachment, attachment_id)
    if not att or att.att_type != "pdf":
        raise HTTPException(status_code=404, detail="PDF 不存在")
    return _attachment_out_with_db(db, att)


@router.get("/{attachment_id}/file")
def serve_pdf_file(
    attachment_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    att = db.get(Attachment, attachment_id)
    if not att or att.att_type != "pdf":
        raise HTTPException(status_code=404, detail="PDF 不存在")
    p = Path(att.store_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(p, media_type="application/pdf", filename=att.filename)


@router.delete("/{attachment_id}")
def delete_pdf(
    attachment_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    att = db.get(Attachment, attachment_id)
    if not att or att.att_type != "pdf":
        raise HTTPException(status_code=404, detail="PDF 不存在")
    # 删除物理文件
    p = Path(att.store_path)
    if p.exists():
        p.unlink()
    db.delete(att)
    db.commit()
    return {"ok": True}


@router.put("/{attachment_id}/link")
def link_pdf_to_paper(
    attachment_id: int,
    paper_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """手动将 PDF 关联到指定论文。"""
    att = db.get(Attachment, attachment_id)
    if not att or att.att_type != "pdf":
        raise HTTPException(status_code=404, detail="PDF 不存在")
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    # 一篇论文最多一个 PDF：先解除该论文已有 PDF 的关联，再关联新的
    ensure_one_pdf_per_paper(db, paper_id)
    att.paper_id = paper_id
    db.commit()
    return {"ok": True, "paper_id": paper_id}


@router.put("/batch-link")
def batch_link_pdfs(
    attachment_ids: List[int] = Body(..., embed=True),
    paper_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """批量将多个 PDF 关联到同一篇论文。

    一篇论文最多一个 PDF：保留最后一条关联，其余（含旧关联）解除。
    """
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    linked = 0
    last_id = None
    for aid in attachment_ids:
        att = db.query(Attachment).filter(Attachment.id == aid, Attachment.att_type == "pdf").first()
        if att:
            att.paper_id = paper_id
            linked += 1
            last_id = att.id
    # flush 让上面的 paper_id 修改对后续查询可见（会话 autoflush=False）
    db.flush()
    # 只保留最后一条，其余（含旧关联 + 本次多条）解除
    ensure_one_pdf_per_paper(db, paper_id, keep_id=last_id)
    db.commit()
    return {"ok": True, "linked": linked, "paper_id": paper_id}


@router.post("/auto-match")
def auto_match_pdfs(
    body: dict = Body(default={}),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """按文件名批量自动匹配未关联论文的 PDF。

    - body.ids: 指定则只匹配这些 PDF；缺省则匹配全部未关联的论文库 PDF。
    - 仅处理 paper_id 为空的 PDF，已关联的不会被重新匹配（保留手动关联）。
    - 匹配不上的返回明细，前端可引导用户走"关联论文"手动选择。
    """
    ids = (body or {}).get("ids") or []
    q = db.query(Attachment).filter(
        Attachment.att_type == "pdf",
        Attachment.entity_type.is_(None),
        Attachment.paper_id.is_(None),
    )
    if ids:
        q = q.filter(Attachment.id.in_(ids))
    targets = q.all()
    # 一次性预加载论文，避免逐个 PDF 重复全表查询
    papers = db.query(Paper).all()
    matched = 0
    unmatched = []
    for att in targets:
        paper = _match_paper_by_filename(db, att.filename, papers)
        if paper:
            # 一篇论文最多一个 PDF：已有关联 PDF 的论文不再自动绑定新的
            existing = db.query(Attachment).filter(
                Attachment.att_type == "pdf",
                Attachment.entity_type.is_(None),
                Attachment.paper_id == paper.id,
                Attachment.id != att.id,
            ).first()
            if existing:
                unmatched.append({"id": att.id, "filename": att.filename})
                continue
            att.paper_id = paper.id
            matched += 1
        else:
            unmatched.append({"id": att.id, "filename": att.filename})
    db.commit()
    return {
        "matched": matched,
        "unmatched_count": len(unmatched),
        "unmatched": unmatched,
    }


