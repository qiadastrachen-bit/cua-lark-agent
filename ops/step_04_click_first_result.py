"""
Step 04: 点击第一条搜索结果（简化版 VLM 定位）

架构：
1. VLM 一步定位 → 坐标输出
2. 移动鼠标到目标位置
3. 点击
4. 结果验证

优化点：
- VLM 调用从 3 次降为 1 次（去掉了分析+确认两步）
- 保留结果验证确保点击有效
"""

import cv2
import numpy as np
import pyautogui
import time
import os
import sys
import base64
import requests
import re
from datetime import datetime
from PIL import Image  # 用于压缩截图后再发给VLM
from config import API_KEY, ENDPOINT_ID, API_URL, PROJECT_ROOT, USE_FIXED_COORDS, FIXED_COORDS
from utils.coords import vlm_coords_to_screen, screen_info_for_prompt, screen_coords_to_screenshot
from utils.vlm_client import call_vlm as vlm_request
from utils.vlm_client import call_vlm_multi_image

# SCREENSHOT_DIR 统一使用项目相对路径
SCREENSHOT_DIR = str(PROJECT_ROOT / "screenshots")

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.mouse_visualizer import MouseVisualizer

SIMPLE_LOCATE_PROMPT = """你是一个飞书GUI坐标定位专家。任务：返回飞书搜索结果中【第一条可点击结果】的中心点坐标。

界面结构（从上到下）：
- 最顶部：搜索框（输入框，里面有文字）
- 搜索框下方：一行标签栏（消息｜云文档｜应用｜联系人｜群组｜日历｜服务台｜妙记｜任务）
- 标签栏正下方：就是【第一条搜索结果】

第一条结果的视觉特征：
- 左侧有一个圆形头像/图标
- 右侧是名称文字（如人名、群名、文档名等）
- 整个条目可以点击
- 它是标签栏下方的第一个条目

⚠️ 坐标要求：
- 必须点在第一条结果的【文字或头像】上
- 不要点在标签栏上
- 不要点在空白处
- 不要点在"展开更多"、"在云文档中搜索更多"等辅助文字上

屏幕分辨率：{screen_info}

**只返回坐标**，格式：x=数字,y=数字
例如：x=960,y=350"""

VERIFY_PROMPT = """你是一个飞书界面分析专家。请对比这两张截图的变化。

第一张（操作前）：显示的是飞书搜索结果面板
第二张（操作后）：点击后的界面

任务：判断点击操作是否成功打开了搜索结果。

成功标志：
- ✅ 搜索面板关闭了，进入了某个详情页
- ✅ 或者面板内容变成了具体的页面内容
- ✅ 或者出现了新的标签页/窗口

失败标志：
- ❌ 两张图几乎一样（没点到东西）
- ❌ 还是搜索结果面板（点击无效）

返回格式：
如果成功：SUCCESS
如果失败：FAIL + 一句话说明"""

MAX_VLM_RETRIES = 1  # 遇到429直接放弃，不浪费等待时间
VLM_RETRY_BASE_DELAY = 15  # 从10升到15
VLM_TIMEOUT = 30  # 从25升到30

MARGIN = 50


def call_vlm(image_path, prompt, max_retries=MAX_VLM_RETRIES, timeout=VLM_TIMEOUT):
    """Wrapper: image-first arg order for this module."""
    return vlm_request(prompt, image_path, max_retries=max_retries, timeout=timeout)


def parse_vlm_coordinates(vlm_output):
    """从 VLM 输出中解析坐标"""
    if not vlm_output:
        return None

    match = re.search(r'x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)', vlm_output)
    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.search(r'\(\s*(\d+)\s*,\s*(\d+)\s*\)', vlm_output)
    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.search(r'(\d{2,4})\s*,\s*(\d{2,4})', vlm_output)
    if match:
        return int(match.group(1)), int(match.group(2))

    return None


