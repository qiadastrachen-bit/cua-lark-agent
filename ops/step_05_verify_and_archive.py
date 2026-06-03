"""
Step 05: 验证执行结果并归档

功能：
1. 截图对比验证 - 每个step执行前后截图保存到screenshots/verify/，对比差异
2. VLM视觉确认 - 在Step 04点击后调用VLM确认是否进入详情页
3. 结果归档增强 - JSON文件归档，按日期组织：archive/YYYY-MM-DD/
4. 失败快速终止 - 记录失败现场：截图+错误信息+鼠标位置
"""

import cv2
import numpy as np
import os
import time
import json
import re
import pyautogui
import base64
import requests
import shutil
from datetime import datetime
from pathlib import Path
from config import API_KEY, ENDPOINT_ID, API_URL, PROJECT_ROOT

SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
VERIFY_DIR = SCREENSHOT_DIR / "verify"
ARCHIVE_DIR = PROJECT_ROOT / "archive"
REPORT_DIR = PROJECT_ROOT / "reports"

VLM_TIMEOUT = 30
VLM_RETRIES = 2


def get_mouse_position():
    """获取当前鼠标位置"""
    x, y = pyautogui.position()
    return {"x": x, "y": y}


def save_failure_scene(step_name, error_msg, screenshot_path=None):
    """保存失败现场：截图+错误信息+鼠标位置"""
    failure_dir = VERIFY_DIR / "failure_scene" / datetime.now().strftime("%Y%m%d_%H%M%S")
    failure_dir.mkdir(parents=True, exist_ok=True)

    scene_info = {
        "timestamp": datetime.now().isoformat(),
        "step": step_name,
        "error": error_msg,
        "mouse_position": get_mouse_position(),
        "screenshot": None
    }

    if screenshot_path and os.path.exists(screenshot_path):
        dest_path = failure_dir / f"failure_{Path(screenshot_path).name}"
        shutil.copy2(screenshot_path, dest_path)
        scene_info["screenshot"] = str(dest_path)

    info_path = failure_dir / "scene_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(scene_info, f, ensure_ascii=False, indent=2)

    print(f"  📸 失败现场已保存: {failure_dir}")
    return str(failure_dir)


def compare_images_similarity(img1_path, img2_path):
    """对比两张图片的相似度，返回0.0-1.0之间的相似度"""
    if not os.path.exists(img1_path) or not os.path.exists(img2_path):
        return None

    img1 = cv2.imread(str(img1_path))
    img2 = cv2.imread(str(img2_path))

    if img1 is None or img2 is None:
        return None

    if img1.shape != img2.shape:
        img2_resized = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    else:
        img2_resized = img2

    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2_resized, cv2.COLOR_BGR2GRAY)

    diff = cv2.absdiff(gray1, gray2)
    non_zero_ratio = np.count_nonzero(diff) / diff.size
    similarity = 1.0 - non_zero_ratio

    return round(similarity, 4)


def verify_step_screenshots(step_results):
    """验证每个step的截图差异，检测界面是否有变化"""
    print("\n🔍 开始截图对比验证...")

    verify_date_dir = VERIFY_DIR / datetime.now().strftime("%Y-%m-%d")
    verify_date_dir.mkdir(parents=True, exist_ok=True)

    verification_results = []

    step_names = ["Step01", "Step02", "Step03", "Step04"]

    for idx, step_result in enumerate(step_results):
        step_name = step_names[idx] if idx < len(step_names) else f"Step{idx+1}"
        # 兼容两种字段名：screenshots（复数）或screenshot（单数）
        screenshots = step_result.get("screenshots", [])
        single_screenshot = step_result.get("screenshot")
        if not screenshots and single_screenshot:
            # 如果只有单数screenshot，当作after截图（无before对比）
            screenshots = [single_screenshot]

        if len(screenshots) >= 2:
            before_path = screenshots[0]
            after_path = screenshots[-1]

            similarity = compare_images_similarity(before_path, after_path)

            if similarity is not None:
                change_detected = similarity < 0.95
                verification_results.append({
                    "step": step_name,
                    "before": before_path,
                    "after": after_path,
                    "similarity": similarity,
                    "change_detected": change_detected
                })

                status = "✅" if change_detected else "⚠️"
                print(f"  {status} {step_name}: 相似度={similarity:.3f}", end="")
                if change_detected:
                    print(" (界面有变化)")
                else:
                    print(" (界面无变化 - 点击可能未生效)")

                if change_detected:
                    try:
                        before_name = Path(before_path).name
                        after_name = Path(after_path).name
                        shutil.copy2(before_path, verify_date_dir / f"{step_name}_before_{before_name}")
                        shutil.copy2(after_path, verify_date_dir / f"{step_name}_after_{after_name}")
                    except Exception as e:
                        print(f"    截图归档失败: {e}")
        else:
            if len(screenshots) == 1:
                print(f"  📸 {step_name}: 仅有1张截图(无before/after对比)")
            else:
                print(f"  ⚠️ {step_name}: 截图数量不足({len(screenshots)}), 跳过对比")

    return verification_results


