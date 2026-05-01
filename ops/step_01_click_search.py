import cv2
import numpy as np
import pyautogui
import time
import os
from datetime import datetime

# ===== 配置 =====
TEMPLATE_PATH = "D:\\feishu-cua-challenge\\assets\\template_search_box.png"
SCREENSHOT_DIR = "D:\\feishu-cua-challenge\\screenshots"

# ===== OpenCV 模板匹配（主手段，不调API）=====
def opencv_match(screenshot_path, template_path, threshold=0.5, max_y_ratio=0.25):
    screenshot = cv2.imread(screenshot_path)
    template = cv2.imread(template_path)
    
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    h, w = template.shape[:2]
    center_x = max_loc[0] + w // 2
    center_y = max_loc[1] + h // 2
    screen_h = screenshot.shape[0]
    
    print(f"  OpenCV 最佳匹配度: {max_val:.3f}")
    
    if max_val >= threshold and center_y < screen_h * max_y_ratio:
        return center_x, center_y, max_val
    return None

# ===== 主流程 =====
def main():
    # 1. 检查模板文件
    if not os.path.exists(TEMPLATE_PATH):
        print(f"错误：找不到模板文件 {TEMPLATE_PATH}")
        print("请先截取搜索框图片保存为 assets/template_search_box.png")
        return
    
    # 2. 激活飞书窗口
    print("步骤1: 激活飞书窗口...")
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle("飞书") or gw.getWindowsWithTitle("Lark")
        if wins:
            win = wins[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(1)
            print("  飞书窗口已激活")
    except Exception as e:
        print(f"  窗口激活失败: {e}，继续执行")
    
    # 3. 截取全屏
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    before_path = os.path.join(SCREENSHOT_DIR, f"before_{timestamp}.png")
    pyautogui.screenshot(before_path)
    print(f"步骤2: 已保存截图")
    
    # 4. OpenCV 模板匹配（主手段，不调API）
    print("步骤3: OpenCV 模板匹配...")
    match = opencv_match(before_path, TEMPLATE_PATH)
    
    if match:
        x, y, conf = match
        print(f"  ✓ 匹配成功! 坐标: ({x}, {y}), 置信度: {conf:.3f}")
    else:
        print("  ✗ OpenCV 匹配失败，程序退出")
        print("  提示：检查模板图是否正确，或尝试调低阈值")
        return False
    
    # 5. 点击
    print(f"步骤4: 移动到 ({x}, {y}) 并点击...")
    pyautogui.moveTo(x, y, duration=1)
    time.sleep(1)
    pyautogui.click()
    time.sleep(2)
    
    # 6. 截取操作后截图
    after_path = os.path.join(SCREENSHOT_DIR, f"after_{timestamp}.png")
    pyautogui.screenshot(after_path)
    print(f"步骤5: 已保存操作后截图")
    print("✓ 完成! 请确认搜索框是否被激活")
    return True

if __name__ == "__main__":
    main()