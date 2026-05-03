"""
core/state_checker.py - VLM 状态分析器（M2 核心模块）

功能：
1. 截图 → VLM 分析 → 返回结构化状态 JSON
2. 支持飞书各界面状态识别
3. 作为 M2/M3/M4 的通用状态感知层

状态定义（M1-M2 阶段）：
- feishu_main:       飞书主界面（左侧导航可见）
- search_box_active: 搜索框已激活（光标在搜索框内）
- searching:         正在输入搜索文字
- search_results:     搜索结果已显示（中间面板有结果列表）
- chat_window:       已进入聊天窗口
- calendar_view:      日历界面
- doc_editing:       文档编辑界面
- unknown:           无法识别的状态
- error:             出错（弹窗/权限提示等）
"""

import base64
import json
import re
import time
import os
from datetime import datetime

# VLM API 配置（复用 step_04 的配置）
API_KEY = "ark-f11e281e-ef25-4cb0-a1ee-c7d14e8d76d4-7419d"
ENDPOINT_ID = "ep-20260423222711-8zfcd"
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# 状态分析 Prompt
STATE_ANALYSIS_PROMPT = """你是一个飞书界面分析专家。请仔细分析这张截图，判断当前屏幕状态。

**可识别的状态（必须严格返回其中之一）：**

1. `feishu_main`      — 飞书主界面，左侧有导航栏（消息/通讯录/云文档等图标）
2. `search_box_active` — 搜索框已激活，光标在搜索框内，可以输入文字
3. `searching`        — 正在输入搜索文字，搜索框有内容但未出结果
4. `search_results`    — 搜索结果已显示，中间面板有结果列表（"消息|云文档|应用|联系人"标签栏可见）
5. `chat_window`       — 已进入聊天窗口，右侧/中间有大片聊天记录区域
6. `calendar_view`     — 日历界面，可见日历网格/日程列表
7. `doc_editing`       — 文档编辑界面，可见文档内容和编辑工具栏
8. `error`             — 出现错误提示、权限弹窗、加载失败等异常
9. `unknown`           — 无法判断当前状态

**返回格式（严格 JSON）：**
```json
{{
  "state": "状态名称",
  "description": "一句话描述当前屏幕内容",
  "can_proceed": true/false,
  "next_suggested_action": "建议的下一步动作（英文，如下拉：click_search / type_text / wait / click_first_result / send_message / unknown）",
  "confidence": 0.95
}}
```

**注意：**
- 必须返回**合法 JSON**，不要有多余文字
- confidence 是你对判断的置信度（0.0~1.0）
- 如果截图中有弹窗/异常，state 必须是 `error`，description 描述异常内容
"""

TIMEOUT = 60


def _call_vlm_for_state(image_path, timeout=TIMEOUT):
    """调用 VLM 分析屏幕状态"""
    import requests

    if not os.path.exists(image_path):
        print(f"  ❌ 截图文件不存在: {image_path}")
        return None

    with open(image_path, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": ENDPOINT_ID,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": STATE_ANALYSIS_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            }
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content.strip()
    except requests.exceptions.Timeout:
        print(f"  ⚠️ VLM 状态分析超时 (>{timeout}s)")
        return None
    except Exception as e:
        print(f"  ❌ VLM 状态分析失败: {e}")
        return None


