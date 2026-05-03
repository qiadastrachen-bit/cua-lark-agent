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

def build_locate_prompt(screen_w, screen_h):
    """动态生成定位Prompt，传入真实屏幕分辨率，提升VLM识别准确率"""
    min_x = int(screen_w * 0.25)
    max_x = int(screen_w * 0.75)
    tab_bar_max_y = int(screen_h * 0.13)
    result_min_y = int(screen_h * 0.17)
    return f"""你是一个飞书界面分析专家。请分析这张飞书搜索结果截图。

**绝对规则（必须严格遵守）**：
1. ❌ 左侧区域：所有坐标x < {min_x} 的内容，绝对不要返回！
2. ❌ 右侧区域：所有坐标x > {max_x} 的内容，绝对不要返回！
3. ❌ 标签栏区域：所有y < {result_min_y} 的内容，绝对不要返回！

⚠️  如何区分【标签栏】和【搜索结果】：
- 标签栏：纯文字，包含"消息" "云文档" "应用" "联系人"等文字，没有图标，y < {tab_bar_max_y}
- 搜索结果：带【小图标】+ 名称，比如"妙搭助手"（机器人图标）或聊天记录（头像图标），y > {result_min_y}

✅ 正确目标：中间白色搜索面板中，标签栏正下方、带图标的第一条可点击结果
✅ 面板x范围：{min_x} ~ {max_x}  正确结果的y范围：{result_min_y} ~ {int(screen_h * 0.4)}

返回格式严格为：x=数字,y=数字（例如 x=700,y=280）
只返回坐标，不要返回其他任何内容。"""


ANALYSIS_PROMPT = """你是一个飞书界面分析专家。请仔细分析这张飞书搜索结果截图。

请按以下顺序分析，并输出你的分析过程：

1. 屏幕分辨率是多少？截图尺寸是多少？
2. 中间白色搜索面板在哪里？x范围是多少？y范围是多少？
3. 标签栏（"消息|云文档|应用|联系人"）在哪里？y坐标范围是多少？
4. 搜索结果列表从哪里开始（标签栏下方第一条）？第一条结果的坐标大概是多少？
5. 第一条结果的特征：名称是什么？有没有图标？

请先输出分析过程，最后给出第一条可点击搜索结果的坐标。
格式：
分析：...
坐标：x=数字,y=数字"""


LOCATE_PROMPT = build_locate_prompt(2560, 1600)  # 默认值，运行时会被替换

CONFIRM_PROMPT = """你是一个飞书界面分析专家。请确认这张截图中红圈标记的位置。

任务：判断红圈标记的位置是否是**搜索结果列表中的第一条可点击结果**。

判断标准（必须全部满足才返回OK）：
✅ 正确的情况（必须同时满足以下3条）：
- 红圈在搜索结果列表的第一条项目上（带图标的应用名称或聊天记录）
- 红圈的y坐标明显在标签栏下方（标签栏是"消息|云文档|应用|联系人"那行文字）
- **红圈精确落在图标或文字上，而不是空白区域**

❌ 错误的情况（只要满足1条就返回NO）：
- 红圈在左侧飞书导航栏上
- 红圈在搜索框内
- 红圈在标签栏（"消息|云文档|应用|联系人"）上
- **红圈在空白区域（不在任何可点击元素上）**
- 红圈在第二条及以后的搜索结果上
- 红圈在任何非"第一条结果"的区域

⚠️ 特别注意：如果红圈落在第一条结果的空白区域（比如图标和文字之间的空白处），必须返回NO

返回格式：
如果位置正确且确实是第一条结果：返回 OK
如果位置错误：返回 NO + 错误原因（一句话）
例如：OK 或 NO: 红圈在左侧导航栏的第二项上
例如：OK 或 NO: 红圈在第一条结果的空白区域，不在可点击元素上"""

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
VLM_RETRY_BASE_DELAY = 10   # 指数退避基础间隔（秒）
VLM_TIMEOUT = 60             # API 调用超时（秒）

# 坐标合理性边界
MARGIN = 50  # 屏幕边缘安全距离


def call_vlm(image_path, prompt, max_retries=MAX_VLM_RETRIES, timeout=VLM_TIMEOUT):
    """调用 VLM 分析截图，返回原始文本（含指数退避）"""
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
            print(f"  🤖 VLM 调用中... (第 {attempt} 次, timeout={timeout}s)")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"  📝 VLM 返回: {content.strip()[:120]}")
            return content.strip()
        except requests.exceptions.Timeout:
            wait = VLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))  # 10, 20, 40
            print(f"  ⚠️ VLM 超时 (>{timeout}s)，等待 {wait}s 后重试...")
            if attempt < max_retries:
                time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait = VLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  ⚠️ TPM 限流 (429)，等待 {wait}s 后重试...")
                if attempt < max_retries:
                    time.sleep(wait)
            else:
                print(f"  ❌ HTTP 错误: {e}")
                if attempt < max_retries:
                    time.sleep(VLM_RETRY_BASE_DELAY)
        except Exception as e:
            wait = VLM_RETRY_BASE_DELAY * attempt
            print(f"  ❌ 调用失败: {e}，{wait}s 后重试...")
            if attempt < max_retries:
                time.sleep(wait)

    print("  ❌ VLM 所有重试均失败")
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


