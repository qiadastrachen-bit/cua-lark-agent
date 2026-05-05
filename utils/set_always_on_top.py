"""
set_always_on_top.py - 设置 Larker Overlay 窗口为 Always on Top
通过窗口标题匹配 Chrome --app 模式的窗口，调用 Win32 API 设置置顶
用法: python set_always_on_top.py
"""

import ctypes
import ctypes.wintypes
import time

# Win32 常量
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SW_SHOW = 9

user32 = ctypes.windll.user32

def find_overlay_hwnd():
    """枚举所有顶层窗口，查找标题为 'Larker' 的 Chrome --app 窗口"""
    result = [None]
    
    def enum_callback(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buffer = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buffer, length)
        title = buffer.value
        
        if title == "Larker":
            result[0] = hwnd
            return False  # 停止枚举
        return True  # 继续枚举
    
    enum_proc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_int, ctypes.c_int
    )(enum_callback)
    
    user32.EnumWindows(enum_proc, 0)
    return result[0]


def get_window_rect(hwnd):
    """获取窗口位置和大小"""
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def set_always_on_top():
    """设置 Larker 窗口为 Always on Top（每次重新查找窗口，避免句柄失效）"""
    hwnd = find_overlay_hwnd()
    if hwnd is None:
        print("  [SetTop] 未找到 Larker 窗口，跳过")
        return False
    
    user32 = ctypes.windll.user32
    
    # 强制激活到前台
    try:
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    except Exception as e:
        print(f"  [SetTop] 激活失败: {e}")
    
    # 确保窗口可见
    if not user32.IsWindowVisible(hwnd):
        user32.ShowWindow(hwnd, SW_SHOW)
        print("  窗口已恢复显示（之前不可见）")
    
    # 设置置顶
    ret = user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOSIZE | SWP_NOMOVE
    )
    
    left, top, right, bottom = get_window_rect(hwnd)
    if ret:
        print(f"Set always-on-top: Larker (hwnd={hwnd}, pos=({left},{top}), size={right-left}x{bottom-top})")
    else:
        err = ctypes.GetLastError()
        print(f"SetWindowPos failed: hwnd={hwnd}, error={err}")
    
    return ret


def main():
    """多次尝试设置置顶，每次重新查找窗口"""
    print("正在查找 Overlay 窗口 (title='Larker')...")
    
    max_attempts = 15
    for attempt in range(max_attempts):
        success = set_always_on_top()
        if success:
            return True
        
        if attempt % 3 == 0:
            print(f"[SetTop] 第{attempt+1}/{max_attempts} 次尝试失败，重试中...")
        time.sleep(1)
    
    print("[SetTop] 15次尝试后仍无法设置置顶")
    return False


def _debug_enum_windows():
    """调试用：打印所有窗口标题"""
    titles = []
    
    def enum_callback(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd) + 1
        if length > 1:
            buffer = ctypes.create_unicode_buffer(length)
            user32.GetWindowTextW(hwnd, buffer, length)
            titles.append(f"  HWND={hwnd}, title='{buffer.value}'")
        return True
    
    enum_proc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_int, ctypes.c_int
    )(enum_callback)
    
    user32.EnumWindows(enum_proc, 0)
    
    # 只显示含 Chrome/localhost/Larker 的
    for t in titles:
        if "Larker" in t or "localhost" in t or "Chrome" in t or "8088" in t:
            print(t)


if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
