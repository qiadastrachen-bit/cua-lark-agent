# VLM 模式基准测试报告

> 生成时间: 2026-06-16 22:57:52
> 模式: `USE_FIXED_COORDS=false`（完整 VLM + OpenCV 双轨）

## 1. 历史运行统计（reports/ 归档）

| 指标 | 数值 |
|------|------|
| 有效运行次数 | 31 |
| Step01–04 全通过次数 | 24 |
| 全通过率 | **77.4%** |

说明: 历史报告仅统计 Step01–04（Step05 归档不计入成功步数）

### M1 阶段（单步稳定性，2026-05-02 ~ 05-03）

| 指标 | 数值 |
|------|------|
| 整体成功率 | **62.5%**（5/8 次运行） |
| 主要失败点 | Step04 过渡区偏移、截图全黑、Step01 OpenCV 模板失效 |

### Demo 模式说明（固定坐标）

2026-05-06 冲刺夜为通过演示，曾启用 `USE_FIXED_COORDS=true`（坐标 1280,350）
绕过 VLM 限流。**该模式不计入 VLM 基准成功率。**

## 2. 本次 Live 基准测试

**未执行**: 未配置 VOLC_API_KEY / VOLC_ENDPOINT_ID（复制 .env.example 为 .env 并填入）

配置完成后重新运行:
```bash
python tools/run_vlm_benchmark.py
```

## 3. 引用方式

在文档或答辩中引用本报告时，请区分:

- **历史全通过率**: 来自 `reports/execution_report_*.md` 自动统计
- **Live VLM 通过率**: 来自本节第 2 部分（需 `.env` + 飞书前置条件）

JSON 原始数据: `VLM_BENCHMARK.json`（每次运行另存带时间戳副本）
