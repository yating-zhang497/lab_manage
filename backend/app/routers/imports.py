import json
import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import custom_fields as cf
from .. import importexport as ie
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..funding import link_funding_by_numbers
from ..models import (
    AwardRecord,
    AwardRecipient,
    ImportJob,
    IntellectualProperty,
    IPInventor,
    Paper,
    PaperAuthor,
    Person,
    PersonNameVariant,
    Project,
    normalize_title,
)

router = APIRouter(prefix="/import", tags=["import"])

XLSX_MT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _with_field_labels(db: Session, entity: str, base_fields: dict) -> dict:
    """将字段定义中的当前标签加入导入别名表。
    用户在字段管理改了字段名后，导入模板用新名称，导入侧也能识别。"""
    result = {k: list(v) for k, v in base_fields.items()}
    for f in cf.defs_for(db, entity, enabled_only=False):
        key = f["key"]
        label = f["label"]
        if key in result and label not in result[key]:
            result[key].append(label)
    return result


def _record_job(db, user, job_type, filename, ok, fail, errors):
    db.add(
        ImportJob(
            job_type=job_type,
            mode="batch",
            filename=filename,
            status="done",
            ok_count=ok,
            fail_count=fail,
            error_detail=json.dumps(errors, ensure_ascii=False)[:4000],
            user_id=user.id,
        )
    )
    db.commit()


def _report(ok, fail, errors):
    return {"ok_count": ok, "fail_count": fail, "errors": errors[:100]}


def _read(file: UploadFile):
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="文件为空")
    try:
        return ie.read_table(data, file.filename or "")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"文件解析失败: {e}")


def _name_variants(nm: str) -> set:
    """生成姓名的小写变体，仅容忍大小写与"姓, 名 / 名 姓"语序差异（精确匹配）。

    不再生成姓氏+名字缩写（如 "wang we"）——这类缩写会让 "Wang, Wenqiang"
    与 "Wang, Wei" 折叠到同一候选，造成错误关联。需要匹配缩写署名时，请在
    人员档案里把该缩写作为"姓名变体"显式录入，由系统精确命中。
    """
    s = set()
    n = (nm or "").strip().lower().replace(".", " ")
    n = " ".join(n.split())
    if not n:
        return s
    s.add(n)
    if "," in n:
        last, first = (x.strip() for x in n.split(",", 1))
        if last and first:
            s.add(f"{first} {last}")
            s.add(f"{last} {first}")
            s.add(f"{last}, {first}")
    else:
        parts = n.split()
        if len(parts) == 2:
            last, first = parts[1], parts[0]
            s.add(f"{first} {last}")
            s.add(f"{last}, {first}")
        elif len(parts) >= 2:
            # 多段名：交换首尾段，容忍 "Wenqiang Wang Wei" ↔ "Wei Wenqiang Wang" 类写法
            s.add(f"{parts[-1]} {parts[0]}")
            s.add(f"{parts[0]} {parts[-1]}")
    return s


def _match_person_by_name(db: Session, name: str):
    """按姓名/英文名（含变体）精确匹配人员，语序不敏感。"""
    low = (name or "").strip().lower()
    if not low:
        return None
    probes = _name_variants(low)
    for p in db.query(Person).all():
        cands = set()
        for nm in [p.name, p.english_name] + [v.name_text for v in p.name_variants]:
            cands |= _name_variants(nm)
        if probes & cands:
            return p
    return None


