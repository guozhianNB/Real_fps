# Real FPS — 体感射击交互原型

> 这是一个结合 **YOLO 目标检测**、**舵机云台控制** 和 **Pygame 游戏 UI** 的实体交互演示项目。
> 系统不直接操控真实游戏，而是通过摄像头云台、屏幕识别和视觉反馈，做出一个可演示、可扩展的体感射击原型。

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [数据流](#3-数据流)
4. [团队分工](#4-团队分工)
5. [开发路线与里程碑](#5-开发路线与里程碑)
6. [接口协议](#6-接口协议)
7. [技术栈](#7-技术栈)
8. [文件结构](#8-文件结构)
9. [快速开始](#9-快速开始)
10. [UI 设计规范](#10-ui-设计规范)

---

## 1. 项目概述

### 1.1 这是什么？

Real FPS 是一个**硬件+软件联动的体感射击演示系统**。你可以把它理解为：

- **用鼠标控制真实的摄像头云台**（鼠标往右移，云台往右转）
- **YOLO 识别画面中的目标**（人、物体），在屏幕上框出来
- **Pygame 渲染战斗风格 HUD**（准星、雷达、分数、命中效果）
- **所有模块通过 JSON 和事件广播联动**

### 1.2 核心亮点

| 亮点 | 说明 |
|------|------|
| 🎯 **鼠标→云台** | 鼠标相对位移直接映射为舵机角度，实时控制物理云台 |
| 👁️ **YOLO 视觉** | 实时目标检测，计算目标中心偏移，辅助锁定 |
| 🖥️ **Pygame HUD** | 准星、雷达、分数、命中提示，科幻战斗风格 |
| 🔄 **模块解耦** | 各模块通过 JSON 文件 + pyee 事件广播通信，可独立开发测试 |
| 📦 **可演示** | 有模拟器，无需硬件也能跑 UI 和输入模块 |

### 1.3 适用场景

- 课程项目 / 毕业设计演示
- 体感交互原型验证
- 目标检测+云台联动的技术展示

---

## 2. 系统架构

系统分为四层，从输入到输出：

```
┌─────────────────────────────────────────────────────────────┐
│  🎮 输入与控制层 (D)                                        │
│  鼠标监听 → dx/dy → 角度映射 → 串口发送 → 舵机云台          │
│  键盘监听 → P键暂停/继续 → Esc键结束                        │
│  鼠标回中锁定                                               │
└──────────────────────┬──────────────────────────────────────┘
                       │ (pyee 事件广播)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  👁️ 视觉识别层 (你 — 主程序)                                 │
│  摄像头/屏幕捕获 → YOLO推理 → 目标中心计算                   │
│  → 写入 state.json (供B轮询)                                 │
│  → 发送角度到串口                                            │
└──────────────────────┬──────────────────────────────────────┘
                       │ (JSON文件 + 摄像头帧)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  🖥️ UI展示层 (B + C)                                        │
│  B: Pygame主循环、摄像头背景、准星、目标框                    │
│  C: 雷达、HUD面板、命中/击杀动画、demo模拟器                │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 各层职责

| 层 | 负责队员 | 关键技术 | 产出 |
|----|----------|----------|------|
| **输入与控制层** | D | `pynput`、`pyee`、`ctypes`、串口 | `D_mouse.py` → `dx/dy/left_click` + 广播事件 |
| **视觉识别层** | 你（主程） | YOLOv8、OpenCV、`mss` | `state.json`（目标+分数） |
| **UI 展示层** | B + C | Pygame、`threading`、`queue` | Pygame 窗口 + HUD 组件 |
| **硬件执行层** | 你（主程） | `pyserial`、Arduino/STM32 | 串口指令 → 舵机 PWM |

---

## 3. 数据流

### 3.1 主循环数据流

```
每帧循环（约 60 FPS）：
    1. D 提供: dx, dy, left_click
    2. 你计算: 角度增量 = dx * 系数
    3. 你发送: 串口指令 "X:120,Y:90"
    4. 你运行: YOLO 推理（单独线程，5-15 FPS）
    5. 你写入: state.json（供 B 轮询）
    6. B 读取: state.json（10-20 Hz）
    7. C 组件: 从 B 的 latest_state 取数据渲染
```

### 3.2 事件广播流（pyee）

```
主程序 (你)                  D (键鼠)
    │                         │
    ├── emit GAME_START ──────► on → start()
    │                         │
    │◄── emit GAME_PAUSE ───── P键按下（游戏中）
    │                         │
    ├── emit GAME_CONTINUE ──► on → resume()
    │                         │
    │◄── emit GAME_CONTINUE ── P键按下（暂停中）
    │                         │
    │◄── emit GAME_OVER ────── Esc键按下
    │                         │
    └── emit GAME_OVER ──────► on → stop()
```

### 3.3 JSON 状态文件数据流

```
你（主程序）                     B（UI）
    │                            │
    │ 每帧写入 state.json        │
    │   ├── system_state         │
    │   ├── fire_state           │
    │   ├── score                │
    │   ├── targets              │
    │   └── serial               │
    │                            │ 每50ms轮询读取
    │───────────────────────────►│ json.loads()
    │                            │ → latest_state
    │                            │ → 准星、HUD、雷达使用
```

---

## 4. 团队分工

### 4.1 分工总表

| 队员 | 角色 | 负责内容 | 参考文档 | 依赖 |
|------|------|----------|----------|------|
| **你（主程）** | 系统集成 | 主程序编排、YOLO 视觉、串口外设、状态机、计分 | `A_*.md` | 依赖 D 的 `get_delta()` |
| **B** | UI 核心 | Pygame 主循环、摄像头背景、准星、JSON 轮询线程、目标框 | `B_pygame.md` | 依赖 `state.json` 和摄像头帧 |
| **C** | UI 辅助 | 雷达、HUD 面板、命中动画、demo 模拟器、UI 配置 | `C_ui_assist.md` | 依赖 B 的 `latest_state` |
| **D** | 键鼠监听 | dx/dy、左键开火、P 键暂停/继续、Esc 结束、鼠标回中锁定、pyee 广播 | `D_mouse.md` | 独立可测 |

### 4.2 协作接口

```
你 ←→ D:  pyee 事件 + get_delta()
你 ←→ B:  state.json + camera_reader()
B  ←→ C:  latest_state（B 传入，C 的组件消费）
你 → 硬件: 串口指令 "X:{angle},Y:{angle}"
```

### 4.3 独立测试能力

| 模块 | 测试命令 |
|------|----------|
| D | `python D_mouse.py` |
| C | `python ui/demo_reader.py` |
| B | `python -c "from ui.core import UI; UI(fullscreen=False).start()"`（需先启动 `demo_emitter.py`） |

---

## 5. 开发路线与里程碑

### 第 1-2 天：独立模块开发

| 任务 | 负责 | 验证方式 |
|------|------|----------|
| 环境搭建 | 全员 | `pip install -r requirement.txt` |
| Pygame 窗口 | B | `python -c "from ui.core import UI; UI(fullscreen=False).start()"` |
| 鼠标监听 | D | `python D_mouse.py` |
| UI 组件 | C | `python ui/demo_reader.py` |
| 串口测试 | 你 | 单片机收到数据 |

### 第 3-4 天：模块联调

| 任务 | 负责 | 说明 |
|------|------|------|
| B 接入 C 的组件 | B + C | 调用 `radar.render()`, `hud.render()`, `effects.render()` |
| state.json 对接 | 你 + B | B 读到你的输出 |
| 鼠标→角度→串口 | 你 | dx/dy → 串口 |

### 第 5-7 天：YOLO + 整合

YOLO 推理 → 写入 state.json → UI 显示目标框 → 调优

---

## 6. 接口协议

### 6.1 state.json 格式（你写入，B 轮询）

```json
{
    "timestamp": 1717320000.0,
    "system_state": {
        "mode": "playing",
        "msg": "normal"
    },
    "fire_state": {
        "fired": false
    },
    "score": {
        "value": 120,
        "delta": 10,
        "reason": "hit"
    },
    "targets": [
        {
            "id": 3,
            "class": "person",
            "conf": 0.94,
            "bbox": [600, 300, 680, 420],
            "cx": 640,
            "cy": 360
        }
    ],
    "serial": {
        "status": "OK",
        "msg": "connected"
    }
}
```

**字段说明：**

| 字段 | 类型 | 含义 | 谁写 | 谁读 |
|------|------|------|------|------|
| `system_state.mode` | str | 模式：`idle`/`playing`/`paused`/`over` | 你 | B（状态栏） |
| `fire_state.fired` | bool | 是否刚开火 | 你 | B（闪光） |
| `score.value` | int | 当前总分 | 你 | B、C（HUD） |
| `score.delta` | int | 本帧加分值 | 你 | C（弹出动画） |
| `score.reason` | str | 加分原因 | 你 | C（提示文字） |
| `targets[]` | array | 目标列表 | 你 | B（框）、C（雷达） |
| `serial.status` | str | 串口状态 | 你 | B（状态栏） |

### 6.2 pyee 广播事件

| 事件 | 发送方 → 接收方 | 触发条件 | 接收方反应 |
|------|-----------------|----------|-----------|
| `GAME_START` | 你 → D | 你启动游戏 | D: `start()` |
| `GAME_CONTINUE` | D → 你 | P 键按下（暂停中） | 你: 恢复 |
| `GAME_PAUSE` | D → 你 | P 键按下（游戏中） | 你: 暂停 |
| `GAME_OVER` | D → 你 | Esc 键按下 | 你: 结束 |

### 6.3 D_mouse.py 接口

```python
from D_mouse import MouseListener

ml = MouseListener(sensitivity=1.0, deadzone=2, center_lock=True)
ml.start()
dx, dy, left_click = ml.get_delta()

ml.emitter.on("GAME_PAUSE", on_pause)
ml.emitter.on("GAME_CONTINUE", on_continue)
ml.emitter.on("GAME_OVER", on_game_over)
```

### 6.4 UI 模块接口

```python
from ui.core import UI
ui = UI(fullscreen=False)
ui.start()
```

---

## 7. 技术栈

| 技术 | 版本 | 用途 | 使用者 |
|------|------|------|--------|
| Python | 3.10+ | 主语言 | 全员 |
| Pygame | 2.5+ | UI 窗口 | B, C |
| pynput | 1.7+ | 鼠标/键盘监听 | D |
| pyee | 12+ | 事件广播 | D, 你 |
| Ultralytics YOLOv8 | 最新 | 目标检测 | 你 |
| OpenCV | 4.x | 图像处理 | 你, B |
| PySerial | 3.x | 串口通信 | 你 |
| uvicorn + FastAPI | 最新 | 摄像头服务 | 你 |

```powershell
pip install pygame pynput pyee ultralytics opencv-python pyserial uvicorn fastapi requests
```

---

## 8. 文件结构

```
Real_fps/
├── main.py                  ← 你：主程序入口
├── start.py                 ← 你：启动器（一键启动）
├── A_serial.py              ← 你：串口通信
├── vision/                  ← 视觉模块
│   ├── camera_share.py      ← FastAPI 摄像头服务
│   ├── vision.py            ← YOLO 人体跟踪
│   └── get_camera.py        ← 画面获取工具
├── ui/                      ← B + C 的 UI 模块（需手动创建）
│   ├── __init__.py
│   ├── core.py              ← B：UI 主循环
│   ├── config.py            ← C：颜色/位置常量
│   ├── assets.py            ← C：字体加载
│   ├── radar.py             ← C：雷达组件
│   ├── hud.py               ← C：HUD 面板
│   ├── effects.py           ← C：命中动画
│   └── demo_reader.py       ← C：自测入口
├── 教学参考文档/
│   ├── A_main.md / A_vision.md / A_serial.md / A_mcu.md
│   ├── B_pygame.md / C_ui_assist.md / D_mouse.md
├── readme.md
└── requirement.txt
```

---

## 9. 快速开始

```powershell
pip install -r requirement.txt

# 终端 1：摄像头服务
uvicorn vision.camera_share:app --port 8010 --host 127.0.0.1 --reload

# 终端 2：模拟状态
python ui/demo_reader.py

# 终端 3：UI
python -c "from ui.core import UI; UI(fullscreen=False).start()"
```

---

## 10. UI 设计规范

### 准星

- 绿色圆环 + 十字线，始终居中
- 开火时短暂闪烁（颜色不变）

### HUD 布局

```
┌──────────────────────────────────────────────┐
│ SCORE: 120                                   │
│ TARGETS: 3                                   │
│ FPS: 60                                      │
│                                              │
│                          ╭──────╮            │
│                          │雷达   │            │
│                          │ ● ●  │            │
│                          ╰──────╯            │
│                                              │
│  ── MODE: PLAYING | SERIAL: OK ────────────  │
└──────────────────────────────────────────────┘
```

### 动画

| 动画 | 触发 | 效果 |
|------|------|------|
| 命中闪光 | `fired=true` | 白屏半透明 300ms 淡出 |
| 得分弹出 | `delta>0` | 淡入 200ms → 保持 1s → 淡出 400ms |

### 状态机

```
GAME_START → playing ──P键──→ paused ──P键──→ playing
                │
                └──Esc──→ over
```

---

> 最后更新: 2026-06-02
