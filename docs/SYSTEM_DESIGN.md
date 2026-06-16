# Larker 系统架构设计

> 版本：v2.1  
> 更新日期：2026-06-17  
> 状态：反映 M2 真实实现（含 hybrid 视觉 + Step06 发消息）

---

## 1. 概述

Larker 是一个**固定流程的桌面自动化流水线**，针对飞书 Windows 客户端的「全局搜索 → 进入第一条结果 →（可选）发送消息」场景。系统通过分层模块完成感知、定位、执行、验证与报告，核心定位策略为 **OpenCV（像素模板）+ VLM（语义视觉）** 混合方案。

**不在本架构内：** LLM 动态规划、多应用适配、Overlay 产品 UI、语音识别 ASR（均为未来扩展点）。

**一句话：** `run_all.py` 编排固定步骤；**OpenCV / 百炼 VLM 负责看屏找位置**；**DeepSeek 仅处理纯文本**（自然语言指令解析）；**pyautogui 负责点击和输入**。

---

## 2. 系统上下文

```
┌──────────────┐     CLI / JSON      ┌─────────────────────┐
│   操作者      │ ─────────────────→ │      Larker         │
│  (开发者)     │                    │  run_all.py         │
└──────────────┘                    └──────────┬──────────┘
                                               │
         ┌─────────────────────────────────────┼─────────────────────────────┐
         │                                     │                             │
         ▼                                     ▼                             ▼
┌──────────────┐                    ┌──────────────────┐          ┌──────────────┐
│ 飞书客户端    │                    │  hybrid AI API    │          │  本地文件系统  │
│ (pyautogui)  │                    │  DeepSeek  文本   │          │ reports/等   │
└──────────────┘                    │  百炼 VLM  视觉   │          └──────────────┘
                                    └──────────────────┘
         ┌──────────────┐
         │ OpenCV 本地   │  （无网络，模板像素匹配）
         └──────────────┘
```

---

## 3. 混合 AI 架构：DeepSeek / 百炼 VLM / OpenCV 分工

### 3.1 三个组件分别是什么

| 组件 | 类型 | 配置 | 干什么 | 精度特点 |
|------|------|------|--------|----------|
| **OpenCV** | 本地算法 | `assets/*.png` 模板 | 在全屏截图里做**像素级**模板匹配 | 快、准、无 API 成本；UI 一变就失效 |
| **百炼 VLM**（qwen3-vl 等） | 云端视觉理解 | `.env` 中 `VISION_*` | 接收**截图 + Prompt**，返回坐标/状态/验证结论 | 语义理解强；坐标是**估计值**，有随机偏差 |
| **DeepSeek** | 云端纯文本 | `.env` 中 `DEEPSEEK_*` | 只处理**字符串**（如 `--instruction` 解析） | **不能**传 `image_url`，**不参与看屏幕** |

> **说明：** 本项目**没有语音识别**。若未来加语音，链路应为：麦克风 → ASR → 文本 → `core/task_parser.py`，与 VLM/OpenCV 无关。

### 3.2 VLM（视觉语言模型）如何工作

VLM 不是「先 OCR 再查表」，而是一次 API 调用：

```
Python Prompt（文字任务描述）
        +
pyautogui 截图 → PNG → 压缩(1280×800) → base64
        ↓
百炼 qwen3-vl /chat/completions
        ↓
返回自然语言（如 "x=640,y=175" 或 JSON {"state":"chat_window"}）
        ↓
Python 正则/JSON 解析 → utils/coords.py 坐标换算 → pyautogui.click()
```

VLM **既做语义**（识别「这是聊天窗口 / 联系人条目」），**也被 Prompt 约束做定位**（「返回第一条结果中心坐标」）。坐标不像 OpenCV 那样逐像素计算，而是模型根据视觉理解**估计**的。

### 3.3 API 路由（`utils/vlm_client.py`）

`config.py` 中 `VLM_PROVIDER=hybrid` 时：

| 函数 | 路由 | 典型调用方 |
|------|------|------------|
| `call_chat()` | `get_text_profile()` → **DeepSeek** | `core/task_parser.py` |
| `call_vlm()` | `get_vision_profile()` → **百炼** | Step01 兜底、Step04、Step06 |
| `call_vlm_json()` | `get_vision_profile()` → **百炼** | `core/state_checker.py` |
| `call_vlm_multi_image()` | `get_vision_profile()` → **百炼** | Step04 点击前后验证 |

