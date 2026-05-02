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
    """获取屏幕分辨率"""
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()  # 支持高DPI
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return w, h


def _find_chrome():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def launch():
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(0.7)

    chrome = _find_chrome()
    screen_w, screen_h = _get_screen_size()
    # Overlay 窗口尺寸
    win_w, win_h = 320, 560
    # 定位到右上角（留 20px 边距）
    pos_x = screen_w - win_w - 20
    pos_y = 40

    if chrome:
        url = f"http://localhost:{PORT}"
        subprocess.Popen(
            [chrome, f"--app={url}",
             f"--window-position={pos_x},{pos_y}",
             f"--window-size={win_w},{win_h}",
             "--no-first-run", "--no-default-browser-check"],
            stderr=subprocess.DEVNULL,
        )
        print(f"[Larker Overlay] Chrome app mode: {url}  (pos={pos_x},{pos_y})")

        # 后台：等窗口出现后自动设为 Always on Top
        def _set_top():
            ps_script = Path(__file__).parent / "set_always_on_top.ps1"
            if ps_script.exists():
                time.sleep(2)
                for _ in range(15):
                    r = subprocess.run(
                        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)],
                        capture_output=True, text=True,
                    )
                    if "Set always-on-top" in (r.stdout or ""):
                        print("[Larker Overlay] Always-on-top set.")
                        break
                    time.sleep(1)

        threading.Thread(target=_set_top, daemon=True).start()
    else:
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
    return t


if __name__ == "__main__":
    launch()
    while True:
        time.sleep(1)