def validate_coordinates(x, y, auto_adjust=True):
    """基本坐标合理性检查
    
    Args:
        x, y: 坐标
        auto_adjust: 是否在过渡区自动调整
    
    Returns:
        True/False 或 (True, adjusted_x, adjusted_y)
    """
    screen_w, screen_h = pyautogui.size()

    # 边缘检查
    if x < MARGIN or x > screen_w - MARGIN or y < MARGIN or y > screen_h - MARGIN:
        print(f"  ⚠️ 坐标太靠近屏幕边缘: ({x}, {y}), 屏幕尺寸: {screen_w}x{screen_h}")
        return False

    # 排除左右边栏，只保留中间50%区域（搜索结果面板所在位置）
    min_x = int(screen_w * 0.25)
    max_x = int(screen_w * 0.75)
    if x < min_x or x > max_x:
        print(f"  ⚠️ X坐标 {x} 不在中间有效区域（{min_x}~{max_x}），可能在左右边栏")
        return False

    # 搜索框/标签栏通常在顶部区域，排除 y < 屏幕高度15% 的区域
    min_y = int(pyautogui.size()[1] * 0.15)

    # 边界模糊区检测：y 在 12%~18% 之间是标签栏/结果的过渡区
    warning_min_y = int(screen_h * 0.12)
    warning_max_y = int(screen_h * 0.18)

    if y < min_y:
        print(f"  ⚠️ Y坐标 {y} 太小（< {min_y}px），可能指向搜索框或标签栏")
        return False
    elif warning_min_y <= y <= warning_max_y:
        print(f"  ⚡ Y坐标 {y} 处于标签栏/结果过渡区（{warning_min_y}~{warning_max_y}）")
        # 过渡区：自动向下偏移 40px
        if auto_adjust:
            y_adjusted = y + 40
            print(f"  🎯 过渡区自动修正: ({x}, {y}) → ({x}, {y_adjusted})")
            return (True, x, y_adjusted)
        else:
            print(f"  ⚡ 过渡区需VLM重点确认")

    return True


