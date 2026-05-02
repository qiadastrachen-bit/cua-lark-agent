"""
Overlay UI Server - Larker 可视化操作界面
启动：python utils/overlay_server.py
接口：GET /state   → 返回当前状态 JSON
       POST /update → 接收步骤状态更新
       GET /        → 返回 Overlay UI 页面
"""

import http.server
import socketserver
import json
import threading
import time
import subprocess
import os
import ctypes
from datetime import datetime
from pathlib import Path

PORT = 8088
HTML_FILE = Path(__file__).parent / "overlay_ui.html"

# 全局状态
state = {
    "step": 0,
    "step_name": "等待开始",
    "phase": "",
    "phase_detail": "",
    "log": [],
    "success": None,
}


def update_state(step, step_name, phase="", phase_detail="", success=None):
    state["step"] = step
    state["step_name"] = step_name
    state["phase"] = phase
    state["phase_detail"] = phase_detail
    if success is not None:
        state["success"] = success
    _log(f"[{phase}] {step_name}: {phase_detail}")


def _log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    state["log"].append(f"[{ts}] {msg}")
    if len(state["log"]) > 80:
        state["log"] = state["log][-80:]


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/overlay"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_FILE.read_bytes())
        elif self.path == "/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(state, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/update":
            length = int(self.headers["Content-Length"])
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
            for k, v in data.items():
                if k in state:
                    state[k] = v
            if "detail" in data:
                _log(data["detail"])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass


def start_server():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"[Larker Overlay] http://localhost:{PORT}")
        httpd.serve_forever()


def _get_screen_size():
    """获取屏幕分辨率（DPI-aware）"""
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        return w, h
    except Exception:
        # fallback: 用 pyautogui
        try:
            import pyautogui
            return pyautogui.size()
        except Exception:
            return 1920, 1080


