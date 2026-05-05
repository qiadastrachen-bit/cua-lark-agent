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
import sys
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
        state["log"] = state["log"][-80:]


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
    """获取屏幕逻辑分辨率（通过实际截图尺寸，最可靠）"""
    try:
        import pyautogui
        # 方法1：用 screenshot 的实际尺寸（与 VLM 看到的一致）
        img = pyautogui.screenshot()
        w, h = img.size
        return w, h
    except Exception:
        try:
            # 方法2：fallback 到 pyautogui.size()
            import pyautogui
            w, h = pyautogui.size()
            return w, h
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


def launch():
    """启动 Overlay 服务 + Chrome --app 悬浮窗"""
    # 启动 HTTP 服务
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(0.7)

    if not _check_port_available(PORT):
        print(f"[Larker Overlay] ⚠️ 端口 {PORT} 可能被占用")

    chrome = _find_chrome()
    if not chrome:
        print("[Larker Overlay] ⚠️ 未找到 Chrome，将使用默认浏览器打开")
        print("[Larker Overlay] 💡 建议：安装 Chrome 以获得悬浮窗效果")
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
        return t

    print(f"[Larker Overlay] ✅ Chrome 路径: {chrome}")

    # 计算窗口位置（放在左上角，确保可见）
    screen_w, screen_h = _get_screen_size()
    win_w, win_h = 320, 560
    # 放在左上角 (100, 100)，确保不被任务栏或其他窗口遮挡
    pos_x = 100
    pos_y = 100

    url = f"http://localhost:{PORT}"
    print(f"[Larker Overlay] 📐 屏幕尺寸: {screen_w}x{screen_h}")
    print(f"[Larker Overlay] 📍 窗口位置: ({pos_x}, {pos_y})")

    # 启动 Chrome --app
    try:
        # 使用 --app 参数启动无地址栏的独立窗口
        # 注意：Chrome 不同版本对 --app 格式要求不同：
        #   新版: chrome.exe --app="http://..."
        #   旧版: chrome.exe --app=http://...
        # 统一使用引号包裹URL确保兼容性
        app_url = f"http://localhost:{PORT}"
        chrome_args = [
            chrome,
            f"--app={app_url}",
            f"--window-position={pos_x},{pos_y}",
            f"--window-size={win_w},{win_h}",
            "--new-window",          # 强制新窗口
            "--no-first-run",
            "--no-default-browser-check",
        ]
        print(f"[Larker Overlay] 🚀 启动参数: {chrome_args}")
        chrome_proc = subprocess.Popen(
            chrome_args,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # 隐藏控制台窗口
        ) if os.name == 'nt' else subprocess.Popen(
            chrome_args,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        print(f"[Larker Overlay] ✅ Chrome 已启动 (PID: {chrome_proc.pid})")
    except Exception as e:
        print(f"[Larker Overlay] ❌ Chrome 启动失败: {e}")
        import webbrowser
        webbrowser.open(url)
        return t

    # 后台设置 Always on Top（set_always_on_top.py 内置重试逻辑）
    py_script = Path(__file__).parent / "set_always_on_top.py"

    def _set_top():
        # 等待窗口出现
        time.sleep(3)
        
        # 调用 Python 脚本，脚本内部有 15 次重试逻辑
        try:
            r = subprocess.run(
                [sys.executable, str(py_script)],
                capture_output=True, text=True, timeout=60,
            )
            # 打印脚本输出
            if r.stdout:
                for line in r.stdout.strip().splitlines():
                    print(f"  [SetTop] {line}")
            if r.stderr:
                for line in r.stderr.strip().splitlines():
                    print(f"  [SetTop-ERR] {line}")
            
            if r.returncode == 0:
                print("[Larker Overlay] ✅ Always-on-top 设置成功")
            else:
                print("[Larker Overlay] ⚠️ 置顶脚本执行失败，请查看上方日志")
        except subprocess.TimeoutExpired:
            print("[Larker Overlay] ⚠️ 置顶脚本执行超时（60s）")
        except Exception as e:
            print(f"[Larker Overlay] ⚠️ 置顶脚本异常: {e}")

    threading.Thread(target=_set_top, daemon=True).start()

    # 延迟验证窗口可见性
    def _verify_visible():
        time.sleep(5)
        try:
            r = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command",
                 "Get-Process chrome -ErrorAction SilentlyContinue | "
                 "Where-Object { $_.MainWindowTitle -eq 'Larker' } | "
                 "ForEach-Object { Write-Output ('VISIBLE=' + $_.MainWindowTitle) }"],
                capture_output=True, text=True, timeout=10,
            )
            result = (r.stdout or "").strip()
            if "VISIBLE" in result:
                print(f"[Larker Overlay] 📊 窗口状态: {result}")
            else:
                print("[Larker Overlay] ⚠️ 5秒后仍未找到 Larker 窗口，请手动检查 Chrome --app 是否正常启动")
        except Exception as e:
            print(f"[Larker Overlay] ⚠️ 窗口验证异常: {e}")

    threading.Thread(target=_verify_visible, daemon=True).start()

    return t


if __name__ == "__main__":
    launch()
    while True:
        time.sleep(1)