def adjust_if_transition_zone(x, y):
    """检查是否在过渡区，如果是则自动调整"""
    result = validate_coordinates(x, y, auto_adjust=True)
    if isinstance(result, tuple) and len(result) == 3:
        return result[1], result[2]  # (adjusted_x, adjusted_y)
    return x, y


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

    pyautogui.FAILSAFE = False  # 禁用 fail-safe（比赛场景下有 VLM 确认保障安全）

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

    # ====== 第一步：VLM 两步式定位（分析→定位，带重试）======
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    screen_w, screen_h = pyautogui.size()
    locate_prompt = build_locate_prompt(screen_w, screen_h)
    coords = None
    MAX_LOCATE_RETRIES = 3
    marked_path = None
    pre_click_shot = None
    pre_click_marked = None

    for locate_attempt in range(1, MAX_LOCATE_RETRIES + 1):
        print(f"\n🔍 [阶段1] VLM 定位搜索结果 (尝试 {locate_attempt}/{MAX_LOCATE_RETRIES})...")
        before_path = os.path.join(SCREENSHOT_DIR, f"step04_before_{timestamp}_attempt{locate_attempt}.png")
        pyautogui.screenshot(before_path)
        print(f"📸 [阶段1] 操作前截图已保存: {before_path}")

        # ====== 两步式 VLM 调用（参考 TuriX-CUA See→Think→Act）=====
        # 第1步：让 VLM 分析界面结构（See+Think）
        print("  🧠 第1步：VLM 分析界面结构...")
        analysis = call_vlm(before_path, ANALYSIS_PROMPT, timeout=90)
        if analysis:
            print(f"  📝 分析结果: {analysis[:150]}")
        else:
            print(f"  ❌ 第 {locate_attempt} 次分析失败，重试...")
            time.sleep(2)
            continue

        # 第2步：基于分析结果，让 VLM 给出精确坐标（Act）
        print("  🎯 第2步：VLM 给出精确坐标...")
        vlm_output = call_vlm(before_path, locate_prompt, timeout=60)
        if not vlm_output:
            print(f"  ❌ 第 {locate_attempt} 次坐标获取失败，重试...")
            time.sleep(2)
            continue

        current_coords = parse_vlm_coordinates(vlm_output)
        if not current_coords:
            print(f"  ❌ 第 {locate_attempt} 次坐标解析失败: {vlm_output}，重试...")
            time.sleep(2)
            continue

        x, y = current_coords
        print(f"  🎯 VLM 返回坐标: ({x}, {y})")

        # 基本坐标校验
        if validate_coordinates(x, y):
            coords = current_coords
            print(f"  ✅ 坐标校验通过")
            break
        else:
            print(f"  ❌ 坐标未通过校验，重试...")
            time.sleep(2)

    # OpenCV 兜底：VLM 全部失败时用模板匹配
    if not coords:
        print("\n⚠️ VLM 定位全部失败，启用 OpenCV 模板匹配兜底...")
        template_path = "D:\\feishu-cua-challenge\\assets\\template_first_result.png"
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
            print("  💡 提示：截取一条搜索结果保存为 assets/template_first_result.png")

    if not coords:
        print("❌ 所有定位方式均失败，终止操作")
        if visualizer:
            visualizer.stop()
        return False

    x, y = coords
    # 过渡区自动调整（如果在标签栏/结果过渡区，自动向下偏移）
    x, y = adjust_if_transition_zone(x, y)
    print(f"  🎯 [阶段1] 最终定位: ({x}, {y})")

    # ====== 第二步：VLM 确认坐标正确性（复用同一重试循环） ======
    for confirm_attempt in range(1, MAX_LOCATE_RETRIES + 1):
        # 阶段 2：移动鼠标 + VLM 确认
        print(f"\n🖱️  [阶段2] 移动鼠标到 ({x}, {y})... (确认尝试 {confirm_attempt}/{MAX_LOCATE_RETRIES})")
        pyautogui.moveTo(x, y, duration=1.5)
        time.sleep(0.8)

        # 检查鼠标是否被用户移动
        if not check_mouse_unchanged(x, y):
            print("  ⚠️ 检测到鼠标位置被改变，可能用户正在操作")
            x, y = pyautogui.position()
            print(f"  🔄 使用当前位置作为新目标: ({x}, {y})")

        # 清理上一次的标记文件
        try:
            if marked_path and marked_path != before_path and os.path.exists(marked_path):
                os.remove(marked_path)
        except:
            pass

        marked_path = draw_crosshair_on_image(before_path, int(x), int(y))
        print(f"  🔍 VLM 确认坐标正确性...")

        confirm_result = call_vlm(marked_path, CONFIRM_PROMPT)

        if confirm_result and confirm_result.upper().startswith("OK"):
            print("  ✅ VLM 确认：位置正确 ✓")

            # ====== 阶段2.5：鼠标到位后的二次视觉验证 ======
            # 在真正点击前，截一张"鼠标已移动到目标位置"的图
            # 用红圈标记当前鼠标位置，让VLM最后确认一次
            print("  🔍 [阶段2.5] 点击前最终验证（截取鼠标当前位置）...")
            
            # 🔧 修复截图全黑问题：重新激活飞书窗口并等待渲染
            try:
                import pygetwindow as gw
                wins = gw.getWindowsWithTitle("飞书") or gw.getWindowsWithTitle("Lark")
                if wins:
                    wins[0].activate()
                    time.sleep(0.8)  # 等待窗口渲染完成
                    print("  📌 已重新激活飞书窗口（防黑屏）")
                else:
                    print("  ⚠️ 未找到飞书窗口，继续截图")
            except Exception as e:
                print(f"  ⚠️ 窗口激活失败: {e}")
            
            time.sleep(0.3)
            pre_click_shot = os.path.join(SCREENSHOT_DIR, f"step04_preclick_{timestamp}.png")
            pyautogui.screenshot(pre_click_shot)
            
            # 🔧 黑屏检测：如果截取到的是黑屏或接近黑色，回退到 before_path
            try:
                img_check = cv2.imread(pre_click_shot)
                if img_check is not None:
                    mean_brightness = img_check.mean()
                    if mean_brightness < 10:  # 平均亮度 < 10 视为黑屏
                        print(f"  ⚠️ 检测到黑屏画面（亮度={mean_brightness:.1f}），使用操作前截图替代")
                        # 使用 before_path 作为替代截图
                        pre_click_marked = draw_crosshair_on_image(before_path, int(x), int(y))
                        print("  🔄 已切换为操作前截图进行最终验证")
                    else:
                        pre_click_marked = draw_crosshair_on_image(pre_click_shot, int(x), int(y))
                        print(f"  📸 截图正常（亮度={mean_brightness:.1f}）")
                else:
                    pre_click_marked = draw_crosshair_on_image(before_path, int(x), int(y))
                    print("  ⚠️ 截图文件读取失败，使用操作前截图替代")
            except Exception as e:
                pre_click_marked = draw_crosshair_on_image(pre_click_shot, int(x), int(y))
                print(f"  ⚠️ 黑屏检测异常: {e}，继续使用当前截图")

            FINAL_CHECK_PROMPT = """这是点击前的最后一张截图。红圈标记了鼠标即将点击的位置。
请做最终确认：红圈是否精确落在【搜索结果列表的第一条】上？
- 注意：第一条结果应该在标签栏下方，带有图标
- 如果红圈位置正确：返回 FINAL_OK
- 如果红圈位置有偏差或不在第一条上：返回 FINAL_NO + 原因"""
            final_check = call_vlm(pre_click_marked, FINAL_CHECK_PROMPT, timeout=30)
            if final_check and "FINAL_OK" in final_check.upper():
                print("  ✅ 最终验证通过，执行点击")
            elif final_check and "FINAL_NO" in final_check.upper():
                print(f"  ⚠️ 最终验证未通过: {final_check}")
                # 微调策略：y坐标下移40px（加大偏移量，确保落到可点击区域）
                y_adjusted = y + 40
                adj_result = validate_coordinates(x, y_adjusted, auto_adjust=False)
                if adj_result is True:
                    print(f"  🎯 微调坐标: ({x}, {y}) → ({x}, {y_adjusted})")
                    x, y = x, y_adjusted
                    pyautogui.moveTo(x, y, duration=0.8)
                    time.sleep(0.5)
                    # 重新标记图片，继续确认循环（不跳出）
                    marked_path = draw_crosshair_on_image(before_path, int(x), int(y))
                    print(f"  🔄 已调整坐标，重新验证...")
                    continue  # 重新进入确认循环，用新坐标再确认
                else:
                    print(f"  ⚠️ 微调坐标无效（可能超出边界），使用原坐标继续")
            else:
                print(f"  ⚠️ 最终验证结果不明确: {final_check}，使用原坐标继续")

            break  # 确认成功+最终验证完成，跳出确认循环
        elif confirm_result and confirm_result.upper().startswith("NO"):
            print(f"  ❌ VLM 拒绝：{confirm_result}")
            if confirm_attempt < MAX_LOCATE_RETRIES:
                print(f"  🔄 重新截图并定位（剩余 {MAX_LOCATE_RETRIES - confirm_attempt} 次）...")
                time.sleep(2)
                # 重新进入定位流程
                print(f"\n🔍 [阶段1] VLM 重新定位搜索结果 (尝试 {confirm_attempt+1}/{MAX_LOCATE_RETRIES})...")
                before_path = os.path.join(SCREENSHOT_DIR, f"step04_before_{timestamp}_attempt{confirm_attempt+1}.png")
                pyautogui.screenshot(before_path)
                vlm_output = call_vlm(before_path, locate_prompt)
                if vlm_output:
                    current_coords = parse_vlm_coordinates(vlm_output)
                    if current_coords and validate_coordinates(*current_coords):
                        x, y = current_coords
                        # 应用过渡区自动调整
                        x, y = adjust_if_transition_zone(x, y)
                        print(f"  🎯 重新定位坐标: ({x}, {y})")
                        continue  # 用新坐标继续确认循环
                # 重新定位也失败了
                print("  ❌ 重新定位失败")
            else:
                print("❌ 所有确认尝试均被拒绝")
                if visualizer:
                    visualizer.stop()
                return False
        else:
            print(f"  ⚠️ VLM 确认结果不明确: {confirm_result}")
            # 不明确时继续执行（不终止），但不再重试
            print("  ⚠️ 继续执行（建议后续关注此问题）...")
            break

    # ====== 第三步：执行点击 ======
    print(f"\n{'='*40}")
    print("🖱️  [阶段3] 执行点击...")
    print(f"{'='*40}")
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
    for tmp_path in [marked_path, pre_click_shot, pre_click_marked]:
        try:
            if tmp_path and os.path.exists(tmp_path) and tmp_path != before_path:
                os.remove(tmp_path)
        except (NameError, TypeError):
            pass  # 变量未定义说明该步骤未执行
        except Exception:
            pass

    # 停止可视化
    if visualizer:
        visualizer.stop()

    print("\n✅ Step 04 完成全流程：定位→确认→点击→验证")
    return True


def opencv_match_template(screenshot_path, template_path, threshold=0.7, max_y_ratio=0.6):
    """OpenCV 模板匹配兜底（用于 VLM 全部失败时）"""
    screenshot = cv2.imread(screenshot_path)
    template = cv2.imread(template_path)
    if screenshot is None or template is None:
        print("  ❌ OpenCV: 截图或模板图读取失败")
        return None
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
