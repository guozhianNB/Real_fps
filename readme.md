# Real FPS — 体感射击交互原型

> 这是一个结合 **YOLO 目标检测**、**舵机云台控制** 和 **Pygame 游戏 UI** 的实体交互演示项目。
> 系统不直接操控真实游戏，而是通过摄像头云台、屏幕识别和视觉反馈，做出一个可演示、可扩展的体感射击原型。

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
│  摄像头/屏幕捕获 → YOLO推理 → 目标中心计算 → 锁定逻辑       │
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
    │   ├── aim_state            │
    │   ├── fire_state           │
    │   ├── target_lock          │
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
| **你（主程）** | 系统集成 | 主程序编排、YOLO 视觉、串口外设、状态机、评分逻辑 | — | 依赖 D 的 `get_delta()` 和 B 的 `state.json` |
| **B** | UI 核心 | Pygame 主循环、摄像头背景、准星、JSON 轮询线程、目标框、窗口管理 | `B_pygame.md` | 依赖你的 `state.json` 和摄像头帧 |
| **C** | UI 辅助 | 雷达、HUD 面板、命中/击杀动画、demo 模拟器、UI 配置与资源管理 | `C_ui_assist.md` | 依赖 B 的 `latest_state`，独立可测 |
| **D** | 键鼠监听 | dx/dy、左键开火、P 键暂停/继续、Esc 结束、鼠标回中锁定、pyee 广播 | `D_mouse.md` | 独立可测 |

### 4.2 协作接口

```
你 ←→ D:  pyee 事件 + get_delta()
你 ←→ B:  state.json + camera_reader()
B  ←→ C:  latest_state（B 传入，C 的组件消费）
你 → 硬件: 串口指令 "X:{angle},Y:{angle}"
```

### 4.3 独立测试能力

每个模块都可以独立运行测试，不依赖其他模块：

| 模块 | 测试命令 | 需要什么 |
|------|----------|----------|
| D | `python D_mouse.py` | 只需一个终端 |
| C | `python ui/demo_reader.py` | 只需一个终端 |
| B | `python -c "from ui.core import UI; UI(fullscreen=False).start()"` | 需先启动 `demo_emitter.py` |
| 你 | `python main.py` | 所有模块就绪后 |

---

## 5. 开发路线与里程碑

### 5.1 第一阶段：独立模块开发（第 1-2 天）

**目标：每个人的模块能独立跑起来。**

| 任务 | 负责 | 产出 | 验证方式 |
|------|------|------|----------|
| 1.1 环境搭建 | 全员 | `pip install -r requirement.txt` 成功 | 终端无报错 |
| 1.2 Pygame 空窗口 | B | `ui/core.py` 打开黑色窗口 | `python -c "from ui.core import UI; UI(fullscreen=False).start()"` |
| 1.3 鼠标监听 | D | `D_mouse.py` 打印 dx, dy | `python D_mouse.py` |
| 1.4 雷达+HUD+动画 | C | `ui/demo_reader.py` 显示组件 | `python ui/demo_reader.py` |
| 1.5 串口测试 | 你 | 串口发送脚本 | 单片机收到数据 |

### 5.2 第二阶段：模块联调（第 3-4 天）

**目标：模块之间能通信。**

| 任务 | 负责 | 说明 |
|------|------|------|
| 2.1 B 接入 C 的组件 | B + C | B 在 `_render()` 中调用 `radar.render()`, `hud.render()`, `effects.render()` |
| 2.2 D 接入主程序 | 你 + D | 你读 D 的 `get_delta()`，写 `state.json` |
| 2.3 B 读取 state.json | B + 你 | B 的 JSON 线程读到你的输出 |
| 2.4 鼠标→角度→串口 | 你 | dx/dy → 角度 → 串口指令 |

### 5.3 第三阶段：YOLO 接入（第 5 天）

**目标：系统能看到目标。**

| 任务 | 负责 | 说明 |
|------|------|------|
| 3.1 YOLO 单帧推理 | 你 | 加载模型，对摄像头帧做检测 |
| 3.2 目标→JSON | 你 | 检测结果写入 state.json 的 `targets` 字段 |
| 3.3 UI 显示目标框 | B | B 读取到 target 后在屏幕上画框 |

### 5.4 第四阶段：整合演示（第 6-7 天）

**目标：跑通完整闭环。**

| 任务 | 负责 | 说明 |
|------|------|------|
| 4.1 完整状态机 | 你 | GAME_START → tracking → locked → firing → GAME_OVER |
| 4.2 评分逻辑 | 你 | 锁定时间 + 命中判定 + 分数 |
| 4.3 参数调优 | 全员 | 灵敏度、死区、平滑、帧率 |
| 4.4 一键启动脚本 | 你 | `python main.py` 启动一切 |