OpenCV **不经过** `vlm_client`，在 `ops/step_*.py` 内直接 `cv2.matchTemplate()`。

### 3.4 坐标从截图到鼠标（排错重点）

```
1. pyautogui.screenshot()     → 全屏 PNG（如 2560×1600）
2. encode_image() 压缩        → 发给百炼的是缩略图（max 1280×800）
3. VLM 返回 x,y               → 基于「缩略图」坐标系
4. vlm_coords_to_screen()     → 缩略图 → 全屏截图像素 → pyautogui 逻辑屏幕
5. pyautogui.click(x, y)      → 实际点击
```

调试时可查看 `screenshots/step04_before_*_marked.png`（红十字标记最终点击位置）。

---

## 4. 逻辑架构（五层）

```
┌────────────────────────────────────────────────────────────┐
│  Layer 5 报告层   verify_and_archive → reports/ + archive/ │
├────────────────────────────────────────────────────────────┤
│  Layer 4 验证层   截图 diff、VLM 详情确认、state_checker    │
├────────────────────────────────────────────────────────────┤
│  Layer 3 执行层   pyautogui 移动/点击/双击、pyperclip 粘贴   │
├────────────────────────────────────────────────────────────┤
│  Layer 2 定位层   OpenCV 模板 | 百炼 VLM 坐标 | 启发式兜底  │
├────────────────────────────────────────────────────────────┤
│  Layer 1 感知层   pyautogui.screenshot、Pillow 压缩、Base64  │
└────────────────────────────────────────────────────────────┘
         ▲
         │ 编排：run_all.py + retry_step()
         │ 配置：config.py + .env
         │ 路由：utils/vlm_client.py + utils/coords.py
```

### 4.1 规划 / 解析层

| 模块 | 作用 |
|------|------|
| `core/task_parser.py` | `--instruction` → `{flow, search_term, message_text?}`；regex 优先，DeepSeek 兜底 |
| `core/state_checker.py` | 步骤间 VLM 状态门禁（`ENABLE_STATE_CHECK` 可关） |

当前**无 LLM 动态 Step 规划**；流程为预定义序列 + `test_cases.json` 用例。

---

## 5. 核心流程

### 5.1 主序列（含可选 Step06）

```
run_all.py
    │
    ├─► [可选] parse_instruction()        DeepSeek / regex
    │
    ├─► retry_step(click_search_box)      Step01 OpenCV → VLM 兜底
    │       state_checker + sleep(STEP_DELAY_SEC)
    ├─► retry_step(input_search_text)     Step02 剪贴板（无 AI）
    │       sleep
    ├─► retry_step(wait_search_results)   Step03 定时等待
    │       state_checker + sleep
    ├─► retry_step(click_first_result)    Step04 百炼 VLM → OpenCV 兜底
    │       state_checker + sleep
    ├─► [可选] retry_step(send_chat_message)  Step06 百炼 VLM 定位输入框
    │       state_checker + sleep
    └─► verify_and_archive()              Step05 验证归档
```

### 5.2 每步 AI 参与对照

| 步骤 | OpenCV | 百炼 VLM | DeepSeek | pyautogui |
|------|--------|----------|----------|-----------|
| 解析 `--instruction` | — | — | 可选（regex 优先） | — |
| Step01 点搜索框 | **主力** | OpenCV 失败时兜底 | — | 点击 |
| Step02 输入搜索词 | — | — | — | 粘贴 |
| Step03 等结果 | — | state_checker | — | 等待 |
| Step04 点第一条 | 兜底 | **主力**（定位 + 验证） | — | 双击 |
| Step06 发消息 | — | 定位输入框 + 验证 | — | 粘贴 + Enter |
| Step05 归档 | — | 可选 | — | — |

### 5.3 Step04 定位决策树

```
click_first_result()
    │
    ├─ USE_FIXED_COORDS == true ──► 固定 (1280, 350)  [Demo 模式]
    │
    └─ USE_FIXED_COORDS == false
            │
            ├─► call_vlm(SIMPLE_LOCATE_PROMPT) → parse → vlm_coords_to_screen()
            │       ├─ validate_coordinates（过渡区 y +35px，仅一次）
            │       └─ 保存 step04_before_*_marked.png
            │
            ├─► pyautogui.doubleClick
            │
            ├─► call_vlm_multi_image 验证 SUCCESS/FAIL
            │       └─ FAIL → Step04 标记失败
            │
            └─ VLM 定位失败 ──► opencv_match_template 兜底
```

---

## 6. 排错决策树

