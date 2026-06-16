"""
Unified VLM client — hybrid (DeepSeek text + Volc vision) or single provider.
"""

from __future__ import annotations

import base64
import io
import json
import time
from typing import Any

import requests
from PIL import Image

from config import (
    VLM_DISABLE_THINKING,
    VLM_RETRIES,
    VLM_TIMEOUT,
    get_text_profile,
    get_vision_profile,
)


def encode_image(image_path: str, max_size=(1280, 800)) -> str:
    img = Image.open(image_path)
    img.thumbnail(max_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _user_message(prompt: str, image_paths: list[str] | None = None) -> dict:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for path in image_paths or []:
        b64 = encode_image(path)
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        )
    return {"role": "user", "content": content}


def _build_payload(profile: dict, messages: list[dict], json_mode: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": profile["model"],
        "messages": messages,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if profile["provider"] == "deepseek" and VLM_DISABLE_THINKING:
        payload["thinking"] = {"type": "disabled"}
    return payload


def _post_chat(
    messages: list[dict],
    profile: dict,
    timeout: int | None = None,
    max_retries: int | None = None,
    json_mode: bool = False,
    require_vision: bool = False,
) -> str | None:
    if require_vision and not profile.get("supports_vision"):
        print(
            "  [ERR] DeepSeek V4 /chat/completions 不支持 image_url（纯文本 API）。\n"
            "        请在 .env 设置 VLM_PROVIDER=hybrid 并配置 VOLC_API_KEY + VOLC_ENDPOINT_ID，\n"
            "        或 VLM_PROVIDER=volc 全部使用火山方舟视觉模型。"
        )
        return None

    if not profile.get("api_key") or not profile.get("model"):
        print(f"  [WARN] API not configured for {profile.get('provider')} ({'vision' if require_vision else 'text'})")
        return None

    timeout = timeout or VLM_TIMEOUT
    max_retries = max_retries or VLM_RETRIES
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {profile['api_key']}",
    }
    payload = _build_payload(profile, messages, json_mode=json_mode)

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(profile["api_url"], headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.Timeout:
            wait = 15 * (2 ** (attempt - 1))
            print(f"  [WARN] VLM timeout, retry in {wait}s...")
            if attempt < max_retries:
                time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            body = ""
            try:
                body = (e.response.text or "")[:400] if e.response is not None else ""
            except Exception:
                pass
            if status == 429:
                wait = 90 + attempt * 45
                print(f"  [WARN] VLM 429, wait {wait}s...")
                if attempt < max_retries:
                    time.sleep(wait)
            else:
                print(f"  [ERR] VLM HTTP {status} [{profile['provider']}]: {body or e}")
                if attempt < max_retries:
                    time.sleep(15)
        except Exception as e:
            print(f"  [ERR] VLM call failed: {e}")
            if attempt < max_retries:
                time.sleep(10)
    return None


def call_vlm(
    prompt: str,
    image_path: str | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> str | None:
    profile = get_vision_profile()
    images = [image_path] if image_path else []
    messages = [_user_message(prompt, images)]
    return _post_chat(messages, profile, timeout=timeout, max_retries=max_retries, require_vision=bool(images))


def call_vlm_multi_image(
    prompt: str,
    image_paths: list[str],
    timeout: int | None = None,
    max_retries: int | None = None,
) -> str | None:
    profile = get_vision_profile()
    messages = [_user_message(prompt, image_paths)]
    return _post_chat(
        messages, profile, timeout=timeout, max_retries=max_retries, require_vision=True
    )


def call_vlm_json(
    prompt: str,
    image_path: str,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> dict | None:
    if "json" not in prompt.lower():
        prompt = prompt + "\n\nReturn valid json only."
    profile = get_vision_profile()
    messages = [_user_message(prompt, [image_path])]
    content = _post_chat(
        messages, profile, timeout=timeout, max_retries=max_retries,
        json_mode=True, require_vision=True,
    )
    if not content:
        return None
    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            cleaned = parts[1] if len(parts) > 1 else cleaned
            if cleaned.lstrip().startswith("json"):
                cleaned = cleaned.lstrip()[4:]
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


def call_chat(
    prompt: str,
    timeout: int | None = None,
    max_retries: int | None = None,
    json_mode: bool = False,
) -> str | None:
    profile = get_text_profile()
    messages = [{"role": "user", "content": prompt}]
    return _post_chat(
        messages, profile, timeout=timeout, max_retries=max_retries,
        json_mode=json_mode, require_vision=False,
    )
