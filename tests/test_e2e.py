import subprocess
import json
import os
import sys
from datetime import datetime
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试用例数据
with open("test_cases.json", encoding="utf-8") as f:
    TEST_CASES = json.load(f)

# 超时设置：10分钟
TIMEOUT_SECONDS = 600


def run_test_case(search_term, case_id):
    """运行单个测试用例"""
    print(f"\n{'='*60}")
    print(f"运行测试用例: {case_id}")
    print(f"搜索词: {search_term}")
    print(f"{'='*60}\n")

    # 构建命令
    cmd = [
        sys.executable,
        "run_all.py",
        "--search-term",
        search_term
    ]

    # 执行命令并收集输出
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as e:
        print(f"❌ 测试超时 ({TIMEOUT_SECONDS}秒)")
        return {
            "success": False,
            "stdout": e.stdout.decode('utf-8', errors='replace') if e.stdout else "",
            "stderr": e.stderr.decode('utf-8', errors='replace') if e.stderr else "",
            "message": "测试超时"
        }

    # 输出日志
    print("=== 标准输出 ===")
    print(result.stdout)
    print("\n=== 标准错误 ===")
    print(result.stderr)

    # 分析结果
    step_successes = []
    for line in result.stdout.split('\n'):
        if 'Step01' in line or 'Step02' in line or 'Step03' in line or 'Step04' in line or 'Step05' in line:
            if '✅' in line:
                step_successes.append(True)
            elif '❌' in line:
                step_successes.append(False)

    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "step_successes": step_successes
    }


def generate_html_report(results):
    """生成HTML测试报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = "reports"
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    html_path = os.path.join(report_dir, f"e2e_test_report_{timestamp}.html")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>飞书CUA E2E测试报告 - {timestamp}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        h1 {{ color: #333; border-bottom: 3px solid #1890ff; padding-bottom: 10px; }}
        .summary {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .test-case {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .pass {{ border-left: 5px solid #52c41a; }}
        .fail {{ border-left: 5px solid #ff4d4f; }}
        .status {{ font-size: 24px; margin-right: 10px; }}
        .case-title {{ display: flex; align-items: center; margin-bottom: 15px; }}
        .logs {{ background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 4px; max-height: 400px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 12px; }}
        .step-result {{ margin: 5px 0; padding: 5px 10px; border-radius: 3px; }}
        .step-pass {{ background: #f6ffed; color: #52c41a; }}
        .step-fail {{ background: #fff2f0; color: #ff4d4f; }}
    </style>
</head>
<body>
    <h1>📊 飞书CUA E2E测试报告</h1>
    <div class="summary">
        <h2>📋 测试摘要</h2>
        <p><strong>执行时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>总用例数:</strong> {len(results)}</p>
        <p><strong>通过数:</strong> {sum(1 for r in results if r['all_steps_passed'])}</p>
        <p><strong>失败数:</strong> {sum(1 for r in results if not r['all_steps_passed'])}</p>
    </div>
"""

    for idx, result in enumerate(results):
        case = TEST_CASES[idx]
        all_passed = result['all_steps_passed']
        status_class = "pass" if all_passed else "fail"
        status_icon = "✅" if all_passed else "❌"

        steps_html = ""
        if 'step_successes' in result:
            for step_idx, step_passed in enumerate(result['step_successes']):
                step_class = "step-pass" if step_passed else "step-fail"
                step_status = "✅" if step_passed else "❌"
                steps_html += f'<div class="step-result {step_class}">{step_status} Step 0{step_idx + 1}</div>'

        html_content += f"""
    <div class="test-case {status_class}">
        <div class="case-title">
            <span class="status">{status_icon}</span>
            <h3>{case['id']}: {case['name']}</h3>
        </div>
        <p><strong>搜索词:</strong> {case['search_term']}</p>
        <p><strong>前置条件:</strong> {case['precondition']}</p>
        <h4>步骤结果:</h4>
        {steps_html if steps_html else '<p>未解析到步骤结果</p>'}
        <h4>标准输出:</h4>
        <div class="logs">{result['stdout'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</div>
        <h4>标准错误:</h4>
        <div class="logs">{result['stderr'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</div>
    </div>
"""

    html_content += """
</body>
</html>
"""

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ 测试报告已生成: {html_path}")
    return html_path


@pytest.mark.parametrize("case", TEST_CASES, ids=[c['id'] for c in TEST_CASES])
def test_e2e_search(case):
    """E2E搜索测试"""
    result = run_test_case(case['search_term'], case['id'])

    # 断言：所有步骤都应该成功
    all_steps_passed = len(result.get('step_successes', [])) >= case['expected_steps'] and \
                       all(result.get('step_successes', []))

    result['all_steps_passed'] = all_steps_passed
    result['case'] = case

    # 保存结果用于报告
    if not hasattr(test_e2e_search, 'results'):
        test_e2e_search.results = []
    test_e2e_search.results.append(result)

    assert all_steps_passed, f"测试用例 {case['id']} 失败"


def pytest_sessionfinish(session, exitstatus):
    """测试会话结束时生成报告"""
    if hasattr(test_e2e_search, 'results'):
        generate_html_report(test_e2e_search.results)