def _template_columns(db: Session, entity: str) -> list:
    """按当前字段定义（含字段管理中的改名/自定义字段）生成模板列 (key, 显示名, options, dtype)。
    返回 list[(key, label, options_or_None, dtype_or_None)]；dtype='date' 的列模板会设
    yyyy-mm-dd 格式，select 列自动加下拉验证。
    """
    fields = cf.defs_for(db, entity, enabled_only=False)
    by_key = {f["key"]: f for f in fields}
    cols = [(f["key"], f["label"], f.get("options") if f["dtype"] == "select" else None, f["dtype"]) for f in fields]
    if entity == "papers":
        out = []
        for k, l, opts, dt in cols:
            out.append((k, l, opts, dt))
            if k == "title":
                out += [("", "作者1", None, None), ("", "作者2", None, None), ("", "作者3", None, None)]
        return out + [
            ("", "项目编号1", None, None),
            ("", "项目编号1对应排序", None, None),
            ("", "项目编号2", None, None),
            ("", "项目编号2对应排序", None, None),
        ]
    if entity == "people":
        return cols + [("", "姓名变体", None, None)]
    if entity == "awards":
        return cols + [("", "获奖人1", None, None), ("", "获奖人2", None, None), ("", "获奖人3", None, None)]
    if entity == "ip":
        return cols + [("", "发明人1", None, None), ("", "发明人2", None, None), ("", "发明人3", None, None)]
    return cols


@router.get("/template/people")
def template_people(db: Session = Depends(get_db), _=Depends(get_current_user)):
    cols = _template_columns(db, "people")
    data = ie.make_template(cols)
    return Response(
        content=data,
        media_type=XLSX_MT,
        headers={"Content-Disposition": "attachment; filename=people_template.xlsx"},
    )


@router.get("/template/projects")
def template_projects(db: Session = Depends(get_db), _=Depends(get_current_user)):
    cols = _template_columns(db, "projects")
    data = ie.make_template(cols)
    return Response(
        content=data,
        media_type=XLSX_MT,
        headers={"Content-Disposition": "attachment; filename=projects_template.xlsx"},
    )


@router.get("/template/papers")
def template_papers(db: Session = Depends(get_db), _=Depends(get_current_user)):
    cols = _template_columns(db, "papers")
    data = ie.make_template(cols)
    return Response(
        content=data,
        media_type=XLSX_MT,
        headers={"Content-Disposition": "attachment; filename=papers_template.xlsx"},
    )


def _parse_award_date(v) -> Optional[date]:
    v = str(v or "").strip()
    if not v:
        return None
    # Excel 日期序列号（5位及以上数字，避开下方4位年份分支）：
    # 用户填 '2026年1月1日' 时 Excel 存为序列号(如 46023)，若格式未被识别会以文本形式传入
    if v.isdigit() and len(v) >= 5:
        iso = ie.excel_serial_to_iso(v)
        if iso:
            return date.fromisoformat(iso)
    if v.isdigit() and len(v) == 4:
        return date(int(v), 1, 1)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _apply_name_variants(db: Session, person: Person, raw) -> None:
    """人员导入行中的"姓名变体"列（;；,，/ 分隔）→ 追加去重，不覆盖已有变体。"""
    if not (raw or "").strip():
        return
    existing = {v.name_text.strip().lower() for v in person.name_variants}
    existing.update(x.lower() for x in (person.name or "", person.english_name or "") if x)
    for nm in re.split(r"[;；,，/]", raw):
        nm = nm.strip()
        if nm and nm.lower() not in existing:
            db.add(PersonNameVariant(person_id=person.id, name_text=nm))
            existing.add(nm.lower())


@router.post("/people")
def import_people(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin)):
    rows = _read(file)
    ok = fail = 0
    errors = []
    # 构建自定义字段 key → 别名列表，供 row_to_entity 识别
    extra_fields = {}
    extra_date_keys = set()
    for f in cf.defs_for(db, "people", enabled_only=False):
        if f["key"].startswith("cf_"):
            extra_fields[f["key"]] = [f["label"]]
            if f["dtype"] == "date":
                extra_date_keys.add(f["key"])
    for i, row in enumerate(rows, start=2):
        data = ie.row_to_entity(row, _with_field_labels(db, "people", ie.PERSON_FIELDS), extra_fields, extra_date_keys)
        uid = (data.get("uid") or "").strip()
        if not uid:
            fail += 1
            errors.append(f"第{i}行：缺少学号/工号，跳过")
            continue
        try:
            extra = data.pop("extra", None)
            existing = db.query(Person).filter(Person.uid == uid).first()
            if existing:
                person = existing
                for k, v in data.items():
                    if k != "uid" and v:
                        setattr(person, k, v)
            else:
                person = Person(**data)
                db.add(person)
                db.flush()
            cf.save_extra(person, extra, db, "people")
            _apply_name_variants(db, person, row.get("姓名变体"))
            ok += 1
        except Exception as e:
            fail += 1
            errors.append(f"第{i}行：{e}")
    db.commit()
    _record_job(db, user, "people", file.filename, ok, fail, errors)
    return _report(ok, fail, errors)


