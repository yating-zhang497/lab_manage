"""把历史 project_no_1/2/3 快照迁移进 paper_funding 关系表（一次性）。

用法（在 backend 目录下）:
    python -m scripts.migrate_funding_snapshots [--dry-run]

背景：早期 AI 提取会把致谢中的项目编号同时写入论文 extra_json 快照
（project_no_1/2/3）与基金标注关系表，形成同一事实两份数据。
现统一以 paper_funding 关系表为唯一事实来源，本脚本：

- 遍历全部论文 extra_json 中的 project_no_*/funding_note_* 快照值；
- 按编号匹配项目库（与 AI 提取相同的归一化规则），
  已有对应标注行（同项目或同原文基金号）则跳过，否则新建
  PaperFunding(source='snapshot')，位置 i 对应标注顺序 i；
- 迁移后从 extra_json 移除这些快照键；
- 顺带删除 field_defs 表中 project_no_* 的覆盖记录（字段已下线）。
"""

from __future__ import annotations

import argparse
import json

from app import custom_fields as cf
from app.database import SessionLocal
from app.funding import link_funding_by_numbers
from app.models import FieldDef, Paper

SNAPSHOT_KEYS = [f"project_no_{i}" for i in (1, 2, 3)] + [
    f"funding_note_{i}" for i in (1, 2, 3)
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只报告不写库")
    args = ap.parse_args()

    db = SessionLocal()
    migrated = skipped = removed_defs = 0
    try:
        for paper in db.query(Paper).all():
            try:
                extra = json.loads(paper.extra_json or "{}")
            except json.JSONDecodeError:
                continue
            numbers = [
                extra.get(f"project_no_{i}") or extra.get(f"funding_note_{i}")
                for i in (1, 2, 3)
            ]
            if not any(numbers):
                continue
            if not args.dry_run:
                added = link_funding_by_numbers(db, paper, numbers, source="snapshot")
            else:
                added = sum(1 for n in numbers if (n or "").strip())
            for k in SNAPSHOT_KEYS:
                extra.pop(k, None)
            if not args.dry_run:
                paper.extra_json = json.dumps(extra, ensure_ascii=False)
            migrated += 1
            print(
                f"[{'DRY' if args.dry_run else 'OK '}] paper#{paper.id} "
                f"{paper.title[:40]!r} 快照{[n for n in numbers if n]} -> 新增标注{added}条"
            )

        # 删除已下线内置字段的覆盖记录（快照字段 + 其他不再是内置字段的 key）
        defs = db.query(FieldDef).all()
        stale = [
            d
            for d in defs
            if not d.key.startswith("cf_")
            and d.key not in cf.builtin_keys(d.entity)
        ]
        removed_defs = len(stale)
        if not args.dry_run:
            for d in stale:
                db.delete(d)
        skipped = db.query(Paper).count() - migrated
        if not args.dry_run:
            db.commit()
        print(
            f"\n完成：迁移论文 {migrated} 篇，无快照 {skipped} 篇，"
            f"删除字段覆盖记录 {removed_defs} 条"
            + ("（dry-run 未写库）" if args.dry_run else "")
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
