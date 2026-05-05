"""
Step 02: 在搜索框中输入文字
- 假设 Step 01 已成功激活搜索框
- 默认输入：飞书妙搭 (可通过命令行参数指定)
- 点击后等待搜索建议出现
- 截图保存输入结果
"""

# 依赖安装: pip install pyperclip
import sys
import time
import pyautogui
import pyperclip
import pygetwindow as gw
from pathlib import Path

# 配置
DEFAULT_TEXT = "飞书妙搭"  # 默认搜索词
SCREENSHOT_DIR = Path("D:/feishu-cua-challenge/screenshots")
ASSETS_DIR = Path("D:/feishu-cua-challenge/assets")

def get_search_text():
    """从命令行参数获取搜索词，默认为 DEFAULT_TEXT"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return DEFAULT_TEXT

def activate_feishu_window():
    """激活飞书窗口"""
    try:
        windows = gw.getWindowsWithTitle("飞书")
        if windows:
            win = windows[0]
            win.activate()
            time.sleep(0.5)
            print(f"✅ 飞书窗口已激活")
        else:
            print("⚠️ 未找到飞书窗口，继续执行")
    except Exception as e:
        print(f"⚠️ 激活窗口失败: {e}")

def input_text(text):
    """在当前焦点位置输入文字（剪贴板粘贴方式，更快更稳定）"""
    print(f"[输入] 正在输入: {text}")
    pyperclip.copy(text)        # 复制到剪贴板
    time.sleep(0.3)
    pyautogui.hotkey('ctrl', 'v')   # 粘贴
    time.sleep(0.5)
    pyperclip.copy('')               # 清空剪贴板
    print("[成功] 文字输入完成")

def wait_for_suggestions():
    """等待搜索建议出现（最多 3 秒）"""
    print("⏳ 等待搜索建议出现...")
    time.sleep(2)
    print("✅ 等待完成")

def take_screenshot(prefix="after_input"):
    """截图保存"""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{prefix}_{timestamp}.png"
    pyautogui.screenshot(str(path))
    print(f"📸 截图已保存: {path}")
    return path

def verify_input():
    """简单验证：截图后检查是否有搜索建议（可用 VLM 进一步验证）"""
    screenshot_path = take_screenshot("step02_after_input")
    print("✅ Step 02 执行完成")
    print(f"📌 请检查截图 {screenshot_path} 确认搜索建议是否正常出现")
    return screenshot_path

def input_search_text(search_term):
    """在搜索框输入指定搜索词，返回标准执行结果"""
    result = {
        "success": False,
        "screenshot": "",
        "message": "",
        "screenshots": []
    }
    print("=" * 50)
    print("Step 02: 在搜索框输入文字")
    print("=" * 50)
    
    try:
        # 激活飞书窗口
        activate_feishu_window()
        time.sleep(0.5)
        
        # 输入文字
        input_text(search_term)
        
        # 等待建议
        wait_for_suggestions()
        
        # 截图验证
        screenshot_path = take_screenshot("step02_after_input")
        result["screenshot"] = str(screenshot_path)
        result["screenshots"].append(str(screenshot_path))
        
        result["success"] = True
        result["message"] = f"搜索词「{search_term}」输入成功"
        print("✅ Step 02 完成！")
    except Exception as e:
        result["message"] = f"输入失败: {str(e)}"
        print(f"❌ {result['message']}")
    
    print("=" * 50)
    return result

if __name__ == "__main__":
    input_search_text(get_search_text())