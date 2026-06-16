# Larker 系统架构设计

> 版本：v2.0  
> 更新日期：2026-06-16  
> 状态：反映 M2 真实实现（非规划愿景）

---

## 1. 概述

Larker 是一个**固定流程的桌面自动化流水线**，针对飞书 Windows 客户端的「全局搜索 → 进入第一条结果」场景。系统通过分层模块完成感知、定位、执行、验证与报告，核心定位策略为 **OpenCV（确定性）+ VLM（语义理解）** 混合方案。

**不在本架构内：** LLM 动态规划、多应用适配、Overlay 产品 UI（均为未来扩展点）。

---

## 2. 系统上下文

```
┌──────────────┐     CLI / JSON      ┌─────────────────────┐
│   操作者      │ ─────────────────→ │      Larker         │
│  (开发者)     │                    │  run_all.py         │
└──────────────┘                    └──────────┬──────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
           ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
           │ 飞书客户端    │          │ 火山方舟 VLM  │          │  本地文件系统  │
           │ (pyautogui)  │          │  (HTTPS API)  │          │ reports/等   │
           └──────────────┘          └──────────────┘          └──────────────┘
```

---

## 3. 逻辑架构（五层）

```
┌────────────────────────────────────────────────────────────┐
│  Layer 5 报告层   verify_and_archive → reports/ + archive/ │
├────────────────────────────────────────────────────────────┤
│  Layer 4 验证层   截图 diff、VLM 详情确认、失败现场保存      │
├────────────────────────────────────────────────────────────┤
│  Layer 3 执行层   pyautogui 移动/点击/双击、pyperclip 粘贴   │
├────────────────────────────────────────────────────────────┤
│  Layer 2 定位层   Step01 OpenCV | Step04 VLM + OpenCV 兜底 │
├────────────────────────────────────────────────────────────┤
│  Layer 1 感知层   pyautogui.screenshot、Pillow 压缩、Base64  │
└────────────────────────────────────────────────────────────┘
         ▲
         │ 编排：run_all.py + retry_step()
         │ 配置：config.py + .env
```

### 3.1 规划层说明

当前**无独立 LLM 规划模块**。流程为预定义 5 步序列；`test_cases.json` 仅提供搜索词，不做意图解析。

`core/state_checker.py` 设计了 VLM 状态枚举（`search_results`、`chat_window` 等），**尚未被 `run_all.py` 引用**，属于预留模块。

---

## 4. 核心流程

### 4.1 主序列图

```
run_all.py
    │
    ├─► retry_step(click_search_box)      [Step01 OpenCV]
    │       sleep(30)
    ├─► retry_step(input_search_text)     [Step02 剪贴板]
    │       sleep(30)
    ├─► retry_step(wait_search_results)   [Step03 定时等待]
    │       sleep(30)
    ├─► retry_step(click_first_result)    [Step04 VLM / 固定坐标]
    │       sleep(30)
    └─► verify_and_archive(step_results)  [Step05 验证归档]
```

### 4.2 Step04 定位决策树

```
click_first_result()
    │
    ├─ USE_FIXED_COORDS == true ──► 固定 (1280, 350)  [Demo 模式]
    │
    └─ USE_FIXED_COORDS == false
            │
            ├─► call_vlm(SIMPLE_LOCATE_PROMPT) → parse coordinates
            │       ├─ validate_coordinates / adjust_if_transition_zone (+35px)
            │       └─ optional opencv_refine
            │
            └─ VLM 失败 ──► opencv_match_template 兜底
```

---

## 5. 模块设计

| 模块 | 文件 | 职责 |
|------|------|------|
| 入口 | `run_all.py` | 用例调度、重试、Step 间延迟 |
| 配置 | `config.py` | API、路径、`USE_FIXED_COORDS` |
| Step01 | `ops/step_01_click_search.py` | OpenCV 模板匹配搜索框 |
| Step02 | `ops/step_02_input_text.py` | 激活窗口 + 粘贴搜索词 |
| Step03 | `ops/step_03_wait_search_results.py` | 倒计时 + 可选鼠标可视化 |
| Step04 | `ops/step_04_click_first_result.py` | VLM 定位、坐标修正、双击 |
| Step05 | `ops/step_05_verify_and_archive.py` | 截图对比、VLM 确认、报告 |
| 状态（预留） | `core/state_checker.py` | VLM 界面状态 JSON |
| 基准测试 | `tools/run_vlm_benchmark.py` | 历史统计 + Live 基准 |
| E2E | `tests/test_e2e.py` | pytest 子进程驱动 |

