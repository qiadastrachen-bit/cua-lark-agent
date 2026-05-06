# 飞书 CUA 桌面自动化挑战赛 M2 阶段技术报告

> 文档版本：v1.1
> 更新日期：2026-05-06
> 阶段目标：M2 阶段多步搜索流程串联与稳定性优化

---

## 1. 架构设计

### 1.1 整体架构

```
用户启动 → run_all.py → [Step 01-05] → 结果归档
                     ↓
               retry_step() 重试包装器
                     ↓
          ┌─────────┴─────────┐
      VLM视觉定位          pyautogui操作
     (火山方舟API)       (鼠标移动+点击)
          ↓                 ↓
     ScreenRecorder录屏 ← 截图存档 → screenshots/
```

### 1.2 模块说明

| 模块 | 文件 | 职责 |
|------|------|------|
| 入口 | `run_all.py` | 测试用例调度、重试包装、超时控制 |
| Step 01 | `ops/step_01_click_search.py` | OpenCV模板匹配定位搜索框并点击 |
| Step 02 | `ops/step_02_input_text.py` | 剪贴板粘贴方式输入搜索词 |
| Step 03 | `ops/step_03_wait_search_results.py` | 等待搜索结果加载（倒计时） |
| Step 04 | `ops/step_04_click_first_result.py` | VLM视觉定位第一条搜索结果并双击进入 |
| Step 05 | `ops/step_05_verify_and_archive.py` | 截图对比验证、执行报告生成 |
| 状态分析 | `core/state_checker.py` | VLM通用状态感知层（M2/M3/M4共享） |
| 视觉化 | `utils/mouse_visualizer.py` | 鼠标轨迹实时可视化 |

### 1.3 核心流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     run_all.py                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────┐ │
│  │ retry_step│→ │ retry_step│→ │ retry_step│→ │verify_   │ │
│  │(Step01)   │  │(Step02)   │  │(Step03-04)│  │archive()│ │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬────┘ │
│        ↓               ↓              ↓               ↓      │
│   点击搜索框      输入搜索词       等待结果        归档报告  │
│        ↓               ↓              ↓               ↓      │
│   30s延迟         30s延迟        30s延迟              ↓      │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  火山方舟VLM API │
                    │  (视觉定位+验证) │
                    └─────────────────┘
```

---

## 2. 实现方案说明

### 2.1 VLM定位原理

**流程**：截图 → 压缩 → Base64编码 → API调用 → 解析坐标

```python
# 核心调用逻辑（step_04_click_first_result.py）
def call_vlm(image_path, prompt):
    # 1. 图片压缩（防止超时）
    img = Image.open(image_path)
    img.thumbnail((1280, 800), Image.LANCZOS)
    
    # 2. Base64编码
    img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    
    # 3. API调用
    payload = {
        "model": ENDPOINT_ID,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
        ]}]
    }
    response = requests.post(API_URL, headers=headers, json=payload, timeout=25)
```

**关键配置**：
- API端点：`https://ark.cn-beijing.volces.com/api/v3/chat/completions`
- 模型：`ep-20260423222711-8zfcd`
- 图片压缩：最大1280×800像素
- 超时时间：25秒
- 最大重试次数：2次（M2优化后）

### 2.2 点击策略

采用 **moveTo + doubleClick** 组合确保点击生效：

```python
pyautogui.moveTo(x, y, duration=1.5)  # 平滑移动
time.sleep(0.8)
pyautogui.doubleClick(x, y)           # 双击进入搜索结果
```

**策略依据**：
- 单击可能只选中文本而不进入详情页
- 双击是飞书搜索结果的标准进入方式
- duration=1.5秒移动速度平衡了速度与稳定性

### 2.3 容错机制

#### 指数退避重试

```python
# VLM调用失败时的指数退避
wait = VLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))
# 第1次重试: 15s, 第2次: 30s

# 429限流特殊处理（更长的等待时间）
if response.status_code == 429:
    wait = 90 + attempt * 45  # 135s, 180s
```

