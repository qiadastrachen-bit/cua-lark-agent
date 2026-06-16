"""
CUA Larker Agent — 统一配置文件

VLM_PROVIDER:
  - hybrid   (推荐) 视觉=百炼/智谱等 OpenAI 兼容 API，文本=DeepSeek
  - volc             全部走火山方舟（视觉+文本）
  - deepseek         仅文本（官方 API 不支持 image_url，不能跑 CUA 识图）

说明: DeepSeek V4 (deepseek-v4-flash/pro) 的 /chat/completions 目前仅接受纯文本，
      传 image_url 会 400。CUA 截图定位必须用 volc 或 hybrid 模式。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
ARCHIVE_DIR = PROJECT_ROOT / "archive"
REPORT_DIR = PROJECT_ROOT / "reports"
VIDEO_DIR = PROJECT_ROOT / "videos"

VLM_PROVIDER = os.getenv("VLM_PROVIDER", "hybrid").lower().strip()


def _deepseek_profile() -> dict:
    return {
        "provider": "deepseek",
        "api_key": os.getenv("DEEPSEEK_API_KEY", os.getenv("VLM_API_KEY", "")),
        "model": os.getenv("DEEPSEEK_MODEL", os.getenv("VLM_MODEL", "deepseek-v4-flash")),
        "api_url": os.getenv(
            "DEEPSEEK_API_URL",
            os.getenv("VLM_API_URL", "https://api.deepseek.com/chat/completions"),
        ),
        "supports_vision": False,
    }


def _vision_profile() -> dict:
    """OpenAI-compatible vision: SiliconFlow / 阿里云百炼 / 智谱 / 原火山方舟等。"""
    api_key = os.getenv("VISION_API_KEY") or os.getenv("VOLC_API_KEY", "")
    model = os.getenv("VISION_MODEL") or os.getenv("VOLC_ENDPOINT_ID", "")
    api_url = os.getenv("VISION_API_URL") or os.getenv(
        "VOLC_API_URL",
        "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
    )
    name = os.getenv("VISION_PROVIDER", "openai_compatible")
    return {
        "provider": name,
        "api_key": api_key,
        "model": model,
        "api_url": api_url,
        "supports_vision": bool(api_key and model),
    }


def get_text_profile() -> dict:
    if VLM_PROVIDER == "volc":
        return _vision_profile()
    return _deepseek_profile()


def get_vision_profile() -> dict:
    if VLM_PROVIDER in ("volc", "hybrid", "openai"):
        return _vision_profile()
    return _deepseek_profile()


# 向后兼容：默认导出视觉侧配置（Step04/05、state_checker）
_vision = get_vision_profile()
API_KEY = _vision["api_key"]
VLM_MODEL = _vision["model"]
API_URL = _vision["api_url"]
ENDPOINT_ID = VLM_MODEL

USE_FIXED_COORDS = os.getenv("USE_FIXED_COORDS", "false").lower() == "true"
FIXED_COORDS = (1280, 350)

VLM_TIMEOUT = int(os.getenv("VLM_TIMEOUT", "30"))
VLM_RETRIES = int(os.getenv("VLM_RETRIES", "2"))
VLM_DISABLE_THINKING = os.getenv("VLM_DISABLE_THINKING", "true").lower() == "true"

ENABLE_STATE_CHECK = os.getenv("ENABLE_STATE_CHECK", "true").lower() == "true"
STRICT_STATE_CHECK = os.getenv("STRICT_STATE_CHECK", "false").lower() == "true"
STEP_DELAY_SEC = int(os.getenv("STEP_DELAY_SEC", "30"))
CASE_DELAY_SEC = int(os.getenv("CASE_DELAY_SEC", "90"))


def vlm_configured(for_vision: bool = True) -> bool:
    p = get_vision_profile() if for_vision else get_text_profile()
    return bool(p.get("api_key") and p.get("model") and (p.get("supports_vision", True) if for_vision else True))


def vlm_config_summary() -> str:
    v = get_vision_profile()
    t = get_text_profile()
    def _hint(k):
        return f"{k[:8]}..." if k and len(k) > 8 else "(未设置)"
    return (
        f"mode={VLM_PROVIDER} | "
        f"vision={v['provider']}/{v['model'] or '?'} key={_hint(v['api_key'])} | "
        f"text={t['provider']}/{t['model'] or '?'} key={_hint(t['api_key'])}"
    )