def _parse_state_response(vlm_output):
    """解析 VLM 返回的 JSON 状态"""
    if not vlm_output:
        return None

    # 尝试直接解析 JSON
    try:
        # 去掉可能的 markdown 代码块包裹
        cleaned = vlm_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        return data
    except json.JSONDecodeError:
        pass

    # 尝试从文本中提取 JSON
    json_match = re.search(r'\{.*\}', vlm_output, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # 兜底：尝试从文字描述中推断状态
    text = vlm_output.lower()
    state_hints = {
        "feishu_main": ["主界面", "导航", "消息列表"],
        "search_results": ["搜索结果", "标签栏", "第一条"],
        "chat_window": ["聊天", "消息记录", "对话"],
        "calendar_view": ["日历", "日程", "calendar"],
        "doc_editing": ["文档", "编辑", "doc"],
        "error": ["错误", "弹窗", "权限", "失败"],
    }
    for state_name, keywords in state_hints.items():
        if any(kw in text for kw in keywords):
            return {
                "state": state_name,
                "description": vlm_output[:100],
                "can_proceed": True,
                "confidence": 0.5
            }

    return None


def check_state(screenshot_path=None, save_screenshot=True, timeout=TIMEOUT):
    """
    截图并分析当前飞书界面状态。

    返回：
        dict: {
            "state": str,           # 状态名称
            "description": str,     # 状态描述
            "can_proceed": bool,    # 是否可以继续执行
            "next_action": str,     # 建议的下一步动作
            "confidence": float,    # 置信度
            "screenshot": str       # 截图路径（如果 save_screenshot=True）
        }
        None: 分析失败
    """
    import pyautogui

    # 截图
    if screenshot_path is None and save_screenshot:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_dir = "D:/feishu-cua-challenge/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f"state_check_{timestamp}.png")

    if screenshot_path:
        pyautogui.screenshot(screenshot_path)
        print(f"  📸 状态检测截图: {screenshot_path}")
    else:
        # 使用临时截图（不保存）
        tmp_path = os.path.join(os.path.dirname(__file__), "..", "screenshots", "state_check_tmp.png")
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        pyautogui.screenshot(tmp_path)
        screenshot_path = tmp_path

    # 调用 VLM 分析
    print("  🤖 VLM 状态分析中...")
    vlm_output = _call_vlm_for_state(screenshot_path, timeout=timeout)

    if not vlm_output:
        print("  ❌ 状态分析失败：VLM 无返回")
        return None

    # 解析结果
    result = _parse_state_response(vlm_output)

    if not result:
        print(f"  ⚠️ 状态解析失败，VLM 原始返回: {vlm_output[:200]}")
        return None

    # 标准化返回
    state_info = {
        "state": result.get("state", "unknown"),
        "description": result.get("description", ""),
        "can_proceed": result.get("can_proceed", True),
        "next_action": result.get("next_suggested_action", "unknown"),
        "confidence": result.get("confidence", 0.5),
        "screenshot": screenshot_path if save_screenshot else None,
    }

    print(f"  ✅ 状态: {state_info['state']} ({state_info['confidence']:.0%}) — {state_info['description'][:60]}")
    return state_info


def is_target_state(current_state, target_states):
    """
    判断当前状态是否在目标状态列表中。
    target_states: str 或 list
    """
    if isinstance(target_states, str):
        target_states = [target_states]
    return current_state.get("state") in target_states


def wait_for_state(target_states, timeout=15, check_interval=1.5):
    """
    等待直到进入目标状态之一。
    返回：state_info dict 或 None（超时）
    """
    import time

    print(f"  ⏳ 等待状态: {target_states} (timeout={timeout}s)")
    start = time.time()

    while time.time() - start < timeout:
        state_info = check_state(save_screenshot=False, timeout=30)
        if state_info and is_target_state(state_info, target_states):
            print(f"  ✅ 状态已达: {state_info['state']}")
            return state_info
        time.sleep(check_interval)

    print(f"  ❌ 等待状态超时 ({timeout}s)")
    return None


# ====== 动作映射（M2 流程使用）======
# 状态 → 建议动作的映射表（供 flow 脚本参考）
STATE_ACTION_MAP = {
    "feishu_main": ["click_search", "open_app"],
    "search_box_active": ["type_text"],
    "searching": ["wait", "continue_typing"],
    "search_results": ["click_first_result", "refine_search"],
    "chat_window": ["type_message", "send_message", "click_back"],
    "calendar_view": ["create_event", "click_event"],
    "doc_editing": ["type_text", "format_text", "save_doc"],
    "error": ["handle_error", "dismiss_popup", "retry"],
    "unknown": ["screenshot_debug", "reset"],
}


if __name__ == "__main__":
    # 测试：截图并分析当前状态
    print("=== 状态检测器测试 ===")
    result = check_state()
    if result:
        print(f"\n结果：")
        print(f"  状态: {result['state']}")
        print(f"  描述: {result['description']}")
        print(f"  置信度: {result['confidence']:.0%}")
        print(f"  建议动作: {result['next_action']}")
    else:
        print("状态分析失败")