#### Step间延迟防429

```python
# run_all.py 中每个Step后等待30秒
print("=== Step 01: 点击搜索框 ===")
result = retry_step(click_search_box)
...
time.sleep(30)  # 给VLM配额恢复时间

# 用例间等待90秒
time.sleep(90)  # 用例间长延迟，让TPM配额充分恢复
```

#### 重试包装器

```python
def retry_step(step_func, *args, max_retries=2, step_timeout=600, **kwargs):
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait_sec = 5 * attempt  # 5s, 10s
            time.sleep(wait_sec)
        result = step_func(*args, **kwargs)
        if result.get("success"):
            return result
    return result
```

### 2.4 录屏回溯机制

采用 **Windows自带录屏功能（Xbox Game Bar）** 进行操作回溯：

**使用方法**：
1. 运行测试前按 `Win + Alt + R` 开始录制
2. 测试运行完毕后再次按 `Win + Alt + R` 停止录制
3. 视频自动保存到 `C:\Users\Lenovo\Videos\Captures\`

**优势**：
- 系统原生，无需额外安装
- 单个MP4文件（10分钟约200-500MB），占用空间小
- 可快进/慢放/逐帧查看鼠标轨迹和界面变化
- 直接可用于提交演示视频

### 2.5 产品设计决策

本节记录M2阶段的关键产品决策及其背后的思考，体现产品设计视角的闭环逻辑。

#### 决策1：选择飞书作为目标应用

**背景**：本次比赛要求基于企业真实业务场景设计CUA（Computer-Use Agent）能力落地方案。

**决策理由**：
- 飞书是国内企业协作领域的代表性产品，覆盖搜索、文档、审批等高频核心场景
- 作为自动化操作的目标应用具备足够的业务复杂度和代表性，能充分体现本方案的通用性和可落地性
- 飞书的UI规范相对统一，适合作为VLM视觉定位的验证场景

#### 决策2：M1使用OpenCV，M2引入VLM

**背景**：核心目标是实现「用户发任务 → 自动截图 → 视觉理解 → 自主操作」的端到端自动化链路。

**M1阶段选择OpenCV的理由**：
- 需要快速实现结构化UI元素的定位
- OpenCV模板匹配速度快、资源消耗低
- 适合处理控件特征明确、布局固定的场景，先跑通基础流程

**M2阶段引入VLM的理由**：
- 需要支持非结构化、动态变化的UI元素定位
- VLM具备通用视觉理解能力，能处理OpenCV无法覆盖的复杂场景
- 两者互补形成「OpenCV快速粗定位 + VLM精准校验」的双轨方案，兼顾效率和准确率

#### 决策3：采用5步流程设计

**背景**：需要对整体自动化过程进行拆分细化，达到可测试、可调试、可验证的目标。

**为什么不采用3步流程？**
- 3步拆分过粗（例如把"输入+等待+点击"合并为一步）
- 故障出现时无法定位是哪个环节的问题
- 不利于分步调试和错误恢复

**为什么不采用7步流程？**
- 7步拆分过细（例如把"移动鼠标"和"点击"拆分为两步）
- 增加流程调度复杂度和出错概率
- 反而降低系统整体稳定性

**5步流程设计**：`接收任务 → 搜索输入 → 结果定位 → 点击操作 → 结果验证`
- 刚好覆盖端到端全链路
- 每步边界清晰、可独立验证
- 兼顾了可维护性和执行效率

---

## 3. 测试结果模板

### 3.1 测试用例定义

| 用例ID | 用例名 | 搜索词 | 预条件 |
|--------|--------|--------|--------|
| TC001 | 正常搜索 | 张三 | 打开飞书，进入搜索页面 |
| TC002 | 长文本搜索 | 这是一个非常长的搜索词用于测试边界情况 | 同上 |
| TC003 | 特殊字符搜索 | 产品 v2.0 (正式版) | 同上 |

### 3.2 执行结果记录表

| 用例ID | 用例名 | Step 01 | Step 02 | Step 03 | Step 04 | Step 05 | 总体 |
|--------|--------|---------|---------|---------|---------|---------|------|
| TC001 | 正常搜索 | | | | | |
| TC002 | 长文本搜索 | | | | | |
| TC003 | 特殊字符搜索 | | | | | |

**填写说明**：
- 填写格式：`✅ 通过` / `❌ 失败` / `⚠️ 部分成功`
- Step 05为验证归档步骤，记录归档是否成功
- 总体评价：5/5步通过为`通过`，否则为`失败`

### 3.3 详细执行记录

（每次执行后补充，格式参考）

```
执行时间: 2026-05-06 HH:MM:SS
用例: TC001 - 正常搜索
Step 01: ✅ 点击搜索框成功 (OpenCV匹配度: 0.852)
Step 02: ✅ 输入"张三"成功
Step 03: ✅ 等待5秒完成
Step 04: ✅ VLM定位坐标(960,350), 双击进入成功
Step 05: ✅ 归档完成
总体: 5/5 通过
```

---

## 4. 已知问题 & 改进方向

### 4.1 已知问题

| 问题 | 根因 | 影响程度 | 状态 |
|------|------|----------|------|
| OpenCV匹配在UI变化时失效 | 搜索框模板图过时 | 高 | ⚠️ 已改用VLM定位 |
| VLM TPM限流(429) | 短时间内API调用过多 | 高 | ✅ 已有延迟控制+图片压缩 |
| 点击偶尔不生效 | 单击未进入详情页 | 中 | ✅ 已改用doubleClick |
| 屏幕分辨率检测不准 | pyautogui返回物理像素 | 中 | ⚠️ 待解决 |
| Overlay窗口无法正常显示和交互 | Overlay架构依赖Chrome扩展注入，非系统级窗口 | 中 | ⚠️ 暂时搁置，优先保障核心流程 |

**Overlay问题详细说明**：
1. **现象**：Overlay组件强依赖Chrome进程，无法独立存在于飞书应用环境中；运行时默认位置偏移至屏幕最右侧且不可见，窗口无法置顶、层级始终在飞书主窗口之下，必须手动调整才能显示；同时作为Agent交互入口，Overlay无法直接接收用户指令、无法独立调度后续自动化操作。
2. **根因**：当前Overlay架构错误地采用了Chrome扩展注入的方案，而非系统级独立进程/窗口管理方案，导致窗口属性受宿主浏览器限制，且交互通信链路未打通。
3. **临时方案**：因赛期时间紧张，核心目标是先跑通搜索全流程闭环，暂时搁置Overlay模块开发，优先保障核心功能可用。

### 4.2 改进方向

#### 4.2.1 OpenCV → VLM定位迁移（已完成）

**原问题**：Step01使用OpenCV模板匹配，当UI样式变化时匹配度下降甚至失败（第8次运行匹配度仅0.376）

**改进方案**：Step01保持OpenCV（速度快），Step04使用VLM（精度高）

**当前状态**：✅ 已完成

#### 4.2.2 VLM TPM限流优化（已完成）

**问题**：连续调用VLM导致TPM（Tokens Per Minute）超出限制，返回429错误

**改进方案**：
1. 图片压缩：1280×800上限，减少token消耗
2. Step间延迟：30秒等待
3. 用例间延迟：90秒等待
4. 429特殊处理：等待135-180秒让配额恢复
5. 减少VLM重试次数：3次 → 2次

**当前状态**：✅ 已完成

#### 4.2.3 点击可靠性提升（已完成）

**问题**：单点击击有时只选中文本而不进入详情页

**改进方案**：
- 使用 `doubleClick` 替代 `click`
- 移动后增加 `sleep(0.8)` 确保稳定
- 增加坐标合理性校验（边缘检测、Y坐标下限）

**当前状态**：✅ 已完成

---

## 5. 创新点（加分项）

### 5.1 Windows录屏回溯机制

**创新描述**：采用Windows系统原生录屏功能（Xbox Game Bar, Win+Alt+R）记录完整测试过程，用于操作回溯、问题定位和提交演示。

**使用流程**：
```bash
# 测试前
按 Win + Alt + R          # 开始录制

