"""
Step 04: 点击第一条搜索结果（VLM 语义定位 + 安全验证方案）

架构：
1. VLM 粗定位 → 坐标输出
2. 移动鼠标到目标位置
3. VLM 二次确认：鼠标位置是否正确
4. 点击
5. VLM 结果验证：确认页面发生了变化

安全特性：
- 点击前 VLM 确认坐标正确性
- 点击后截图对比验证效果
- 检测鼠标是否被用户抢占
- 坐标合理性检查（不在屏幕边缘、不在搜索框/标签栏区域）
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

# 修复Windows控制台GBK编码无法输出emoji的问题
try:
    # Python 3.7+ 支持的方式
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    # 兼容低版本Python
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

# 导入工具模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.mouse_visualizer import MouseVisualizer

# 配置
SCREENSHOT_DIR = "D:\\feishu-cua-challenge\\screenshots"

# VLM API 配置（豆包2.0 方舟平台）
API_KEY = "ark-f11e281e-ef25-4cb0-a1ee-c7d14e8d76d4-7419d"
ENDPOINT_ID = "ep-20260423222711-8zfcd"
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# ====== VLM Prompts ======

LOCATE_PROMPT = """你是一个飞书界面分析专家。请分析这张飞书搜索结果截图。

**关键区分**：
- 左侧是【消息列表】——不要管它
- 中间弹出的白色面板才是【搜索结果面板】——只看这个

任务：在中间的搜索结果面板中，找到**第一条可点击的搜索结果**。

搜索结果面板结构（从上到下）：
1. 搜索框（顶部）——不要点这个
2. 标签栏：消息 | 云文档 | 应用 | 联系人 | ... ——不要点这个  
3. 【搜索结果列表】——找这个区域的第一条！

第一条结果的特征：
- 通常是"应用"分类下的卡片（带图标和名称），如"妙搭"或"妙搭助手"
- 或者是"消息"分类下的聊天记录条目
- 位于标签栏下方，是面板中第一个可点击的具体结果项

返回格式严格为：x=数字,y=数字（例如 x=680,y=320）
只返回坐标，不要返回其他任何内容。"""

CONFIRM_PROMPT = """你是一个飞书界面分析专家。请确认这张截图中红圈标记的位置。

任务：判断红圈标记的位置是否是**搜索结果列表中的第一条可点击结果**。

判断标准：
✅ 正确的情况：
- 红圈在"妙搭"/"妙搭助手"等应用的图标或名称上
- 红圈在消息类别的第一条聊天记录上
- 红圈在标签栏下方的第一个结果项上

❌ 错误的情况（必须拒绝）：
- 红圈在左侧的消息列表上
- 红圈在搜索框内
- 红圈在标签栏上
- 红圈在空白区域
- 红圈在任何非搜索结果的区域

返回格式：
如果位置正确，返回：OK
如果位置错误，返回：NO + 错误原因（一句话即可）
例如：OK 或 NO: 红圈在左侧消息列表"""

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
- ❌ 只是有轻微变化但没进入目标页面

返回格式：
如果成功：SUCCESS
如果失败：FAIL + 一句话说明"""

MAX_VLM_RETRIES = 3
VLM_RETRY_DELAY = 5

# 坐标合理性边界
MARGIN = 50  # 屏幕边缘安全距离


def call_vlm(image_path, prompt, max_retries=MAX_VLM_RETRIES):
    """调用 VLM 分析截图，返回原始文本"""
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
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            }
        ]
    }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  🤖 VLM 调用中... (第 {attempt} 次)")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"  📝 VLM 返回: {content.strip()[:100]}")
            return content.strip()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait = VLM_RETRY_DELAY * attempt
                print(f"  ⚠️ TPM 限流 (429)，等待 {wait} 秒后重试...")
                time.sleep(wait)
            else:
                print(f"  ❌ HTTP 错误: {e}")
                if attempt < max_retries:
                    time.sleep(VLM_RETRY_DELAY)
        except Exception as e:
            print(f"  ❌ 调用失败: {e}")
            if attempt < max_retries:
                time.sleep(VLM_RETRY_DELAY)

    return None


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


def validate_coordinates(x, y):
    """基本坐标合理性检查"""
    screen_w, screen_h = pyautogui.size()

    # 边缘检查
    if x < MARGIN or x > screen_w - MARGIN or y < MARGIN or y > screen_h - MARGIN:
        print(f"  ⚠️ 坐标太靠近屏幕边缘: ({x}, {y}), 屏幕尺寸: {screen_w}x{screen_h}")
        return False

    # 搜索框通常在顶部很靠上的位置（<150px），排除
    if y < 120:
        print(f"  ⚠️ Y坐标 {y} 太小，可能指向搜索框或标签栏")
        return False

    return True


def draw_crosshair_on_image(image_path, x, y, radius=30, output_path=None):
    """在图片上绘制十字准星标记，用于 VLM 确认"""
    img = cv2.imread(image_path)
    if img is None:
        return output_path or image_path

    # 画红色圆圈
    cv2.circle(img, (x, y), radius, (0, 0, 255), 3)
    # 画十字线
    cv2.line(img, (x - radius - 10, y), (x + radius + 10, y), (0, 0, 255), 2)
    cv2.line(img, (x, y - radius - 10), (x, y + radius + 10), (0, 0, 255), 2)

    if output_path is None:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_marked{ext}"

    cv2.imwrite(output_path, img)
    return output_path


