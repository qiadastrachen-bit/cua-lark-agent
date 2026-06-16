# Larker — 飞书桌面自动化 Agent（CUA 挑战赛）

> 基于视觉理解的飞书 Windows 客户端搜索自动化框架。  
> 起源：2026 飞书 CUA 挑战赛 M1/M2 阶段。

---

## 项目定位

Larker 在**无 DOM / 无 Accessibility API** 的前提下，通过 **OpenCV + VLM + pyautogui** 完成飞书搜索闭环：

```
点击搜索框 → 输入关键词 → 等待结果 → 点击第一条 → 验证归档
```

当前是**可运行的工程 Demo**，不是已量产的无人值守 Agent。能力边界与实测数据见下文。

---

## 实测数据（可引用）

| 指标 | 数值 | 来源 |
|------|------|------|
| M1 单步稳定性 | **62.5%**（5/8 次） | `reports/M1_test_record.md` |
| M2 流水线 Step01–04 全通过 | **77.4%**（24/31 次） | `reports/vlm_benchmark_20260616_225752.md` |
| 正式测试用例 | 3 条 | `test_cases.json` |
| Demo 演示模式（固定坐标） | 3/3 通过 | 2026-05-06，`USE_FIXED_COORDS=true` |

**重要区分：**

- **VLM 模式**（`USE_FIXED_COORDS=false`）：Step04 调用火山方舟 VLM 定位，OpenCV 兜底。
- **Demo 模式**（`USE_FIXED_COORDS=true`）：Step04 使用固定坐标 `(1280, 350)`，仅适用于特定分辨率/窗口布局，**不计入 VLM 基准成功率**。

重新生成基准报告：

```bash
python tools/run_vlm_benchmark.py --historical   # 仅统计历史 reports/
python tools/run_vlm_benchmark.py                # Live 跑全部用例（需 .env + 飞书已打开）
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 视觉定位 | OpenCV 模板匹配（Step01）、火山方舟 VLM（Step04/05） |
| 桌面操作 | pyautogui、pyperclip |
| 编排 | Python 5 步流水线 + `retry_step` 重试 |
| 测试 | pytest + subprocess |
| 录屏 | mss + cv2（`run_e2e_with_recording.py`） |

---

## 快速开始

```bash
git clone <repo-url>
cd feishu-cua-challenge
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env：填入 VOLC_API_KEY、VOLC_ENDPOINT_ID

# 单条用例（VLM 模式）
python run_all.py --search-term "陈锦彤"

# 全部用例
python run_all.py --run-all

# E2E + 录屏
python run_e2e_with_recording.py --run-all
```

**前置条件：** 飞书 Windows 客户端已打开并处于主界面；运行期间勿操作键鼠。

---

## 项目结构

```
feishu-cua-challenge/
├── run_all.py                 # 主入口：5 步流水线
├── run_e2e_with_recording.py  # E2E + MP4 录屏
├── config.py                  # API、路径、USE_FIXED_COORDS
├── test_cases.json            # 3 条测试用例
├── ops/                       # Step 01–05 实现
├── core/state_checker.py      # VLM 状态分析（已实现，尚未接入主流程）
├── tests/test_e2e.py
├── tools/run_vlm_benchmark.py # 基准测试与报告生成
├── reports/                   # 执行报告 + 基准报告
└── docs/
    ├── REQUIREMENTS.md        # 需求分析
    └── SYSTEM_DESIGN.md       # 系统架构设计
```

---

## 已知限制

1. **Step01 依赖 OpenCV 模板**：UI 变化或缩放会导致匹配失败。
2. **分辨率/DPI**：物理像素与逻辑坐标不一致时，VLM 坐标可能偏移（见 M1 测试记录）。
3. **VLM 限流（429）**：连续运行需 Step 间 30s、用例间 90s 等待。
4. **Overlay 悬浮窗**：已搁置，Chrome `--app` 方案不稳定。
5. **自然语言入口**：尚未实现；当前通过 CLI 参数或 JSON 配置搜索词。

---

## 文档

- [需求分析](docs/REQUIREMENTS.md)
- [系统架构设计](docs/SYSTEM_DESIGN.md)
- [VLM 基准报告](reports/VLM_BENCHMARK.md)
- [M1 测试记录](reports/M1_test_record.md)

---

## License

MIT

## Recently updated

2026.6.3 Chen JinTong
