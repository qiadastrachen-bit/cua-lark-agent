import time
import os
import sys
# 导入工具模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.mouse_visualizer import MouseVisualizer

def wait_search_results(wait_seconds=5, enable_visualizer=True):
    """等待搜索结果加载，带倒计时反馈"""
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
    
    return True

if __name__ == "__main__":
    wait_search_results()
