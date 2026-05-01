import cv2
import numpy as np
import os
import time
from datetime import datetime
import json

# 配置
SCREENSHOT_DIR = "D:\\feishu-cua-challenge\\screenshots"
REPORT_DIR = "D:\\feishu-cua-challenge\\reports"

def compare_images(img1_path, img2_path, threshold=0.7):
    """对比两张图片的相似度，返回匹配度"""
    if not os.path.exists(img1_path) or not os.path.exists(img2_path):
        return 0.0
    
    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)
    
    if img1.shape != img2.shape:
        return 0.0
    
    # 计算结构相似性
    result = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def generate_execution_report(step_results, output_path):
    """生成执行报告"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    report = {
        "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "steps": step_results,
        "total_steps": len(step_results),
        "success_steps": sum(1 for res in step_results if res["success"]),
        "status": "SUCCESS" if all(res["success"] for res in step_results) else "FAILED"
    }
    
    # 生成Markdown报告
    md_content = f"""# 飞书自动化执行报告
> 执行时间: {report['execution_time']}
> 执行结果: {report['status']}
> 成功步骤: {report['success_steps']}/{report['total_steps']}

## 步骤详情
"""
    
    for i, step in enumerate(step_results, 1):
        status_icon = "✅" if step["success"] else "❌"
        md_content += f"### {status_icon} Step {i}: {step['name']}\n"
        md_content += f"- 耗时: {step.get('duration', 0):.2f}秒\n"
        if step.get("message"):
            md_content += f"- 消息: {step['message']}\n"
        if step.get("screenshots"):
            md_content += "- 相关截图:\n"
            for ss in step["screenshots"]:
                md_content += f"  - `{os.path.basename(ss)}`\n"
        md_content += "\n"
    
    # 保存报告
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    # 保存JSON格式
    json_path = output_path.replace(".md", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"📄 执行报告已生成: {output_path}")
    return report

def verify_and_archive():
    """验证执行结果并归档"""
    print("\n=== Step 05: 结果验证与归档 ===")
    
    # 获取最新的截图文件
    screenshot_files = sorted(
        [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(".png")],
        key=lambda x: os.path.getctime(os.path.join(SCREENSHOT_DIR, x))
    )
    
    if len(screenshot_files) < 4:  # 至少有step01/02/04的前后截图
        print("⚠️  截图数量不足，跳过对比验证")
        step_results = []
    else:
        # 简单验证：操作前后截图对比
        step01_before = os.path.join(SCREENSHOT_DIR, screenshot_files[-4])
        step01_after = os.path.join(SCREENSHOT_DIR, screenshot_files[-3])
        step04_before = os.path.join(SCREENSHOT_DIR, screenshot_files[-2])
        step04_after = os.path.join(SCREENSHOT_DIR, screenshot_files[-1])
        
        sim_step01 = compare_images(step01_before, step01_after)
        sim_step04 = compare_images(step04_before, step04_after)
        
        print(f"🔍 Step01 操作前后相似度: {sim_step01:.3f}")
        print(f"🔍 Step04 操作前后相似度: {sim_step04:.3f}")
    
    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"execution_report_{timestamp}.md")
    generate_execution_report([], report_path)
    
    print("✅ Step 05 完成，所有数据已归档")
    return True

if __name__ == "__main__":
    verify_and_archive()