def _find_chrome():
    """查找 Chrome 浏览器路径"""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _check_port_available(port):
    """检查端口是否可用"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        s.close()
        return False


def _set_always_on_top_ps1():
    """生成并返回置顶脚本的绝对路径"""
    return str(Path(__file__).parent / "set_always_on_top.ps1")


def launch():
    """启动 Overlay 服务 + Chrome --app 悬浮窗"""
    # ====== 阶段1：启动 HTTP 服务 ======
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(0.7)

    # 检查端口
    if not _check_port_available(PORT):
        print(f"[Larker Overlay] ⚠️ 端口 {PORT} 可能被占用，服务可能未正常启动")

    # ====== 阶段2：查找 Chrome ======
    chrome = _find_chrome()
    if not chrome:
        print("[Larker Overlay] ⚠️ 未找到 Chrome，将使用默认浏览器打开")
        print("[Larker Overlay] 💡 建议：安装 Chrome 以获得悬浮窗效果")
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
        return t

    print(f"[Larker Overlay] ✅ Chrome 路径: {chrome}")

    # ====== 阶段3：计算窗口位置（DPI-aware）=====
    screen_w, screen_h = _get_screen_size()
    win_w, win_h = 320, 560
    pos_x = screen_w - win_w - 20  # 右上角，留20px边距
    pos_y = 40

    # 安全边界检查：防止窗口超出屏幕
    if pos_x < 0:
        pos_x = 0
    if pos_y < 0:
        pos_y = 0
    if screen_w > 3840:  # 4K 或超高分辨率
        # 高分屏下 Chrome --app 可能需要缩放补偿
        pos_x = max(0, pos_x)

    url = f"http://localhost:{PORT}"
    print(f"[Larker Overlay] 📐 屏幕尺寸: {screen_w}x{screen_h}")
    print(f"[Larker Overlay] 📍 窗口位置: ({pos_x}, {pos_y}), 尺寸: {win_w}x{win_h}")

    # ====== 阶段4：启动 Chrome --app ======
    chrome_proc = None
    try:
        chrome_proc = subprocess.Popen(
            [chrome, f"--app={url}",
             f"--window-position={pos_x},{pos_y}",
             f"--window-size={win_w},{win_h}",
             "--no-first-run", "--no-default-browser-check",
             "--disable-infobars"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        print(f"[Larker Overlay] ✅ Chrome 已启动 (PID: {chrome_proc.pid})")
    except Exception as e:
        print(f"[Larker Overlay] ❌ Chrome 启动失败: {e}")
        import webbrowser
        webbrowser.open(url)
        return t

    # ====== 阶段5：设置 Always on Top（多重保障）======
    ps_script = _set_always_on_top_ps1()

    def _set_top():
        """后台循环尝试设置窗口置顶"""
        time.sleep(2)  # 等 Chrome 窗口创建完成
        ps_script_path = _set_always_on_top_ps1()

        for attempt in range(15):
            try:
                r = subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_script_path],
                    capture_output=True, text=True, timeout=10,
                )
                stdout_clean = (r.stdout or "").strip()
                stderr_clean = (r.stderr or "").strip()

                if "Set always-on-top" in stdout_clean:
                    print(f"[Larker Overlay] ✅ Always-on-top 设置成功 (第{attempt+1}次尝试)")
                    break
                elif "Window not found" in stdout_clean:
                    # 窗口还没出现，继续等
                    if attempt % 3 == 0:
                        print(f"[Larker Overlay] ⏳ 窗口尚未就绪，等待中... (第{attempt+1}/15次)")
                elif stderr_clean:
                    if attempt < 3:
                        print(f"[Larker Overlay] ⚠️ PowerShell 输出: {stderr_clean[:100]}")
                else:
                    # 有输出但不是成功标记，打印看看
                    if attempt % 5 == 0 and stdout_clean:
                        print(f"[Larker Overlay] 🔍 PS输出: {stdout_clean[:80]}")
            except subprocess.TimeoutExpired:
                print(f"[Larker Overlay] ⚠️ PowerShell 执行超时 (第{attempt+1}次)")
            except Exception as e:
                if attempt < 3:
                    print(f"[Larker Overlay] ⚠️ 置顶脚本异常: {e}")

            time.sleep(1)
        else:
            print("[Larker Overlay] ⚠️ 15次尝试后仍无法设置置顶，可能需要手动操作")

    threading.Thread(target=_set_top, daemon=True).start()

    # ====== 阶段6：延迟验证窗口可见性 ======
    def _verify_visible():
        """5秒后验证窗口是否确实存在且可见"""
        time.sleep(5)
        try:
            r = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass",
                 f"-Command", f"""
                    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class Win32Chk {{
        [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
        [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
        [StructLayout(LayoutKind.Sequential)] public struct RECT {{ public int Left; public int Top; public int Right; public int Bottom; }}
    }}
"@
                    $h = [Win32Chk]::FindWindow($null, 'Larker')
                    if ($h -eq [IntPtr]::Zero) {{ Write-Output 'NOT_FOUND'; exit }}
                    $vis = [Win32Chk]::IsWindowVisible($h)
                    $rect = New-Object Win32Chk+RECT
                    [Win32Chk]::GetWindowRect($h, [ref]$rect) | Out-Null
                    Write-Output "VISIBLE=$vis POS=({{ $rect.Left }},{{ $rect.Top }}) SIZE=({{ $rect.Right-$rect.Left }}x{{ $rect.Bottom-$rect.Top }})"
                 """],
                capture_output=True, text=True, timeout=10,
            )
            result = (r.stdout or "").strip()
            if result.startswith("VISIBLE="):
                print(f"[Larker Overlay] 📊 窗口状态: {result}")
            elif result == "NOT_FOUND":
                print("[Larker Overlay] ❌ 5秒后仍未找到 Larker 窗口！Chrome 可能未正常启动")
                print("[Larker Overlay] 💡 尝试手动访问 http://localhost:8088 查看服务是否正常")
        except Exception as e:
            print(f"[Larker Overlay] ⚠️ 窗口验证异常: {e}")

    threading.Thread(target=_verify_visible, daemon=True).start()

    return t


if __name__ == "__main__":
    launch()
    while True:
        time.sleep(1)
