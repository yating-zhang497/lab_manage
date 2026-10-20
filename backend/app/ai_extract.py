"""PDF 自动提取通讯作者与基金信息。

参考原手工脚本 tool_for_papers/corresponding_author_fund.py 并改进：
- 提示词同时覆盖论文头部（作者/邮箱）与尾部（致谢/基金段落）
- 提取结果自动与项目库（编号匹配）和人员库（英文名模糊匹配）比对
- API Key 仅从环境变量 IM_LLM_API_KEY 读取
"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable, Optional

from thefuzz import fuzz

from .config import AUTHOR_MATCH_THRESHOLD, LLM_DEFAULT_BASE_URL, LLM_DEFAULT_MODEL

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

PROMPT_TEMPLATE = """你是一个科研文档解析专家。请从提供的论文文本中提取以下信息：

1. 通讯作者信息：找到标注为 Corresponding author(s) 的那句，照抄该句的完整原文——可能包含多个姓名和多个 Email，以句号、分号或换行作为该句结束，不要只取一位、不要省略、不要改写。整句照抄即可。
2. 致谢原文：完整返回致谢（Acknowledgements / Funding）段落的原文，不要改写，不要省略。
3. 基金项目编号：从致谢段落中识别并列出所有项目编号（如 62172016、2022YFA1303000、19ZDA105、U20A2038 等格式），仅列出编号，不要解释。

要求：
- 返回 JSON，包含三个键：
  * author：通讯作者那句的完整原文，例如 "Corresponding author: Zhang San, zhangsan@example.com; Li Si, lisi@example.com."；若文中未标注通讯作者则填 "Not Found"
  * funding_text：致谢段落原文，原文是什么就返回什么，不要省略、不要改写；若不存在则填 "Not Found"
  * funding_nos：项目编号列表，如 ["62172016", "2022YFA1303000"]；若没有则填 []
- 三个字段缺一不可，不要省略任何字段。

