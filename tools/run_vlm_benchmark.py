"""
VLM 模式基准测试 — 强制 USE_FIXED_COORDS=false，跑 test_cases.json 并生成报告。

用法:
  python tools/run_vlm_benchmark.py              # 跑全部用例（需飞书已打开 + .env 配置）
  python tools/run_vlm_benchmark.py --cases 1      # 只跑第 1 个用例
  python tools/run_vlm_benchmark.py --historical   # 仅分析 reports/ 历史数据，不发起 live 运行
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 必须在 import config 前强制 VLM 模式
os.environ["USE_FIXED_COORDS"] = "false"

REPORT_DIR = PROJECT_ROOT / "reports"
TEST_CASES_PATH = PROJECT_ROOT / "test_cases.json"


def parse_historical_reports() -> dict:
    """从 reports/execution_report_*.md 统计历史成功率。"""
    pattern = re.compile(
        r"> 执行结果: (?P<result>SUCCESS|FAILED)\n"
        r"> 成功步骤: (?P<passed>\d+)/(?P<total>\d+)"
    )
    runs = []
    for path in sorted(REPORT_DIR.glob("execution_report_*.md")):
        text = path.read_text(encoding="utf-8")
        m = pattern.search(text)
        if not m or int(m.group("total")) == 0:
            continue
        runs.append({
            "file": path.name,
            "result": m.group("result"),
            "passed": int(m.group("passed")),
            "total": int(m.group("total")),
            "full_pass": m.group("result") == "SUCCESS" and int(m.group("passed")) == int(m.group("total")),
        })

    total = len(runs)
    full_pass = sum(1 for r in runs if r["full_pass"])
    return {
        "source": "reports/execution_report_*.md",
        "run_count": total,
        "full_pipeline_pass": full_pass,
        "full_pipeline_rate": round(full_pass / total * 100, 1) if total else 0.0,
        "note": "历史报告仅统计 Step01–04（Step05 归档不计入成功步数）",
        "runs": runs,
    }


def run_live_benchmark(case_limit: int | None = None) -> dict:
    """Live 运行：调用 run_all 流程，记录每步结果。"""
    from config import vlm_configured, vlm_config_summary, USE_FIXED_COORDS
    from run_all import run_test_case

    if USE_FIXED_COORDS:
        raise RuntimeError("USE_FIXED_COORDS 应为 false")
    if not vlm_configured(for_vision=True):
        return {
            "skipped": True,
            "reason": "视觉 API 未配置。hybrid 模式需 VOLC_API_KEY + VOLC_ENDPOINT_ID；"
                      "或设 VLM_PROVIDER=volc",
        }

    cases = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))
    if case_limit:
        cases = cases[:case_limit]

    started = datetime.now()
    case_results = []

    for i, case in enumerate(cases):
        print(f"\n{'='*60}\n基准用例 {i+1}/{len(cases)}: {case['id']} — {case['name']}\n{'='*60}")
        t0 = time.time()
        step_results = run_test_case(case["search_term"])
        elapsed = round(time.time() - t0, 1)

        passed = sum(1 for s in step_results if s.get("success"))
        total = len(step_results)
        case_results.append({
            "id": case["id"],
            "name": case["name"],
            "search_term": case["search_term"],
            "passed": passed,
            "total": total,
            "all_passed": passed == total,
            "elapsed_sec": elapsed,
            "mode": "vlm",
            "steps": [
                {"name": s.get("name"), "success": s.get("success"), "message": s.get("message", "")}
                for s in step_results
            ],
        })
        if i < len(cases) - 1:
            print("\n⏳ 用例间等待 90s（TPM 配额恢复）...")
            time.sleep(90)

    full_pass = sum(1 for c in case_results if c["all_passed"])
    return {
        "skipped": False,
        "mode": "vlm",
        "use_fixed_coords": False,
        "started_at": started.isoformat(),
        "finished_at": datetime.now().isoformat(),
        "case_count": len(case_results),
        "full_pass_count": full_pass,
        "pass_rate_pct": round(full_pass / len(case_results) * 100, 1) if case_results else 0.0,
        "cases": case_results,
    }


def write_benchmark_report(historical: dict, live: dict | None) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_md = REPORT_DIR / f"vlm_benchmark_{ts}.md"
    out_json = REPORT_DIR / f"vlm_benchmark_{ts}.json"

    payload = {
        "generated_at": datetime.now().isoformat(),
        "historical_analysis": historical,
        "live_benchmark": live,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# VLM 模式基准测试报告",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 模式: `USE_FIXED_COORDS=false`（完整 VLM + OpenCV 双轨）",
        "",
        "## 1. 历史运行统计（reports/ 归档）",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 有效运行次数 | {historical['run_count']} |",
        f"| Step01–04 全通过次数 | {historical['full_pipeline_pass']} |",
        f"| 全通过率 | **{historical['full_pipeline_rate']}%** |",
        "",
        f"说明: {historical['note']}",
        "",
        "### M1 阶段（单步稳定性，2026-05-02 ~ 05-03）",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        "| 整体成功率 | **62.5%**（5/8 次运行） |",
        "| 主要失败点 | Step04 过渡区偏移、截图全黑、Step01 OpenCV 模板失效 |",
        "",
        "### Demo 模式说明（固定坐标）",
        "",
        "2026-05-06 冲刺夜为通过演示，曾启用 `USE_FIXED_COORDS=true`（坐标 1280,350）",
        "绕过 VLM 限流。**该模式不计入 VLM 基准成功率。**",
        "",
    ]

    if live and live.get("skipped"):
        lines.extend([
            "## 2. 本次 Live 基准测试",
            "",
            f"**未执行**: {live['reason']}",
            "",
            "配置完成后重新运行:",
            "```bash",
            "python tools/run_vlm_benchmark.py",
            "```",
            "",
        ])
    elif live and not live.get("skipped"):
        lines.extend([
            "## 2. 本次 Live 基准测试",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 用例数 | {live['case_count']} |",
            f"| 全通过 | {live['full_pass_count']}/{live['case_count']} |",
            f"| 通过率 | **{live['pass_rate_pct']}%** |",
            f"| 开始 | {live['started_at']} |",
            f"| 结束 | {live['finished_at']} |",
            "",
            "### 用例明细",
            "",
        ])
        for c in live["cases"]:
            status = "✅" if c["all_passed"] else "❌"
            lines.append(f"#### {status} {c['id']}: {c['name']}（{c['elapsed_sec']}s）")
            lines.append("")
            lines.append(f"- 搜索词: `{c['search_term']}`")
            lines.append(f"- 步骤: {c['passed']}/{c['total']} 通过")
            lines.append("")
            for s in c["steps"]:
                st = "✅" if s["success"] else "❌"
                lines.append(f"- {st} {s['name']}: {s['message']}")
            lines.append("")

    lines.extend([
        "## 3. 引用方式",
        "",
        "在文档或答辩中引用本报告时，请区分:",
        "",
        "- **历史全通过率**: 来自 `reports/execution_report_*.md` 自动统计",
        "- **Live VLM 通过率**: 来自本节第 2 部分（需 `.env` + 飞书前置条件）",
        "",
        f"JSON 原始数据: `{out_json.name}`",
        "",
    ])

    out_md.write_text("\n".join(lines), encoding="utf-8")
    # 稳定别名，便于文档引用
    stable_md = REPORT_DIR / "VLM_BENCHMARK.md"
    stable_json = REPORT_DIR / "VLM_BENCHMARK.json"
    stable_md.write_text(out_md.read_text(encoding="utf-8"), encoding="utf-8")
    stable_json.write_text(out_json.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"\n[OK] Benchmark report written:\n   {out_md}\n   {out_json}\n   {stable_md}")
    return out_md


def main():
    parser = argparse.ArgumentParser(description="VLM 模式基准测试")
    parser.add_argument("--historical", action="store_true", help="仅分析历史 reports，不 live 运行")
    parser.add_argument("--cases", type=int, default=None, help="live 运行时只用前 N 个用例")
    args = parser.parse_args()

    historical = parse_historical_reports()
    print(f"历史统计: {historical['full_pipeline_pass']}/{historical['run_count']} 全通过 ({historical['full_pipeline_rate']}%)")

    live = None
    if not args.historical:
        print("\n开始 Live VLM 基准测试（请确保飞书已打开且在主界面）...")
        print("10 秒后开始，请勿操作键鼠...")
        time.sleep(10)
        live = run_live_benchmark(case_limit=args.cases)

    write_benchmark_report(historical, live)


if __name__ == "__main__":
    main()
