# Larker — 飞书桌面自动化 Agent

> 2026 飞书 CUA 挑战赛 M1/M2 工程实现。  
> 在**无 DOM、无 Accessibility API** 的飞书 Windows 客户端上，用**截图 + 视觉理解 + 键鼠模拟**完成搜索与消息发送。

---

## 这是什么

Larker 是一条**固定步骤的桌面自动化流水线**（不是自主规划 Agent）：

```
点击搜索框 → 输入关键词 → 等待结果 → 点击第一条 →（可选）发送消息 → 验证归档
```

**典型场景：** 搜索联系人「陈锦彤」→ 打开会话 → 发送 `hello`。

**交互方式：** 命令行 + `.env` 配置；每次运行生成 `reports/`、`archive/` 执行报告。

---

## 为什么需要它

| 痛点 | Larker 的做法 |
|------|----------------|
| 飞书桌面端无法走 Selenium / 控件树 | 全屏截图 + 视觉定位 |
| 固定坐标随分辨率失效 | OpenCV 模板 + VLM 语义定位混合 |
| 失败难复盘 | 分步截图、JSON/MD 报告、基准统计 |

---

## 怎么工作的

系统把「看屏幕」和「理解指令」拆开，各用合适的 API：

| 组件 | 作用 | 用在哪 |
|------|------|--------|
| **OpenCV** | 像素模板匹配，快且准 | Step01 搜索框（主）；Step04 兜底 |
| **百炼 VLM**（qwen3-vl） | 看截图，返回坐标 / 状态 / 验证 | Step04 点结果、Step06 发消息、状态门禁 |
| **DeepSeek** | 纯文本，**不看截图** | `--instruction` 自然语言解析（可选） |
| **pyautogui** | 截图、点击、键盘 | 所有执行动作 |

推荐配置 **`VLM_PROVIDER=hybrid`**：DeepSeek 负责文本，百炼负责视觉。  
DeepSeek 官方 API 不支持 `image_url`，不能单独承担识图任务。

更细的调用链与排错路径见 [系统架构设计](docs/SYSTEM_DESIGN.md)。

---

## 实测数据

| 指标 | 数值 | 说明 |
|------|------|------|
| M1 单步稳定性 | **62.5%**（5/8） | `reports/M1_test_record.md` |
| M2 流水线 Step01–04 全通过 | **77.4%**（24/31） | 历史 `reports/` 统计 |
| 测试用例 | 4 条 | `test_cases.json`（含发消息 TC004） |
| Demo 固定坐标模式 | 3/3 | `USE_FIXED_COORDS=true`，**不计入 VLM 基准** |

两种运行模式：

- **VLM 模式**（`USE_FIXED_COORDS=false`）：Step04 百炼定位 + OpenCV 兜底，用于真实能力评估。
- **Demo 模式**（`USE_FIXED_COORDS=true`）：Step04 固定坐标 `(1280, 350)`，仅适合特定分辨率演示。

重新生成基准报告：

```bash
python tools/run_vlm_benchmark.py --historical
python tools/run_vlm_benchmark.py   # Live 跑用例，需 .env + 飞书已打开
```

---

## 快速开始

**环境：** Windows，已登录飞书客户端，Python 3.10+。

```bash
pip install -r requirements.txt
# 若 pip 报 HASH 错误，改用：
# pip install -r requirements-min.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir

cp .env.example .env
# 填入 DEEPSEEK_API_KEY + VISION_*（百炼视觉 Key）

python tools/test_vlm_connection.py
python run_all.py --search-term "陈锦彤"
python run_all.py --search-term "陈锦彤" --message "hello"
python run_all.py --instruction "搜索陈锦彤并给她发送hello"
```

`.env` 关键项（详见 `.env.example`）：

```env
VLM_PROVIDER=hybrid
DEEPSEEK_API_KEY=sk-...
VISION_API_KEY=sk-...
VISION_MODEL=qwen3.6-flash
VISION_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
```

| 变量 | 说明 | 默认 |
|------|------|------|
| `USE_FIXED_COORDS` | 固定坐标 Demo 模式 | `false` |
| `ENABLE_STATE_CHECK` | 步骤后 VLM 状态检测 | `true` |
| `STEP_DELAY_SEC` | Step 间等待（防 API 限流） | `30` |

**运行注意：** Agent 会控制键鼠；跑前飞书回主界面（`Esc`），窗口最大化，运行中勿触碰鼠标。

---

## 项目结构

```
feishu-cua-challenge/
├── run_all.py              # 主入口
├── config.py               # hybrid 双 API 配置
├── test_cases.json         # 4 条用例
├── ops/                    # Step 01–06
├── core/
│   ├── state_checker.py    # 步骤间状态门禁
│   └── task_parser.py      # 自然语言指令解析
├── utils/
│   ├── vlm_client.py       # DeepSeek / 百炼 统一路由
│   └── coords.py           # VLM 坐标换算
├── tools/
│   ├── test_vlm_connection.py
│   └── run_vlm_benchmark.py
├── reports/                # 执行报告与基准
└── docs/
    ├── REQUIREMENTS.md
    └── SYSTEM_DESIGN.md
```

---

## 已知限制

1. **Step01 依赖 OpenCV 模板**，飞书 UI 变更需更新 `assets/template_search_box.png`。
2. **Step04 VLM 坐标有随机偏差**，同一界面多次运行可能点偏；已做坐标换算与点击验证，仍非像素级稳定。
3. **VLM API 限流（429）**，连续运行依赖 Step 间 30s、用例间 90s 等待。
4. **固定流水线**，仅覆盖搜索 + 打开第一条 + 可选发消息，不支持审批、日历等场景。
5. **Overlay 悬浮窗**已搁置，未接入主流程。

---

## 文档

- [需求分析](docs/REQUIREMENTS.md)
- [系统架构与排错](docs/SYSTEM_DESIGN.md)
- [VLM 基准报告](reports/VLM_BENCHMARK.md)
- [M1 测试记录](reports/M1_test_record.md)

---

## License

MIT

## Recently updated

2026.6.3 Chen JinTong
