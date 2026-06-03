import pyautogui
import base64
import os
import sys
import requests
import time
from datetime import datetime

# 确保能导入项目根目录的 config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_KEY, ENDPOINT_ID, API_URL

def take_screenshot_and_analyze(prompt="请描述这张截图的内容", save_md=True, delay=0):
    # 延迟截图（给用户切换窗口的时间）
    if delay > 0:
        print(f"请在 {delay} 秒内切换到需要分析的窗口...")
        for i in range(delay, 0, -1):
            print(f"倒计时：{i} 秒", end="\r")
            time.sleep(1)
        print("开始截图！" + " " * 20)
    
    # 1. 使用PyAutoGUI截取全屏
    screenshot = pyautogui.screenshot()
    # 保存为临时图片文件
    temp_img_path = "temp_screenshot.png"
    screenshot.save(temp_img_path)
    
    # 2. 将图片转换为base64编码
    with open(temp_img_path, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode("utf-8")
    
    # 删除临时文件
    os.remove(temp_img_path)
    
    # 3. 使用统一配置中的 API 参数（不再硬编码）
    
    # 4. 构造请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 5. 构造请求体
    payload = {
        "model": ENDPOINT_ID,
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
    
    # 6. 发送HTTP请求调用豆包2.0多模态模型
    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()  # 检查请求是否成功
    
    # 7. 解析返回结果
    result = response.json()
    analysis_result = result["choices"][0]["message"]["content"]
    
    # 8. 保存分析结果为Markdown文件
    if save_md:
        # 生成带时间戳的文件名，避免覆盖
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_filename = f"screenshot_analysis_{timestamp}.md"
        
        # 构造Markdown内容
        md_content = f"""# 飞书界面元素识别分析结果
> 分析时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> 分析Prompt：{prompt}

## 识别到的可点击元素
{analysis_result}
"""
        
        # 写入文件
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"\n分析结果已保存到文件：{md_filename}")
    
    return analysis_result

if __name__ == "__main__":
    # 自定义配置：设置delay=3表示延迟3秒截图，给你时间切换到飞书窗口
    delay_seconds = 3
    print(f"将在 {delay_seconds} 秒后截取屏幕并识别飞书界面元素...")
    # 已设置你需要的自定义prompt
    custom_prompt = "请识别截图中的飞书界面元素，列出所有可点击的按钮和菜单"
    result = take_screenshot_and_analyze(prompt=custom_prompt, save_md=True, delay=delay_seconds)
    print("\n识别结果：")
    print(result)
