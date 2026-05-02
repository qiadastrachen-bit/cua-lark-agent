"""
Overlay Client - 供 Agent 各步骤调用的轻量推送接口
用法：
    from utils.overlay_client import push
    push(step=1, name="点击搜索框", phase="See", detail="正在截屏分析...")
"""

import json
import sys
from pathlib import Path

# 尝试导入 requests，失败则用标准库
try:
    import requests
    _HAVE_REQUESTS = True
except ImportError:
    import urllib.request
    _HAVE_REQUESTS = False

URL = "http://localhost:8088/update"
TIMEOUT = 2  # 不阻塞主流程


def push(step, name, phase="", detail="", success=None):
    """向 Overlay UI 推送状态（不阻塞）"""
    data = {"step": step, "step_name": name, "phase": phase, "phase_detail": detail}
    if success is not None:
        data["success"] = success
    try:
        if _HAVE_REQUESTS:
            requests.post(URL, json=data, timeout=TIMEOUT)
        else:
            req = urllib.request.Request(
                URL,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=TIMEOUT)
    except Exception:
        # 静默失败，不影响主流程
        pass


def log(msg):
    """向 Overlay UI 追加一条日志"""
    try:
        data = {"detail": msg}
        if _HAVE_REQUESTS:
            requests.post(URL, json=data, timeout=TIMEOUT)
        else:
            req = urllib.request.Request(
                URL,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=TIMEOUT)
    except Exception:
        pass