---

## 6. 接口协议

### 6.1 state.json 格式（你写入，B 轮询）

```json
{
    "timestamp": 1717320000.0,
    "system_state": {
        "mode": "tracking",
        "msg": "normal"
    },
    "aim_state": {
        "on_target": true,
        "hit_zone": "head",
        "target_id": 3,
        "conf": 0.94
    },
    "fire_state": {
        "ready": true,
        "fired": false,
        "cooldown_ms": 0
    },
    "target_lock": {
        "locked": true,
        "target_id": 3,
        "cx": 640,
        "cy": 360,
        "distance": 18.2
    },
    "score": {
        "value": 120,
        "delta": 10,
        "reason": "headshot"
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
| `timestamp` | float | UNIX 时间戳 | 你 | B（判断数据是否过期） |
| `system_state.mode` | str | 系统模式：`idle`/`tracking`/`locked`/`firing`/`error` | 你 | B（显示状态栏）、C（HUD颜色） |
| `aim_state.on_target` | bool | 准星是否在目标上 | 你 | B（准星颜色） |
| `aim_state.hit_zone` | str | 命中部位：`none`/`body`/`head` | 你 | B（HEADSHOT提示） |
| `fire_state.fired` | bool | 是否刚开火 | 你 | B（闪光）、C（闪光效果） |
| `target_lock.locked` | bool | 是否锁定目标 | 你 | B（红色锁定框） |
| `target_lock.distance` | float | 目标到准星距离（像素） | 你 | B（锁定环松紧） |
| `score.value` | int | 当前总分 | 你 | B、C（HUD显示） |
| `score.delta` | int | 本帧加分值 | 你 | C（得分弹出动画） |
| `score.reason` | str | 加分原因：`hit`/`headshot`/`lock` | 你 | C（爆头提示） |
| `targets[]` | array | 当前画面所有目标 | 你 | B（目标框）、C（雷达） |
| `serial.status` | str | 串口状态：`OK`/`ERROR` | 你 | B（状态栏颜色） |

### 6.2 pyee 广播事件

| 事件 | 发送方 → 接收方 | 触发条件 | 接收方反应 |
|------|-----------------|----------|-----------|
| `GAME_START` | 你 → D | 你启动游戏 | D: `start()` 开始监听+回中 |
| `GAME_CONTINUE` | 你 → D | 你恢复游戏 | D: `resume()` 恢复监听 |
| `GAME_CONTINUE` | D → 你 | P 键按下（暂停中） | 你: 状态机回到 playing |
| `GAME_PAUSE` | D → 你 | P 键按下（游戏中） | 你: 状态机切到 paused |
| `GAME_OVER` | D → 你 | Esc 键按下 | 你: 状态机切到 over |
| `GAME_OVER` | 你 → D | 你结束游戏 | D: `stop()` 停止监听 |
| `GAME_OVER` | 你 → B | 你结束游戏 | B: 关闭窗口 |

### 6.3 D_mouse.py 接口

```python
from D_mouse import MouseListener

ml = MouseListener(sensitivity=1.0, deadzone=2, center_lock=True)

# 生命周期
ml.start()          # 开始监听（响应 GAME_START / GAME_CONTINUE）
ml.stop()           # 停止监听（响应 GAME_PAUSE / GAME_OVER）

# 数据获取（主循环每帧调用）
dx, dy, left_click = ml.get_delta()

# 事件订阅
ml.emitter.on("GAME_PAUSE", on_pause)
ml.emitter.on("GAME_CONTINUE", on_continue)
ml.emitter.on("GAME_OVER", on_game_over)
```

### 6.4 UI 模块接口（B 的 UI 类）

```python
from ui.core import UI

# 创建 UI
ui = UI(width=1280, height=720, fullscreen=True,
        status_reader=read_status_func,   # 返回 state.json 文本
        camera_reader=read_camera_func)   # 返回 numpy 图像

# 启动（阻塞）
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
| mss | 最新 | 屏幕截图（可选） | 你 |
| pywin32/ctypes | 内置 | Windows API 调用 | D |

### 安装命令

```powershell
pip install pygame pynput pyee ultralytics opencv-python pyserial mss
```

---

## 8. 文件结构

