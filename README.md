# Larker — AI-Powered Desktop Automation Agent

> An AI agent that sees, thinks, and acts on desktop interfaces like a human.
> Originated from Feishu CUA Challenge 2026 (M1 success rate 57.1%, M2 E2E 100%).

---

## What Larker Does

Larker takes a natural language instruction — "search for 陈锦彤 in Feishu" — and autonomously completes the full operation: locate the search box, type the query, identify the first result, click into it, and verify success. No hardcoded coordinates. No fragile scripts.

---

## Core Capabilities

### 1. VLM-Powered Visual Understanding

Uses vision-language models to interpret screenshots and locate UI elements by **semantics**, not fixed coordinates.

- Screenshots compressed to 1280x800 before VLM inference — reduces API response time by ~60%
- Model-agnostic design: originally Doubao-1.5-vision-pro, migrating to DeepSeek
- Input: compressed PNG via Base64 → Output: pixel coordinates for PyAutoGUI

### 2. Dual-Track Localization (OpenCV + VLM)

| Scenario | Method | Why |
|----------|--------|-----|
| Fixed UI elements (search box) | OpenCV template matching | <0.5s, sub-pixel precision |
| Dynamic content (search results) | VLM visual understanding | Variable positions, needs semantic reasoning |

OpenCV handles the fast lane. VLM handles the smart lane. Not a binary choice — a routing decision based on the task.

### 3. Multi-Step Operation Pipeline

```
Instruction → 5-step pipeline → Verified result + MP4 recording

Step 01: Locate search box (OpenCV)
Step 02: Input search term (clipboard paste)
Step 03: Wait for results (adaptive timing)
Step 04: Locate first result (VLM) → double-click
Step 05: Screenshot verification + archive report
```

Why 5? 3 steps → failures hard to isolate. 7 steps → scheduling overhead increases. 5 balances granularity and complexity.

### 4. Built-in Resilience

| Mechanism | Problem Solved |
|-----------|---------------|
| Coordinate transition-zone correction (+35px) | VLM drift near UI chrome/tabs |
| Tiered rate-limit backoff (429 handling) | API quota preservation across long runs |
| E2E test framework (pytest + subprocess) | Regression detection after each code change |
| Background MP4 recording (mss + cv2.VideoWriter) | 90% storage savings vs PNG frame sequences |

---

## Technical Architecture

```
User Instruction
       │
       ▼
┌─────────────────────────────────┐
│  Layer 1: Perception            │  PyAutoGUI, Pillow, mss
│  Screenshot → Compress → Base64 │
├─────────────────────────────────┤
│  Layer 2: Planning              │  Predefined pipeline
│  Instruction → 5-step pipeline  │  (LLM-dynamic planned)
├─────────────────────────────────┤
│  Layer 3: Execution             │  OpenCV, VLM, PyAutoGUI
│  Locate → Click → Type → Verify │
├─────────────────────────────────┤
│  Layer 4: Verification          │  VLM re-confirmation
│  Before/after screenshot diff   │
├─────────────────────────────────┤
│  Layer 5: Reporting             │  cv2.VideoWriter, JSON
│  MP4 recording + execution logs │
└─────────────────────────────────┘
```

**Stack:** Python · VLM (Doubao/DeepSeek) · OpenCV · PyAutoGUI · mss · pytest · Pillow

---

## E2E Test Results

| Test Case | Search Term | Result |
|-----------|-------------|--------|
| TC001 | 陈锦彤 (contact) | Pass |
| TC002 | 一些小计划 (doc) | Pass |
| TC003 | 日历 (function) | Pass |

**Pass rate: 3/3 (100%)**

| Metric | Manual | Larker | Improvement |
|--------|--------|--------|-------------|
| Per-search time | 10-15s | 5-8s | ~50% |
| Availability | Work hours | 24/7 | — |
| Consistency | Human-variable | Deterministic | — |

---

## Quick Start

```bash
git clone https://github.com/qiadastrachen-bit/larker.git
cd larker

pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env with your API credentials

# Run a single task
python run_all.py --search-term "search term here"

# Run full E2E suite + recording
python run_e2e_with_recording.py
```

---

## Roadmap

**In Progress**
- [ ] Migrate from Doubao to DeepSeek API
- [ ] LLM-based dynamic step generation (replace predefined 5-step pipeline)
- [ ] Abstract app adapter layer for multi-application support

**Planned**
- [ ] Overlay UI: floating command panel for natural language input
- [ ] Human-in-the-loop override at critical decision points
- [ ] Multi-application: Feishu → WeCom → DingTalk

**Exploratory**
- [ ] Cross-platform: Windows → macOS → Linux
- [ ] Plugin architecture for community-contributed app adapters

---

## Project Structure

```
larker/
├── run_all.py                       # Main entry: 5-step pipeline
├── run_e2e_with_recording.py        # E2E test + screen recording
├── config.py                        # Centralized config (API keys, feature flags)
├── .env.example                     # Environment variable template
├── test_cases.json                  # Test case definitions
├── core/
│   └── state_checker.py             # VLM-based state verification
├── ops/
│   ├── step_01_click_search.py      # OpenCV: locate search box
│   ├── step_02_input_text.py        # Clipboard paste
│   ├── step_03_wait_search_results.py
│   ├── step_04_click_first_result.py # VLM: locate + click result
│   └── step_05_verify_and_archive.py # Verify + report
├── tests/
│   └── test_e2e.py
└── docs/
    ├── M2_TECHNICAL_REPORT.md
    └── SYSTEM_DESIGN.md
```

---

## Origin

Larker began as a submission to the 2026 Feishu CUA Challenge (Track 5: CUA-Lark Agent). M1 achieved 57.1% success rate on the competition benchmark. M2 delivered 100% E2E pass rate on a 3-case search suite. The competition API is no longer available — Larker is now evolving into a standalone, model-agnostic desktop agent.

---

## License

MIT