### 5.1 统一 Step 返回协议

```python
{
    "success": bool,
    "message": str,
    "screenshot": str | None,
    "screenshots": list[str]   # Step05 归档用
}
```

### 5.2 retry_step 包装器

- 默认 `max_retries=2` → 最多 3 次执行
- 重试间隔：5s、10s
- 单步超时参数 `step_timeout=600`（实际依赖 VLM 内部 timeout）

---

## 6. 外部依赖

### 6.1 火山方舟 VLM

| 配置项 | 环境变量 |
|--------|----------|
| API Key | `VOLC_API_KEY` |
| Endpoint | `VOLC_ENDPOINT_ID` |
| URL | `VOLC_API_URL`（默认北京节点） |

调用特点：

- 请求前图片压缩至 1280×800
- `MAX_VLM_RETRIES=1`（Step04 内，遇 429 长等待后放弃）
- 429 等待：`90 + attempt * 45` 秒

### 6.2 桌面自动化

- `pyautogui`：截图、移动、双击
- `pygetwindow`：窗口激活
- `pyperclip`：中文输入

---

## 7. 数据流与存储

```
screenshots/          每步 before/after PNG
archive/YYYY-MM-DD/   run_*.json + run_*.md
reports/              execution_report_* + vlm_benchmark_*
videos/               run_e2e_with_recording 产出 MP4
assets/               OpenCV 模板图
```

报告中的「成功步骤」目前统计 **Step01–04**（4 步），Step05 归档不计入该计数——与 README 中 5 步描述需在阅读报告时注意区分。

---

## 8. 双模式运行

| 模式 | 环境变量 | Step04 行为 | 适用场景 |
|------|----------|-------------|----------|
| VLM | `USE_FIXED_COORDS=false` | API 定位 + OpenCV 兜底 | 基准测试、真实能力评估 |
| Demo | `USE_FIXED_COORDS=true` | 固定坐标 (1280, 350) | 答辩演示、无限流风险 |

Demo 模式在 2026-05-06 用于 3 用例录屏通过，**不应与 VLM 基准混报**。

---

## 9. 容错设计

| 机制 | 位置 | 说明 |
|------|------|------|
| 步骤重试 | `run_all.retry_step` | 整步重跑 |
| VLM 退避 | `step_04.call_vlm` | 超时/429 指数或分级等待 |
| 过渡区修正 | `step_04.validate_coordinates` | y 在 10%–18% 屏高时 +35px |
| 截图有效性 | step04 | 全黑截图重试 |
| Step 间延迟 | `run_all` | 各 30s，防 TPM |
| 用例间延迟 | `--run-all` | 90s |
| 失败现场 | step05 | 截图 + 鼠标位置 + JSON |

---

## 10. 已知架构债务

1. **Step01 单点依赖 OpenCV**：UI 变更即失效，无 VLM 兜底
2. **坐标系未统一**：物理像素 vs 逻辑分辨率未做 scale 映射
3. **state_checker 孤立**：未参与流程分支或失败恢复
4. **Overlay 半成品**：`utils/overlay_*.py` 未集成入主链路
5. **硬编码路径**：`run_e2e_with_recording.py` 内 `PROJECT_DIR` 仍为绝对路径
6. **报告步数不一致**：对外称 5 步，报告统计 4 步

---

## 11. 扩展方向（架构演进）

```
当前                          目标
─────────────────────────────────────────────
固定 5 步流水线        →    LLM 动态 Step 生成
单应用（飞书）          →    AppAdapter 接口
CLI 传参               →    NLU 任务解析层
state_checker 孤立     →    每步前后状态门禁
Overlay 搁置           →    系统级透明窗口 + 暂停
```

建议下一版优先：**坐标 scale 统一 + Step01 VLM 兜底 + 接入 state_checker**。

---

## 12. 技术选型理由

| 选型 | 理由 |
|------|------|
| 豆包 VLM（火山方舟） | 国内低延迟、中文 UI 友好、赛题生态 |
| OpenCV 模板匹配 | Step01 固定控件，快、无 API 成本 |
| pyautogui | 桌面通用、赛题允许 |
| 固定流水线 vs Agent | M2 时间约束下可调试、可度量 |

---

*本文档取代原 M2_TECHNICAL_REPORT.md、SUBMISSION 系列中的架构描述。*