```
Real_fps/
│
├── main.py                  ← 你：主程序入口（YOLO + 状态机 + 串口）
├── D_mouse.py               ← D：鼠标键盘监听模块
├── mouse_test.py            ← D：独立测试脚本
│
├── state.json               ← 运行时生成：你写入，B轮询
│
├── ui/                      ← B + C 的工作目录
│   ├── __init__.py          ← 空（让 ui/ 成为 Python 包）
│   ├── core.py              ← B：UI 主循环、JSON线程、摄像头线程
│   ├── config.py            ← C：颜色、位置、尺寸常量
│   ├── assets.py            ← C：字体/资源加载工具
│   ├── radar.py             ← C：雷达组件
│   ├── hud.py               ← C：HUD面板组件
│   ├── effects.py           ← C：动画效果组件
│   └── demo_reader.py       ← C：自测入口（模拟主程序）
│
├── B_pygame.md              ← B 的任务说明（零基础教程）
├── C_ui_assist.md           ← C 的任务说明（零基础教程）
├── D_mouse.md               ← D 的任务说明（零基础教程）
├── readme.md                ← 本文件
└── requirement.txt          ← 依赖清单
```

---

## 9. 快速开始

### 9.1 克隆与安装

```powershell
# 进入项目目录
cd Real_fps

# 安装依赖
pip install -r requirement.txt

# 如果 requirement.txt 不完整，装全量
pip install pygame pynput pyee ultralytics opencv-python pyserial mss
```

### 9.2 逐个模块验证

**步骤 1：测试 D 的鼠标监听**

```powershell
python D_mouse.py
```
→ 移动鼠标看 dx/dy，按 P 看暂停广播，按 Esc 看结束广播。

**步骤 2：测试 C 的 UI 组件**

```powershell
python ui/demo_reader.py
```
→ 窗口显示雷达旋转、HUD 面板、场景自动切换。

**步骤 3：测试 B 的主 UI**

```powershell
# 终端 1：启动模拟器
python ui/demo_reader.py

# 终端 2：启动 UI
python -c "from ui.core import UI; UI(fullscreen=False).start()"
```
→ 看到准星、目标框、HUD。

**步骤 4：全系统联调**

```powershell
python main.py
```
→ 一切启动，进入完整游戏循环。

### 9.3 运行顺序建议

```
第一天：python D_mouse.py 和 python ui/demo_reader.py
第二天：python -c "from ui.core import UI; UI().start()" + demo_reader
第三天：python main.py（YOLO 单帧）
第四天以后：迭代优化
```

---

## 10. UI 设计规范

### 10.1 风格

- **复古科幻风**（参考 80 年代街机 + 军事 HUD）
- 主色：荧光绿 `(0, 255, 100)`、警示红 `(255, 50, 50)`、深灰黑 `(0, 0, 0)`
- 辅助色：黄 `(255, 200, 0)`、淡蓝白 `(200, 220, 255)`
- 文字和边框带轻微发光效果（用半透明叠加实现）

### 10.2 准星

| 状态 | 颜色 | 动画 |
|------|------|------|
| 默认 | 绿色 | 静态 |
| 目标在准星附近 | 黄色 | 轻微放大 |
| 锁定目标 | 红色 | 缩放脉冲（300ms 1.25x 回弹） |
| 开火 | 红色 | 短暂闪烁 |

### 10.3 HUD 布局

```
┌──────────────────────────────────────────────────┐
│ SCORE: 120                    MODE: TRACKING     │
│ TARGETS: 3                                        │
│ FPS: 60                                           │
│                                                   │
│                                                   │
│                                       ╭──────╮   │
│                                       │雷达   │   │
│                                       │ ●  ●  │   │
│                                       ╰──────╯   │
│                                                   │
│  ─── MODE: TRACKING | SERIAL: OK ───────────────  │
└──────────────────────────────────────────────────┘
```

### 10.4 动画时间轴

| 动画 | 触发 | 时间线 |
|------|------|--------|
| 锁定缩放 | `on_target=true` | 放大 300ms → 回弹 |
| 命中闪光 | `fired=true` | 白屏 alpha=80 → 淡出 300ms |
| 得分弹出 | `delta>0` | 淡入 200ms → 保持 1s → 淡出 400ms |
| 爆头提示 | `reason=headshot` | 大字红色 1.3x 缩放 → 回正 + 淡出 |
| 雷达扫描 | 每帧 | 扫描线匀速旋转 (120°/s) |
| 目标闪烁 | 每帧 | 锁定目标 200ms 周期，普通 400ms 周期 |

---

## 附录 A：状态机定义

```
                    GAME_START
                        │
                        ▼
               ┌────────────────┐
               │    playing     │
               │  (正常运行)     │
               └────┬──────┬────┘
                    │      │
               P键  │      │ Esc
                    │      │
                    ▼      ▼
          ┌──────────┐  ┌──────────┐
          │  paused  │  │   over   │
          │ (暂停)    │  │ (结束)    │
          └────┬─────┘  └──────────┘
               │
          P键  │
               ▼
          ┌──────────┐
          │ playing  │
          │ (恢复)    │
          └──────────┘
```

