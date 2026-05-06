"""
E2E 测试 + 屏幕录制一体化脚本
=============================
在运行完整测试流程的同时录制屏幕为 MP4 视频
用于 Demo 视频产出（飞书 CUA 挑战赛提交）

用法:
  # 单用例测试 + 录屏（推荐先跑这个验证）
  python run_e2e_with_recording.py --search-term "张三"

  # 全量3用例 + 录屏
  python run_e2e_with_recording.py --run-all

输出:
  - videos/e2e_demo_YYYYMMDD_HHMMSS.mp4  (录屏文件)
  - screenshots/                         (步骤截图)
  - archive/                             (归档报告)
"""

import sys
import os
import time
import json
import argparse
import threading
import queue
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import mss

# ===== 项目路径 =====
PROJECT_DIR = Path(r"D:\feishu-cua-challenge")
sys.path.append(str(PROJECT_DIR))

VIDEO_DIR = PROJECT_DIR / "videos"
VIDEO_DIR.mkdir(exist_ok=True)


# ============================================================
#  录屏器：后台线程截帧 → 主线程结束后合成视频
# ============================================================
class ScreenRecorder:
    """
    使用 mss 在后台线程持续截帧，
    停止后用 cv2.VideoWriter 将帧合成为 MP4。
    """

    def __init__(self, fps=10, output_path=None):
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self.output_path = output_path or str(
            VIDEO_DIR / f"e2e_demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        self.frames = []
        self.running = False
        self.thread = None
        self.sct = mss.mss()
        # 截取主显示器全屏
        self.monitor = self.sct.monitors[1]  # monitor[0]是汇总, [1]是第一块屏
        print(f"📹 录屏初始化: {self.monitor['width']}x{self.monitor['height']} @ {fps}fps")
        print(f"📹 输出路径: {self.output_path}")

    def _capture_loop(self):
        """后台线程：持续截帧存入队列"""
        while self.running:
            try:
                start = time.time()
                frame = np.array(self.sct.grab(self.monitor))
                # mss 返回 BGRA → 转 BGR 给 cv2
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                self.frames.append(frame)
                # 精确控制帧率
                elapsed = time.time() - start
                sleep_time = self.frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            except Exception as e:
                if self.running:
                    print(f"⚠️ 录屏截帧异常: {e}")
                break

    def start(self):
        """开始录屏"""
        self.running = True
        self.frames = []
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print("▶️  录屏已启动...")

    def stop(self):
        """停止录屏并写入MP4文件"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

        frame_count = len(self.frames)
        if frame_count == 0:
            print("⚠️ 没有录制到任何帧")
            return None

        print(f"⏹️  录屏停止，共 {frame_count} 帧，正在编码视频...")

        # 用第一帧确定尺寸
        h, w = self.frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (w, h))

        for frame in self.frames:
            writer.write(frame)

        writer.release()

        file_size_mb = os.path.getsize(self.output_path) / (1024 * 1024)
        duration_sec = frame_count / self.fps
        print(f"✅ 视频已保存: {self.output_path}")
        print(f"   时长: ~{duration_sec:.0f}秒 | 大小: {file_size_mb:.1f}MB | 帧数: {frame_count}")
        return self.output_path


# ============================================================
#  E2E 执行逻辑（复用 run_all.py 的流程）
# ============================================================
def run_single_test(search_term, recorder):
    """执行单个测试用例（含录屏）"""
    from ops.step_01_click_search import click_search_box
    from ops.step_02_input_text import input_search_text
    from ops.step_03_wait_search_results import wait_search_results
    from ops.step_04_click_first_result import click_first_result
    from ops.step_05_verify_and_archive import verify_and_archive

    step_results = []

    print("\n" + "=" * 60)
    print(f"  E2E 测试: 搜索词「{search_term}」")
    print(f"  时间: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    # Step 01: 点击搜索框
    print("\n▶️  Step 01: 点击搜索框")
    result = click_search_box()
    step_results.append({
        "name": "Step01 点击搜索框",
        "success": result["success"],
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot"),
        "screenshots": result.get("screenshots", [])
    })
    print(f"  结果: {'✅ 成功' if result['success'] else '❌ 失败'} - {result.get('message', '')}")
    time.sleep(30)

    # Step 02: 输入搜索词
    print("\n▶️  Step 02: 输入搜索词")
    result = input_search_text(search_term)
    step_results.append({
        "name": "Step02 输入搜索词",
        "success": result["success"],
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot"),
        "screenshots": result.get("screenshots", [])
    })
    print(f"  结果: {'✅ 成功' if result['success'] else '❌ 失败'} - {result.get('message', '')}")
    time.sleep(30)

    # Step 03: 等待结果
    print("\n▶️  Step 03: 等待搜索结果")
    result = wait_search_results(wait_seconds=5, enable_visualizer=True)
    step_results.append({
        "name": "Step03 等待搜索结果",
        "success": result["success"],
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot"),
        "screenshots": result.get("screenshots", [])
    })
    print(f"  结果: {'✅ 成功' if result['success'] else '❌ 失败'} - {result.get('message', '')}")
    time.sleep(30)

    # Step 04: VLM定位+点击
    print("\n▶️  Step 04: VLM定位并点击第一条结果")
    result = click_first_result(enable_visualizer=True, use_opencv_refine=False)
    step_results.append({
        "name": "Step04 点击第一条结果",
        "success": result["success"],
        "message": result.get("message", ""),
        "screenshot": result.get("screenshot"),
        "screenshots": [result.get("screenshot")] if result.get("screenshot") else []
    })
    print(f"  结果: {'✅ 成功' if result['success'] else '❌ 失败'} - {result.get('message', '')}")
    time.sleep(30)

    # Step 05: 验证归档
    print("\n▶️  Step 05: 验证与归档")
    verify_and_archive(step_results)

    # 汇总
    print("\n" + "=" * 60)
    print("  📊 E2E 执行汇总")
    print("=" * 60)
    passed = sum(1 for r in step_results if r["success"])
    total = len(step_results)
    for r in step_results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['name']}: {r.get('message', '')}")
    print(f"\n  总计: {passed}/{total} 步通过")

    return {
        "search_term": search_term,
        "passed": passed,
        "total": total,
        "all_passed": passed == total,
        "steps": step_results
    }


def main():
    parser = argparse.ArgumentParser(description="E2E 测试 + 屏幕录制")
    parser.add_argument("--search-term", type=str, default="张三", help="搜索词 (默认: 张三)")
    parser.add_argument("--run-all", action="store_true", help="运行全部测试用例")
    parser.add_argument("--fps", type=int, default=10, help="录屏帧率 (默认: 10)")
    args = parser.parse_args()

    print("\n" + "#" * 60)
    print("#  飞书 CUA E2E 测试 + Demo 录制")
    print(f"#  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#" * 60)

    # ⚠️ 安全提示
    print("\n⚠️  重要提示:")
    print("  1. 请确保飞书已打开且处于搜索页面")
    print("  2. 录屏期间请不要操作鼠标/键盘")
    print("  3. Agent将完全控制鼠标移动和点击")
    print("\n⏳  5秒后开始，请准备好...")
    time.sleep(5)

    # 初始化录屏器
    recorder = ScreenRecorder(fps=args.fps)

    try:
        # 启动录屏
        recorder.start()
        time.sleep(1)  # 让录屏先跑几帧

        all_results = []

        if args.run_all:
            # 全量模式
            test_cases_path = PROJECT_DIR / "test_cases.json"
            with open(test_cases_path, encoding="utf-8") as f:
                cases = json.load(f)

            for case in cases:
                result = run_single_test(case["search_term"], recorder)
                all_results.append(result)
                if not args.run_all:
                    break
                # 用例间等待90s让TPM配额恢复
                print(f"\n⏳ 用例间等待 90s (TPM配额恢复)...")
                time.sleep(90)
        else:
            # 单用例模式
            result = run_single_test(args.search_term, recorder)
            all_results.append(result)

    except KeyboardInterrupt:
        print("\n\n⛔ 用户中断 (Ctrl+C)")

    finally:
        # 停止录屏并保存
        video_path = recorder.stop()

        # 最终报告
        print("\n" + "#" * 60)
        print("#  E2E 测试完成")
        print("#" * 60)
        if video_path:
            print(f"\n🎬 Demo 视频: {video_path}")
        print(f"📸 截图目录: {PROJECT_DIR / 'screenshots'}")
        print(f"📦 归档目录: {PROJECT_DIR / 'archive'}")
        print(f"⏱️  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if all_results:
            total_passed = sum(1 for r in all_results if r["all_passed"])
            print(f"\n📊 最终结果: {total_passed}/{len(all_results)} 个用例全部通过")


if __name__ == "__main__":
    main()
