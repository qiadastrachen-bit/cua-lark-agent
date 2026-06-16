"""Test text + vision API profiles."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import VLM_PROVIDER, get_text_profile, get_vision_profile, vlm_config_summary, vlm_configured
from utils.vlm_client import call_chat, call_vlm


def main():
    print("=== VLM Connection Test ===")
    print(vlm_config_summary())
    print()

    if not vlm_configured(for_vision=False):
        print("FAIL: text API not configured (DEEPSEEK_API_KEY or VOLC_*)")
        sys.exit(1)

    print("[1/2] Text chat (text profile)...")
    text = call_chat("Reply with exactly: OK", timeout=30, max_retries=1)
    if not text:
        print("FAIL: text chat")
        sys.exit(1)
    print(f"  OK: {text[:80]}")

    v = get_vision_profile()
    if VLM_PROVIDER == "deepseek" or not v.get("supports_vision"):
        print("\n[2/2] Vision SKIPPED")
        print("  DeepSeek 官方 API 不支持 image_url。")
        print("  请设 VLM_PROVIDER=hybrid 并配置 VOLC_API_KEY + VOLC_ENDPOINT_ID")
        sys.exit(0)

    if not vlm_configured(for_vision=True):
        print("\n[2/2] Vision FAIL: configure VOLC_API_KEY + VOLC_ENDPOINT_ID")
        sys.exit(1)

    candidates = list(Path("screenshots").glob("*.png")) if Path("screenshots").exists() else []
    if not candidates:
        print("\n[2/2] Vision SKIPPED (no screenshots/*.png)")
        print("PASS (text only; add PNG to test vision)")
        return

    print(f"\n[2/2] Vision ({v['provider']}/{v['model']})...")
    img = str(candidates[0])
    vision = call_vlm("Describe this UI in one short sentence.", img, timeout=60, max_retries=1)
    if not vision:
        print(f"FAIL: vision on {img}")
        sys.exit(1)
    print(f"  OK: {vision[:120]}")
    print("\nPASS (text + vision)")


if __name__ == "__main__":
    main()