def validate_coordinates(x, y, auto_adjust=True):
    """基本坐标合理性检查 + 过渡区自动修正"""
    screen_w, screen_h = pyautogui.size()

    if x < MARGIN or x > screen_w - MARGIN or y < MARGIN or y > screen_h - MARGIN:
        print(f"  ⚠️ 坐标太靠近屏幕边缘: ({x}, {y}), 屏幕尺寸: {screen_w}x{screen_h}")
        return False

    # Y坐标检查：VLM经常把Y算偏高（点到标签栏而非结果列表）
    # 搜索框+标签栏区域大约在 y=0~200（2K屏），搜索结果列表从 ~200 开始
    min_y = int(screen_h * 0.10)   # ~160px，低于此直接拒绝
    warning_y = int(screen_h * 0.18) # ~288px，此值以下可能是标签栏区域

    if y < min_y:
        print(f"  ⚠️ Y坐标 {y} 太小（< {min_y}px），可能指向搜索框或标签栏")
        return False
    elif y < warning_y:
        print(f"  ⚡ Y坐标 {y} 处于过渡区（< {warning_y}px），自动向下修正")
        if auto_adjust:
            y_adjusted = y + 35
            print(f"  🎯 自动修正: ({x}, {y}) → ({x}, {y_adjusted})")
            return (True, x, y_adjusted)
        else:
            print(f"  ⚡ 过渡区未修正，原样使用")

    return True


def adjust_if_transition_zone(x, y):
    """检查是否在过渡区，如果是则自动调整Y坐标"""
    result = validate_coordinates(x, y, auto_adjust=True)
    if isinstance(result, tuple) and len(result) == 3:
        return result[1], result[2]
    return x, y


def draw_crosshair_on_image(image_path, x, y, radius=30, output_path=None):
    """在图片上绘制十字准星标记"""
    img = cv2.imread(image_path)
    if img is None:
        return output_path or image_path

    cv2.circle(img, (x, y), radius, (0, 0, 255), 3)
    cv2.line(img, (x - radius - 10, y), (x + radius + 10, y), (0, 0, 255), 2)
    cv2.line(img, (x, y - radius - 10), (x, y + radius + 10), (0, 0, 255), 2)

    if output_path is None:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_marked{ext}"

    cv2.imwrite(output_path, img)
    return output_path


# 录屏说明：使用 Windows 自带录屏功能（推荐）
# 操作方法：
#   1. 运行此脚本前，按 Win + Alt + R 开始录屏（或 Win+G 打开 Xbox Game Bar）
#   2. 脚本运行完毕后，再次按 Win + Alt + R 停止录制
#   3. 视频自动保存到 C:\Users\Lenovo\Videos\Captures\
# 优势：单个MP4文件，占用空间小（10分钟约200-500MB），可直接播放回溯


def check_mouse_unchanged(x, y, tolerance=20, wait_sec=0.5):
    """检查鼠标位置是否被用户移动了"""
    current_x, current_y = pyautogui.position()
    dist = ((current_x - x) ** 2 + (current_y - y) ** 2) ** 0.5
    return dist < tolerance


