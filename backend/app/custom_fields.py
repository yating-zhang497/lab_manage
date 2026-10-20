"""自定义字段：定义管理 + 实体extra_json读写。"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from .models import FieldDef

ENTITY_TYPES = ("people", "projects", "papers", "ip", "awards")
DTYPES = ("text", "number", "date", "select", "boolean")
UNIQUE_KEYS = {"people": "uid", "projects": "project_no", "papers": "title", "ip": "title", "awards": "award_name"}


# 内置字段定义：key 与数据库列名一致，dtype/options 决定前端渲染方式，
# show_in_list 决定是否默认出现在列表页（可在字段管理页调整）
BUILTIN_FIELDS = {
    "people": [
        {"key": "uid", "label": "学号/工号", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "name", "label": "姓名", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "english_name", "label": "英文名", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "current_activity", "label": "目前状态", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "research_direction", "label": "学位论文题目或研究方向", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "status", "label": "状态", "dtype": "select", "options": ["在读/在职", "其他"], "show_in_list": True},
        {"key": "degree_type", "label": "类型", "dtype": "select", "options": ["硕士", "博士", "博士后", "其他"], "show_in_list": True},
        {"key": "phone", "label": "电话号码", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "email", "label": "Email", "dtype": "text", "options": [], "show_in_list": False},
    ],
    "projects": [
        {"key": "project_no", "label": "项目编号", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "name", "label": "项目名称", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "category", "label": "项目类别", "dtype": "select", "options": ["纵向", "横向"], "show_in_list": True},
        {"key": "duration", "label": "项目起止时间", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "status", "label": "状态", "dtype": "select", "options": ["在研", "已结题", "其他"], "show_in_list": True},
        {"key": "source", "label": "项目来源", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "budget_no", "label": "经费编号", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "budget_total", "label": "项目总经费", "dtype": "number", "options": [], "show_in_list": False},
        {"key": "budget_ours", "label": "我方总经费", "dtype": "number", "options": [], "show_in_list": False},
        {"key": "budget_received", "label": "已到款经费", "dtype": "number", "options": [], "show_in_list": False},
        {"key": "targets", "label": "项目KPI", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "targets_done", "label": "KPI完成情况", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "notes", "label": "其他说明", "dtype": "text", "options": [], "show_in_list": False},
    ],
    "papers": [
        {"key": "title", "label": "论文题目", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "venue", "label": "期刊/会议名称", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "year", "label": "发表时间", "dtype": "number", "options": [], "show_in_list": True},
        {"key": "volume", "label": "卷号", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "issue", "label": "期号", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "pages", "label": "页码", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "pub_date", "label": "出版日期", "dtype": "date", "options": [], "show_in_list": False},
        {"key": "address", "label": "出版地", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "publisher", "label": "出版者", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "doi", "label": "DOI", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "url", "label": "链接", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "abstract", "label": "摘要", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "ack_index", "label": "论文检索号", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "acknowledgements", "label": "致谢", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "corresponding_text", "label": "通讯作者", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "extract_status", "label": "提取状态", "dtype": "select", "options": ["已提取", "未提取"], "show_in_list": True},
        {"key": "notes", "label": "备注", "dtype": "text", "options": [], "show_in_list": False},
    ],
    "ip": [
        {"key": "title", "label": "产权名称", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "ip_type", "label": "类型", "dtype": "select", "options": ["patent", "software_copyright", "other"], "show_in_list": True},
        {"key": "grant_date", "label": "获批时间", "dtype": "date", "options": [], "show_in_list": False},
        {"key": "applicant", "label": "专利权人", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "notes", "label": "其他说明", "dtype": "text", "options": [], "show_in_list": False},
    ],
    "awards": [
        {"key": "award_name", "label": "奖项名称", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "level", "label": "奖励等级", "dtype": "select", "options": ["特等奖", "一等奖", "二等奖", "三等奖", "其他"], "show_in_list": True},
        {"key": "award_date", "label": "获奖时间", "dtype": "date", "options": [], "show_in_list": True},
        {"key": "issuer", "label": "颁奖单位", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "summary", "label": "获奖作品", "dtype": "text", "options": [], "show_in_list": True},
        {"key": "cert_no", "label": "证书编号", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "pr_url", "label": "公示链接", "dtype": "text", "options": [], "show_in_list": False},
        {"key": "all_awardees", "label": "所有获奖人", "dtype": "text", "options": [], "show_in_list": False},
    ],
}


def builtin_keys(entity: str) -> set:
    return {b["key"] for b in BUILTIN_FIELDS.get(entity, [])}


def _field_to_dict(f, entity: str, builtin: bool) -> dict:
    """统一字段定义输出格式（内置dict / 数据库行 两种来源）。"""
    if isinstance(f, dict):
        return {
            "id": f.get("id", 0),
            "entity": entity,
            "key": f["key"],
            "label": f["label"],
            "dtype": f["dtype"],
            "options": f.get("options", []),
            "enabled": f.get("enabled", True),
            "show_in_list": f.get("show_in_list", True),
            "sort": f.get("sort", 0),
            "builtin": True,
        }
    try:
        options = json.loads(f.options or "[]")
    except json.JSONDecodeError:
        options = []
    return {
        "id": f.id,
        "entity": f.entity,
        "key": f.key,
        "label": f.label,
        "dtype": f.dtype,
        "options": options,
        "enabled": f.enabled,
        "show_in_list": bool(f.show_in_list) if f.show_in_list is not None else True,
        "sort": f.sort or 0,
        "builtin": builtin,
    }


def defs_for(db: Session, entity: str, enabled_only: bool = True) -> list:
    """返回内置字段(应用数据库覆盖) + 自定义字段，按sort排序。"""
    overrides = {}
    for row in db.query(FieldDef).filter(FieldDef.entity == entity).all():
        if row.key in builtin_keys(entity):
            overrides[row.key] = row
    result = []
    for b in BUILTIN_FIELDS.get(entity, []):
        ov = overrides.get(b["key"])
        merged = dict(b)
        if ov:
            if enabled_only and not ov.enabled:
                continue
            merged["id"] = ov.id
            if ov.label:
                merged["label"] = ov.label
            if ov.dtype:
                merged["dtype"] = ov.dtype
            if ov.options:
                try:
                    merged["options"] = json.loads(ov.options)
                except json.JSONDecodeError:
                    pass
            merged["enabled"] = ov.enabled
            if ov.show_in_list is not None:
                merged["show_in_list"] = bool(ov.show_in_list)
            merged["sort"] = ov.sort or 0
        else:
            merged["id"] = 0
        result.append(_field_to_dict(merged, entity, True))
    customs = db.query(FieldDef).filter(
        FieldDef.entity == entity,
        FieldDef.key.like("cf_%"),
    )
    if enabled_only:
        customs = customs.filter(FieldDef.enabled == True)  # noqa: E712
    for row in customs.order_by(FieldDef.sort, FieldDef.id).all():
        if enabled_only and not row.enabled:
            continue
        result.append(_field_to_dict(row, entity, False))
    result.sort(key=lambda x: (x["sort"], 0 if x["builtin"] else 1, x["id"]))
    return result


def parse_extra(entity) -> dict:
    try:
        return json.loads(entity.extra_json or "{}")
    except json.JSONDecodeError:
        return {}


def field_key(f) -> str:
    """兼容内置字段(dict)与自定义字段(FieldDef ORM)。"""
    return f["key"] if isinstance(f, dict) else f.key


def save_extra(entity, extra, db: Session, entity_type: str) -> None:
    """按字段定义更新自定义字段值；显式传空字符串/None表示清空该字段。"""
    if not extra:
        return
    valid_keys = {field_key(f) for f in defs_for(db, entity_type)}
    merged = parse_extra(entity)
    for k, v in extra.items():
        if k not in valid_keys:
            continue
        if v in (None, ""):
            merged.pop(k, None)
        else:
            merged[k] = v
    entity.extra_json = json.dumps(merged, ensure_ascii=False)


def make_key() -> str:
    return "cf_" + uuid.uuid4().hex[:8]