待处理文本：
{text}
"""


def extract_text(pdf_io) -> str:
    """使用 pypdf 提取全部页面文本。"""
    from pypdf import PdfReader

    reader = PdfReader(pdf_io)
    parts = []
    for i, page in enumerate(reader.pages):
        parts.append(f"\n--- Page {i + 1} ---\n")
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    text = "".join(parts)
    # 去除 pypdf 可能产生的孤立代理字符（数学粗斜体等符号的 UTF-16 残片），
    # 否则后续 UTF-8 编码（HTTP 请求体）会报 surrogates not allowed
    text = text.encode("utf-8", errors="replace").decode("utf-8")
    return text


def build_prompt(text: str) -> str:
    """直接返回完整文本，不截断，确保致谢不被遗漏。"""
    return PROMPT_TEMPLATE.format(text=text)


def get_llm_settings() -> dict:
    return {
        "base_url": os.environ.get("IM_LLM_BASE_URL", LLM_DEFAULT_BASE_URL),
        "api_key": os.environ.get("IM_LLM_API_KEY", ""),
        "model": os.environ.get("IM_LLM_MODEL", LLM_DEFAULT_MODEL),
    }


def call_llm(prompt: str, settings: dict) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
    resp = client.chat.completions.create(
        model=settings["model"],
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=180,
    )
    return json.loads(resp.choices[0].message.content)


def clean_name_text(author_field) -> str:
    """去掉邮箱、括号备注、特殊标记，保留纯姓名文本。"""
    if not isinstance(author_field, str):
        author_field = str(author_field) if author_field else ""
    s = EMAIL_RE.sub(" ", author_field)
    s = re.sub(r"(?i)\(?corresponding\s+author[s]?\s*[:：]?\)?", " ", s)
    stripped = re.sub(r"[（(].*?[)）]", " ", s).strip()
    s = stripped if stripped else re.sub(r"[（）()]", " ", s).strip()
    s = re.sub(r"[*†‡§¶#]", " ", s)
    return re.sub(r"\s+", " ", s).strip(" ,;:\t.）)")


def person_name_candidates(english_name: Optional[str], variants: Iterable[str]) -> list:
    """生成英文名的小写变体集合：容忍大小写、姓/名顺序、缩写与标点差异。"""
    cands = set()
    for nm in [english_name or "", *variants]:
        n = (nm or "").strip().lower().replace(".", " ")
        n = " ".join(n.split())
        if not n:
            continue
        cands.add(n)
        if "," in n:
            last, first = (x.strip() for x in n.split(",", 1))
            if last and first:
                cands.add(f"{first} {last}")
                cands.add(f"{last} {first}")
                fl = first.split()[0][0] if first.split() else ""
                if fl:
                    cands.add(f"{last} {fl}")
                    cands.add(f"{fl} {last}")
                    cands.add(f"{last}, {fl}")
        else:
            parts = n.split()
            if len(parts) == 2:
                cands.add(f"{parts[1]}, {parts[0]}")
                cands.add(f"{parts[0]} {parts[1][0]}")
                cands.add(f"{parts[1][0]} {parts[0]}")
                cands.add(f"{parts[1]} {parts[0]}")
    return list(cands)


def _windows(words: list, n: int) -> list:
    if len(words) <= n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def match_corresponding(
    author_text, people: list, threshold: int = AUTHOR_MATCH_THRESHOLD
) -> Optional[dict]:
    """把 LLM 返回的通讯作者文本与人员库英文名做模糊匹配。"""
    cleaned = clean_name_text(author_text).lower()
    if not cleaned or cleaned == "not found":
        return None
    words = cleaned.split()
    probes = {cleaned}
    probes.update(_windows(words, 2))
    probes.update(_windows(words, 3))

    best = None
    for person in people:
        cands = person_name_candidates(
            getattr(person, "english_name", None),
            [v.name_text for v in getattr(person, "name_variants", [])],
        )
        for probe in probes:
            for cand in cands:
                score = fuzz.token_set_ratio(probe, cand)
                if best is None or score > best["score"]:
                    best = {
                        "person_id": person.id,
                        "person_name": person.name,
                        "matched_name": cand,
                        "score": score,
                    }
    if best and best["score"] >= threshold:
        return best
    return None


def match_funding_projects(funding_info, projects: list) -> list:
    """从 LLM 返回的 funding 信息中匹配项目库。

    funding_info 可以是：
      - 列表：直接是项目编号字符串列表
      - 字符串：致谢原文，需要从中提取项目编号

    返回列表中每项含：
      - seq: 仅 matched=True 的项按匹配顺序编号（1起）
      - project_no: 项目编号原文
      - project_id: 若能在项目库中匹配到则返回其id，否则null
      - matched: 是否匹配到项目库
    """
    # 处理 LLM 返回的列表（直接是编号列表）
    if isinstance(funding_info, list):
        raw_nos = [str(x).strip() for x in funding_info if x and str(x).strip().lower() != "not found"]
    elif isinstance(funding_info, str):
        if not funding_info or funding_info.strip().lower() == "not found":
            return []
        raw_nos = _extract_funding_nos(funding_info)
    else:
        return []

    if not raw_nos:
        return []

    # 建立项目编号→id的快速查找表（去空格大写）
    no_to_id = {}
    for p in projects:
        no = (p.project_no or "").strip()
        if len(no) < 5:
            continue
        key = re.sub(r"\s+", "", no.upper())
        no_to_id[key] = {"project_id": p.id, "project_no": no}

    final = []
    seq = 0
    seen_keys = set()
    for raw in raw_nos:
        key = re.sub(r"\s+", "", raw.upper())
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        if key in no_to_id:
            seq += 1
            final.append({
                "seq": seq,
                "project_no": no_to_id[key]["project_no"],
                "project_id": no_to_id[key]["project_id"],
                "matched": True,
            })
        else:
            final.append({
                "seq": 0,
                "project_no": raw,
                "project_id": None,
                "matched": False,
            })
    return final


def _extract_funding_nos(text: str) -> list:
    """从致谢原文中提取所有项目编号。"""
    # 项目编号常见格式：62172016、2022YFA1303000、19ZDA105、U20A2038 等
    pattern = re.compile(r"\b[A-Za-z0-9]{6,}\b")
    result = []
    for m in pattern.finditer(text):
        raw = m.group().strip()
        if not any(ch.isdigit() for ch in raw):
            continue  # 纯字母单词不是项目编号
        result.append(raw)
    return result
