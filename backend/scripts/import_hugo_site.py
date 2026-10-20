"""从课题组现有官网(HugoBlox)导入论文与作者映射。

用法（在 backend 目录下）:
    python -m scripts.import_hugo_site <官网仓库路径> [--create-persons]

- 作者档案: content/authors/*/_index.md（英文名↔中文名↔入学年份）
- 论文: content/publication/*/index.md（标题/作者序/DOI/日期）
- 按论文标题唯一标识upsert；作者按英文名（语序不敏感）匹配人员库
- 默认只为库内已有人员建立关联，不自动创建新人员；
  加 --create-persons 后为未匹配作者创建占位人员(uid=SITE-xxx)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.models import Paper, PaperAuthor, Person, normalize_title
from app.routers.imports import _match_person_by_name


def parse_front_matter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data = {}
    current_key = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and not stripped.startswith("-") and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val:
                data[key] = val.strip("'\"")
            else:
                data[key] = []
            current_key = key
        elif stripped.startswith("- ") and current_key:
            if current_key in ("links", "organizations", "social"):
                continue
            if not isinstance(data.get(current_key), list):
                continue
            data[current_key].append(stripped[2:].strip().strip("'\""))
        elif indent > 0 and current_key and isinstance(data.get(current_key), str):
            data[current_key] = f"{data[current_key]} {stripped}"
    return data


def load_authors(site: Path) -> dict:
    profiles = {}
    for idx in sorted((site / "content" / "authors").glob("*/_index.md")):
        fm = parse_front_matter(idx.read_text(encoding="utf-8", errors="replace"))
        display = fm.get("title", "").strip()
        if not display:
            continue
        profiles[display] = {
            "display": display,
            "zh_name": fm.get("zh_name", "").strip(),
            "role": fm.get("role", "").strip(),
            "weight": fm.get("weight", "").strip(),
            "slug": idx.parent.name,
        }
    return profiles


def load_publications(site: Path) -> list:
    pubs = []
    for idx in sorted((site / "content" / "publication").glob("*/index.md")):
        fm = parse_front_matter(idx.read_text(encoding="utf-8", errors="replace"))
        title = fm.get("title", "").strip()
        if not title:
            continue
        authors = fm.get("authors") or []
        pub_type = ""
        types = fm.get("publication_types")
        if isinstance(types, list) and types:
            pub_type = types[0]
        pub_date = None
        raw_date = fm.get("date", "")
        if raw_date:
            try:
                pub_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                pub_date = None
        pubs.append(
            {
                "title": title,
                "authors": [a for a in authors if isinstance(a, str)],
                "doi": fm.get("doi", "").strip(),
                "date": pub_date,
                "venue_type": "期刊" if pub_type.startswith("article") else "会议",
            }
        )
    return pubs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("site_path")
    ap.add_argument("--create-persons", action="store_true")
    args = ap.parse_args()

    site = Path(args.site_path)
    if not (site / "content" / "publication").exists():
        print(f"路径不是官网仓库: {site}")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    profiles = load_authors(site)
    pubs = load_publications(site)
    print(f"读取到 {len(profiles)} 个作者档案, {len(pubs)} 篇论文")

    matched_persons = 0
    created_persons = 0
    display_to_person = {}
    for display, info in profiles.items():
        person = None
        if info["zh_name"]:
            person = db.query(Person).filter(Person.name == info["zh_name"]).first()
        if person is None:
            person = _match_person_by_name(db, display)
        if person:
            if not person.english_name:
                person.english_name = display
            if info["zh_name"] and not person.name:
                person.name = info["zh_name"]
            matched_persons += 1
        elif args.create_persons:
            uid = "SITE-" + info["slug"].replace(" ", "-")
            if not db.query(Person).filter(Person.uid == uid).first():
                person = Person(
                    uid=uid,
                    name=info["zh_name"] or None,
                    english_name=display,
                )
                db.add(person)
                db.flush()
                created_persons += 1
        if person:
            display_to_person[display] = person
    db.commit()
    print(f"作者档案: 匹配库内人员 {matched_persons} 人, 新建占位人员 {created_persons} 人")

    new_papers = updated_papers = 0
    author_links = author_total = 0
    for pub in pubs:
        norm = normalize_title(pub["title"])
        paper = db.query(Paper).filter(Paper.title_norm == norm).first()
        if paper:
            updated_papers += 1
        else:
            paper = Paper(title=pub["title"], title_norm=norm)
            db.add(paper)
            db.flush()
            new_papers += 1
        if pub["doi"]:
            existing_doi = (
                db.query(Paper)
                .filter(Paper.doi == pub["doi"], Paper.id != paper.id)
                .first()
            )
            if not existing_doi:
                paper.doi = pub["doi"]
        if pub["date"]:
            paper.pub_date = pub["date"]
        if pub["venue_type"]:
            paper.venue_type = pub["venue_type"]

        for a in list(paper.authors):
            db.delete(a)
        db.flush()
        for seq, name in enumerate(pub["authors"], start=1):
            person = display_to_person.get(name) or _match_person_by_name(db, name)
            db.add(
                PaperAuthor(
                    paper_id=paper.id,
                    seq=seq,
                    author_name=name,
                    person_id=person.id if person else None,
                )
            )
            author_total += 1
            if person:
                author_links += 1
        db.commit()

    print(f"论文: 新增 {new_papers} 篇, 更新 {updated_papers} 篇")
    print(f"作者关联: {author_links}/{author_total} 位作者匹配到人员库")
    db.close()


if __name__ == "__main__":
    main()