## 附录 B：串口协议（初版）

```
格式: "X:角度,Y:角度\n"
角度范围: 0-180
示例: "X:120,Y:90\n"

后续可扩展:
- 回中命令: "RESET\n"
- 急停: "STOP\n"
- 查询: "STATUS?\n"
- 响应: "OK:X:120,Y:90\n"
```

---

> 最后更新: 2026-06-02

建议按这个顺序做：

1. 创建 Python 主程序入口。
2. 打开一个 Pygame 窗口，先画准星和状态文字。
3. 写一个串口测试脚本，验证电脑能和单片机通信。
4. 写一个鼠标监听脚本，确认能稳定拿到位移数据。

这一阶段只验证环境，不追求效果。

### 第二步：把输入变成控制量

把鼠标位移转换成舵机角度，是整个项目的第一条闭环。

实现方式：

- 监听鼠标的相对位移 `dx`、`dy`。
- 乘上比例系数，得到角度增量。
- 对角度做范围限制，例如水平 0 到 180 度。
- 把结果按协议发给单片机，例如 `X:120,Y:90`。

这一步完成后，鼠标移动应该能直接带动云台转动。

### 第三步：把检测结果接进来

YOLO 的任务不是直接控制系统，而是提供“目标在哪里”的信息。

实现方式：

- 截取固定分辨率的画面。
- 对画面做 YOLO 推理。
- 从检测框中取出目标中心点。
- 计算目标中心和屏幕中心的偏差。
- 把偏差转换成锁定状态、准星颜色变化和提示信息。

这一步完成后，系统就能知道“有没有目标、目标在哪”。

### 第四步：把 UI 做成状态面板

UI 不是装饰，而是让你知道系统现在是否正常工作。

建议 UI 显示以下内容：

- 准星：显示当前瞄准状态。
- Score：显示已识别或已命中的次数。
- Target：显示当前目标数量。
- FPS：显示画面刷新速度。
- 串口状态：显示连接成功、断开或延迟。

如果 UI 状态清晰，调试效率会高很多。

### 第五步：做联调和稳定性优化

系统能跑之后，重点是稳定。

建议从这几个方向优化：

- 给检测结果加阈值，减少误报。
- 给舵机控制加平滑，减少抖动。
- 给 UI 加帧率限制，避免卡顿。
- 给串口加异常处理，避免断连后程序崩溃。
- 把耗时任务拆开，避免主循环阻塞。

### 第六步：最后做演示效果

一周项目最重要的是演示清楚，而不是功能堆满。

最后一晚建议只做这些事情：

- 固定参数。
- 关闭不稳定的新功能。
- 准备一键启动脚本。
- 准备演示说明和运行截图。

## 一周内的实现顺序

### 第 1 天

- 搭建目录和依赖。
- 跑通 Pygame 窗口。
- 跑通串口收发测试。

### 第 2 天

- 完成鼠标监听和角度映射。
- 跑通云台基础控制。

### 第 3 天

- 接入 YOLO 单帧推理。
- 计算目标中心点和偏差。

### 第 4 天

- 把检测结果接入 UI。
- 做准星、状态栏、雷达的基础绘制。

### 第 5 天

- 完成主程序整合。
- 做串口、检测、渲染联动。

### 第 6 天

- 压测和修 bug。
- 调整阈值、速度和平滑参数。

### 第 7 天

- 固定演示版本。
- 准备展示文案、视频和答辩材料。

## 系统组成

### 1. 输入与控制层

- 监听鼠标移动和按键事件。
- 将鼠标位移转换为云台角度增量。
- 将控制指令通过串口发送给 Arduino 或 STM32。

### 2. 视觉识别层

- 截取指定窗口或屏幕画面。
- 使用 YOLOv8 检测目标。
- 计算目标中心点、边界框和相对准星的偏差。
- 根据检测结果更新锁定状态和得分逻辑。

### 3. UI 展示层

- 使用 Pygame 渲染准星、HUD、雷达和提示信息。
- 通过颜色、缩放和闪烁效果反馈当前状态。
- 用双缓冲方式减少闪烁和撕裂。

### 4. 硬件执行层

- 双舵机云台负责水平和俯仰转动。
- 单片机解析串口协议并输出 PWM 信号。
- 需要对舵机做限幅、平滑和回中处理。

## 推荐技术栈

