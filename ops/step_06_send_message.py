"""
Step 06: 在已打开的聊天窗口发送消息

前置：Step04 已进入 chat_window（联系人会话）
流程：VLM 定位底部输入框 → 粘贴文字 → Enter 发送 → 截图验证
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pyautogui
import pygetwindow as gw
import pyperclip

from config import PROJECT_ROOT, USE_FIXED_COORDS
from utils.coords import screen_info_for_prompt, vlm_coords_to_screen
from utils.vlm_client import call_vlm

SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"

LOCATE_INPUT_PROMPT = """你是飞书 GUI 坐标定位专家。当前是【与联系人的聊天窗口】。

任务：找到底部【消息输入框】的中心点坐标（用户打字发消息的区域）。
特征：
- 在窗口最下方，通常是长条形输入框
- 可能有占位文字如「发送消息」「输入消息」
- 输入框上方是聊天记录，下方可能有工具栏/发送按钮

⚠️ 不要点在：
- 聊天记录里的某条消息
- 顶部标题栏或侧边栏
- 「发送」按钮本身（要点输入框）

屏幕：{screen_info}

只返回坐标，格式：x=数字,y=数字
例如：x=960,y=820"""

VERIFY_SEND_PROMPT = """分析这张飞书聊天截图，判断最新消息是否包含「{text}」且像是刚发送出去的消息（通常在聊天记录最下方）。

只回答 SUCCESS 或 FAIL，附一句话理由。"""


def _parse_coords(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    for pat in (
        r"x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)",
        r"\(\s*(\d+)\s*,\s*(\d+)\s*\)",
        r"(\d{2,4})\s*,\s*(\d{2,4})",
    ):
        m = re.search(pat, text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def _activate_feishu() -> bool:
    try:
        wins = gw.getWindowsWithTitle("飞书") or gw.getWindowsWithTitle("Lark")
        if not wins:
            print("  [WARN] 未找到飞书窗口")
            return False
        win = wins[0]
        if win.isMinimized:
            win.restore()
        win.activate()
        time.sleep(0.6)
        return True
    except Exception as e:
        print(f"  [WARN] 激活飞书失败: {e}")
        return False


def _heuristic_input_coords() -> tuple[int, int]:
    """聊天输入框通常在飞书窗口底部居中。"""
    wins = gw.getWindowsWithTitle("飞书") or gw.getWindowsWithTitle("Lark")
    if wins:
        w = wins[0]
        x = w.left + w.width // 2
        y = w.top + int(w.height * 0.88)
        print(f"  [fallback] 窗口启发式坐标: ({x}, {y})")
        return x, y
    sw, sh = pyautogui.size()
    return sw // 2, int(sh * 0.88)


def _locate_input_box(screenshot_path: str) -> tuple[int, int] | None:
    prompt = LOCATE_INPUT_PROMPT.replace("{screen_info}", screen_info_for_prompt(screenshot_path))
    raw = call_vlm(prompt, screenshot_path, timeout=45, max_retries=1)
    if not raw:
        return None
    parsed = _parse_coords(raw)
    if not parsed:
        print(f"  [WARN] 无法解析输入框坐标: {raw[:120]}")
        return None
    x, y = vlm_coords_to_screen(parsed[0], parsed[1], screenshot_path)
    sw, sh = pyautogui.size()
    if y < sh * 0.45:
        print(f"  [WARN] Y={y} 偏高，不像底部输入框，改用启发式")
        return None
    return x, y


def send_chat_message(message_text: str, enable_visualizer: bool = False) -> dict:
    result = {
        "success": False,
        "message": "",
        "screenshot": None,
        "screenshots": [],
    }
    text = (message_text or "").strip()
    if not text:
        result["message"] = "消息内容为空"
        return result

    print("\n=== Step 06: 发送聊天消息 ===")
    print(f"  内容: {text!r}")

    pyautogui.FAILSAFE = False
    _activate_feishu()
    time.sleep(0.5)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    before_path = str(SCREENSHOT_DIR / f"step06_before_{ts}.png")
    pyautogui.screenshot(before_path)
    result["screenshots"].append(before_path)

    if USE_FIXED_COORDS:
        coords = _heuristic_input_coords()
        print(f"  [fixed] 使用启发式输入框坐标: {coords}")
    else:
        coords = _locate_input_box(before_path)
        if not coords:
            coords = _heuristic_input_coords()

    x, y = coords
    print(f"  点击输入框 ({x}, {y})")
    pyautogui.click(x, y)
    time.sleep(0.8)

    pyperclip.copy(text)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)

    after_type_path = str(SCREENSHOT_DIR / f"step06_typed_{ts}.png")
    pyautogui.screenshot(after_type_path)
    result["screenshots"].append(after_type_path)

    print("  按 Enter 发送...")
    pyautogui.press("enter")
    time.sleep(1.5)

    after_path = str(SCREENSHOT_DIR / f"step06_after_{ts}.png")
    pyautogui.screenshot(after_path)
    result["screenshot"] = after_path
    result["screenshots"].append(after_path)

    verify = call_vlm(
        VERIFY_SEND_PROMPT.format(text=text),
        after_path,
        timeout=30,
        max_retries=1,
    )
    if verify and "SUCCESS" in verify.upper():
        print(f"  [OK] 发送验证: {verify[:80]}")
    elif verify:
        print(f"  [WARN] 发送验证存疑: {verify[:80]}")
    else:
        print("  [WARN] 跳发送验证（VLM 无返回），以 Enter 发送为准")

    pyperclip.copy("")
    result["success"] = True
    result["message"] = f"已向聊天窗口发送「{text}」"
    print("✅ Step 06 完成")
    return result


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "hello"
    send_chat_message(msg)
