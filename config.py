"""
CUA Larker Agent — 统一配置文件
===============================
所有 API Key、端点、路径等配置集中管理。
通过 .env 文件注入敏感信息（API Key 等），不硬编码在源码中。

用法:
    from config import API_KEY, ENDPOINT_ID, API_URL, PROJECT_ROOT
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ========== API 配置（从环境变量读取，不硬编码）==========
API_KEY = os.getenv("VOLC_API_KEY", "")
ENDPOINT_ID = os.getenv("VOLC_ENDPOINT_ID", "")
API_URL = os.getenv("VOLC_API_URL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")

# ========== 项目路径 ==========
PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
ARCHIVE_DIR = PROJECT_ROOT / "archive"
REPORT_DIR = PROJECT_ROOT / "reports"
VIDEO_DIR = PROJECT_ROOT / "videos"

# ========== 操作模式 ==========
# 设为 "true" 则绕过 VLM 直接用固定坐标（用于 VLM 限流/调试）
# 设为 "false" 则启用完整 VLM+OpenCV 双轨定位
USE_FIXED_COORDS = os.getenv("USE_FIXED_COORDS", "false").lower() == "true"
FIXED_COORDS = (1280, 350)  # 仅 USE_FIXED_COORDS=True 时生效

# ========== VLM 配置 ==========
VLM_TIMEOUT = int(os.getenv("VLM_TIMEOUT", "30"))
VLM_RETRIES = int(os.getenv("VLM_RETRIES", "2"))
