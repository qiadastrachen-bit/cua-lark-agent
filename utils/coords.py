"""Coordinate scaling between screenshot pixels and pyautogui logical screen."""

from __future__ import annotations

import pyautogui
from PIL import Image

# Must match utils/vlm_client.encode_image thumbnail limits
VLM_ENCODE_MAX_SIZE = (1280, 800)


def get_logical_size() -> tuple[int, int]:
    size = pyautogui.size()
    return int(size.width), int(size.height)


def get_screenshot_size(image_path: str) -> tuple[int, int]:
    with Image.open(image_path) as img:
        return img.size


def get_encoded_image_size(image_path: str, max_size=VLM_ENCODE_MAX_SIZE) -> tuple[int, int]:
    """Size of the image actually sent to VLM (after thumbnail, same as encode_image)."""
    with Image.open(image_path) as img:
        copy = img.copy()
        copy.thumbnail(max_size, Image.LANCZOS)
        return copy.size


def scale_point(x: int, y: int, from_size: tuple[int, int], to_size: tuple[int, int]) -> tuple[int, int]:
    fw, fh = from_size
    tw, th = to_size
    if fw <= 0 or fh <= 0:
        return x, y
    if (fw, fh) == (tw, th):
        return x, y
    sx = tw / fw
    sy = th / fh
    return int(round(x * sx)), int(round(y * sy))


def vlm_coords_to_screen(x: int, y: int, screenshot_path: str) -> tuple[int, int]:
    """
    Map VLM-returned coordinates to pyautogui logical screen.

    VLM receives a thumbnail (max 1280x800), so returned x,y are usually in that
    encoded image space — NOT full screenshot pixels.
    """
    encoded_size = get_encoded_image_size(screenshot_path)
    shot_size = get_screenshot_size(screenshot_path)
    logical = get_logical_size()
    x_shot, y_shot = scale_point(x, y, encoded_size, shot_size)
    return scale_point(x_shot, y_shot, shot_size, logical)


def screen_coords_to_screenshot(x: int, y: int, screenshot_path: str) -> tuple[int, int]:
    """Inverse of vlm_coords_to_screen final step (logical → screenshot pixels)."""
    shot_size = get_screenshot_size(screenshot_path)
    logical = get_logical_size()
    return scale_point(x, y, logical, shot_size)


def screen_info_for_prompt(screenshot_path: str | None = None) -> str:
    lw, lh = get_logical_size()
    if screenshot_path:
        sw, sh = get_screenshot_size(screenshot_path)
        ew, eh = get_encoded_image_size(screenshot_path)
        return (
            f"模型实际看到的图片尺寸 {ew}x{eh}（请在此尺寸坐标系下返回 x,y），"
            f"原始截图 {sw}x{sh}，屏幕逻辑 {lw}x{lh}"
        )
    return f"pyautogui逻辑分辨率 {lw}x{lh}"
