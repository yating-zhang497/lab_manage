from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "runtime"
DATA_DIR.mkdir(exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATA_DIR / 'im.db'}"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

TOKEN_TTL_DAYS = 7

# LLM 配置默认值（实际值从环境变量读取，禁止硬编码密钥）
LLM_DEFAULT_BASE_URL = "https://api.deepseek.com"
LLM_DEFAULT_MODEL = "deepseek-chat"

# 通讯作者模糊匹配阈值(0-100)，可用环境变量 IM_AUTHOR_MATCH_THRESHOLD 覆盖
AUTHOR_MATCH_THRESHOLD = int(os.environ.get("IM_AUTHOR_MATCH_THRESHOLD", "80"))
