import time
import os
import sys
import pyautogui
from datetime import datetime
# 导入工具模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.mouse_visualizer import MouseVisualizer

SCREENSHOT_DIR = "D:\\feishu-cua-challenge\\screenshots"

def wait_search_results(wait_seconds=5, enable_visualizer=True):
    """等待搜索结果加载，带倒计时反馈，返回标准执行结果"""
    result = {
        "success": False,
        "message": "",
        "screenshot": None
    }
    print("\n=== Step 03: 等待搜索结果加载 ===")
    
    # 启动鼠标可视化
    visualizer = None
    if enable_visualizer:
        visualizer = MouseVisualizer()
        visualizer.start()
    
    # 倒计时
    print(f"[等待] 等待搜索结果加载，共 {wait_seconds} 秒...")
    for i in range(wait_seconds, 0, -1):
        print(f"   倒计时: {i} 秒", end="\r")
        time.sleep(1)
    
    print("[成功] 搜索结果加载完成" + " " * 20)
    
    # 停止可视化
    if visualizer:
        visualizer.stop()
    
    # 保存截图
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"step03_wait_{timestamp}.png")
    pyautogui.screenshot(screenshot_path)
    print(f"📸 截图已保存: {screenshot_path}")
    
    result["success"] = True
    result["message"] = "等待搜索结果完成"
    result["screenshot"] = str(screenshot_path)
    return result

if __name__ == "__main__":
    wait_search_results()