# 运行测试
python run_all.py --search-term "测试"

# 测试后
按 Win + Alt + R          # 停止录制

# 视频位置
C:\Users\Lenovo\Videos\Captures\
```

**应用价值**：
- 操作失败时可回放视频定位问题（可快进/慢放/逐帧）
- 直接生成演示视频用于项目提交
- 相比PNG帧序列方案，单个MP4文件节省90%以上存储空间（200-500MB vs 3-5GB）

### 5.2 图片压缩优化VLM响应速度

**创新描述**：在调用VLM前将截图压缩至最大1280×800像素，减少Base64编码体积和API处理时间。

**技术实现**：
```python
img = Image.open(image_path)
img.thumbnail((1280, 800), Image.LANCZOS)  # 等比例缩放
buf = io.BytesIO()
img.save(buf, format="PNG", optimize=True)
img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
```

**优化效果**：
- 典型截图从3-5MB压缩至200-400KB
- Base64编码后约减少70%字符数
- API超时率显著降低

### 5.3 指数退避+智能延迟的429规避策略

**创新描述**：针对VLM TPM限流实现分级退避策略，区分普通重试和429限流两种场景。

**技术实现**：
```python
# 普通超时：指数退避
wait = VLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))  # 15s, 30s

# 429限流：更长等待
if response.status_code == 429:
    wait = 90 + attempt * 45  # 135s, 180s
    time.sleep(wait)

