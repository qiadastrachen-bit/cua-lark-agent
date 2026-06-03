import sys
import os
import json
import time
import argparse
import signal
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ops.step_01_click_search import click_search_box
from ops.step_02_input_text import input_search_text, activate_feishu_window
from ops.step_03_wait_search_results import wait_search_results
from ops.step_04_click_first_result import click_first_result
from ops.step_05_verify_and_archive import verify_and_archive


def retry_step(step_func, *args, max_retries=2, step_timeout=600, **kwargs):
    """
    单步重试包装器：
    - 如果某一步返回 success=False，自动整步重试
    - max_retries=2 表示：首次 + 最多重试2次 = 共3次机会
    - 每次重试前等待 5 * 重试次数 秒（5s, 10s）
    - step_timeout: 单步超时（默认600秒=10分钟），超时强制返回失败
    - 任意一次成功就立即返回成功结果
    - 全部失败则返回最后一次的结果（无论成功/失败）
    """
    import time

    def _run_with_timeout():
        nonlocal result
        result = step_func(*args, **kwargs)

    result = {"success": False, "message": "超时未完成"}
    for attempt in range(max_retries + 1):   # 0, 1, 2
        if attempt > 0:
            wait_sec = 5 * attempt
            print(f"  🔄 重试 {step_func.__name__} (第 {attempt}/{max_retries} 次，等待 {wait_sec}s)...")
            time.sleep(wait_sec)
        else:
            print(f"  ▶️  执行 {step_func.__name__}... (超时: {step_timeout}s)")

        result = {"success": False, "message": "超时未完成"}
        timer = threading.Timer(step_timeout, lambda: None)  # 简化：依赖内部VLM超时
        timer.start()
        try:
            result = step_func(*args, **kwargs)
        except Exception as e:
            result = {"success": False, "message": f"异常: {str(e)}"}
        finally:
            timer.cancel()

        if result.get("success"):
            if attempt > 0:
                print(f"  ✅ {step_func.__name__} 重试成功！(第 {attempt} 次)")
            return result
        else:
            msg = result.get("message", "未知错误")
            print(f"  ❌ {step_func.__name__} 失败: {msg}")

    print(f"  ❌ {step_func.__name__} 所有重试均失败")
    return result


def run_test_case(search_term):
    step_results = []

    print("=== Step 01: 点击搜索框 ===")
    result = retry_step(click_search_box)
    step_results.append({
        "name": "Step01 点击搜索框",
        "success": result["success"],
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot")
    })
    time.sleep(30)  # 给VLM配额恢复时间

    print("=== Step 02: 输入搜索词 ===")
    result = retry_step(input_search_text, search_term)
    step_results.append({
        "name": "Step02 输入搜索词",
        "success": result["success"],
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot")
    })
    time.sleep(30)

    print("=== Step 03: 等待结果 ===")
    result = retry_step(wait_search_results, wait_seconds=5, enable_visualizer=True)
    step_results.append({
        "name": "Step03 等待搜索结果",
        "success": result["success"],
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot")
    })
    time.sleep(30)

    print("=== Step 04: 点击第一条结果 ===")
    # use_opencv_refine=True: VLM 定位后 OpenCV 精定位（双轨定位完整版）
    # 设为 False 可跳过 OpenCV 精定位（调试/纯 VLM 对比时用）
    result = retry_step(click_first_result, enable_visualizer=True, use_opencv_refine=True)
    step_results.append({
        "name": "Step04 点击第一条结果",
        "success": result["success"],
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot")
    })
    time.sleep(30)

    print("=== Step 05: 验证归档 ===")
    verify_and_archive(step_results)

    print("\n=== 执行汇总 ===")
    for r in step_results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} {r['name']}: {r.get('message', '')}")

    return step_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="飞书 CUA 多步操作串联")
    parser.add_argument("--search-term", type=str, default="测试", help="搜索词")
    parser.add_argument("--run-all", action="store_true", help="运行所有测试用例")
    args = parser.parse_args()

    if args.run_all:
        with open("test_cases.json", encoding="utf-8") as f:
            cases = json.load(f)
        all_results = []
        for case in cases:
            print(f"\n{'='*50}")
            print(f"运行用例: {case['id']} - {case['name']}")
            step_results = run_test_case(case["search_term"])
            all_results.append({"case": case, "results": step_results})
            time.sleep(90)  # 用例间长延迟，让TPM配额充分恢复

        print(f"\n{'='*50}")
        print("=== 全部用例执行完毕 ===")
        for r in all_results:
            success_count = sum(1 for s in r["results"] if s["success"])
            print(f"{r['case']['id']} {r['case']['name']}: {success_count}/{len(r['results'])} 步成功")
    else:
        run_test_case(args.search_term)