- Python 3.10+
- OpenCV：画面截取、图像处理
- Ultralytics YOLOv8：目标检测
- Pygame：UI 渲染与交互显示
- PySerial：串口通信
- Pynput 或 PyWin32：鼠标监听
- Arduino / STM32：舵机控制

## 开发路线

### 第一阶段：项目骨架

先把整体工程拆成三个独立模块：视觉识别、硬件控制、UI 渲染。这个阶段的目标不是做功能最全，而是先让程序能稳定启动、显示界面、连上串口。

建议先完成以下内容：

- 建立项目目录结构。
- 写一个最小可运行的 Pygame 窗口。
- 写一个串口发送测试脚本。
- 写一个鼠标位移打印脚本。

### 第二阶段：云台控制闭环

这一阶段先不接 YOLO，只做“鼠标移动 -> 角度计算 -> 云台响应”。

建议步骤：

- 定义鼠标位移和舵机角度的映射关系。
- 设计串口协议，例如 `X:120,Y:90`。
- 在单片机端实现协议解析。
- 加入角度限幅，避免舵机越界。
- 加入平滑插值，避免云台抖动。

### 第三阶段：视觉识别闭环

这一阶段把 YOLO 接入进来，先做识别，再做状态反馈。

建议步骤：

- 选择一个固定分辨率作为推理输入。
- 读取 YOLO 模型权重并完成单帧检测。
- 计算每个目标的中心点、置信度和类别。
- 计算目标中心与屏幕中心的偏差。
- 用偏差决定准星颜色、锁定状态和命中提示。

### 第四阶段：UI 细化

当基础闭环能跑通后，再把界面做完整。

建议加入以下元素：

- 动态准星：默认绿色，锁定时切换为红色。
- HUD 面板：显示分数、状态、帧率和目标数。
- 击杀提示：目标被锁定或命中时弹出提示。
- 雷达组件：在角落显示扫描线和目标点。

### 第五阶段：整合与调优

最终把所有模块合在一起，重点解决稳定性和手感。

建议做这些优化：

- 调整 YOLO 推理帧率和画面刷新率。
- 给舵机控制加入死区和低通滤波。
- 将检测和渲染拆成不同线程或异步任务。
- 记录日志，方便排查串口和识别问题。

## 建议分工

| 队员 | 模块 | 负责内容 | 参考文件 |
|---|---|---|---|
| **你（主程）** | 主程序编排、视觉识别、外设 | YOLO 检测 + 主状态机 + pyee 事件总线 + 串口通信 + 角度映射 | — |
| **B** | UI 渲染（核心） | Pygame 主循环、摄像头背景、准星、JSON 轮询线程、目标框 | `B_pygame.md` |
| **C** | UI 辅助 | 雷达、HUD 面板（Score/Targets/FPS）、命中/击杀动画、demo 模拟器、UI 配置与资源管理 | `C_ui_assist.md` |
| **D** | 键鼠监听 | dx/dy、左键开火、P 键暂停/继续、Esc 结束、鼠标回中锁定、pyee 广播 | `D_mouse.md` |

### 协作说明

- B 和 C 同属 UI 层，代码都在 `ui/` 目录下。
- C 的组件（雷达、HUD、动画）是独立类，B 在 `_render()` 中调用即可，接口见 `C_ui_assist.md`。
- D 对外只暴露 `get_delta()` 和广播事件，不关心消费方是谁。
- 你（主程）负责把 B/C/D 三块粘起来：读 D 的 dx/dy → 算角度 → 发串口；跑 YOLO → 写状态 JSON → B 轮询；管理 `GAME_START/PAUSE/CONTINUE/OVER` 状态机。


## UI 设计建议

### 准星

- 默认显示为绿色圆环或十字。
- 锁定目标时切换为红色，并增加轻微缩放动画。

### HUD

- 左上角显示 Score、Target、FPS。
- 右上角显示状态信息，例如 Tracking、Locked、Idle。
- 底部显示串口连接状态和系统提示。

### 雷达

- 在右下角做一个小型扫描雷达。
- 使用旋转扫描线表现实时检测。
- 检测到目标时在对应方位画闪烁点。

### 风格

- 采用复古科幻风。
- 主色建议用荧光绿、警示红和深灰黑。
- 文字和边框可加轻微发光效果，增强科技感。

## 里程碑建议

