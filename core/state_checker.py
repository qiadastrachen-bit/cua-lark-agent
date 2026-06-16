"""
core/state_checker.py - VLM 状态分析器

截图 → VLM → 结构化状态 JSON，供 run_all 步骤间门禁使用。
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from config import SCREENSHOT_DIR, ENABLE_STATE_CHECK
from utils.vlm_client import call_vlm_json

STATE_ANALYSIS_PROMPT = """你是一个飞书界面分析专家。请仔细分析这张截图，判断当前屏幕状态。

可识别状态（必须严格返回其中之一）：
feishu_main, search_box_active, searching, search_results, chat_window,
calendar_view, doc_editing, error, unknown

返回严格 JSON（不要 markdown）：
{"state":"状态名","description":"一句话","can_proceed":true,"next_suggested_action":"click_search","confidence":0.95}
"""


def _parse_state_response(vlm_output: str | None) -> dict | None:
    if not vlm_output:
        return None

    cleaned = vlm_output.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip("` \n")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"\{.*\}", vlm_output, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    text = vlm_output.lower()
    hints = {
        "search_results": ["搜索结果", "标签栏"],
        "search_box_active": ["搜索框", "光标"],
        "chat_window": ["聊天", "对话"],
        "doc_editing": ["文档", "编辑"],
        "error": ["错误", "弹窗", "失败"],
    }
    for state_name, keywords in hints.items():
        if any(k in text for k in keywords):
            return {
                "state": state_name,
                "description": vlm_output[:100],
                "can_proceed": True,
                "confidence": 0.5,
            }
    return None


def check_state_from_image(screenshot_path: str, timeout: int = 45) -> dict | None:
    """Analyze an existing screenshot (no new capture)."""
    if not ENABLE_STATE_CHECK:
        return None
    if not os.path.exists(screenshot_path):
        print(f"  [WARN] state check: missing screenshot {screenshot_path}")
        return None

    print(f"  [state] analyzing {os.path.basename(screenshot_path)}...")
    result = call_vlm_json(STATE_ANALYSIS_PROMPT, screenshot_path, timeout=timeout, max_retries=1)
    if not result:
        print("  [WARN] state parse failed")
        return None

    info = {
        "state": result.get("state", "unknown"),
        "description": result.get("description", ""),
        "can_proceed": result.get("can_proceed", True),
        "next_action": result.get("next_suggested_action", "unknown"),
        "confidence": float(result.get("confidence", 0.5)),
        "screenshot": screenshot_path,
    }
    print(f"  [state] {info['state']} ({info['confidence']:.0%}) — {info['description'][:50]}")
    return info


def check_state(save_screenshot: bool = True, screenshot_path: str | None = None, timeout: int = 45) -> dict | None:
    import pyautogui

    if not ENABLE_STATE_CHECK:
        return None

    if screenshot_path is None:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = str(SCREENSHOT_DIR / f"state_check_{ts}.png")
        pyautogui.screenshot(screenshot_path)
        print(f"  [state] captured {screenshot_path}")
    elif save_screenshot is False and not os.path.exists(screenshot_path):
        import pyautogui
        pyautogui.screenshot(screenshot_path)

    return check_state_from_image(screenshot_path, timeout=timeout)


def is_target_state(state_info: dict | None, target_states: str | list[str]) -> bool:
    if not state_info:
        return False
    if isinstance(target_states, str):
        target_states = [target_states]
    return state_info.get("state") in target_states


def gate_step(
    screenshot_path: str | None,
    expected_states: list[str],
    step_label: str,
    strict: bool = False,
    min_confidence: float = 0.55,
) -> tuple[bool, str, dict | None]:
    """
    Returns (ok, message, state_info).
    strict=False: mismatch only warns; strict=True: mismatch fails step.
    """
    if not ENABLE_STATE_CHECK or not screenshot_path:
        return True, "", None

    info = check_state_from_image(screenshot_path)
    if info is None:
        msg = f"{step_label}: 状态检测跳过（VLM 不可用或解析失败）"
        return (False, msg, None) if strict else (True, msg, None)

    if is_target_state(info, expected_states):
        return True, f"{step_label}: 状态 OK ({info['state']})", info

    msg = (
        f"{step_label}: 期望 {expected_states}，实际 {info['state']} "
        f"(conf={info['confidence']:.0%})"
    )
    if strict and info["confidence"] >= min_confidence:
        return False, msg, info
    return True, f"[WARN] {msg}", info


STATE_ACTION_MAP = {
    "feishu_main": ["click_search"],
    "search_box_active": ["type_text"],
    "search_results": ["click_first_result"],
    "chat_window": ["send_message", "verify"],
    "doc_editing": ["verify"],
    "error": ["retry"],
    "unknown": ["screenshot_debug"],
}
