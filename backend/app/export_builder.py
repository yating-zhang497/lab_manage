"""自定义列导出：把跨表关联信息展平成一张可选字段的大表。

可选字段目录 = 模块当前字段定义（字段管理中的启用/改名/排序）+ 关联派生列。
派生列按"多值维度"标注：同一次导出最多选择一个维度的多值（列表型）列，
否则不同关联（如作者列表与项目标注列表）无法在一张二维表中清晰对应。

选中某个多值维度的列时，导出按"一行一条关联项"展开：每个实体拆成 N 行
（N = 该维度下的关联项数），实体的标量字段在每行重复，该维度的列只填本行
对应的那一项；未选任何多值维度列时仍是"一个实体一行"。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .custom_fields import defs_for, parse_extra
from .models import (
    AwardRecipient,
    Paper,
    PaperAuthor,
    PaperFunding,
    Person,
    Project,
    ProjectMember,
)

MODULE_LABEL = {"papers": "论文", "people": "人员", "projects": "项目", "ip": "知识产权", "awards": "奖励荣誉"}

# 位置型列的上限，避免单篇论文作者过多时生成太多列
MAX_AUTHOR_POSITIONS = 15
MAX_FUNDING_POSITIONS = 5

# 关联派生列: (key, 显示名, 分组, 多值维度 or None)
# 维度非 None 表示该列是"1对多列表"，同时选择两个及以上维度的列表列会被拒绝导出
# 注意：论文的位置型列（author_N / project_no_N / project_seq_N）由 _paper_position_columns 动态生成
RELATION_COLUMNS = {
    "papers": [
        ("authors_full", "作者署名", "作者关联", "作者"),
        ("team_names", "作者姓名", "作者关联", "作者"),
        ("team_uids", "作者学号/工号", "作者关联", "作者"),
        ("team_english", "作者英文名", "作者关联", "作者"),
        ("corresponding_name", "通讯作者", "作者关联", None),
        ("corresponding_uid", "通讯作者学号/工号", "作者关联", None),
        ("corresponding_names", "通讯作者姓名", "作者关联", "作者"),
        ("corresponding_uids", "通讯作者学号/工号", "作者关联", "作者"),
        ("project_names", "标注项目名称", "项目标注", "项目"),
        ("project_nos", "标注项目编号", "项目标注", "项目"),
        ("funding_seqs", "标注顺序(一标=1)", "项目标注", "项目"),
        ("funding_labels", "标注项目[顺序]", "项目标注", "项目"),
        ("funding_nos", "项目编号(致谢原文)", "项目标注", "项目"),
    ],
    "people": [
        ("name_variants", "姓名变体", "人员字段", None),
        ("paper_count", "论文作者次数", "论文关联", None),
        ("first_author_count", "一作次数", "论文关联", None),
        ("corresponding_count", "通讯作者次数", "论文关联", None),
        ("paper_titles", "参与论文标题", "论文关联", "论文"),
        ("award_names", "获奖名称", "获奖关联", "获奖"),
        ("award_details", "获奖详情(等级/时间/作品)", "获奖关联", "获奖"),
        ("award_ranks", "本人排名", "获奖关联", "获奖"),
        ("award_all_awardees", "所有获奖人", "获奖关联", "获奖"),
        ("award_issuers", "颁奖单位", "获奖关联", "获奖"),
        ("award_cert_nos", "证书编号", "获奖关联", "获奖"),
        ("award_pr_urls", "公示链接", "获奖关联", "获奖"),
        ("project_names", "参与项目", "项目关联", "项目"),
    ],
    "projects": [
        ("member_names", "成员姓名", "成员", "成员"),
        ("member_uids", "成员学号/工号", "成员", "成员"),
        ("member_roles", "成员角色", "成员", "成员"),
        ("paper_count", "资助论文数", "论文关联", None),
        ("first_label_count", "一标论文数", "论文关联", None),
        ("paper_titles", "资助论文标题", "论文关联", "论文"),
        ("funding_seqs", "标注顺序(一标=1)", "论文关联", "论文"),
    ],
    "ip": [
        ("first_inventor", "第一发明人", "人员关联", None),
        ("inventor_names", "发明人/著作权人", "人员关联", "人员"),
        ("inventor_uids", "发明人学号/工号", "人员关联", "人员"),
        ("funding_nos", "标注基金号", "项目标注", "项目"),
    ],
    "awards": [
        ("recipient_names", "获奖人", "获奖人关联", "人员"),
        ("recipient_uids", "获奖人学号/工号", "获奖人关联", "人员"),
    ],
}


def _paper_position_columns(db: Session) -> list:
    """根据当前数据库中论文的最大作者数和最大基金标注数，动态生成位置型列。

    author_1..N / project_no_1..M / project_seq_1..M 均为标量列（dim=None），
    可与其他任意维度列自由组合。
    """
    author_sub = (
        db.query(PaperAuthor.paper_id, func.count(PaperAuthor.id).label("cnt"))
        .group_by(PaperAuthor.paper_id)
        .subquery()
    )
    max_authors = db.query(func.max(author_sub.c.cnt)).scalar() or 0
    max_authors = min(max_authors, MAX_AUTHOR_POSITIONS)

    funding_sub = (
        db.query(PaperFunding.paper_id, func.count(PaperFunding.id).label("cnt"))
        .group_by(PaperFunding.paper_id)
        .subquery()
    )
    max_funding = db.query(func.max(funding_sub.c.cnt)).scalar() or 0
    max_funding = min(max_funding, MAX_FUNDING_POSITIONS)

    cols = []
    for i in range(1, max_authors + 1):
        cols.append({"key": f"author_{i}", "label": f"作者{i}", "group": "作者关联", "dim": None})
    for i in range(1, max_funding + 1):
        cols.append({"key": f"project_no_{i}", "label": f"项目编号{i}", "group": "项目标注", "dim": None})
        cols.append({"key": f"project_seq_{i}", "label": f"项目编号{i}对应排序", "group": "项目标注", "dim": None})
    return cols


def export_columns_for(db: Session, type_: str) -> list:
    """导出字段目录：模块字段定义（与其他模块一致）+ 关联派生列。"""
    cols = [
        {
            "key": f["key"] if f["builtin"] else f"extra:{f['key']}",
            "label": f["label"],
            "group": f"{MODULE_LABEL[type_]}字段",
            "dim": None,
        }
        for f in defs_for(db, type_)
    ]
    # 论文的位置型列（author_N / project_no_N）按实际数据动态生成
    if type_ == "papers":
        cols += _paper_position_columns(db)
    cols += [
        {"key": k, "label": label, "group": group, "dim": dim}
        for k, label, group, dim in RELATION_COLUMNS[type_]
    ]
    return cols


def conflict_dims(type_: str, columns: list) -> list:
    """所选列涉及的多值关联维度；多于一个时对应关系无法在二维表中表达。"""
    selected = set(columns)
    return sorted(
        {dim for k, _, _, dim in RELATION_COLUMNS[type_] if dim and k in selected}
    )


def selected_dim(type_: str, columns: list) -> Optional[str]:
    """所选列命中的多值维度（conflict_dims 已保证最多一个）。

    返回该维度名或 None；有维度时导出按"一行一条关联项"展开。
    """
    dims = conflict_dims(type_, columns)
    return dims[0] if dims else None


def _funding_no_of(f) -> Optional[str]:
    """基金号以项目库唯一标识为准，未关联项目时回退致谢原文编号。"""
    if f.project and f.project.project_no:
        return f.project.project_no
    return f.funding_no


def _paper_base_row(p: Paper) -> dict:
    """论文标量字段：内置列 + 自定义 + 位置型列 + 标量关联（corresponding_name 等）。

    多值关联列（作者/项目维度）不在此处，由 _paper_dim_rows 按维度逐项展开。
    """
    authors = sorted(p.authors, key=lambda a: a.seq or 0)
    corr = [a for a in authors if a.is_corresponding]
    funding = sorted(p.funding, key=lambda f: f.seq or 99)
    # 内置字段与数据库列同名：先装入全部模型列，避免新增内置字段时遗漏
    # （否则该字段在导出目录里出现却取不到值，恒为空——历史回归 bug 根因）
    row = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    row["_extra"] = parse_extra(p)
    row["corresponding_name"] = (
        (corr[0].person.name if corr[0].person else corr[0].author_name)
        if corr else None
    )
    row["corresponding_uid"] = (
        corr[0].person.uid
        if corr and corr[0].person and corr[0].person.uid
        else None
    )
    # 位置型列：按实际作者/基金标注数量动态生成（上限由 MAX_*_POSITIONS 控制）
    for i, a in enumerate(authors, 1):
        if i > MAX_AUTHOR_POSITIONS:
            break
        row[f"author_{i}"] = a.author_name
    for i, f in enumerate(funding, 1):
        if i > MAX_FUNDING_POSITIONS:
            break
        row[f"project_no_{i}"] = _funding_no_of(f)
        row[f"project_seq_{i}"] = f.seq
    return row


def _paper_dim_rows(p: Paper, dim: str) -> list:
    """按维度展开成多行（一行一个关联项）；无关联项时返回一行空值以保留实体本身。"""
    if dim == "作者":
        authors = sorted(p.authors, key=lambda a: a.seq or 0)
        if not authors:
            # 无结构化作者但留有原文署名时，用原文占一行
            return [{"authors_full": p.authors_raw or None}]
        rows = []
        for a in authors:
            rows.append({
                "authors_full": a.author_name,
                "team_names": a.person.name if a.person else None,
                "team_uids": a.person.uid if a.person and a.person.uid else None,
                "team_english": (a.person.english_name or a.author_name) if a.person else a.author_name,
                "corresponding_names": (
                    (a.person.name if a.person else a.author_name) if a.is_corresponding else None
                ),
                "corresponding_uids": (
                    a.person.uid if a.is_corresponding and a.person and a.person.uid else None
                ),
            })
        return rows
    if dim == "项目":
        funding = sorted(p.funding, key=lambda f: f.seq or 99)
        if not funding:
            return [{}]
        rows = []
        for f in funding:
            proj = f.project
            rows.append({
                "project_names": proj.name if proj else None,
                "project_nos": proj.project_no if proj and proj.project_no else None,
                "funding_seqs": f.seq,
                "funding_labels": f"{(proj.name if proj else None) or f.funding_no or '-'}[{f.seq or '-'}标]",
                "funding_nos": f.funding_no,
            })
        return rows
    return [{}]


def _select(full: dict, columns: list) -> dict:
    """columns 支持 'extra:KEY' 形式的自定义字段列。"""
    row = {}
    extra = full.get("_extra", {})
    for c in columns:
        if c.startswith("extra:"):
            row[c] = extra.get(c.split(":", 1)[1])
        else:
            row[c] = full.get(c)
    return row


def _expand(base: dict, dim_rows: list, columns: list) -> list:
    """把一个实体按维度的多行展开后，逐行裁剪到所选列。"""
    return [_select({**base, **d}, columns) for d in dim_rows]


def build_paper_rows(db: Session, papers: list, columns: list) -> list:
    dim = selected_dim("papers", columns)
    out = []
    for p in papers:
        base = _paper_base_row(p)
        if dim:
            out.extend(_expand(base, _paper_dim_rows(p, dim), columns))
        else:
            out.append(_select(base, columns))
    return out


def _person_base_row(p: Person, db: Session) -> dict:
    """人员标量字段：内置列 + 自定义 + 标量关联（论文/获奖计数等）。"""
    authorships = db.query(PaperAuthor).filter(PaperAuthor.person_id == p.id).all()
    first = sum(1 for a in authorships if a.seq == 1)
    corr = sum(1 for a in authorships if a.is_corresponding)
    # 内置字段与数据库列同名：先装入全部模型列，避免新增内置字段时遗漏（导出恒空）
    row = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    row["_extra"] = parse_extra(p)
    row.update({
        "name_variants": "; ".join(v.name_text for v in p.name_variants if v.name_text) or None,
        "paper_count": len(authorships),
        "first_author_count": first,
        "corresponding_count": corr,
    })
    return row


def _person_dim_rows(p: Person, db: Session, dim: str) -> list:
    if dim == "论文":
        authorships = db.query(PaperAuthor).filter(PaperAuthor.person_id == p.id).all()
        if not authorships:
            return [{}]
        rows = []
        for a in authorships:
            paper = db.get(Paper, a.paper_id)
            rows.append({"paper_titles": paper.title if paper else None})
        return rows
    if dim == "获奖":
        person_awards = db.query(AwardRecipient).filter(AwardRecipient.person_id == p.id).all()
        person_awards = [r for r in person_awards if r.award]
        if not person_awards:
            return [{}]
        rows = []
        for r in person_awards:
            aw = r.award
            detail = "、".join(
                x for x in [
                    aw.level,
                    aw.award_date.isoformat() if aw.award_date else None,
                    aw.summary,
                ] if x
            )
            rows.append({
                "award_names": aw.award_name,
                "award_details": detail or None,
                "award_ranks": r.rank,
                "award_all_awardees": aw.all_awardees,
                "award_issuers": aw.issuer,
                "award_cert_nos": aw.cert_no,
                "award_pr_urls": aw.pr_url,
            })
        return rows
    if dim == "项目":
        memberships = db.query(ProjectMember).filter(ProjectMember.person_id == p.id).all()
        if not memberships:
            return [{}]
        rows = []
        for m in memberships:
            proj = db.get(Project, m.project_id)
            rows.append({"project_names": (proj.name or proj.project_no) if proj else None})
        return rows
    return [{}]


def build_people_rows(db: Session, people: list, columns: list) -> list:
    dim = selected_dim("people", columns)
    out = []
    for p in people:
        base = _person_base_row(p, db)
        if dim:
            out.extend(_expand(base, _person_dim_rows(p, db, dim), columns))
        else:
            out.append(_select(base, columns))
    return out


def _project_base_row(p: Project, db: Session) -> dict:
    """项目标量字段：内置列 + 自定义 + 标量关联（资助论文数等）。"""
    fundings = db.query(PaperFunding).filter(PaperFunding.project_id == p.id).all()
    first_label = sum(1 for f in fundings if f.seq == 1)
    # 内置字段与数据库列同名：先装入全部模型列，避免新增内置字段时遗漏（导出恒空）
    row = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    row["_extra"] = parse_extra(p)
    row.update({
        "paper_count": len(fundings),
        "first_label_count": first_label,
    })
    return row


def _project_dim_rows(p: Project, db: Session, dim: str) -> list:
    if dim == "成员":
        members = [m for m in p.members if m.person]
        if not members:
            return [{}]
        return [
            {
                "member_names": m.person.name,
                "member_uids": m.person.uid,
                "member_roles": m.role or "成员",
            }
            for m in members
        ]
    if dim == "论文":
        fundings = db.query(PaperFunding).filter(PaperFunding.project_id == p.id).all()
        if not fundings:
            return [{}]
        rows = []
        for f in fundings:
            paper = db.get(Paper, f.paper_id)
            rows.append({
                "paper_titles": paper.title if paper else None,
                "funding_seqs": f.seq,
            })
        return rows
    return [{}]


def build_project_rows(db: Session, projects: list, columns: list) -> list:
    dim = selected_dim("projects", columns)
    out = []
    for p in projects:
        base = _project_base_row(p, db)
        if dim:
            out.extend(_expand(base, _project_dim_rows(p, db, dim), columns))
        else:
            out.append(_select(base, columns))
    return out


def _ip_base_row(ip, db: Session) -> dict:
    """知识产权标量字段：内置列 + 自定义 + 标量关联（第一发明人）。"""
    inventors = sorted(ip.inventors, key=lambda v: v.seq or 0)
    first = next((v for v in inventors if v.is_first), inventors[0] if inventors else None)
    # 内置字段与数据库列同名：先装入全部模型列，避免新增内置字段时遗漏（导出恒空）
    row = {c.name: getattr(ip, c.name) for c in ip.__table__.columns}
    row["_extra"] = parse_extra(ip)
    row["first_inventor"] = (
        (first.person.name if first.person else first.inventor_name) if first else None
    )
    return row


def _ip_dim_rows(ip, db: Session, dim: str) -> list:
    if dim == "人员":
        inventors = sorted(ip.inventors, key=lambda v: v.seq or 0)
        if not inventors:
            return [{}]
        return [
            {
                "inventor_names": (v.person.name if v.person else v.inventor_name) or "-",
                "inventor_uids": v.person.uid if v.person and v.person.uid else None,
            }
            for v in inventors
        ]
    if dim == "项目":
        fundings = list(ip.funding)
        if not fundings:
            return [{}]
        return [{"funding_nos": f.funding_no} for f in fundings]
    return [{}]


def build_ip_rows(db: Session, ips: list, columns: list) -> list:
    dim = selected_dim("ip", columns)
    out = []
    for ip in ips:
        base = _ip_base_row(ip, db)
        if dim:
            out.extend(_expand(base, _ip_dim_rows(ip, db, dim), columns))
        else:
            out.append(_select(base, columns))
    return out


def _award_base_row(a, db: Session) -> dict:
    """奖励荣誉标量字段：内置列 + 自定义。"""
    row = {c.name: getattr(a, c.name) for c in a.__table__.columns}
    row["_extra"] = parse_extra(a)
    return row


def _award_dim_rows(a, db: Session, dim: str) -> list:
    if dim == "人员":
        from .models import AwardRecipient
        recipients = db.query(AwardRecipient).filter(AwardRecipient.award_id == a.id).all()
        if not recipients:
            return [{}]
        return [
            {
                "recipient_names": (r.person.name if r.person else r.recipient_name) or "-",
                "recipient_uids": r.person.uid if r.person and r.person.uid else None,
            }
            for r in recipients
        ]
    return [{}]


def build_award_rows(db: Session, awards: list, columns: list) -> list:
    dim = selected_dim("awards", columns)
    out = []
    for a in awards:
        base = _award_base_row(a, db)
        if dim:
            out.extend(_expand(base, _award_dim_rows(a, db, dim), columns))
        else:
            out.append(_select(base, columns))
    return out
