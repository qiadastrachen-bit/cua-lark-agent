import sys
import os
import json
import time
import argparse
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import STEP_DELAY_SEC, CASE_DELAY_SEC, STRICT_STATE_CHECK
from core.state_checker import gate_step
from core.task_parser import parse_instruction
from ops.step_01_click_search import click_search_box
from ops.step_02_input_text import input_search_text
from ops.step_03_wait_search_results import wait_search_results
from ops.step_04_click_first_result import click_first_result
from ops.step_05_verify_and_archive import verify_and_archive
from ops.step_06_send_message import send_chat_message


def retry_step(step_func, *args, max_retries=2, step_timeout=600, **kwargs):
    result = {"success": False, "message": "timeout"}
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait_sec = 5 * attempt
            print(f"  retry {step_func.__name__} ({attempt}/{max_retries}, wait {wait_sec}s)...")
            time.sleep(wait_sec)
        else:
            print(f"  run {step_func.__name__}... (timeout {step_timeout}s)")

        try:
            result = step_func(*args, **kwargs)
        except Exception as e:
            result = {"success": False, "message": f"exception: {e}"}

        if result.get("success"):
            if attempt > 0:
                print(f"  OK {step_func.__name__} recovered on retry {attempt}")
            return result
        print(f"  FAIL {step_func.__name__}: {result.get('message', '')}")

    print(f"  FAIL {step_func.__name__}: all retries exhausted")
    return result


def _append_step(step_results, name, result, elapsed_sec, extra=None):
    entry = {
        "name": name,
        "success": result.get("success", False),
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot"),
        "screenshots": result.get("screenshots", []),
        "elapsed_sec": round(elapsed_sec, 2),
    }
    if extra:
        entry.update(extra)
    step_results.append(entry)
    return entry


def _state_gate(step_results, screenshot, expected, label):
    ok, msg, info = gate_step(screenshot, expected, label, strict=STRICT_STATE_CHECK)
    if msg:
        print(f"  {msg}")
    if step_results and info:
        step_results[-1]["state_check"] = info
        if not ok:
            step_results[-1]["success"] = False
            step_results[-1]["message"] += f" | {msg}"
    return ok


def run_test_case(search_term, case_meta=None, message_text=None):
    step_results = []
    case_meta = case_meta or {}
    run_started = time.time()

    t0 = time.time()
    print("=== Step 01: click search box ===")
    result = retry_step(click_search_box)
    _append_step(step_results, "Step01 click search", result, time.time() - t0, {"locate_method": result.get("locate_method")})
    if result.get("success"):
        _state_gate(step_results, result.get("screenshot"), ["search_box_active", "searching", "search_results"], "after Step01")
    if not step_results[-1]["success"]:
        verify_and_archive(step_results, case_meta=case_meta, total_elapsed=time.time() - run_started)
        return step_results
    time.sleep(STEP_DELAY_SEC)

    t0 = time.time()
    print("=== Step 02: input search term ===")
    result = retry_step(input_search_text, search_term)
    _append_step(step_results, "Step02 input text", result, time.time() - t0)
    time.sleep(STEP_DELAY_SEC)

    t0 = time.time()
    print("=== Step 03: wait for results ===")
    result = retry_step(wait_search_results, wait_seconds=5, enable_visualizer=True)
    _append_step(step_results, "Step03 wait results", result, time.time() - t0)
    if result.get("success"):
        shot = result.get("screenshot") or (result.get("screenshots") or [None])[-1]
        _state_gate(step_results, shot, ["search_results", "searching"], "after Step03")
    if not step_results[-1]["success"]:
        verify_and_archive(step_results, case_meta=case_meta, total_elapsed=time.time() - run_started)
        return step_results
    time.sleep(STEP_DELAY_SEC)

    t0 = time.time()
    print("=== Step 04: click first result ===")
    result = retry_step(click_first_result, enable_visualizer=True, use_opencv_refine=True, search_term=search_term)
    _append_step(step_results, "Step04 click result", result, time.time() - t0)
    if result.get("success"):
        _state_gate(
            step_results,
            result.get("screenshot"),
            ["chat_window", "doc_editing", "calendar_view", "feishu_main"],
            "after Step04",
        )
    if not step_results[-1]["success"]:
        verify_and_archive(step_results, case_meta=case_meta, total_elapsed=time.time() - run_started)
        return step_results
    time.sleep(STEP_DELAY_SEC)

    if message_text:
        t0 = time.time()
        print("=== Step 06: send chat message ===")
        result = retry_step(send_chat_message, message_text)
        _append_step(step_results, "Step06 send message", result, time.time() - t0)
        if result.get("success"):
            _state_gate(step_results, result.get("screenshot"), ["chat_window"], "after Step06")
        if not step_results[-1]["success"]:
            verify_and_archive(step_results, case_meta=case_meta, total_elapsed=time.time() - run_started)
            return step_results
        time.sleep(STEP_DELAY_SEC)

    t0 = time.time()
    print("=== Step 05: verify and archive ===")
    archive_result = verify_and_archive(
        step_results,
        case_meta=case_meta,
        total_elapsed=time.time() - run_started,
    )
    step05 = {
        "success": archive_result.get("success", False),
        "message": archive_result.get("message", "archive done"),
        "screenshot": None,
        "screenshots": [],
        "archive_path": archive_result.get("archive_path"),
        "execution_report": archive_result.get("execution_report"),
    }
    _append_step(step_results, "Step05 verify archive", step05, time.time() - t0)

    print("\n=== summary ===")
    for r in step_results:
        status = "OK" if r["success"] else "FAIL"
        print(f"  [{status}] {r['name']} ({r.get('elapsed_sec', 0)}s): {r.get('message', '')}")

    passed = sum(1 for r in step_results if r["success"])
    print(f"\nTotal: {passed}/{len(step_results)} steps passed in {time.time() - run_started:.1f}s")
    return step_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Feishu CUA pipeline")
    parser.add_argument("--search-term", type=str, help="Search keyword")
    parser.add_argument("--message", type=str, help="Message to send after opening chat (Step06)")
    parser.add_argument("--instruction", type=str, help="Natural language test instruction")
    parser.add_argument("--run-all", action="store_true", help="Run all cases in test_cases.json")
    args = parser.parse_args()

    message_text = None

    if args.instruction:
        task = parse_instruction(args.instruction)
        search_term = task["search_term"]
        message_text = task.get("message_text") or args.message
        print(
            f"Parsed instruction ({task['source']}): flow={task['flow']}, "
            f"term={search_term}, message={message_text or '(none)'}"
        )
    elif args.search_term:
        search_term = args.search_term
        message_text = args.message
    else:
        search_term = "测试"
        message_text = args.message

    if args.run_all:
        with open("test_cases.json", encoding="utf-8") as f:
            cases = json.load(f)
        for case in cases:
            print(f"\n{'='*50}\nCase {case['id']}: {case['name']}\n{'='*50}")
            term = case["search_term"]
            msg = case.get("message_text")
            if case.get("instruction"):
                parsed = parse_instruction(case["instruction"])
                term = parsed["search_term"]
                msg = parsed.get("message_text") or msg
            run_test_case(term, case_meta=case, message_text=msg)
            time.sleep(CASE_DELAY_SEC)
    else:
        run_test_case(search_term, message_text=message_text)
