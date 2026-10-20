import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import custom_fields as cf
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import FieldDef

router = APIRouter(prefix="/fields", tags=["fields"])


class FieldDefIn(BaseModel):
    entity: str
    key: Optional[str] = None
    label: str
    dtype: str = "text"
    options: List[str] = []
    show_in_list: bool = True


class FieldDefUpdate(BaseModel):
    label: Optional[str] = None
    dtype: Optional[str] = None
    options: Optional[List[str]] = None
    enabled: Optional[bool] = None
    show_in_list: Optional[bool] = None
    sort: Optional[int] = None


class FieldDefOut(BaseModel):
    id: int
    entity: str
    key: str
    label: str
    dtype: str
    options: List[str] = []
    enabled: bool
    show_in_list: bool = True
    sort: int = 0
    builtin: bool = False


class SortItem(BaseModel):
    id: int
    sort: int


class BuiltinOverride(BaseModel):
    label: Optional[str] = None
    options: Optional[List[str]] = None
    show_in_list: Optional[bool] = None
    enabled: Optional[bool] = None
    sort: Optional[int] = None


@router.get("", response_model=List[dict])
def list_fields(entity: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if entity not in cf.ENTITY_TYPES:
        raise HTTPException(status_code=422, detail=f"entity 必须为 {'/'.join(cf.ENTITY_TYPES)}")
    return cf.defs_for(db, entity, enabled_only=False)


@router.post("", response_model=FieldDefOut, status_code=201)
def create_field(body: FieldDefIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    if body.entity not in cf.ENTITY_TYPES:
        raise HTTPException(status_code=422, detail=f"entity 必须为 {'/'.join(cf.ENTITY_TYPES)}")
    if body.dtype not in cf.DTYPES:
        raise HTTPException(status_code=422, detail="dtype 必须为 text/number/date/select/boolean")
    if body.dtype == "select" and not body.options:
        raise HTTPException(status_code=422, detail="select 类型必须提供选项")
    builtin_keys = {b["key"] for b in cf.BUILTIN_FIELDS.get(body.entity, [])}
    if body.key:
        if body.key in builtin_keys:
            raise HTTPException(status_code=422, detail="该key为内置字段，不能重复创建")
        if not body.key.startswith("cf_"):
            raise HTTPException(status_code=422, detail="自定义字段key必须以cf_开头")
    key = body.key if body.key else cf.make_key()
    dup = db.query(FieldDef).filter(
        FieldDef.entity == body.entity, FieldDef.key == key
    ).first()
    if dup:
        raise HTTPException(status_code=409, detail=f"字段「{body.label}」已存在（key冲突）")
    f = FieldDef(
        entity=body.entity,
        key=key,
        label=body.label,
        dtype=body.dtype,
        options=json.dumps(body.options, ensure_ascii=False),
        show_in_list=body.show_in_list,
        sort=(db.query(FieldDef).filter(FieldDef.entity == body.entity).count() + 1) * 10,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return cf._field_to_dict(f, body.entity, False)


@router.put("/builtin/{entity}/{key}", response_model=List[dict])
def update_builtin_field(
    entity: str,
    key: str,
    body: BuiltinOverride,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """内置字段覆盖：改名/改选项/调整列表显示/启停。唯一标识字段同样允许（用于纠正录入错误）。"""
    if entity not in cf.ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="entity 不合法")
    builtin = {b["key"]: b for b in cf.BUILTIN_FIELDS.get(entity, [])}
    if key not in builtin:
        raise HTTPException(status_code=404, detail="内置字段不存在")
    if key == cf.UNIQUE_KEYS.get(entity) and body.enabled is False:
        raise HTTPException(status_code=422, detail="唯一标识字段不能禁用")
    row = db.query(FieldDef).filter(FieldDef.entity == entity, FieldDef.key == key).first()
    if not row:
        row = FieldDef(
            entity=entity,
            key=key,
            label=builtin[key]["label"],
            dtype=builtin[key]["dtype"],
            options=json.dumps(builtin[key].get("options", []), ensure_ascii=False),
            show_in_list=builtin[key].get("show_in_list", True),
            sort=0,
        )
        db.add(row)
        db.flush()
    if body.label is not None:
        row.label = body.label
    if body.options is not None:
        row.options = json.dumps(body.options, ensure_ascii=False)
    if body.show_in_list is not None:
        row.show_in_list = body.show_in_list
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.sort is not None:
        row.sort = body.sort
    db.commit()
    db.refresh(row)
    return cf.defs_for(db, entity, enabled_only=False)


@router.put("/{field_id}", response_model=dict)
def update_field(
    field_id: int, body: FieldDefUpdate, db: Session = Depends(get_db), _=Depends(require_admin)
):
    f = db.get(FieldDef, field_id)
    if not f:
        raise HTTPException(status_code=404, detail="字段不存在")
    is_builtin = f.key in {b["key"] for b in cf.BUILTIN_FIELDS.get(f.entity, [])}
    if body.dtype is not None and is_builtin:
        raise HTTPException(status_code=422, detail="内置字段不可修改类型")
    if body.label is not None:
        f.label = body.label
    if body.dtype is not None:
        f.dtype = body.dtype
    if body.options is not None:
        f.options = json.dumps(body.options, ensure_ascii=False)
    if body.enabled is not None:
        f.enabled = body.enabled
    if body.show_in_list is not None:
        f.show_in_list = body.show_in_list
    if body.sort is not None:
        f.sort = body.sort
    db.commit()
    db.refresh(f)
    return cf._field_to_dict(f, f.entity, is_builtin)


@router.patch("/sort", response_model=List[dict])
def patch_sort(body: List[SortItem], db: Session = Depends(get_db), _=Depends(require_admin)):
    """批量更新排序，接收 [{id, sort}, ...]"""
    for item in body:
        f = db.get(FieldDef, item.id)
        if f:
            f.sort = item.sort
    db.commit()
    if not body:
        return []
    first = db.get(FieldDef, body[0].id)
    if not first:
        return []
    return cf.defs_for(db, first.entity, enabled_only=False)


@router.delete("/builtin/{entity}/{key}")
def delete_builtin_field(
    entity: str, key: str, db: Session = Depends(get_db), _=Depends(require_admin)
):
    """删除内置字段 = 永久停用（表单/列表/导入模板/导出均不再出现），唯一标识除外。"""
    if entity not in cf.ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="entity 不合法")
    keys = {b["key"] for b in cf.BUILTIN_FIELDS.get(entity, [])}
    if key not in keys:
        raise HTTPException(status_code=404, detail="内置字段不存在")
    if key == cf.UNIQUE_KEYS.get(entity):
        raise HTTPException(status_code=422, detail="唯一标识字段不能删除")
    row = db.query(FieldDef).filter(FieldDef.entity == entity, FieldDef.key == key).first()
    if not row:
        b = {b["key"]: b for b in cf.BUILTIN_FIELDS.get(entity, [])}[key]
        row = FieldDef(
            entity=entity,
            key=key,
            label=b["label"],
            dtype=b["dtype"],
            options=json.dumps(b.get("options", []), ensure_ascii=False),
            show_in_list=b.get("show_in_list", True),
            sort=0,
        )
        db.add(row)
    row.enabled = False
    db.commit()
    return {"ok": True}


@router.delete("/{field_id}")
def delete_field(field_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """删除字段 = 停用（与所有字段一致）：隐藏并保留已录入数据，可重新启用。"""
    f = db.get(FieldDef, field_id)
    if not f:
        raise HTTPException(status_code=404, detail="字段不存在")
    if f.key == cf.UNIQUE_KEYS.get(f.entity):
        raise HTTPException(status_code=422, detail="唯一标识字段不能删除")
    f.enabled = False
    db.commit()
    return {"ok": True}


# ─── 统一端点（不区分来源，所有字段一视同仁）─────────────────────────────────

@router.put("/{entity}/{key}", response_model=List[dict])
def update_field_by_key(
    entity: str,
    key: str,
    body: FieldDefUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """统一字段更新：所有字段（不论来源）走同一条路径——改名/改类型/改选项/启停/排序。
    内置字段首次编辑时自动创建覆盖记录。唯一标识字段不能停用。
    """
    if entity not in cf.ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="entity 不合法")
    builtin_map = {b["key"]: b for b in cf.BUILTIN_FIELDS.get(entity, [])}
    row = db.query(FieldDef).filter(FieldDef.entity == entity, FieldDef.key == key).first()
    if not row:
        if key in builtin_map:
            b = builtin_map[key]
            row = FieldDef(
                entity=entity, key=key,
                label=b["label"], dtype=b["dtype"],
                options=json.dumps(b.get("options", []), ensure_ascii=False),
                show_in_list=b.get("show_in_list", True), sort=0,
            )
            db.add(row)
            db.flush()
        else:
            raise HTTPException(status_code=404, detail="字段不存在")
    if body.enabled is False and key == cf.UNIQUE_KEYS.get(entity):
        raise HTTPException(status_code=422, detail="唯一标识字段不能停用")
    if body.label is not None:
        row.label = body.label
    if body.dtype is not None:
        row.dtype = body.dtype
    if body.options is not None:
        row.options = json.dumps(body.options, ensure_ascii=False)
    if body.show_in_list is not None:
        row.show_in_list = body.show_in_list
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.sort is not None:
        row.sort = body.sort
    db.commit()
    db.refresh(row)
    return cf.defs_for(db, entity, enabled_only=False)


@router.delete("/{entity}/{key}")
def delete_field_by_key(
    entity: str, key: str, db: Session = Depends(get_db), _=Depends(require_admin)
):
    """统一删除=停用（所有字段一致）：隐藏并保留数据，可重新启用。唯一标识字段除外。"""
    if entity not in cf.ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="entity 不合法")
    if key == cf.UNIQUE_KEYS.get(entity):
        raise HTTPException(status_code=422, detail="唯一标识字段不能删除")
    builtin_map = {b["key"]: b for b in cf.BUILTIN_FIELDS.get(entity, [])}
    row = db.query(FieldDef).filter(FieldDef.entity == entity, FieldDef.key == key).first()
    if not row:
        if key in builtin_map:
            b = builtin_map[key]
            row = FieldDef(
                entity=entity, key=key, label=b["label"], dtype=b["dtype"],
                options=json.dumps(b.get("options", []), ensure_ascii=False),
                show_in_list=b.get("show_in_list", True), sort=0, enabled=False,
            )
            db.add(row)
        else:
            raise HTTPException(status_code=404, detail="字段不存在")
    else:
        row.enabled = False
    db.commit()
    return {"ok": True}