def call_vlm_for_detail_verification(screenshot_path):
    """调用VLM确认是否已进入搜索结果详情页"""
    print("\n🤖 VLM视觉确认: 检查是否已进入详情页...")

    prompt = """请检查这张截图，确认是否已经进入了搜索结果的详情页面。

重要判断依据：
- 详情页特征：不再显示搜索结果列表，而是显示具体的文档/消息内容
- 可能看到：文档正文、内容编辑区、消息详情等
- 不是详情页的特征：仍然是搜索结果下拉列表、悬浮面板

返回格式（严格JSON）：
{"entered_detail": true/false, "current_page": "页面描述", "confidence": 0.0-1.0}

只返回JSON，不要其他内容。"""

    try:
        from PIL import Image
        img = Image.open(screenshot_path)
        img.thumbnail((1280, 800), Image.LANCZOS)
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"  ⚠️ 图片压缩失败: {e}")
        with open(screenshot_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": ENDPOINT_ID,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            }
        ]
    }

    for attempt in range(1, VLM_RETRIES + 1):
        try:
            print(f"  📤 VLM请求中... (第{attempt}次)")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=VLM_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            print(f"  📝 VLM返回: {content[:100]}")

            # 第一层：直接解析（response_format 生效后应为纯 JSON）
            try:
                vlm_result = json.loads(content)
                print(f"  ✅ JSON直接解析成功")
                return vlm_result
            except json.JSONDecodeError:
                pass  # 继续走正则提取

            # 第二层：正则提取 JSON 块（VLM 在 JSON 前后加了废话）
            json_match = re.search(r'\{.*?\}', content, re.DOTALL)
            if json_match:
                try:
                    vlm_result = json.loads(json_match.group())
                    print(f"  ✅ 正则提取JSON成功")
                    return vlm_result
                except json.JSONDecodeError:
                    pass  # JSON 格式仍有问题，继续走兜底逻辑

            # 第三层：关键词匹配（补充中文"是/否"）
            print(f"  ⚠️ VLM返回格式异常，尝试关键词解析...")
            content_lower = content.lower()
            if ("true" in content_lower or "是" in content_lower) and "detail" in content_lower:
                return {"entered_detail": True, "current_page": "可能已进入详情页", "confidence": 0.5}
            elif "false" in content_lower or "否" in content_lower:
                return {"entered_detail": False, "current_page": "可能未进入详情页", "confidence": 0.5}

        except requests.exceptions.Timeout:
            wait = 10 * (2 ** (attempt - 1))
            print(f"  ⏳ VLM超时，等待{wait}s后重试...")
            if attempt < VLM_RETRIES:
                time.sleep(wait)
        except Exception as e:
            print(f"  ❌ VLM调用失败: {e}")
            if attempt < VLM_RETRIES:
                time.sleep(5)

    return {"entered_detail": None, "current_page": "VLM调用失败", "confidence": 0.0}


def should_stop_on_failure(step_results):
    """检查是否应该停止后续步骤（失败且重试耗尽）"""
    for result in step_results:
        if not result.get("success"):
            return True
    return False


