# CUA-Lark Agent 🚀

> **飞书 AI 挑战赛 2026 · Track5 CUA-Lark** — 让大模型像人一样操作飞书桌面端

## 📌 项目简介

本项目实现了一个 **Computer Use Agent (CUA)**，通过**视觉语言模型 (VLM) + 图像识别 + 自动化操作**的组合方案，让大模型"看懂"飞书桌面端界面并执行自动化操作。

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    用户自然语言指令                     │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│              VLM 理解层（豆包 2.0 多模态）              │
│   截图 → Base64 编码 → VLM 分析 → 识别 GUI 元素        │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│              定位层（混合方案）                         │
│   VLM 粗定位 + OpenCV 模板匹配精定位 → 像素坐标         │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│              执行层（PyAutoGUI）                       │
│   坐标 → 鼠标移动/点击/键盘输入 → 操作飞书桌面端          │
└──────────────────────────────────────────────────────┘
```

## 🔧 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 视觉语言模型 | 豆包 2.0（Doubao-1.5-vision-pro） | 字节跳动火山引擎 Ark 平台 |
| 屏幕截图 | PyAutoGUI + Pillow | 全屏截取、区域裁剪 |
| 元素定位 | OpenCV 模板匹配（TM_CCOEFF_NORMED）| 高精度像素级定位 |
| 自动化操作 | PyAutoGUI | 鼠标移动/点击、键盘输入 |
| HTTP 请求 | requests | 调用 VLM API |

## 📁 项目结构

```
cua-lark-agent/
├── assets/                      # 模板图片资源
│   └── template_search_box.png  # 搜索框模板（OpenCV 匹配用）
├── ops/                         # 自动化操作脚本（按步骤拆分）
│   ├── step_01_click_search.py # Step 1: 点击 IM 搜索框
│   └── ...                      # 更多步骤（开发中）
├── ziliaoshouji/                # 参考资料
│   └── *.pdf                    # 比赛官方文档 / 飞书 AI 接口文档
├── screenshot_analysis.py       # 截图 → VLM 分析核心模块
├── requirements.txt             # Python 依赖
└── README.md                    # 本文件
```

## ⚡ 快速开始

### 环境准备

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 配置 API Key

编辑代码中的 `API_KEY` 和 `ENDPOINT_ID`：

```python
API_KEY = "your-api-key"
ENDPOINT_ID = "your-endpoint-id"
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
```

### 运行示例

```bash
# 截图分析测试
python screenshot_analysis.py

# Step 1: 点击搜索框（需要先准备好模板图片）
python ops/step_01_click_search.py
```

## 🎯 核心设计：混合定位方案

### 为什么不用纯 VLM 坐标？

VLM（视觉语言模型）能**看懂**界面，但返回的像素坐标**精度很差**（误差可达几十像素）。经过多次实验验证：
- ❌ **全屏截图** → 模型返回 (52, 68)，实际搜索框在 (120, 60)
- ❌ **区域裁剪** → 模型返回 (335, 545)，点到知识问答图标
- ✅ **OpenCV 模板匹配** → 亚像素精度，准确率接近 100%

### 最终方案：VLM 粗理解 + OpenCV 精定位

```
用户指令："在飞书里搜索 xxx"
    ↓
VLM 理解意图 → 识别目标元素类型（搜索框）
    ↓
OpenCV 在预定义区域做模板匹配 → 精确坐标
    ↓
PyAutoGUI 执行点击
```

## 📊 开发进度

| 步骤 | 功能 | 状态 |
|------|------|------|
| Step 0 | 环境搭建 + VLM 接通 | ✅ 完成 |
| Step 0 | 截图分析模块 | ✅ 完成 |
| Step 1 | 点击 IM 搜索框 | 🔄 进行中（VLM坐标不准，正在切 OpenCV）|
| Step 2 | 搜索框输入文字 | ⬜ 待开始 |
| Step 3+ | 完整操作流程 | ⬜ 规划中 |

## 📝 开发日志

详细开发过程见 [工作日志](docs/dev-log.md)

## 📄 许可证

MIT License

## 👥 作者

[qiadastrachen-bit](https://github.com/qiadastrachen-bit)
