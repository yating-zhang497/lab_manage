from datetime import datetime
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# 必须在 database 导入前 setup_logging()：database 模块加载时即触发 _ensure_schema()，
# 其中会 logger.info/error 输出 schema 迁移结果，logger 没 handler 时输出会丢
from .logging_config import setup_logging

setup_logging()
logger = logging.getLogger("app.main")

from .database import Base, engine, SessionLocal  # noqa: E402
from .models import Archive  # noqa: E402
from .routers import (  # noqa: E402
    ai, archives, auth, awards, exports, fields, imports,
    ip, papers, people, projects, search, pdfs, attachments, users,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Research Group Information Management API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_http_errors(request: Request, call_next):
    """记录 4xx/5xx 请求：4xx 用 INFO（用户操作问题），5xx 用 ERROR（真实 bug）。"""
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    if response.status_code >= 500:
        logger.error(
            "%s %s -> %d %.0fms",
            request.method, request.url.path, response.status_code, elapsed_ms,
        )
    elif response.status_code >= 400:
        logger.info(
            "%s %s -> %d %.0fms",
            request.method, request.url.path, response.status_code, elapsed_ms,
        )
    return response

API_PREFIX = "/api"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(people.router, prefix=API_PREFIX)
app.include_router(projects.router, prefix=API_PREFIX)
app.include_router(papers.router, prefix=API_PREFIX)
app.include_router(ip.router, prefix=API_PREFIX)
app.include_router(awards.router, prefix=API_PREFIX)
app.include_router(ai.router, prefix=API_PREFIX)
app.include_router(imports.router, prefix=API_PREFIX)
app.include_router(exports.router, prefix=API_PREFIX)
app.include_router(fields.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(pdfs.router, prefix=API_PREFIX)
app.include_router(attachments.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(archives.router, prefix=API_PREFIX)


@app.on_event("startup")
def start_scheduler():
    scheduler = BackgroundScheduler()

    def monthly_auto_export():
        """每月1日凌晨2点自动导出四个模块数据。"""
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            month_key = now.strftime("%Y-%m")
            for entity in ("people", "projects", "papers", "ip"):
                # 同月份已有自动存档则跳过
                existing = db.query(Archive).filter(
                    Archive.entity == entity,
                    Archive.is_auto == True,
                    Archive.filename.like(f"%{month_key}%"),
                ).first()
                if existing:
                    continue
                try:
                    archives._do_export(db, entity, username="system", is_auto=True)
                except Exception:
                    logger.exception("自动导出 %s 失败", entity)
        finally:
            db.close()

    scheduler.add_job(
        monthly_auto_export,
        CronTrigger(day=1, hour=2, minute=0),
        id="monthly_auto_export",
        replace_existing=True,
    )
    scheduler.start()


@app.get("/api/health")
def health():
    return {"status": "ok"}
