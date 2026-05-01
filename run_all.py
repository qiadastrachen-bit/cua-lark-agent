import os
import sys
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入所有步骤
from ops.step_01_click_search import main as step01
from ops.step_02_input_text import main as step02
from ops.step_03_wait_search_results import wait_search_results as step03
from ops.step_04_click_first_result import click_first_result as step04
from ops.step_05_verify_and_archive import verify_and_archive as step05

def main():
    print("=" * 60)
    print("[启动] 飞书自动化完整流程启动")
    print("=" * 60)
    
    start_time = time.time()
    step_results = []
    
    # Step 01: 点击搜索框
    step_start = time.time()
    print("\n" + "="*40)
    print("执行 Step 01: 点击搜索框")
    print("="*40)
    success = step01()
    step_results.append({
        "name": "点击搜索框",
        "success": success,
        "duration": time.time() - step_start,
        "message": "成功激活搜索框" if success else "搜索框点击失败"
    })
    if not success:
        print("[失败] Step 01 失败，终止流程")
        return False
    time.sleep(0.5)
    
    # Step 02: 输入搜索文字
    step_start = time.time()
    print("\n" + "="*40)
    print("执行 Step 02: 输入搜索文字")
    print("="*40)
    success = step02("飞书妙搭")
    step_results.append({
        "name": "输入搜索文字",
        "success": success,
        "duration": time.time() - step_start,
        "message": "成功输入'飞书妙搭'并搜索" if success else "文字输入失败"
    })
    if not success:
        print("[失败] Step 02 失败，终止流程")
        return False
    time.sleep(0.5)
    
    # Step 03: 等待搜索结果
    step_start = time.time()
    print("\n" + "="*40)
    print("执行 Step 03: 等待搜索结果")
    print("="*40)
    success = step03(wait_seconds=5, enable_visualizer=True)
    step_results.append({
        "name": "等待搜索结果",
        "success": success,
        "duration": time.time() - step_start,
        "message": "搜索结果加载完成"
    })
    time.sleep(0.5)
    
    # Step 04: 点击第一个搜索结果
    step_start = time.time()
    print("\n" + "="*40)
    print("执行 Step 04: 点击第一个搜索结果")
    print("="*40)
    success = step04(enable_visualizer=True, use_opencv_refine=True)
    step_results.append({
        "name": "点击第一个搜索结果",
        "success": success,
        "duration": time.time() - step_start,
        "message": "成功打开第一个搜索结果" if success else "点击搜索结果失败"
    })
    if not success:
        print("[失败] Step 04 失败，终止流程")
        return False
    time.sleep(0.5)
    
    # Step 05: 验证与归档
    step_start = time.time()
    print("\n" + "="*40)
    print("执行 Step 05: 结果验证与归档")
    print("="*40)
    success = step05()
    step_results.append({
        "name": "结果验证与归档",
        "success": success,
        "duration": time.time() - step_start,
        "message": "数据归档完成"
    })
    
    # 统计结果
    total_time = time.time() - start_time
    success_count = sum(1 for res in step_results if res["success"])
    total_count = len(step_results)
    
    print("\n" + "="*60)
    print("[完成] 流程执行完成")
    print("="*60)
    print(f"总耗时: {total_time:.2f} 秒")
    print(f"成功步骤: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("[成功] 所有步骤执行成功！")
    else:
        print("[提示] 部分步骤执行失败，请检查日志")
    
    return success_count == total_count

if __name__ == "__main__":
    main()