@router.post("/projects")
def import_projects(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin)):
    rows = _read(file)
    ok = fail = 0
    errors = []
    extra_fields = {}
    extra_date_keys = set()
    for f in cf.defs_for(db, "projects", enabled_only=False):
        if f["key"].startswith("cf_"):
            extra_fields[f["key"]] = [f["label"]]
            if f["dtype"] == "date":
                extra_date_keys.add(f["key"])
    for i, row in enumerate(rows, start=2):
        data = ie.row_to_entity(row, _with_field_labels(db, "projects", ie.PROJECT_FIELDS), extra_fields, extra_date_keys)
        project_no = (data.get("project_no") or "").strip()
        if not project_no:
            fail += 1
            errors.append(f"第{i}行：缺少项目编号，跳过")
            continue
        try:
            extra = data.pop("extra", None)
            proj = db.query(Project).filter(Project.project_no == project_no).first()
            if proj:
                for k, v in data.items():
                    if k != "project_no" and v:
                        setattr(proj, k, v)
            else:
                proj = Project(**data)
                db.add(proj)
                db.flush()
            cf.save_extra(proj, extra, db, "projects")
            ok += 1
        except Exception as e:
            fail += 1
            errors.append(f"第{i}行：{e}")
    db.commit()
    _record_job(db, user, "projects", file.filename, ok, fail, errors)
    return _report(ok, fail, errors)


def _build_person_lookup(db) -> dict:
    """批量导入时一次性预加载人员姓名索引（中文名/英文名含变体），避免逐条全表查询。"""
    from sqlalchemy.orm import selectinload

    lookup = {}
    people = db.query(Person).options(selectinload(Person.name_variants)).all()
    for p in people:
        for nm in [p.name, p.english_name] + [v.name_text for v in p.name_variants]:
            for cand in _name_variants(nm):
                lookup.setdefault(cand, p)
    return lookup


def _match_person_in_lookup(lookup: dict, name: str):
    for cand in _name_variants(name):
        if cand in lookup:
            return lookup[cand]
    return None


def _upsert_paper(db: Session, data: dict, errors: list, idx: int, people_lookup: dict = None) -> int:
    title = (data.get("title") or "").strip()
    if not title:
        errors.append(f"第{idx}行：缺少论文标题，跳过")
        return 0
    # 项目编号列落入基金标注关系表（唯一事实来源），不再存快照；
    # "项目编号N对应排序"列优先决定标注顺序（一标/二标），缺省按列位置
    funding_nos = [data.pop(k, None) for k in ("project_no_1", "project_no_2", "project_no_3")]
    funding_seqs = [data.pop(k, None) for k in ("project_seq_1", "project_seq_2", "project_seq_3")]
    extra = data.pop("extra", None)
    norm = normalize_title(title)
    existing = db.query(Paper).filter(Paper.title_norm == norm).first()
    if existing:
        for k, v in data.items():
            if k != "title" and v:
                setattr(existing, k, v)
        paper = existing
    else:
        paper = Paper(**data)
        paper.title_norm = norm
        db.add(paper)
        db.flush()
    cf.save_extra(paper, extra, db, "papers")
    authors = ie.split_authors(data.get("authors_raw") or paper.authors_raw or "")
    if authors:
        lookup = people_lookup if people_lookup is not None else _build_person_lookup(db)
        # 先收集现有作者（用于比对）
        existing_authors = {a.author_name.lower(): a for a in paper.authors}
        seen_lower = set()
        for seq, name in enumerate(authors, start=1):
            name_lower = name.lower()
            seen_lower.add(name_lower)
            person = _match_person_in_lookup(lookup, name)
            if name_lower in existing_authors:
                # 更新已有作者（顺序、person_id）
                a = existing_authors[name_lower]
                a.seq = seq
                a.person_id = person.id if person else None
                a.author_name = name
            else:
                # 新增作者
                db.add(
                    PaperAuthor(
                        paper_id=paper.id,
                        seq=seq,
                        author_name=name,
                        person_id=person.id if person else None,
                    )
                )
        # 删除不再存在的作者
        for a in paper.authors:
            if a.author_name.lower() not in seen_lower:
                db.delete(a)
    if funding_nos:
        link_funding_by_numbers(db, paper, funding_nos, source="import", seqs=funding_seqs)
    return 1