def generate_archive_report(step_results, verification_results=None, vlm_result=None, failure_scene=None):
    """生成归档报告，按日期组织"""
    today = datetime.now().strftime("%Y-%m-%d")
    archive_date_dir = ARCHIVE_DIR / today
    archive_date_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "timestamp": datetime.now().isoformat(),
        "test_case": "TC001",
        "steps": [],
        "overall": {
            "success": all(r["success"] for r in step_results) if step_results else False,
            "passed": sum(1 for r in step_results if r["success"]),
            "failed": sum(1 for r in step_results if not r["success"])
        },
        "screenshots": [],
        "verification": verification_results or [],
        "vlm_detail_check": vlm_result,
        "failure_scene": failure_scene
    }

    for idx, result in enumerate(step_results):
        step_entry = {
            "step": idx + 1,
            "name": result.get("name", f"Step{idx+1}"),
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "screenshots": result.get("screenshots", [])
        }
        report["steps"].append(step_entry)
        report["screenshots"].extend(step_entry["screenshots"])

    archive_json_path = archive_date_dir / f"run_{timestamp}.json"
    with open(archive_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    md_content = f"""# 飞书CUA执行报告
> 执行时间: {report['timestamp']}
> 执行结果: {"✅ 全部成功" if report['overall']['success'] else "❌ 部分失败"}
> 成功步骤: {report['overall']['passed']}/{report['overall']['passed'] + report['overall']['failed']}

## 步骤详情
"""

    for step in report["steps"]:
        status = "✅" if step["success"] else "❌"
        md_content += f"### {status} Step {step['step']}: {step['name']}\n"
        md_content += f"- 消息: {step['message']}\n"
        if step["screenshots"]:
            md_content += f"- 截图数: {len(step['screenshots'])}\n"
        md_content += "\n"

    if verification_results:
        md_content += "## 截图对比验证\n"
        for v in verification_results:
            status = "✅" if v["change_detected"] else "⚠️"
            md_content += f"- {status} {v['step']}: 相似度={v['similarity']:.3f}\n"
        md_content += "\n"

    if vlm_result:
        md_content += "## VLM详情页确认\n"
        md_content += f"- 进入详情页: {vlm_result.get('entered_detail', '未知')}\n"
        md_content += f"- 当前页面: {vlm_result.get('current_page', '未知')}\n"
        md_content += f"- 置信度: {vlm_result.get('confidence', 0.0):.2f}\n\n"

    if failure_scene:
        md_content += f"## 失败现场\n"
        md_content += f"- 现场目录: {failure_scene}\n\n"

    archive_md_path = archive_date_dir / f"run_{timestamp}.md"
    with open(archive_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"📦 归档完成: {archive_date_dir}")
    print(f"  📄 JSON: {archive_json_path}")
    print(f"  📝 MD: {archive_md_path}")

    return str(archive_json_path)


def check_suspicious_failure(step_results, verification_results):
    """检测可疑失败：如果点击操作后界面没变化，标记为可疑"""
    suspicious_flags = []

    step_mapping = {
        0: ("Step01", "点击搜索框"),
        1: ("Step02", "输入搜索词"),
        2: ("Step03", "等待搜索结果"),
        3: ("Step04", "点击第一条结果")
    }

    for idx, (step_name, step_desc) in step_mapping.items():
        if idx < len(step_results):
            result = step_results[idx]
            if not result.get("success"):
                if idx < len(verification_results):
                    v = verification_results[idx]
                    if not v.get("change_detected", True):
                        suspicious_flags.append({
                            "step": step_name,
                            "description": step_desc,
                            "reason": "操作后界面无变化，可能点击未生效"
                        })

    return suspicious_flags


def verify_and_archive(step_results=None, stop_on_failure=True):
    """验证执行结果并归档

    Args:
        step_results: run_all传入的步骤执行结果列表
        stop_on_failure: 是否在失败时停止后续验证
    Returns:
        dict: 包含验证结果和归档路径
    """
    print("\n" + "=" * 60)
    print("=== Step 05: 结果验证与归档 ===")
    print("=" * 60)

    if step_results is None:
        step_results = []

    print(f"\n📊 共 {len(step_results)} 个步骤待验证")

    failure_scene = None
    if should_stop_on_failure(step_results):
        print("\n⚠️ 检测到步骤执行失败...")
        failed_step = next((r for r in step_results if not r.get("success")), None)
        if failed_step:
            print(f"  失败步骤: {failed_step.get('name', '未知')}")
            print(f"  失败原因: {failed_step.get('message', '未知')}")
            failure_scene = save_failure_scene(
                failed_step.get("name", "未知"),
                failed_step.get("message", "未知"),
                failed_step.get("screenshot")
            )

    print("\n📸 步骤1: 截图对比验证")
    verification_results = verify_step_screenshots(step_results)

    print("\n🎯 步骤2: VLM详情页确认")
    vlm_result = None
    if len(step_results) >= 4:
        step04_screenshots = step_results[3].get("screenshots", [])
        if step04_screenshots:
            last_screenshot = step04_screenshots[-1]
            if os.path.exists(last_screenshot):
                vlm_result = call_vlm_for_detail_verification(last_screenshot)

                if vlm_result:
                    entered = vlm_result.get("entered_detail")
                    if entered is True:
                        print("  ✅ VLM确认: 已进入详情页")
                    elif entered is False:
                        print("  ⚠️ VLM确认: 可能未进入详情页")
                    else:
                        print("  ⚠️ VLM确认失败或结果不确定")

    print("\n📦 步骤3: 生成归档报告")
    archive_path = generate_archive_report(step_results, verification_results, vlm_result, failure_scene)

    print("\n🔎 步骤4: 可疑失败检测")
    suspicious = check_suspicious_failure(step_results, verification_results)
    if suspicious:
        print("  ⚠️ 检测到可疑失败:")
        for s in suspicious:
            print(f"    - {s['step']} ({s['description']}): {s['reason']}")
    else:
        print("  ✅ 未检测到可疑失败")

    print("\n" + "=" * 60)
    print("=== 执行汇总 ===")
    print("=" * 60)
    for r in step_results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} {r.get('name', '未知')}: {r.get('message', '')}")

    print("\n✅ Step 05 完成，所有数据已归档")
    print(f"📦 归档位置: {archive_path}")

    return {
        "success": all(r["success"] for r in step_results) if step_results else True,
        "verification_results": verification_results,
        "vlm_result": vlm_result,
        "archive_path": archive_path,
        "suspicious_failures": suspicious,
        "failure_scene": failure_scene
    }


if __name__ == "__main__":
    result = verify_and_archive()
    print("\n最终结果:", "成功" if result["success"] else "失败")