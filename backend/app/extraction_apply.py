"""AI 提取结果应用到论文的唯一入口。

三处端点（routers/papers.py 的 batch-extract、routers/ai.py 的 re-extract 与
apply_extraction）都调用本模块的 ``apply_extraction_result``，避免历史上多次
出现的"逻辑漂移"（如 acknowledgements 写入条件在不同端点不同）。

行为约定（与 README "AI 提取致谢原文" 条目一致）：
- 基金标注：只写 matched=True 的项；同 (paper_id, project_id) 已存在则跳过；
  source=auto / confirmed=True。
- 通讯作者：优先按 person_id 命中 PaperAuthor；找不到则按 fuzz 兜底（阈值
  AUTHOR_MATCH_THRESHOLD）；命中后置 is_corresponding=True。
- 致谢原文 / 通讯作者原文：有内容时**无条件覆盖**（不再用
  ``not paper.acknowledgements`` 守卫——已确认正确）。
- confirmed 标记：set_confirmed=True 且"实际有产出"（新增标注 / 标记通讯 /
  有 author / 有 funding / 有 funding_text）时，extraction.status=confirmed、
  paper.extract_status="已提取"。
"""

from __future__ import annotations

import json
from typing import Tuple

from sqlalchemy.orm import Session

from .config import AUTHOR_MATCH_THRESHOLD
from .models import AIExtraction, Paper, PaperAuthor, PaperFunding


def _load_result(extraction: AIExtraction) -> dict:
    try:
        return json.loads(extraction.result_json or "{}")
    except json.JSONDecodeError:
        return {}


def _fuzz_match(name_a: str, name_b: str) -> bool:
    """通讯作者兜底模糊匹配（与 ai.py 旧 fuzz_match 等价）。"""
    from thefuzz import fuzz

    return (
        fuzz.token_set_ratio((name_a or "").lower(), (name_b or "").lower())
        >= AUTHOR_MATCH_THRESHOLD
    )


def apply_extraction_result(
    db: Session,
    extraction: AIExtraction,
    paper: Paper,
    user_id: int,
    set_confirmed: bool = True,
) -> Tuple[int, int]:
    """把单次 AIExtraction 的结果应用到论文，返回 (added_funding, marked_corresponding)。

    - set_confirmed=True：批量提取/apply 端点用，写入后标 confirmed + extract_status="已提取"
    - set_confirmed=False：re-extract 端点用，只应用结果不动 status（保留 pending 语义）
    """
    data = _load_result(extraction)

    # ── 基金标注：写 PaperFunding 关系表（matched=True 才写，去重）──
    added_funding = 0
    for m in data.get("funding_matches", []):
        if not m.get("matched"):
            continue
        dup = (
            db.query(PaperFunding)
            .filter(
                PaperFunding.paper_id == paper.id,
                PaperFunding.project_id == m["project_id"],
            )
            .first()
        )
        if dup:
            continue
        db.add(
            PaperFunding(
                paper_id=paper.id,
                project_id=m["project_id"],
                funding_no=m.get("project_no"),
                seq=m["seq"],
                source="auto",
                confirmed=True,
            )
        )
        added_funding += 1

    # ── 通讯作者：先按 person_id 命中；找不到则按 fuzz 兜底 ──
    marked = False
    match = data.get("corresponding_match")
    if match and match.get("person_id"):
        rows = (
            db.query(PaperAuthor)
            .filter(
                PaperAuthor.paper_id == paper.id,
                PaperAuthor.person_id == match["person_id"],
            )
            .all()
        )
        if not rows:
            rows = [
                a
                for a in db.query(PaperAuthor).filter(PaperAuthor.paper_id == paper.id)
                if _fuzz_match(a.author_name, match.get("matched_name", ""))
            ]
        if rows:
            for r in rows:
                r.is_corresponding = True
            marked = True

    # ── 致谢原文 / 通讯作者原文：无条件覆盖（README 已确认此为正确行为）──
    funding_text = data.get("funding_text") or ""
    if funding_text.strip().lower() not in ("", "not found"):
        paper.acknowledgements = funding_text

    author_text = data.get("author") or ""
    if author_text.strip().lower() not in ("", "not found"):
        paper.corresponding_text = author_text

    # ── confirmed 标记：实际有产出且调用方要求时才置位 ──
    has_author = bool(data.get("author") and data["author"].lower() != "not found")
    has_funding = bool(data.get("funding_nos") and len(data["funding_nos"]) > 0)
    has_funding_text = funding_text.strip().lower() not in ("", "not found")
    if set_confirmed and (
        added_funding or marked or has_author or has_funding or has_funding_text
    ):
        extraction.status = "confirmed"
        extraction.confirmer_id = user_id
        paper.extract_status = "已提取"

    return added_funding, marked