1. 跑通 Pygame 窗口与串口连接。
2. 跑通鼠标输入到舵机动作的闭环。
3. 跑通 YOLO 检测并在界面上标记目标。
4. 跑通 UI、识别和硬件联动。
5. 做平滑、限幅、性能和视觉细节优化。

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
    │   ├── aim_state            │
    │   ├── fire_state           │
    │   ├── target_lock          │
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
| **你（主程）** | 系统集成 | 主程序编排、YOLO 视觉、串口外设、状态机、评分逻辑 | — | 依赖 D 的 `get_delta()` 和 B 的 `state.json` |
| **B** | UI 核心 | Pygame 主循环、摄像头背景、准星、JSON 轮询线程、目标框、窗口管理 | `B_pygame.md` | 依赖你的 `state.json` 和摄像头帧 |
| **C** | UI 辅助 | 雷达、HUD 面板、命中/击杀动画、demo 模拟器、UI 配置与资源管理 | `C_ui_assist.md` | 依赖 B 的 `latest_state`，独立可测 |
| **D** | 键鼠监听 | dx/dy、左键开火、P 键暂停/继续、Esc 结束、鼠标回中锁定、pyee 广播 | `D_mouse.md` | 独立可测 |

### 4.2 协作接口

```
你 ←→ D:  pyee 事件 + get_delta()
你 ←→ B:  state.json + camera_reader()
B  ←→ C:  latest_state（B 传入，C 的组件消费）
你 → 硬件: 串口指令 "X:{angle},Y:{angle}"
```

### 4.3 独立测试能力

每个模块都可以独立运行测试，不依赖其他模块：

| 模块 | 测试命令 | 需要什么 |
|------|----------|----------|
| D | `python D_mouse.py` | 只需一个终端 |
| C | `python ui/demo_reader.py` | 只需一个终端 |
| B | `python -c "from ui.core import UI; UI(fullscreen=False).start()"` | 需先启动 `demo_emitter.py` |
| 你 | `python main.py` | 所有模块就绪后 |

---

## 5. 开发路线与里程碑

### 5.1 第一阶段：独立模块开发（第 1-2 天）

**目标：每个人的模块能独立跑起来。**

| 任务 | 负责 | 产出 | 验证方式 |
|------|------|------|----------|
| 1.1 环境搭建 | 全员 | `pip install -r requirement.txt` 成功 | 终端无报错 |
| 1.2 Pygame 空窗口 | B | `ui/core.py` 打开黑色窗口 | `python -c "from ui.core import UI; UI(fullscreen=False).start()"` |
| 1.3 鼠标监听 | D | `D_mouse.py` 打印 dx, dy | `python D_mouse.py` |
| 1.4 雷达+HUD+动画 | C | `ui/demo_reader.py` 显示组件 | `python ui/demo_reader.py` |
| 1.5 串口测试 | 你 | 串口发送脚本 | 单片机收到数据 |

### 5.2 第二阶段：模块联调（第 3-4 天）

**目标：模块之间能通信。**

| 任务 | 负责 | 说明 |
|------|------|------|
| 2.1 B 接入 C 的组件 | B + C | B 在 `_render()` 中调用 `radar.render()`, `hud.render()`, `effects.render()` |
| 2.2 D 接入主程序 | 你 + D | 你读 D 的 `get_delta()`，写 `state.json` |
| 2.3 B 读取 state.json | B + 你 | B 的 JSON 线程读到你的输出 |
| 2.4 鼠标→角度→串口 | 你 | dx/dy → 角度 → 串口指令 |

### 5.3 第三阶段：YOLO 接入（第 5 天）

**目标：系统能看到目标。**

| 任务 | 负责 | 说明 |
|------|------|------|
| 3.1 YOLO 单帧推理 | 你 | 加载模型，对摄像头帧做检测 |
| 3.2 目标→JSON | 你 | 检测结果写入 state.json 的 `targets` 字段 |
| 3.3 UI 显示目标框 | B | B 读取到 target 后在屏幕上画框 |

### 5.4 第四阶段：整合演示（第 6-7 天）

**目标：跑通完整闭环。**

| 任务 | 负责 | 说明 |
|------|------|------|
| 4.1 完整状态机 | 你 | GAME_START → tracking → locked → firing → GAME_OVER |
| 4.2 评分逻辑 | 你 | 锁定时间 + 命中判定 + 分数 |
| 4.3 参数调优 | 全员 | 灵敏度、死区、平滑、帧率 |
| 4.4 一键启动脚本 | 你 | `python main.py` 启动一切 |

---

## 6. 接口协议

### 6.1 state.json 格式（你写入，B 轮询）

