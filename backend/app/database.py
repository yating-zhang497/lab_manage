from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import logging

from .config import SQLALCHEMY_DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def _relax_not_null(db_path: str, table: str, column: str) -> bool:
    """老库放宽 NOT NULL 约束（模型后来允许为空的列）。

    SQLite 不支持 ALTER COLUMN，只能按官方推荐的建新表→拷数据→改名→重建索引流程。
    仅当该列当前确实带 NOT NULL 时才重建，幂等。返回是否执行了重建。
    """
    import re
    import sqlite3

    con = sqlite3.connect(db_path, isolation_level=None)
    try:
        cur = con.cursor()
        rows = cur.execute(f'PRAGMA table_info("{table}")').fetchall()
        info = {r[1]: r for r in rows}
        if column not in info or not info[column][3]:  # 不存在或本来就可空
            return False
        ddl = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        new_ddl, n = re.subn(
            rf'("{re.escape(column)}"|(?<![\w]){re.escape(column)}(?![\w]))(\s+\w+(?:\(\d+\))?)\s+NOT NULL',
            r"\1\2",
            ddl,
            count=1,
            flags=re.IGNORECASE,
        )
        if not n:
            return False
        tmp = f"{table}__nn_fix"
        new_ddl = re.sub(
            r'^CREATE TABLE\s+("[^"]+"|[\w]+)\s*\(',
            f'CREATE TABLE "{tmp}" (',
            new_ddl,
            count=1,
            flags=re.IGNORECASE,
        )
        indexes = cur.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
            (table,),
        ).fetchall()
        cols = ", ".join(f'"{r[1]}"' for r in rows)
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("BEGIN IMMEDIATE")
        try:
            cur.execute(new_ddl)
            cur.execute(f'INSERT INTO "{tmp}" ({cols}) SELECT {cols} FROM "{table}"')
            cur.execute(f'DROP TABLE "{table}"')
            cur.execute(f'ALTER TABLE "{tmp}" RENAME TO "{table}"')
            for _name, idx_sql in indexes:
                cur.execute(idx_sql)
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        cur.execute("PRAGMA foreign_keys=ON")
        return True
    finally:
        con.close()


def _ensure_schema() -> None:
    """旧库轻量升级（无迁移框架）：补缺失列并回填，任何进程入口都会执行。"""
    # 先放宽历史 NOT NULL 约束（需在 engine 建立连接前用裸 sqlite3 重建，避免 schema 缓存）
    db_path = SQLALCHEMY_DATABASE_URL.removeprefix("sqlite:///")
    for table, column in (
        ("people", "name"),
        ("projects", "name"),
        ("intellectual_property", "title"),
        ("intellectual_property", "reg_no"),
    ):
        try:
            if _relax_not_null(db_path, table, column):
                logger.info("已放宽 %s.%s 的 NOT NULL 约束", table, column)
        except Exception as e:  # noqa: BLE001
            logger.error("放宽 %s.%s 失败: %s", table, column, e)
    with engine.begin() as conn:
        # 获奖模块重构：旧表有 person_id 列则删除重建（用户已确认数据可弃）
        old_award_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(award_records)"))]
        if old_award_cols and "person_id" in old_award_cols:
            conn.execute(text("DROP TABLE IF EXISTS award_records"))
            conn.execute(text("DROP TABLE IF EXISTS award_recipients"))
        # 补充 all_awardees 列（新字段，旧库可能缺）
        cur_award_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(award_records)"))]
        if cur_award_cols and "all_awardees" not in cur_award_cols:
            conn.execute(text('ALTER TABLE award_records ADD COLUMN all_awardees TEXT'))
        for table in ("people", "projects", "papers", "intellectual_property", "award_records"):
            cols = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))]
            if cols and "extra_json" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN extra_json TEXT"))
        fd_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(field_defs)"))]
        if fd_cols and "show_in_list" not in fd_cols:
            conn.execute(
                text("ALTER TABLE field_defs ADD COLUMN show_in_list BOOLEAN NOT NULL DEFAULT 1")
            )
        proj_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(projects)"))]
        if proj_cols:
            if "duration" not in proj_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN duration VARCHAR(32)"))
                conn.execute(
                    text(
                        "UPDATE projects SET duration = trim(\n"
                        "  coalesce(start_date, '') ||\n"
                        "  CASE WHEN start_date IS NOT NULL AND start_date != '' AND end_date IS NOT NULL AND end_date != '' THEN '-' ELSE '' END ||\n"
                        "  coalesce(end_date, ''))\n"
                        "WHERE (duration IS NULL OR duration = '') AND (start_date IS NOT NULL AND start_date != '' OR end_date IS NOT NULL AND end_date != '')"
                    )
                )
            if "budget_no" not in proj_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN budget_no VARCHAR(64)"))
        # papers 表新增列（通讯作者 / AI提取状态 / GB参考文献字段）；老库缺列会让论文列表与全站搜索整条 500
        paper_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(papers)"))]
        if paper_cols:
            if "corresponding_text" not in paper_cols:
                conn.execute(text("ALTER TABLE papers ADD COLUMN corresponding_text TEXT"))
            if "extract_status" not in paper_cols:
                conn.execute(text("ALTER TABLE papers ADD COLUMN extract_status VARCHAR(16)"))
            # GB/T 7714 参考文献字段：出版地/出版者（会议论文集、专著用）
            if "address" not in paper_cols:
                conn.execute(text("ALTER TABLE papers ADD COLUMN address VARCHAR(128)"))
            if "publisher" not in paper_cols:
                conn.execute(text("ALTER TABLE papers ADD COLUMN publisher VARCHAR(128)"))
        # User 表新增列（登录失败锁定）
        user_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(users)"))]
        if user_cols:
            if "login_fail_count" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN login_fail_count INTEGER NOT NULL DEFAULT 0"))
            if "login_locked_until" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN login_locked_until TIMESTAMP"))
        # attachments 表新增列（行内附件：关联 projects/people/ip/awards）
        att_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(attachments)"))]
        if att_cols:
            for col, ddl in (
                ("entity_type", "VARCHAR(16)"),
                ("entity_id", "INTEGER"),
            ):
                if col not in att_cols:
                    conn.execute(text(f"ALTER TABLE attachments ADD COLUMN {col} {ddl}"))
            # 一篇论文最多一个 PDF：清理历史重复关联——每篇论文只保留最新一条 PDF，
            # 其余解除关联（paper_id=NULL，文件仍留在文献库）
            conn.execute(text(
                "UPDATE attachments SET paper_id = NULL "
                "WHERE att_type = 'pdf' AND entity_type IS NULL AND paper_id IS NOT NULL "
                "AND id NOT IN ("
                "  SELECT MAX(id) FROM attachments "
                "  WHERE att_type = 'pdf' AND entity_type IS NULL AND paper_id IS NOT NULL "
                "  GROUP BY paper_id"
                ")"
            ))


_ensure_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