_AUTHOR_COL = re.compile(r"^作者(\d+)$")


def _merge_author_columns(row: dict) -> None:
    """作者1/作者2/… 列按序号合并为"所有作者名排序"（与导入文件一一对应）。"""
    if row.get("所有作者名排序"):
        return
    named = []
    for key in row:
        m = _AUTHOR_COL.match(key)
        if m:
            named.append((int(m.group(1)), row[key]))
    names = [v for _, v in sorted(named, key=lambda t: t[0]) if v]
    if names:
        row["所有作者名排序"] = "; ".join(names)


@router.post("/papers")
def import_papers(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin)):
    rows = _read(file)
    ok = fail = 0
    errors = []
    people_lookup = None
    extra_fields = {}
    extra_date_keys = set()
    for f in cf.defs_for(db, "papers", enabled_only=False):
        if f["key"].startswith("cf_"):
            extra_fields[f["key"]] = [f["label"]]
            if f["dtype"] == "date":
                extra_date_keys.add(f["key"])
    for i, row in enumerate(rows, start=2):
        _merge_author_columns(row)
        data = ie.row_to_entity(row, _with_field_labels(db, "papers", ie.PAPER_FIELDS), extra_fields, extra_date_keys)
        try:
            if people_lookup is None:
                people_lookup = _build_person_lookup(db)
            ok += _upsert_paper(db, data, errors, i, people_lookup)
            if not data.get("title"):
                fail += 1
        except Exception as e:
            fail += 1
            errors.append(f"第{i}行：{e}")
    db.commit()
    _record_job(db, user, "papers", file.filename, ok, fail, errors)
    return _report(ok, fail, errors)


def _clean_bib(v):
    """剥离 BibTeX/Better BibTeX 字段值里的花括号与 LaTeX 转义，保留可读文本。"""
    if not v:
        return v
    return v.replace("{", "").replace("}", "").strip()


