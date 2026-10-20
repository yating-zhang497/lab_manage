"""基金标注关系的唯一写入口：把致谢中的项目编号落到 paper_funding 关系表。

编号 → 项目 的匹配规则与 AI 提取保持一致（去空格、大写比对）。
"""

import re

from sqlalchemy.orm import Session

from .models import Paper, PaperFunding, Project


def normalize_project_no(no) -> str:
    return re.sub(r"\s+", "", (no or "").strip().upper())


def project_no_index(db: Session) -> dict:
    """项目编号(归一化) -> Project 的查找表；过短编号不入表避免误匹配。"""
    index = {}
    for p in db.query(Project).all():
        key = normalize_project_no(p.project_no)
        if len(key) >= 5:
            index.setdefault(key, p)
    return index


def link_funding_by_numbers(
    db: Session,
    paper: Paper,
    numbers: list,
    source: str = "import",
    seqs: list = None,
) -> int:
    """按编号列表为论文建立/补全基金标注关系，返回新增条数。

    numbers 第 i 项默认对应标注顺序 i（一标/二标/三标）；
    提供 seqs 时以其中第 i 项的整数为标注顺序（空/非法时回退默认位置）。
    已存在的同项目或同原文编号的标注不重复创建。
    """
    index = project_no_index(db)
    added = 0
    for i, num in enumerate(numbers, start=1):
        num = (num or "").strip()
        if not num:
            continue
        seq = i
        if seqs is not None and i - 1 < len(seqs):
            try:
                seq = int(str(seqs[i - 1]).strip()) or i
            except ValueError:
                seq = i
        proj = index.get(normalize_project_no(num))
        dup = (
            db.query(PaperFunding)
            .filter(PaperFunding.paper_id == paper.id)
            .filter(
                (PaperFunding.project_id == proj.id)
                if proj
                else (PaperFunding.funding_no == num)
            )
            .first()
        )
        if dup:
            if not dup.seq:
                dup.seq = seq
            continue
        db.add(
            PaperFunding(
                paper_id=paper.id,
                project_id=proj.id if proj else None,
                funding_no=proj.project_no if proj else num,
                seq=seq,
                source=source,
                confirmed=True,
            )
        )
        added += 1
    return added
