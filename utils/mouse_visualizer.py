import cv2
import numpy as np
import pyautogui
import threading
import time

class MouseVisualizer:
    """鼠标可视化工具，独立窗口显示鼠标红圈和实时坐标"""
    def __init__(self, window_size=(300, 300), circle_radius=20, circle_color=(0, 0, 255), circle_thickness=2):
        self.window_size = window_size
        self.circle_radius = circle_radius
        self.circle_color = circle_color
        self.circle_thickness = circle_thickness
        self.running = False
        self.thread = None
        self.screen_width, self.screen_height = pyautogui.size()
        
    def _update_window(self):
        """后台线程更新可视化窗口"""
        cv2.namedWindow("Mouse Visualizer", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Mouse Visualizer", *self.window_size)
        cv2.moveWindow("Mouse Visualizer", self.screen_width - self.window_size[0] - 20, 20)
        
        while self.running:
            # 创建黑色背景
            frame = np.zeros((self.window_size[1], self.window_size[0], 3), dtype=np.uint8)
            
            # 获取当前鼠标坐标
            x, y = pyautogui.position()
            
            # 绘制红圈
            center = (self.window_size[0]//2, self.window_size[1]//2)
            cv2.circle(frame, center, self.circle_radius, self.circle_color, self.circle_thickness)
            
            # 绘制坐标文字
            text = f"X: {x}, Y: {y}"
            cv2.putText(frame, text, (20, self.window_size[1] - 20), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # 显示窗口
            cv2.imshow("Mouse Visualizer", frame)
            
            # 按ESC退出
            if cv2.waitKey(1) == 27:
                self.running = False
                break
                
            time.sleep(0.01)
        
        cv2.destroyAllWindows()
        
    def start(self):
        """启动可视化窗口"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update_window, daemon=True)
            self.thread.start()
            print("🖱️  鼠标可视化已启动，按ESC键关闭窗口")
            
    def stop(self):
        """停止可视化窗口"""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join()
            cv2.destroyAllWindows()
            print("🛑 鼠标可视化已停止")

# 单独运行测试
if __name__ == "__main__":
    visualizer = MouseVisualizer()
    visualizer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        visualizer.stop()