```json
{
    "timestamp": 1717320000.0,
    "system_state": {
        "mode": "tracking",
        "msg": "normal"
    },
    "aim_state": {
        "on_target": true,
        "hit_zone": "head",
        "target_id": 3,
        "conf": 0.94
    },
    "fire_state": {
        "ready": true,
        "fired": false,
        "cooldown_ms": 0
    },
    "target_lock": {
        "locked": true,
        "target_id": 3,
        "cx": 640,
        "cy": 360,
        "distance": 18.2
    },
    "score": {
        "value": 120,
        "delta": 10,
        "reason": "headshot"
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
| `timestamp` | float | UNIX 时间戳 | 你 | B（判断数据是否过期） |
| `system_state.mode` | str | 系统模式：`idle`/`tracking`/`locked`/`firing`/`error` | 你 | B（显示状态栏）、C（HUD颜色） |
| `aim_state.on_target` | bool | 准星是否在目标上 | 你 | B（准星颜色） |
| `aim_state.hit_zone` | str | 命中部位：`none`/`body`/`head` | 你 | B（HEADSHOT提示） |
| `fire_state.fired` | bool | 是否刚开火 | 你 | B（闪光）、C（闪光效果） |
| `target_lock.locked` | bool | 是否锁定目标 | 你 | B（红色锁定框） |
| `target_lock.distance` | float | 目标到准星距离（像素） | 你 | B（锁定环松紧） |
| `score.value` | int | 当前总分 | 你 | B、C（HUD显示） |
| `score.delta` | int | 本帧加分值 | 你 | C（得分弹出动画） |
| `score.reason` | str | 加分原因：`hit`/`headshot`/`lock` | 你 | C（爆头提示） |
| `targets[]` | array | 当前画面所有目标 | 你 | B（目标框）、C（雷达） |
| `serial.status` | str | 串口状态：`OK`/`ERROR` | 你 | B（状态栏颜色） |

### 6.2 pyee 广播事件

| 事件 | 发送方 → 接收方 | 触发条件 | 接收方反应 |
|------|-----------------|----------|-----------|
| `GAME_START` | 你 → D | 你启动游戏 | D: `start()` 开始监听+回中 |
| `GAME_CONTINUE` | 你 → D | 你恢复游戏 | D: `resume()` 恢复监听 |
| `GAME_CONTINUE` | D → 你 | P 键按下（暂停中） | 你: 状态机回到 playing |
| `GAME_PAUSE` | D → 你 | P 键按下（游戏中） | 你: 状态机切到 paused |
| `GAME_OVER` | D → 你 | Esc 键按下 | 你: 状态机切到 over |
| `GAME_OVER` | 你 → D | 你结束游戏 | D: `stop()` 停止监听 |
| `GAME_OVER` | 你 → B | 你结束游戏 | B: 关闭窗口 |

### 6.3 D_mouse.py 接口

```python
from D_mouse import MouseListener

ml = MouseListener(sensitivity=1.0, deadzone=2, center_lock=True)

# 生命周期
ml.start()          # 开始监听（响应 GAME_START / GAME_CONTINUE）
ml.stop()           # 停止监听（响应 GAME_PAUSE / GAME_OVER）

# 数据获取（主循环每帧调用）
dx, dy, left_click = ml.get_delta()

# 事件订阅
ml.emitter.on("GAME_PAUSE", on_pause)
ml.emitter.on("GAME_CONTINUE", on_continue)
ml.emitter.on("GAME_OVER", on_game_over)
```

### 6.4 UI 模块接口（B 的 UI 类）

```python
from ui.core import UI

# 创建 UI
ui = UI(width=1280, height=720, fullscreen=True,
        status_reader=read_status_func,   # 返回 state.json 文本
        camera_reader=read_camera_func)   # 返回 numpy 图像

# 启动（阻塞）
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
| mss | 最新 | 屏幕截图（可选） | 你 |
| pywin32/ctypes | 内置 | Windows API 调用 | D |

### 安装命令

```powershell
pip install pygame pynput pyee ultralytics opencv-python pyserial mss
```

---

## 8. 文件结构

```
Real_fps/
│
├── main.py                  ← 你：主程序入口（YOLO + 状态机 + 串口）
├── D_mouse.py               ← D：鼠标键盘监听模块
├── mouse_test.py            ← D：独立测试脚本
│
├── state.json               ← 运行时生成：你写入，B轮询
│
├── ui/                      ← B + C 的工作目录
│   ├── __init__.py          ← 空（让 ui/ 成为 Python 包）
│   ├── core.py              ← B：UI 主循环、JSON线程、摄像头线程
│   ├── config.py            ← C：颜色、位置、尺寸常量
│   ├── assets.py            ← C：字体/资源加载工具
│   ├── radar.py             ← C：雷达组件
│   ├── hud.py               ← C：HUD面板组件
│   ├── effects.py           ← C：动画效果组件
│   └── demo_reader.py       ← C：自测入口（模拟主程序）
│
├── B_pygame.md              ← B 的任务说明（零基础教程）
├── C_ui_assist.md           ← C 的任务说明（零基础教程）
├── D_mouse.md               ← D 的任务说明（零基础教程）
├── readme.md                ← 本文件
└── requirement.txt          ← 依赖清单
```

