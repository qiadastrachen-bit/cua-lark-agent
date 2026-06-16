import cv2
import pyautogui
import time
import os
import sys
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PROJECT_ROOT, SCREENSHOT_DIR as SCREENSHOT_DIR_PATH
from utils.vlm_client import call_vlm
from utils.coords import vlm_coords_to_screen, screen_info_for_prompt

TEMPLATE_PATH = str(PROJECT_ROOT / "assets" / "template_search_box.png")
SCREENSHOT_DIR = str(SCREENSHOT_DIR_PATH)

SEARCH_BOX_LOCATE_PROMPT = """你是飞书 GUI 定位专家。返回顶部【全局搜索框】可点击区域中心坐标。
搜索框通常在窗口最上方，有放大镜图标或「搜索」占位文字。
{screen_info}
只返回: x=数字,y=数字
"""


def opencv_match(screenshot_path, template_path, threshold=0.5, max_y_ratio=0.25):
    screenshot = cv2.imread(screenshot_path)
    template = cv2.imread(template_path)
    if screenshot is None or template is None:
        return None

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    h, w = template.shape[:2]
    center_x = max_loc[0] + w // 2
    center_y = max_loc[1] + h // 2
    screen_h = screenshot.shape[0]

    print(f"  OpenCV best match: {max_val:.3f}")

    if max_val >= threshold and center_y < screen_h * max_y_ratio:
        return center_x, center_y, max_val
    return None


def parse_vlm_coordinates(vlm_output):
    if not vlm_output:
        return None
    for pat in (
        r"x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)",
        r"\(\s*(\d+)\s*,\s*(\d+)\s*\)",
        r"(\d{2,4})\s*,\s*(\d{2,4})",
    ):
        m = re.search(pat, vlm_output)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def vlm_locate_search_box(screenshot_path):
    prompt = SEARCH_BOX_LOCATE_PROMPT.format(screen_info=screen_info_for_prompt(screenshot_path))
    print("  OpenCV failed, trying VLM for search box...")
    out = call_vlm(prompt, screenshot_path, timeout=45, max_retries=2)
    coords = parse_vlm_coordinates(out)
    if not coords:
        return None
    x, y = vlm_coords_to_screen(coords[0], coords[1], screenshot_path)
    print(f"  VLM search box: ({x}, {y})")
    return x, y


def click_search_box():
    result = {
        "success": False,
        "screenshot": "",
        "message": "",
        "screenshots": [],
        "locate_method": "",
    }

    if not os.path.exists(TEMPLATE_PATH):
        msg = f"Missing template: {TEMPLATE_PATH}"
        result["message"] = msg
        print(msg)
        return result

    print("Step1: activate Feishu window...")
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle("飞书") or gw.getWindowsWithTitle("Lark")
        if wins:
            win = wins[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(1)
    except Exception as e:
        print(f"  window activate warning: {e}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    before_path = os.path.join(SCREENSHOT_DIR, f"step01_before_{timestamp}.png")
    pyautogui.screenshot(before_path)
    result["screenshots"].append(before_path)

    match = opencv_match(before_path, TEMPLATE_PATH)
    if match:
        x, y, conf = match
        result["locate_method"] = f"opencv({conf:.3f})"
    else:
        vlm_xy = vlm_locate_search_box(before_path)
        if not vlm_xy:
            result["message"] = "OpenCV and VLM both failed to locate search box"
            return result
        x, y = vlm_xy
        result["locate_method"] = "vlm"

    pyautogui.FAILSAFE = False
    pyautogui.moveTo(x, y, duration=1)
    time.sleep(0.5)
    pyautogui.click()
    time.sleep(1.5)

    after_path = os.path.join(SCREENSHOT_DIR, f"step01_after_{timestamp}.png")
    pyautogui.screenshot(after_path)
    result["screenshots"].append(after_path)
    result["screenshot"] = after_path
    result["success"] = True
    result["message"] = f"Search box clicked ({result['locate_method']})"
    return result


if __name__ == "__main__":
    click_search_box()
