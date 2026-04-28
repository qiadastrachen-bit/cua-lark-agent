import pyautogui
import base64
import os
import requests
import json
import re
import time
import io
from datetime import datetime
from PIL import Image

# 全局配置
API_KEY = "ark-f11e281e-ef25-4cb0-a1ee-c7d14e8d76d4-7419d"
ENDPOINT_ID = "ep-20260423222711-8zfcd"
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
SAVE_DIR = "D:\\feishu-cua-challenge\\ops"

# 设置操作间隔防止太快
pyautogui.PAUSE = 1

def activate_feishu_window():
    """激活飞书窗口到前台，支持匹配"飞书"或"Lark"标题"""
    # 尝试匹配飞书窗口
    windows = pyautogui.getWindowsWithTitle("飞书")
    if not windows:
        windows = pyautogui.getWindowsWithTitle("Lark")
    
    if not windows:
        raise Exception("未找到飞书/Lark窗口，请先打开飞书")
    
    feishu_window = windows[0]
    if feishu_window.isMinimized:
        feishu_window.restore()
    feishu_window.activate()
    time.sleep(2)  # 等待窗口激活完成
    return feishu_window

def save_screenshot(prefix):
    """保存截图到ops目录，带时间戳"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    save_path = os.path.join(SAVE_DIR, filename)
    screenshot = pyautogui.screenshot()
    screenshot.save(save_path)
    return save_path, filename

def analyze_search_box_position(img_base64):
    """调用豆包API分析搜索框坐标，返回JSON格式结果"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    prompt = """这是飞书桌面端 IM 界面左上角的截图。

请找到"搜索"输入框，它的视觉特征是：
- 灰色背景的长条形状
- 左侧有放大镜图标
- 中间有文字"搜索 (Ctrl + K)"
- 位于界面最顶部，头像下方

注意：不要把右下角的"知识问答"彩色图标当成搜索框。搜索框是横向的长条输入框。

返回这个搜索框的中心坐标（相对于这张裁剪图片的坐标），格式为 JSON：{"x": 数字, "y": 数字}
只返回 JSON，不要其他内容。"""
    
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
    
    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def parse_coordinates(response_text):
    """解析模型返回的坐标，容错处理非标准JSON"""
    # 先尝试直接解析
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        # 尝试提取JSON部分
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        # 尝试提取数字
        num_match = re.findall(r'\d+', response_text)
        if len(num_match) >= 2:
            return {"x": int(num_match[0]), "y": int(num_match[1])}
    raise Exception(f"无法解析坐标信息，模型返回内容：{response_text}")



def main():
    try:
        print("步骤1：激活飞书窗口...")
        activate_feishu_window()
        print("飞书窗口已激活")
        
        print("\n步骤2：截取操作前截图...")
        before_screenshot, before_filename = save_screenshot("before_click")
        print(f"操作前截图已保存：{before_filename}")
        
        # 裁剪左上角区域(0,0)到(400,600)提高识别精度
        full_img = Image.open(before_screenshot)
        crop_area = (0, 0, 400, 600)  # 左, 上, 右, 下
        cropped_img = full_img.crop(crop_area)
        # 保存裁剪后的截图用于调试
        cropped_filename = before_filename.replace("before_click", "cropped")
        cropped_path = os.path.join(SAVE_DIR, cropped_filename)
        cropped_img.save(cropped_path)
        print(f"裁剪后的区域截图已保存：{cropped_filename}")
        
        # 将裁剪后的图片转换为base64
        buffer = io.BytesIO()
        cropped_img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        print("\n步骤3：调用AI分析搜索框坐标...")
        ai_response = analyze_search_box_position(img_base64)
        print(f"模型返回结果：{ai_response}")
        
        print("\n步骤4：解析坐标信息...")
        coordinates = parse_coordinates(ai_response)
        # 加上裁剪偏移量换算回全屏坐标（裁剪起始位置为左上角(0,0)）
        offset_x = 0
        offset_y = 0
        x = coordinates["x"] + offset_x
        y = coordinates["y"] + offset_y
        print(f"裁剪图坐标：x={coordinates['x']}, y={coordinates['y']}")
        print(f"换算后全屏坐标：x={x}, y={y}")
        
        print("\n步骤5：点击搜索框...")
        print(f"即将点击坐标: ({x}, {y})")
        # 慢速移动鼠标到目标位置，1秒完成移动
        pyautogui.moveTo(x, y, duration=1)
        # 移动完成后等待2秒
        time.sleep(2)
        # 执行点击
        pyautogui.click(x, y)
        # 点击后等待2秒再截图
        time.sleep(2)
        
        print("\n步骤6：截取操作后截图...")
        after_screenshot, after_filename = save_screenshot("after_click")
        print(f"操作后截图已保存：{after_filename}")
        
        print("\n步骤7：点击完成，请手动确认搜索框是否被激活")
        
        return True
        
    except Exception as e:
        print(f"[操作失败] {str(e)}")
        return False

if __name__ == "__main__":
    main()