按现象先判断**是哪一层、哪种 AI**，再查对应日志/截图。

```
出现问题
    │
    ├─ 启动 / API 报错
    │     ├─ image_url 400 ──→ DeepSeek 被误用于识图 → 改 VLM_PROVIDER=hybrid + VISION_*
    │     ├─ 401/403 ──→ 检查 .env 中 DEEPSEEK_* / VISION_* Key
    │     └─ 429 ──→ 等 STEP_DELAY_SEC / CASE_DELAY_SEC，或减少 VLM 调用
    │
    ├─ --instruction 解析错
    │     └─ task_parser（DeepSeek / regex）→ 终端 Parsed instruction 一行
    │
    ├─ Step01 搜索框点不到
    │     ├─ OpenCV 置信度低 ──→ 更新 assets/template_search_box.png
    │     └─ OpenCV 失败且 VLM 兜底失败 ──→ 查 step01 截图 + 百炼连通性
    │
    ├─ Step04 点偏 / 点错行 / 进了错误页面
    │     ├─ 看 step04_before_*_marked.png 红十字位置
    │     ├─ 看终端 VLM 返回坐标 (scaled)
    │     ├─ 坐标系统性偏移 ──→ utils/coords.py 换算（缩略图→全屏→逻辑屏）
    │     ├─ 每次随机偏一点 ──→ VLM 固有方差；Prompt 已强调联系人名
    │     └─ VLM 验证 FAIL 但以前仍成功 ──→ 现已改为验证失败则 Step04 失败
    │
    ├─ Step04 后不是聊天窗口（发消息场景）
    │     ├─ state_checker 状态非 chat_window
    │     └─ 第一条结果歧义（文档 vs 联系人）→ 搜索词/结果排序；跑前 Esc 回主界面
    │
    ├─ Step06 发不出消息
    │     └─ step06_before/typed/after 截图 + 输入框 VLM 定位
    │
    └─ 整体太慢
          └─ 设计使然：STEP_DELAY_SEC=30 + 每步多次 VLM；调 .env 可缩短（稳定性下降）
```

### 6.1 快速对照表

| 现象 | 最可能环节 | 优先检查 |
|------|------------|----------|
| API 400 `image_url` | Provider 配错 | `.env` hybrid + `VISION_*` |
| 搜索框点不到 | OpenCV | `assets/template_search_box.png`、匹配置信度 |
| 第一条结果偏一点 | 百炼 VLM + coords | `_marked.png`、坐标日志 |
| 点到了但 Step04 FAIL | VLM 验证 | 前后截图、verify 输出 |
| 指令理解错 | DeepSeek / regex | `Parsed instruction` |
| 聊天窗对但发不出 | Step06 | `step06_*.png` |

---

## 7. 模块设计

| 模块 | 文件 | 职责 |
|------|------|------|
| 入口 | `run_all.py` | 用例调度、重试、Step 间延迟、可选 Step06 |
| 配置 | `config.py` | hybrid 双 Profile、`USE_FIXED_COORDS` |
| API 客户端 | `utils/vlm_client.py` | DeepSeek 文本 / 百炼视觉 统一路由 |
| 坐标 | `utils/coords.py` | 缩略图→全屏→逻辑屏换算 |
| 任务解析 | `core/task_parser.py` | NL → search_term / message_text |
| 状态门禁 | `core/state_checker.py` | 步骤间 VLM 状态 JSON |
| Step01 | `ops/step_01_click_search.py` | OpenCV 优先，VLM 兜底 |
| Step02 | `ops/step_02_input_text.py` | 激活窗口 + 粘贴搜索词 |
| Step03 | `ops/step_03_wait_search_results.py` | 倒计时 + 可选鼠标可视化 |
| Step04 | `ops/step_04_click_first_result.py` | VLM 定位、坐标修正、双击、验证 |
| Step05 | `ops/step_05_verify_and_archive.py` | 截图对比、VLM 确认、报告 |
| Step06 | `ops/step_06_send_message.py` | VLM 定位输入框、发送、验证 |
| 基准测试 | `tools/run_vlm_benchmark.py` | 历史统计 + Live 基准 |
| 连通性 | `tools/test_vlm_connection.py` | 分别测 DeepSeek 文本 + 百炼视觉 |
| E2E | `tests/test_e2e.py` | pytest 子进程驱动 |

### 7.1 统一 Step 返回协议

```python
{
    "success": bool,
    "message": str,
    "screenshot": str | None,
    "screenshots": list[str]
}
```