def click_first_result(enable_visualizer=True, use_opencv_refine=False, search_term: str | None = None):
    """点击第一条搜索结果（简化版：只调1次VLM定位）"""
    result = {
        "success": False,
        "message": "",
        "screenshot": None
    }
    print("\n=== Step 04: 点击第一条搜索结果 (简化版) ===")
    print("📍 安全提示：Agent 将控制鼠标，请勿触碰鼠标")

    pyautogui.FAILSAFE = False

    visualizer = None
    if enable_visualizer:
        visualizer = MouseVisualizer()
        visualizer.start()

    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle("飞书") or gw.getWindowsWithTitle("Lark")
        if wins:
            win = wins[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.5)
            print("✅ 飞书窗口已激活")
    except Exception as e:
        print(f"⚠️  窗口激活失败: {str(e)}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    coords = None
    MAX_LOCATE_RETRIES = 1  # 只尝试1次VLM，失败后直接OpenCV兜底
    before_path = None

    # ========== 固定坐标模式（调试/限流绕行）==========
    # USE_FIXED_COORDS 通过 .env 或 config.py 控制，默认 False
    # 设为 True 时跳过 VLM 定位，直接用固定坐标 (1280, 350) 点击
    # 用途：VLM 429 限流时临时绕行 / 快速验证点击逻辑 / CI 环境无 API Key

    if USE_FIXED_COORDS:
        print(f"🔧 使用固定坐标模式（绕过VLM）: {FIXED_COORDS}")
        before_path = os.path.join(SCREENSHOT_DIR, f"step04_before_{timestamp}_fixed.png")
        pyautogui.screenshot(before_path)
        coords = FIXED_COORDS
    else:
        print("⏳ 预热等待 30s，让VLM配额恢复...")
        time.sleep(30)

        for locate_attempt in range(1, MAX_LOCATE_RETRIES + 1):
            print(f"\n🔍 [阶段1] VLM 定位搜索结果 (尝试 {locate_attempt}/{MAX_LOCATE_RETRIES})...")
            before_path = os.path.join(SCREENSHOT_DIR, f"step04_before_{timestamp}_attempt{locate_attempt}.png")
            pyautogui.screenshot(before_path)
            prompt = SIMPLE_LOCATE_PROMPT.replace("{screen_info}", screen_info_for_prompt(before_path))
            if search_term:
                prompt += f"\n\n优先点击名称包含「{search_term}」的【联系人】条目（有头像的人名行），不要点云文档或其他类型。"
            print("  🎯 VLM 直接定位第一条结果...")
            vlm_output = call_vlm(before_path, prompt, timeout=VLM_TIMEOUT)

            if not vlm_output:
                print(f"  ❌ 第 {locate_attempt} 次定位失败，重试...")
                time.sleep(2)
                continue

            raw = parse_vlm_coordinates(vlm_output)
            if not raw:
                print(f"  ❌ 第 {locate_attempt} 次坐标解析失败: {vlm_output}，重试...")
                time.sleep(2)
                continue

            current_coords = vlm_coords_to_screen(raw[0], raw[1], before_path)
            x, y = current_coords
            print(f"  🎯 VLM 返回坐标 (scaled): ({x}, {y})")

            val_result = validate_coordinates(x, y)
            if val_result is True:
                coords = current_coords
                print("  ✅ 坐标校验通过")
                break
            elif isinstance(val_result, tuple) and len(val_result) == 3:
                coords = (val_result[1], val_result[2])
                print("  ✅ 坐标校验通过（已自动修正）")
                break
            else:
                print("  ❌ 坐标未通过校验，重试...")
                time.sleep(2)

    if not coords and not USE_FIXED_COORDS:
        print("\n⚠️ VLM 定位全部失败，启用 OpenCV 模板匹配兜底...")
        template_path = str(PROJECT_ROOT / "assets" / "search_result_first_item.png")
        if os.path.exists(template_path):
            match = opencv_match_template(before_path, template_path)
            if match:
                x, y, conf = match
                print(f"  ✅ OpenCV 兜底成功! 坐标: ({x}, {y}), 置信度: {conf:.3f}")
                coords = (x, y)
            else:
                print("  ❌ OpenCV 模板匹配也失败")
        else:
            print(f"  ⚠️ 模板图不存在: {template_path}，跳过 OpenCV 兜底")

    if not coords:
        print("❌ 所有定位方式均失败，终止操作")
        if visualizer:
            visualizer.stop()
        result["message"] = "VLM定位和OpenCV兜底均失败"
        return result

    x, y = coords
    print(f"  🎯 最终定位: ({x}, {y})")

    marked_path = draw_crosshair_on_image(
        before_path, *screen_coords_to_screenshot(x, y, before_path)
    )
    if marked_path:
        print(f"  📍 定位标记图: {marked_path}")

    # ====== 录屏提醒（使用 Windows 录屏）======
    # 请在运行脚本前按 Win+Alt+R 开始录屏，运行结束后按 Win+Alt+R 停止

    print(f"\n🖱️  [阶段2] 移动鼠标到 ({x}, {y})...")
    pyautogui.moveTo(x, y, duration=1.5)
    time.sleep(0.8)

    if not check_mouse_unchanged(x, y):
        print("  ⚠️ 检测到鼠标位置被改变，使用当前位置")
        x, y = pyautogui.position()

    print(f"\n{'='*40}")
    print("🖱️  [阶段3] 执行点击（双击进入）...")
    print(f"{'='*40}")
    # 明确指定坐标 + 双击（飞书搜索结果需要双击进入）
    pyautogui.doubleClick(x, y)
    print(f"  ✅ 已双击坐标 ({x}, {y})")
    time.sleep(2.5)

    # 录屏提醒：如果正在录屏，现在可以停止了（Win+Alt+R）

    after_path = os.path.join(SCREENSHOT_DIR, f"step04_after_{timestamp}.png")
    pyautogui.screenshot(after_path)
    print(f"  📸 [阶段4] 操作后截图已保存: {after_path}")

    print("  🔍 [阶段4] VLM 验证点击结果...")
    verify_ok = True
    try:
        verify_result = call_vlm_multi_image(VERIFY_PROMPT, [before_path, after_path], timeout=30, max_retries=1)
        if verify_result:
            print(f"  📝 VLM 验证: {verify_result[:80]}")
            if "SUCCESS" in verify_result.upper():
                print("  ✅ [阶段4] 验证通过：点击成功打开目标页面 ✓")
            else:
                verify_ok = False
                print(f"  ❌ [阶段4] 验证失败：{verify_result}")
        else:
            print("  ⚠️ [阶段4] 验证调用无返回（不阻断，但坐标可能不准）")
    except Exception as e:
        print(f"  ⚠️ [阶段4] 验证调用失败: {e}（不阻断）")

    if visualizer:
        visualizer.stop()

    if not verify_ok:
        result["message"] = "点击后页面验证失败（可能点偏或未进入目标）"
        result["screenshot"] = str(after_path)
        print("\n❌ Step 04 失败：VLM 验证未通过")
        return result

    print("\n✅ Step 04 完成：定位→点击→验证")
    result["success"] = True
    result["message"] = "点击第一条搜索结果成功"
    result["screenshot"] = str(after_path)
    return result


def opencv_match_template(screenshot_path, template_path, threshold=0.5, max_y_ratio=0.6):
    """OpenCV 模板匹配兜底（自动缩放防止OOM）"""
    screenshot = cv2.imread(screenshot_path)
    template = cv2.imread(template_path)
    if screenshot is None or template is None:
        print("  ❌ OpenCV: 截图或模板图读取失败")
        return None

    # 自动缩放：如果截图太大，缩小到合理尺寸（最大1920宽）
    max_width = 1920
    scale = 1.0
    if screenshot.shape[1] > max_width:
        scale = max_width / screenshot.shape[1]
        screenshot = cv2.resize(screenshot, (max_width, int(screenshot.shape[0] * scale)))
        template = cv2.resize(template, (int(template.shape[1] * scale), int(template.shape[0] * scale)))

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    h, w = template.shape[:2]
    center_x = max_loc[0] + w // 2
    center_y = max_loc[1] + h // 2
    screen_h = screenshot.shape[0]
    print(f"  🔍 OpenCV 模板匹配置信度: {max_val:.3f}")
    if max_val >= threshold and center_y < screen_h * max_y_ratio:
        return center_x, center_y, max_val
    return None


if __name__ == "__main__":
    click_first_result()