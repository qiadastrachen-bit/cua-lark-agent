"""
Parse natural-language test instructions into structured tasks.
"""

from __future__ import annotations

import json
import re

from config import vlm_configured
from utils.vlm_client import call_chat

SEARCH_PATTERNS = [
    re.compile(r"(?:搜索|查找|搜一下|搜|search)\s*[「\"'『]?(.+?)[」\"'』]?(?:并|然后)?(?:打开|点击)?(?:第一(?:条|个)结果)?$", re.I),
    re.compile(r"(?:在飞书)?(?:里|中)?(?:搜索|查找)\s*(.+?)(?:并打开|$)", re.I),
    re.compile(r"^search\s+(.+)$", re.I),
]

MESSAGE_PATTERNS = [
    re.compile(
        r"(?:搜索|查找|搜)\s*[「\"'『]?(.+?)[」\"'』]?\s*(?:并|然后)?(?:给)?(?:她|他|对方)?(?:发送|发)\s*[「\"'『]?(.+?)[」\"'』]?\s*$",
        re.I,
    ),
    re.compile(
        r"(?:给|向)\s*[「\"'『]?(.+?)[」\"'』]?\s*(?:发送|发)\s*[「\"'『]?(.+?)[」\"'』]?\s*$",
        re.I,
    ),
    re.compile(
        r"^search\s+(.+?)\s+and\s+send\s+[「\"'『]?(.+?)[」\"'』]?\s*$",
        re.I,
    ),
]


def _regex_parse(instruction: str) -> dict | None:
    text = instruction.strip()
    if not text:
        return None
    for pat in MESSAGE_PATTERNS:
        m = pat.search(text)
        if m:
            term = m.group(1).strip(" ，。.")
            msg = m.group(2).strip(" ，。.")
            if term and msg:
                return {
                    "flow": "search_and_message",
                    "search_term": term,
                    "message_text": msg,
                    "source": "regex",
                }
    for pat in SEARCH_PATTERNS:
        m = pat.search(text)
        if m:
            term = m.group(1).strip(" ，。.")
            if term:
                return {"flow": "search", "search_term": term, "source": "regex"}
    return None


def _llm_parse(instruction: str) -> dict | None:
    if not vlm_configured(for_vision=False):
        return None

    prompt = f"""Parse this Feishu test instruction into JSON.
Keys: flow ("search" or "search_and_message"), search_term (string), message_text (string, optional).

Instruction: {instruction}

Return json only, examples:
{{"flow":"search","search_term":"陈锦彤"}}
{{"flow":"search_and_message","search_term":"陈锦彤","message_text":"hello"}}"""

    content = call_chat(prompt, timeout=30, max_retries=1, json_mode=True)
    if not content:
        return None
    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip("` \n")
        data = json.loads(cleaned)
        flow = data.get("flow")
        if flow in ("search", "search_and_message") and data.get("search_term"):
            if flow == "search_and_message" and not data.get("message_text"):
                data["flow"] = "search"
            data["source"] = "llm"
            return data
    except (json.JSONDecodeError, TypeError) as e:
        print(f"  [WARN] LLM task parse failed: {e}")
    return None


def parse_instruction(instruction: str, use_llm: bool = True) -> dict:
    parsed = _regex_parse(instruction)
    if parsed:
        return parsed
    if use_llm:
        parsed = _llm_parse(instruction)
        if parsed:
            return parsed
    if len(instruction.strip()) <= 64:
        return {"flow": "search", "search_term": instruction.strip(), "source": "passthrough"}
    raise ValueError(f"无法解析指令: {instruction}")