---

## 8. 外部依赖

### 8.1 hybrid 模式（推荐）

| 角色 | 环境变量 | 模型示例 |
|------|----------|----------|
| 文本 | `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` | `deepseek-v4-flash` |
| 视觉 | `VISION_API_KEY`, `VISION_MODEL`, `VISION_API_URL` | `qwen3.6-flash` @ 百炼 compatible-mode |

`VLM_PROVIDER=hybrid` 时：`call_chat` → DeepSeek；`call_vlm*` → 百炼。

DeepSeek V4 **不支持** `image_url`；识图任务必须走 `VISION_*`。

### 8.2 调用特点

- 视觉请求前图片压缩至 max 1280×800（`encode_image`）
- VLM 坐标按缩略图尺寸换算（`vlm_coords_to_screen`）
- 429 退避：`90 + attempt * 45` 秒
- Step 间 / 用例间延迟：`STEP_DELAY_SEC` / `CASE_DELAY_SEC`（默认 30s / 90s）

### 8.3 桌面自动化

- `pyautogui`：截图、移动、双击
- `pygetwindow`：窗口激活
- `pyperclip`：中文输入

---

## 9. 数据流与存储

```
screenshots/          每步 before/after PNG；step04 *_marked.png 调试标记
archive/YYYY-MM-DD/   run_*.json + run_*.md
reports/              execution_report_* + vlm_benchmark_*
videos/               run_e2e_with_recording 产出 MP4
assets/               OpenCV 模板图
.env                  DEEPSEEK_* + VISION_*（勿提交仓库）
```

---

## 10. 双模式运行

| 模式 | 环境变量 | Step04 行为 | 适用场景 |
|------|----------|-------------|----------|
| VLM | `USE_FIXED_COORDS=false` | 百炼定位 + OpenCV 兜底 | 基准测试、真实能力评估 |
| Demo | `USE_FIXED_COORDS=true` | 固定坐标 (1280, 350) | 答辩演示、无限流风险 |

Demo 模式在 2026-05-06 用于 3 用例录屏通过，**不应与 VLM 基准混报**。

---

## 11. 容错设计

| 机制 | 位置 | 说明 |
|------|------|------|
| 步骤重试 | `run_all.retry_step` | 整步重跑，默认最多 3 次 |
| VLM 退避 | `utils/vlm_client._post_chat` | 超时/429 分级等待 |
| 过渡区修正 | `step_04.validate_coordinates` | y 在 10%–18% 屏高时 +35px（仅一次） |
| 坐标换算 | `utils/coords.py` | 缩略图 → 全屏 → 逻辑屏 |
| Step04 验证门禁 | `step_04` | VLM 验证 FAIL 则步骤失败 |
| 状态门禁 | `core/state_checker` | 步骤后可选严格校验 |
| Step / 用例延迟 | `config.py` | 防 TPM 限流 |
| 失败现场 | step05 | 截图 + JSON 归档 |

---

## 12. 已知架构债务

1. **Step04 VLM 坐标仍有随机方差**：依赖 Prompt + 验证，未做多次采样投票
2. **OpenCV 模板与 UI 版本绑定**：模板过期需人工重截
3. **Overlay 半成品**：`utils/overlay_*.py` 未集成入主链路
4. **报告步数口径**：终端可显示 5/6 步，部分 JSON 仍按 4 步统计 overall
5. **`use_opencv_refine` 参数**：Step04 函数签名保留，逻辑尚未实现

---

## 13. 扩展方向

```
当前                          目标
─────────────────────────────────────────────
固定 6 步流水线        →    LLM 动态 Step 生成
hybrid 双 API           →    单 Provider 或多 Provider 负载均衡
CLI / --instruction     →    语音 ASR → task_parser
百炼 VLM 单点定位        →    坐标多次采样 + 中位数
Overlay 搁置            →    系统级透明窗口 + 暂停
```

---

## 14. 技术选型理由

| 选型 | 理由 |
|------|------|
| hybrid（DeepSeek 文本 + 百炼视觉） | DeepSeek 无识图；百炼 qwen-vl 中文 UI 稳定 |
| OpenCV 模板匹配 | Step01 固定控件，快、无 API 成本 |
| pyautogui | 桌面通用、赛题允许 |
| 固定流水线 vs Agent | 可调试、可度量、排错路径清晰 |

---

*本文档取代原 M2_TECHNICAL_REPORT.md、SUBMISSION 系列中的架构描述。*
