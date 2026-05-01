"""
模板图截取工具
用法：python tools/capture_template.py
1. 运行后会倒计时，期间切换到飞书并让搜索结果出现
2. 截图完成后弹出框选窗口，用鼠标拖动选取目标区域
3. 自动保存到 assets/ 目录
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import pyautogui
import time
import os
import sys

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

TEMPLATES = {
    "1": ("search_result_first_item.png", "搜索结果第一条"),
    "2": ("template_search_box.png", "搜索框"),
}


def countdown(seconds, msg):
    for i in range(seconds, 0, -1):
        print(f"\r{msg} {i} 秒... ", end="", flush=True)
        time.sleep(1)
    print()


class RegionSelector:
    """弹出全屏截图，让用户拖动框选区域"""

    def __init__(self, screenshot: Image.Image):
        self.screenshot = screenshot
        self.result = None  # (x1, y1, x2, y2) 原始坐标

        self.root = tk.Toplevel()
        self.root.title("框选模板区域（拖动鼠标，ESC取消）")
        self.root.attributes("-topmost", True)
        self.root.attributes("-fullscreen", True)
        self.root.configure(cursor="crosshair")

        # 转成 tkinter 可用的图片
        self.tk_img = ImageTk.PhotoImage(screenshot)

        self.canvas = tk.Canvas(self.root, cursor="crosshair",
                                width=screenshot.width, height=screenshot.height)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        # 提示文字
        self.canvas.create_text(
            screenshot.width // 2, 30,
            text="拖动鼠标框选目标区域，释放鼠标确认，ESC 取消",
            fill="yellow", font=("Arial", 16, "bold"),
            tags="hint"
        )

        self.start_x = self.start_y = 0
        self.rect_id = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.cancel())

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def on_drag(self, event):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline="red", width=2
        )

    def on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)

        if x2 - x1 < 10 or y2 - y1 < 10:
            print("⚠️  框选区域太小，请重新拖动")
            return

        self.result = (x1, y1, x2, y2)
        self.root.destroy()

    def cancel(self):
        self.result = None
        self.root.destroy()


def main():
    # 选择要截取的模板
    print("=" * 50)
    print("  飞书 CUA 模板截取工具")
    print("=" * 50)
    print("请选择要截取的模板：")
    for k, (fname, desc) in TEMPLATES.items():
        print(f"  {k}. {desc}  →  {fname}")
    print("  q. 退出")

    choice = input("\n输入编号: ").strip()
    if choice == "q":
        return
    if choice not in TEMPLATES:
        print("❌ 无效编号")
        return

    filename, desc = TEMPLATES[choice]
    save_path = os.path.join(ASSETS_DIR, filename)

    print(f"\n✅ 目标：截取「{desc}」")
    print(f"📁 保存路径：{save_path}")
    print()
    print("请在 5 秒内切换到飞书窗口，并确保搜索结果已显示...")

    countdown(5, "⏳ 倒计时")

    print("📸 正在截图...")
    screenshot = pyautogui.screenshot()
    print(f"✅ 截图完成（{screenshot.width}x{screenshot.height}）")
    print("🖱️  请在弹出窗口中框选「{desc}」区域...\n".format(desc=desc))

    # 弹出 tkinter 框选窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口

    selector = RegionSelector(screenshot)
    root.wait_window(selector.root)

    if selector.result is None:
        print("❌ 已取消")
        root.destroy()
        return

    x1, y1, x2, y2 = selector.result
    print(f"✅ 框选区域：({x1}, {y1}) → ({x2}, {y2})，尺寸 {x2-x1}x{y2-y1}")

    # 裁剪并保存
    cropped = screenshot.crop((x1, y1, x2, y2))
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # 备份旧文件
    if os.path.exists(save_path):
        backup = save_path.replace(".png", "_backup.png")
        os.replace(save_path, backup)
        print(f"📦 旧模板已备份为：{os.path.basename(backup)}")

    cropped.save(save_path)
    print(f"✅ 新模板已保存：{save_path}")
    print(f"   尺寸：{cropped.width}x{cropped.height} px")

    print("\n🎉 完成！现在可以运行 step_04 了：")
    print("   python ops\\step_04_click_first_result.py")

    # 预览：用 PIL show，不依赖 tkinter（避免同进程 PhotoImage bug）
    try:
        print("\n👁️  正在预览截取的模板图（会用系统默认图片查看器打开）...")
        cropped.show()
    except Exception:
        pass

    root.destroy()


if __name__ == "__main__":
    main()
