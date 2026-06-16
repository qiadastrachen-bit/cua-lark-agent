import pyautogui
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.vlm_client import call_vlm


def take_screenshot_and_analyze(prompt="请描述这张截图的内容", save_md=True, delay=0):
    if delay > 0:
        print(f"Switch to target window within {delay}s...")
        time.sleep(delay)

    temp_img_path = "temp_screenshot.png"
    pyautogui.screenshot(temp_img_path)

    analysis_result = call_vlm(prompt, temp_img_path, timeout=60, max_retries=2)
    os.remove(temp_img_path)

    if not analysis_result:
        raise RuntimeError("VLM returned no result — check .env (DeepSeek or Volc)")

    if save_md:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_filename = f"reports/screenshot_analysis_{timestamp}.md"
        os.makedirs("reports", exist_ok=True)
        md_content = f"""# Screenshot analysis
> Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> Prompt: {prompt}

{analysis_result}
"""
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Saved: {md_filename}")

    return analysis_result


if __name__ == "__main__":
    delay_seconds = 3
    custom_prompt = "请识别截图中的飞书界面元素，列出所有可点击的按钮和菜单"
    result = take_screenshot_and_analyze(prompt=custom_prompt, save_md=True, delay=delay_seconds)
    print(result)