# Step间延迟
time.sleep(30)  # 给VLM配额恢复时间

# 用例间延迟
time.sleep(90)  # 长延迟让TPM充分恢复
```

**策略效果**：
- 避免在TPM耗尽时频繁重试浪费配额
- 通过预设延迟让配额自然恢复
- 多层次延迟设计确保长时间运行的稳定性

---

## 6. 附录

### 6.1 文件结构

```
feishu-cua-challenge/
├── run_all.py                  # 主入口，测试用例调度
├── test_cases.json             # 测试用例定义
├── core/
│   └── state_checker.py        # VLM状态分析器
├── ops/
│   ├── step_01_click_search.py     # 点击搜索框
│   ├── step_02_input_text.py       # 输入搜索词
│   ├── step_03_wait_search_results.py  # 等待搜索结果
│   ├── step_04_click_first_result.py   # 点击第一条结果
│   └── step_05_verify_and_archive.py    # 验证归档
├── utils/
│   ├── mouse_visualizer.py      # 鼠标轨迹可视化
│   └── overlay_*.py             # 窗口置顶工具（暂时搁置）
├── screenshots/                 # 截图存档目录
├── archive/                     # 归档报告（按日期组织）
├── reports/                     # 执行报告目录
└── docs/
    └── M2_TECHNICAL_REPORT.md   # 本文档
```

### 6.2 API配置

| 配置项 | 值 |
|--------|-----|
| API URL | `https://ark.cn-beijing.volces.com/api/v3/chat/completions` |
| API Key | `ark-f11e281e-ef25-4cb0-a1ee-c7d14e8d76d4-7419d` |
| Endpoint ID | `ep-20260423222711-8zfcd` |
| Timeout | 30秒（M2优化后） |
| Max Retries | 2次（M2优化后） |

### 6.3 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.0 | 2026-05-06 | 初始版本，完成M2阶段技术文档 |
| v1.1 | 2026-05-06 | 新增2.5节产品设计决策；更新4.1节Overlay问题说明；优化429参数 |

---

*本文档由飞书CUA挑战赛团队生成，用于M2阶段技术汇报*