@router.post("/papers/bib")
def import_bib(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin)):
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="文件为空")
    for enc in ("utf-8", "gb18030", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(status_code=422, detail="无法识别bib文件编码")
    try:
        import bibtexparser

        parser = bibtexparser.bparser.BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        bib = bibtexparser.loads(text, parser=parser)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"bib解析失败: {e}")

    ok = fail = 0
    errors = []
    people_lookup = None
    for i, e in enumerate(bib.entries, start=1):
        entry = {k.lower(): v for k, v in e.items()}
        title = _clean_bib(entry.get("title"))
        if not title:
            fail += 1
            errors.append(f"第{i}条：缺少title，跳过")
            continue
        # 期刊/会议：兼容 BibTeX 的 journal/booktitle 与 BibLaTeX 的 journaltitle
        venue = _clean_bib(
            entry.get("journal") or entry.get("journaltitle") or entry.get("booktitle") or ""
        )
        # 年份：优先 year；Better BibLaTeX 用 date（如 2025-01-01），从中取年份+完整日期
        year = entry.get("year")
        pub_date = None
        if not year and entry.get("date"):
            date_val = _clean_bib(entry["date"])
            m = re.match(r"(\d{4})", date_val)
            if m:
                year = m.group(1)
            if re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
                pub_date = date_val
        bib_raw = f"@{e.get('ENTRYTYPE', 'misc')}{{{e.get('ID', '')},\n" + ",\n".join(
            f"  {k} = {{{v}}}" for k, v in entry.items() if k != "id"
        ) + "\n}"
        paper_data = {
            "title": title,
            "authors_raw": (entry.get("author") or "").replace(" and ", "; "),
            "venue": venue,
            "venue_type": "会议" if entry.get("booktitle") else "期刊",
            "bib_key": e.get("ID"),
            "bib_raw": bib_raw,
            "doi": entry.get("doi"),
            # Better BibTeX 导出更完整：摘要/链接也一并带回
            "abstract": _clean_bib(entry.get("abstract")) or None,
            "url": _clean_bib(entry.get("url")) or None,
            # GB/T 7714 参考文献字段：出版地/出版者（会议论文集、专著用）；note→备注
            "address": _clean_bib(entry.get("address")) or None,
            "publisher": _clean_bib(entry.get("publisher")) or None,
            "notes": _clean_bib(entry.get("note")) or None,
        }
        if pub_date:
            paper_data["pub_date"] = pub_date
        for src, dst in [("year", "year"), ("volume", "volume"), ("number", "issue"), ("pages", "pages")]:
            if entry.get(src):
                paper_data[dst] = _clean_bib(entry.get(src))
        # year 可能来自 year 字段，也可能上面从 date 字段解析得到（local var year）
        if not paper_data.get("year") and year:
            paper_data["year"] = year
        if paper_data.get("year"):
            try:
                paper_data["year"] = int(re.search(r"\d{4}", str(paper_data["year"])).group())
            except (ValueError, AttributeError):
                paper_data.pop("year", None)
        try:
            if people_lookup is None:
                people_lookup = _build_person_lookup(db)
            ok += _upsert_paper(db, paper_data, errors, i, people_lookup)
        except Exception as ex:
            fail += 1
            errors.append(f"第{i}条：{ex}")
    db.commit()
    _record_job(db, user, "bib", file.filename, ok, fail, errors)
    return _report(ok, fail, errors)


@router.get("/template/papers/bib")
def template_papers_bib(_=Depends(get_current_user)):
    sample = (
        "@article{fu2025example,\n"
        "  title = {An Example Paper Title},\n"
        "  author = {Fu, Haohuan and Zhang, San},\n"
        "  journal = {Nature},\n"
        "  year = {2025},\n"
        "  volume = {1},\n"
        "  pages = {1--10},\n"
        "  doi = {10.1000/example}\n"
        "}\n"
    )
    return Response(
        content=sample.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=papers_template.bib"},
    )


IP_TYPE_ALIASES = {
    "专利": "patent",
    "软著": "software_copyright",
    "软件著作": "software_copyright",
    "software_copyright": "software_copyright",
    "其他": "other",
    "other": "other",
}


def _ip_type_aliases(db: Session) -> dict:
    """从字段定义动态构建 ip_type 别名映射：选项值->选项值 + 旧兼容别名。"""
    aliases = dict(IP_TYPE_ALIASES)  # 保留旧别名兼容
    for f in cf.defs_for(db, "ip", enabled_only=True):
        if f["key"] == "ip_type":
            for opt in f.get("options") or []:
                aliases[opt] = opt  # 选项值->选项值（自己映射自己）
    return aliases

_INVENTOR_COL = re.compile(r"^发明人(\d+)$")


