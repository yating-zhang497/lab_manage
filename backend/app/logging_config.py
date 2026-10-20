"""统一日志配置：stdout + 可选文件。

环境变量：
- ``IM_LOG_LEVEL``: DEBUG/INFO/WARN/ERROR，默认 INFO
- ``IM_LOG_FILE``: 文件路径，未设则只输出 stdout
"""
import logging
import os
import sys
from pathlib import Path


def setup_logging() -> None:
    """配置 root logger：stdout handler + 可选 file handler。

    幂等：多次调用不会重复添加 handler。测试环境也安全（pytest 默认捕获 stdout）。
    """
    level_name = os.environ.get("IM_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()  # 清掉默认 handler，避免重复

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(level)
    root.addHandler(sh)

    file_path = os.environ.get("IM_LOG_FILE")
    if file_path:
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(file_path, encoding="utf-8")
            fh.setFormatter(fmt)
            fh.setLevel(level)
            root.addHandler(fh)
        except OSError:
            # 文件不可写时不让进程启动失败
            root.warning("无法打开日志文件 %s，仅用 stdout", file_path)

    # 收紧常用库的噪声
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
