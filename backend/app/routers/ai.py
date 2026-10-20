import hashlib
import io
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ai_extract
from ..config import UPLOAD_DIR
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..extraction_apply import apply_extraction_result
from ..models import (
    AIExtraction,
    Attachment,
    Paper,
    PaperAuthor,
    PaperFunding,
    Person,
    Project,
)

router = APIRouter(tags=["ai_extraction"])


def _load_result(e: AIExtraction) -> dict:
    try:
        return json.loads(e.result_json or "{}")
    except json.JSONDecodeError:
        return {}


def _to_out_with_att(e: AIExtraction, att: Attachment) -> dict:
    data = _load_result(e)
    return {
        "id": e.id,
        "paper_id": att.paper_id,
        "filename": att.filename,
        "model": e.model,
        "status": e.status,
        "created_at": e.created_at,
        "author": data.get("author"),
        "funding_text": data.get("funding_text"),
        "funding_nos": data.get("funding_nos", []),
        "corresponding_match": data.get("corresponding_match"),
        "funding_matches": data.get("funding_matches", []),
    }


@router.post("/papers/{paper_id}/extract")
def extract_from_pdf(
    paper_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """上传论文PDF，自动提取通讯作者与基金信息并匹配库内人员/项目。"""
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    settings = ai_extract.get_llm_settings()
    if not settings["api_key"]:
        raise HTTPException(
            status_code=400,
            detail="未配置 IM_LLM_API_KEY 环境变量，无法调用AI提取",
        )
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="仅支持PDF文件")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="文件为空")

    try:
        text = ai_extract.extract_text(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF解析失败: {e}")
    if not text.strip():
        raise HTTPException(status_code=422, detail="PDF中未提取到文本（可能是扫描件）")

    try:
        llm_result = ai_extract.call_llm(ai_extract.build_prompt(text), settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI接口调用失败: {e}")

    funding_matches = ai_extract.match_funding_projects(
        llm_result.get("funding_nos", []), db.query(Project).all()
    )
    corresponding_match = ai_extract.match_corresponding(
        llm_result.get("author", ""), db.query(Person).all()
    )

    sha = hashlib.sha256(data).hexdigest()

    # 一篇论文最多一个 PDF：解除该论文已有 PDF 的关联（旧文件留在文献库，不删）
    from .pdfs import ensure_one_pdf_per_paper

    # 内容去重：同 sha256 的 PDF 已存在则复用，不重复落盘
    att = (
        db.query(Attachment)
        .filter(
            Attachment.att_type == "pdf",
            Attachment.entity_type.is_(None),
            Attachment.sha256 == sha,
        )
        .first()
    )
    if att:
        # 复用已有附件：更新文件名为本次上传名，并关联到当前论文（1:1）
        att.filename = file.filename
        att.uploader_id = user.id
        att.paper_id = paper_id
    else:
        store_name = f"paper_{paper_id}_{uuid.uuid4().hex[:8]}.pdf"
        store_path = UPLOAD_DIR / store_name
        store_path.write_bytes(data)
        att = Attachment(
            att_type="pdf",
            filename=file.filename,
            store_path=str(store_path),
            sha256=sha,
            size=len(data),
            paper_id=paper_id,
            uploader_id=user.id,
        )
        db.add(att)
        db.flush()
    ensure_one_pdf_per_paper(db, paper_id, keep_id=att.id)

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
    db.commit()
    db.refresh(extraction)

    data_out = _load_result(extraction)
    data_out["extraction_id"] = extraction.id
    data_out["attachment_id"] = att.id
    return data_out


@router.post("/attachments/{attachment_id}/re-extract")
def re_extract_from_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """对已上传的 PDF 重新进行 AI 提取（无论之前是否已提取）。"""
    att = db.get(Attachment, attachment_id)
    if not att or att.att_type != "pdf":
        raise HTTPException(status_code=404, detail="PDF 不存在")
    if not att.paper_id:
        raise HTTPException(status_code=422, detail="PDF 未关联论文，请先关联后再提取")
    paper = db.get(Paper, att.paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="关联的论文不存在")

    settings = ai_extract.get_llm_settings()
    if not settings["api_key"]:
        raise HTTPException(status_code=400, detail="未配置 IM_LLM_API_KEY 环境变量")

    pdf_path = Path(att.store_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=422, detail="PDF 文件不存在")

    try:
        text = ai_extract.extract_text(io.BytesIO(pdf_path.read_bytes()))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF解析失败: {e}")
    if not text.strip():
        raise HTTPException(status_code=422, detail="PDF 中未提取到文本（可能是扫描件）")

    try:
        llm_result = ai_extract.call_llm(ai_extract.build_prompt(text), settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI接口调用失败: {e}")

    funding_matches = ai_extract.match_funding_projects(
        llm_result.get("funding_nos", []), db.query(Project).all()
    )
    corresponding_match = ai_extract.match_corresponding(
        llm_result.get("author", ""), db.query(Person).all()
    )

    # 创建新提取记录，原有记录保留
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

    # 自动应用结果（re-extract 路径：保持 status=pending，不自动 confirmed）
    apply_extraction_result(db, extraction, paper, user.id, set_confirmed=False)

    db.commit()
    db.refresh(extraction)
    data_out = _load_result(extraction)
    data_out["extraction_id"] = extraction.id
    return data_out


@router.post("/extractions/{extraction_id}/apply")
def apply_extraction(
    extraction_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """自动应用提取结果：写入论文-基金关系、标记通讯作者，无需人工确认。"""
    e = db.get(AIExtraction, extraction_id)
    if not e:
        raise HTTPException(status_code=404, detail="提取记录不存在")
    att = db.get(Attachment, e.attachment_id)
    if not att or not att.paper_id:
        raise HTTPException(status_code=404, detail="关联论文不存在")
    paper = db.get(Paper, att.paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="关联论文已被删除")

    added_funding, marked_corresponding = apply_extraction_result(
        db, e, paper, user.id, set_confirmed=True
    )
    db.commit()
    return {
        "ok": True,
        "added_funding": added_funding,
        "marked_corresponding": marked_corresponding,
        "paper_id": paper.id,
    }


def fuzz_match(name_a: str, name_b: str) -> bool:
    """已废弃：保留为兼容入口；新代码用 extraction_apply.apply_extraction_result。"""
    from thefuzz import fuzz


    from ..config import AUTHOR_MATCH_THRESHOLD

    return (
        fuzz.token_set_ratio((name_a or "").lower(), (name_b or "").lower())
        >= AUTHOR_MATCH_THRESHOLD
    )


@router.get("/papers/{paper_id}/extractions")
def list_extractions(
    paper_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    rows = (
        db.query(AIExtraction, Attachment)
        .join(Attachment, Attachment.id == AIExtraction.attachment_id)
        .filter(Attachment.paper_id == paper_id)
        .order_by(AIExtraction.id.desc())
        .all()
    )
    out = []
    for e, att in rows:
        out.append(_to_out_with_att(e, att))
    return out