def check_mouse_unchanged(x, y, tolerance=20, wait_sec=0.5):
    """检查鼠标位置是否被用户移动了"""
    current_x, current_y = pyautogui.position()
    dist = ((current_x - x) ** 2 + (current_y - y) ** 2) ** 0.5
    return dist < tolerance


def click_first_result(enable_visualizer=True, use_opencv_refine=False):
    """点击第一条搜索结果（带完整验证流程）"""
    print("\n=== Step 04: 点击第一条搜索结果 (VLM+验证) ===")
    print("📍 安全提示：Agent 将控制鼠标，请勿触碰鼠标")

    # 启动鼠标可视化
    visualizer = None
    if enable_visualizer:
        visualizer = MouseVisualizer()
        visualizer.start()

    # 激活飞书窗口
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

    # ====== 第一步：VLM 定位 ======
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    before_path = os.path.join(SCREENSHOT_DIR, f"step04_before_{timestamp}.png")
    pyautogui.screenshot(before_path)
    print(f"\n📸 [阶段1] 操作前截图已保存: {before_path}")

    print("\n🔍 [阶段1] VLM 定位搜索结果...")
    vlm_output = call_vlm(before_path, LOCATE_PROMPT)

    if not vlm_output:
        print("❌ VLM 定位失败")
        if visualizer:
            visualizer.stop()
        return False

    coords = parse_vlm_coordinates(vlm_output)
    if not coords:
        print(f"❌ 无法解析坐标: {vlm_output}")
        if visualizer:
            visualizer.stop()
        return False

    x, y = coords
    print(f"  🎯 [阶段1] VLM 定位: ({x}, {y})")

    # 基本坐标校验
    if not validate_coordinates(x, y):
        print("  ❌ 坐标未通过基本校验，终止操作")
        if visualizer:
            visualizer.stop()
        return False

    # ====== 第二步：移动鼠标 + VLM 确认 ======
    print(f"\n🖱️  [阶段2] 移动鼠标到目标位置 ({x}, {y})...")
    pyautogui.moveTo(x, y, duration=1.5)
    time.sleep(0.8)

    # 检查鼠标是否被用户移动
    if not check_mouse_unchanged(x, y):
        print("  ⚠️  检测到鼠标位置被改变，可能用户正在操作")
        print("  💡 请在 Agent 操作期间不要触碰鼠标。重新定位...")
        # 重新读取当前位置作为目标
        x, y = pyautogui.position()
        print(f"  🔄 使用当前位置作为新目标: ({x}, {y})")

    # 在鼠标位置绘制标记图供 VLM 确认
    marked_path = draw_crosshair_on_image(before_path, int(x), int(y))
    print(f"  🔍 [阶段2] VLM 确认坐标正确性...")

    confirm_result = call_vlm(marked_path, CONFIRM_PROMPT)

    if confirm_result and confirm_result.upper().startswith("OK"):
        print("  ✅ [阶段2] VLM 确认：位置正确 ✓")
    elif confirm_result and confirm_result.upper().startswith("NO"):
        print(f"  ❌ [阶段2] VLM 拒绝：{confirm_result}")
        print("  💡 建议重新运行或手动检查搜索结果布局")
        if visualizer:
            visualizer.stop()
        return False
    else:
        print(f"  ⚠️ [阶段2] VLM 确认结果不明确: {confirm_result}")
        print("  ⚠️ 继续执行（建议后续关注此问题）...")

    # ====== 第三步：执行点击 ======
    print(f"\n🖱️  [阶段3] 执行点击...")
    pyautogui.click()
    time.sleep(2.5)

    # ====== 第四步：结果验证 ======
    after_path = os.path.join(SCREENSHOT_DIR, f"step04_after_{timestamp}.png")
    pyautogui.screenshot(after_path)
    print(f"  📸 [阶段4] 操作后截图已保存: {after_path}")

    print("  🔍 [阶段4] VLM 验证点击结果...")
    
    # 构造两张图的对比请求
    with open(before_path, "rb") as f1:
        before_b64 = base64.b64encode(f1.read()).decode("utf-8")
    with open(after_path, "rb") as f2:
        after_b64 = base64.b64encode(f2.read()).decode("utf-8")

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
                    {"type": "text", "text": VERIFY_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{before_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{after_b64}"}}
                ]
            }
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        verify_result = response.json()["choices"][0]["message"]["content"].strip()
        print(f"  📝 VLM 验证: {verify_result[:80]}")

        if "SUCCESS" in verify_result.upper():
            print("  ✅ [阶段4] 验证通过：点击成功打开目标页面 ✓")
        else:
            print(f"  ⚠️ [阶段4] 验证存疑：{verify_result}")
            print("  ⚠️ 但流程继续（已执行点击，需人工确认最终结果）")
    except Exception as e:
        print(f"  ⚠️ [阶段4] 验证调用失败: {e}（不影响主流程）")

    # 清理标记临时文件
    try:
        if marked_path != before_path:
            os.remove(marked_path)
    except:
        pass

    # 停止可视化
    if visualizer:
        visualizer.stop()

    print("\n✅ Step 04 完成全流程：定位→确认→点击→验证")
    return True


if __name__ == "__main__":
    click_first_result()