def _merge_inventor_columns(row: dict) -> list:
    """发明人1/发明人2/… 列按序号合并为一一对应的发明人列表。"""
    named = []
    for key in row:
        m = _INVENTOR_COL.match(key)
        if m:
            named.append((int(m.group(1)), row[key]))
    return [v for _, v in sorted(named, key=lambda t: t[0]) if v]


@router.get("/template/ip")
def template_ip(db: Session = Depends(get_db), _=Depends(get_current_user)):
    cols = _template_columns(db, "ip")
    data = ie.make_template(cols)
    return Response(
        content=data,
        media_type=XLSX_MT,
        headers={"Content-Disposition": "attachment; filename=ip_template.xlsx"},
    )


@router.post("/ip")
def import_ip(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin)):
    rows = _read(file)
    ok = fail = 0
    errors = []
    people_lookup = None
    type_aliases = _ip_type_aliases(db)
    extra_fields = {}
    extra_date_keys = set()
    for f in cf.defs_for(db, "ip", enabled_only=False):
        if f["key"].startswith("cf_"):
            extra_fields[f["key"]] = [f["label"]]
            if f["dtype"] == "date":
                extra_date_keys.add(f["key"])
    for i, row in enumerate(rows, start=2):
        data = ie.row_to_entity(row, _with_field_labels(db, "ip", ie.IP_FIELDS), extra_fields, extra_date_keys)
        title = (data.get("title") or "").strip()
        if not title:
            fail += 1
            errors.append(f"第{i}行：缺少产权名称（唯一标识），跳过")
            continue
        raw_type = (data.get("ip_type") or "").strip()
        ip_type = type_aliases.get(raw_type) or type_aliases.get(raw_type.lower())
        if not ip_type:
            valid_types = [f["options"] for f in cf.defs_for(db, "ip", enabled_only=True) if f["key"] == "ip_type"]
            valid_str = "/".join(valid_types[0]) if valid_types else "专利/软著/其他"
            fail += 1
            errors.append(f"第{i}行：类型必须为 {valid_str}")
            continue
        try:
            extra = data.pop("extra", None)
            existing = (
                db.query(IntellectualProperty)
                .filter(IntellectualProperty.title == title)
                .first()
            )
            fields = {
                "ip_type": ip_type,
                "grant_date": _parse_award_date(data.get("grant_date")),
                "applicant": data.get("applicant") or None,
                "notes": data.get("notes") or None,
            }
            if existing:
                ip = existing
                for k, v in fields.items():
                    if v:
                        setattr(ip, k, v)
            else:
                ip = IntellectualProperty(title=title, **fields)
                db.add(ip)
                db.flush()
            cf.save_extra(ip, extra, db, "ip")
            inventors = _merge_inventor_columns(row)
            if inventors:
                if people_lookup is None:
                    people_lookup = _build_person_lookup(db)
                # 先收集现有发明人
                existing_inventors = {v.inventor_name.lower(): v for v in ip.inventors}
                seen_lower = set()
                for seq, name in enumerate(inventors, start=1):
                    name_lower = name.lower()
                    seen_lower.add(name_lower)
                    person = _match_person_in_lookup(people_lookup, name)
                    if name_lower in existing_inventors:
                        # 更新已有发明人
                        v = existing_inventors[name_lower]
                        v.seq = seq
                        v.person_id = person.id if person else None
                        v.is_first = (seq == 1)
                    else:
                        # 新增发明人
                        db.add(
                            IPInventor(
                                ip_id=ip.id,
                                seq=seq,
                                inventor_name=name,
                                person_id=person.id if person else None,
                                is_first=(seq == 1),
                            )
                        )
                # 删除不再存在的发明人
                for v in ip.inventors:
                    if v.inventor_name.lower() not in seen_lower:
                        db.delete(v)
            ok += 1
        except Exception as e:
            fail += 1
            errors.append(f"第{i}行：{e}")
    db.commit()
    _record_job(db, user, "ip", file.filename, ok, fail, errors)
    return _report(ok, fail, errors)