---

## 9. 快速开始

### 9.1 克隆与安装

```powershell
# 进入项目目录
cd Real_fps

# 安装依赖
pip install -r requirement.txt

# 如果 requirement.txt 不完整，装全量
pip install pygame pynput pyee ultralytics opencv-python pyserial mss
```

### 9.2 逐个模块验证

**步骤 1：测试 D 的鼠标监听**

```powershell
python D_mouse.py
```
→ 移动鼠标看 dx/dy，按 P 看暂停广播，按 Esc 看结束广播。

**步骤 2：测试 C 的 UI 组件**

```powershell
python ui/demo_reader.py
```
→ 窗口显示雷达旋转、HUD 面板、场景自动切换。

**步骤 3：测试 B 的主 UI**

```powershell
# 终端 1：启动模拟器
python ui/demo_reader.py

# 终端 2：启动 UI
python -c "from ui.core import UI; UI(fullscreen=False).start()"
```
→ 看到准星、目标框、HUD。

**步骤 4：全系统联调**

```powershell
python main.py
```
→ 一切启动，进入完整游戏循环。

### 9.3 运行顺序建议

```
第一天：python D_mouse.py 和 python ui/demo_reader.py
第二天：python -c "from ui.core import UI; UI().start()" + demo_reader
第三天：python main.py（YOLO 单帧）
第四天以后：迭代优化
```

---

## 10. UI 设计规范

### 10.1 风格

- **复古科幻风**（参考 80 年代街机 + 军事 HUD）
- 主色：荧光绿 `(0, 255, 100)`、警示红 `(255, 50, 50)`、深灰黑 `(0, 0, 0)`
- 辅助色：黄 `(255, 200, 0)`、淡蓝白 `(200, 220, 255)`
- 文字和边框带轻微发光效果（用半透明叠加实现）

### 10.2 准星

| 状态 | 颜色 | 动画 |
|------|------|------|
| 默认 | 绿色 | 静态 |
| 目标在准星附近 | 黄色 | 轻微放大 |
| 锁定目标 | 红色 | 缩放脉冲（300ms 1.25x 回弹） |
| 开火 | 红色 | 短暂闪烁 |

### 10.3 HUD 布局

```
┌──────────────────────────────────────────────────┐
│ SCORE: 120                    MODE: TRACKING     │
│ TARGETS: 3                                        │
│ FPS: 60                                           │
│                                                   │
│                                                   │
│                                       ╭──────╮   │
│                                       │雷达   │   │
│                                       │ ●  ●  │   │
│                                       ╰──────╯   │
│                                                   │
│  ─── MODE: TRACKING | SERIAL: OK ───────────────  │
└──────────────────────────────────────────────────┘
```

### 10.4 动画时间轴

| 动画 | 触发 | 时间线 |
|------|------|--------|
| 锁定缩放 | `on_target=true` | 放大 300ms → 回弹 |
| 命中闪光 | `fired=true` | 白屏 alpha=80 → 淡出 300ms |
| 得分弹出 | `delta>0` | 淡入 200ms → 保持 1s → 淡出 400ms |
| 爆头提示 | `reason=headshot` | 大字红色 1.3x 缩放 → 回正 + 淡出 |
| 雷达扫描 | 每帧 | 扫描线匀速旋转 (120°/s) |
| 目标闪烁 | 每帧 | 锁定目标 200ms 周期，普通 400ms 周期 |

---

## 附录 A：状态机定义

```
                    GAME_START
                        │
                        ▼
               ┌────────────────┐
               │    playing     │
               │  (正常运行)     │
               └────┬──────┬────┘
                    │      │
               P键  │      │ Esc
                    │      │
                    ▼      ▼
          ┌──────────┐  ┌──────────┐
          │  paused  │  │   over   │
          │ (暂停)    │  │ (结束)    │
          └────┬─────┘  └──────────┘
               │
          P键  │
               ▼
          ┌──────────┐
          │ playing  │
          │ (恢复)    │
          └──────────┘
```

## 附录 B：串口协议（初版）

```
格式: "X:角度,Y:角度\n"
角度范围: 0-180
示例: "X:120,Y:90\n"

后续可扩展:
- 回中命令: "RESET\n"
- 急停: "STOP\n"
- 查询: "STATUS?\n"
- 响应: "OK:X:120,Y:90\n"
```

---

> 最后更新: 2026-06-02