_RECIPIENT_COL = re.compile(r"^获奖人(\d+)$")


def _merge_recipient_columns(row: dict) -> list:
    """获奖人1/获奖人2/… 列 → 有序列表"""
    names = []
    for key in row:
        m = _RECIPIENT_COL.match(key)
        if m and (row.get(key) or "").strip():
            names.append((int(m.group(1)), row[key].strip()))
    names.sort(key=lambda x: x[0])
    return [n for _, n in names]


@router.get("/template/awards")
def template_awards(db: Session = Depends(get_db), _=Depends(get_current_user)):
    cols = _template_columns(db, "awards")
    data = ie.make_template(cols)
    return Response(
        content=data,
        media_type=XLSX_MT,
        headers={"Content-Disposition": "attachment; filename=awards_template.xlsx"},
    )


@router.post("/awards")
def import_awards(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin)):
    rows = _read(file)
    ok = fail = 0
    errors = []
    people_lookup = None
    extra_fields = {}
    extra_date_keys = set()
    for f in cf.defs_for(db, "awards", enabled_only=False):
        if f["key"].startswith("cf_"):
            extra_fields[f["key"]] = [f["label"]]
            if f["dtype"] == "date":
                extra_date_keys.add(f["key"])
    fields = _with_field_labels(db, "awards", ie.AWARD_FIELDS)
    for i, row in enumerate(rows, start=2):
        try:
            data = ie.row_to_entity(row, fields, extra_fields, extra_date_keys)
            name = (data.get("award_name") or "").strip()
            if not name:
                errors.append(f"第{i}行：缺少奖项名称，跳过")
                fail += 1
                continue
            level = data.get("level") or None
            award_date = _parse_award_date(data.get("award_date")) if data.get("award_date") else None
            issuer = data.get("issuer") or None
            cert_no = data.get("cert_no") or None
            pr_url = data.get("pr_url") or None
            all_awardees = data.get("all_awardees") or None
            summary = data.get("summary") or None
            extra = data.pop("extra", None)
            # upsert by award_name
            existing = db.query(AwardRecord).filter(AwardRecord.award_name == name).first()
            if existing:
                if level: existing.level = level
                if award_date: existing.award_date = award_date
                if issuer: existing.issuer = issuer
                if cert_no: existing.cert_no = cert_no
                if pr_url: existing.pr_url = pr_url
                if all_awardees: existing.all_awardees = all_awardees
                if summary: existing.summary = summary
                award = existing
            else:
                award = AwardRecord(
                    award_name=name, level=level, award_date=award_date,
                    issuer=issuer, cert_no=cert_no, pr_url=pr_url,
                    all_awardees=all_awardees, summary=summary,
                )
                db.add(award)
                db.flush()
            if extra:
                cf.save_extra(award, extra, db, "awards")
            # 获奖人列
            recipients = _merge_recipient_columns(row)
            if recipients:
                if people_lookup is None:
                    people_lookup = _build_person_lookup(db)
                existing_recs = {r.recipient_name.lower(): r for r in award.recipients}
                seen_lower = set()
                for seq, r_name in enumerate(recipients, start=1):
                    seen_lower.add(r_name.lower())
                    person = _match_person_in_lookup(people_lookup, r_name)
                    if r_name.lower() in existing_recs:
                        r = existing_recs[r_name.lower()]
                        r.seq = seq
                        r.person_id = person.id if person else r.person_id
                    else:
                        db.add(AwardRecipient(
                            award_id=award.id, seq=seq,
                            recipient_name=r_name,
                            person_id=person.id if person else None,
                        ))
                for r in award.recipients:
                    if r.recipient_name.lower() not in seen_lower:
                        db.delete(r)
            ok += 1
        except Exception as e:
            fail += 1
            errors.append(f"第{i}行：{e}")
    db.commit()
    _record_job(db, user, "awards", file.filename, ok, fail, errors)
    return _report(ok, fail, errors)
