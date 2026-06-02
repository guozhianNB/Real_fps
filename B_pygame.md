# B — Pygame UI 渲染（零基础入门版）

> 这份文档是**手把手教程**，假设你只有最基础的 Python 语法知识。
> 每个概念都会先解释「是什么」再告诉你「怎么写」。
> **所有代码都是完整的、可以直接复制运行**。

---

## 目录

1. [你需要先理解的概念](#1-你需要先理解的概念)
2. [安装环境](#2-安装环境)
3. [项目文件结构](#3-项目文件结构)
4. [第一步：创建空白窗口](#4-第一步创建空白窗口)
5. [第二步：在窗口上画东西](#5-第二步在窗口上画东西)
6. [第三步：理解帧率和时钟](#6-第三步理解帧率和时钟)
7. [第四步：读取 JSON 文件](#7-第四步读取-json-文件)
8. [第五步：线程 — 让程序同时做多件事](#8-第五步线程--让程序同时做多件事)
9. [第六步：最终的 UI 核心代码](#9-第六步最终的-ui-核心代码)
10. [第七步：demo_emitter.py — 自己模拟测试](#10-第七步-demo_emitterpy--自己模拟测试)
11. [常见错误与解决](#11-常见错误与解决)

---

## 1. 你需要先理解的概念

### 什么是 Pygame？

Pygame 是一个 Python 库，它可以让你：
- 打开一个**窗口**
- 在窗口里**画图**（圆形、矩形、文字、图片）
- 检测用户的**键盘和鼠标操作**
- 实现**动画**（让画面动起来）

简单说：Pygame = 画板 + 时钟 + 事件检测器。

### 什么是游戏循环（Game Loop）？

几乎所有的游戏和实时程序都是这样工作的：

```
while True:
    处理用户输入（鼠标、键盘）
    更新游戏状态（分数、位置、动画）
    绘制画面（画到窗口上）
    等待一小段时间（控制速度）
```

这个循环每秒会跑很多次（通常是 60 次），所以看起来是流畅的动画。

### 什么是事件（Event）？

事件就是「发生了什么」。比如：
- 用户移动了鼠标 → `MOUSEMOTION` 事件
- 用户按下了键盘 → `KEYDOWN` 事件
- 用户点了关闭按钮 → `QUIT` 事件

Pygame 会把所有事件放在一个**队列**里，你通过 `pygame.event.get()` 取出处理。

### 什么是 JSON？

JSON 是一种**文本格式**，用来在不同程序之间传递数据。它长这样：

```json
{
    "score": 100,
    "mode": "tracking",
    "targets": [
        {"id": 1, "x": 640, "y": 360}
    ]
}
```

你只需要知道两件事：
- `json.loads(字符串)` → 把 JSON 文本变成 Python 字典
- `json.dumps(字典)` → 把 Python 字典变成 JSON 文本

### 什么是线程（Thread）？

线程让程序可以**同时做多件事**。比如：

- **主线程**：负责画 UI（Pygame 窗口）
- **另一个线程**：负责读取 JSON 文件

这样即使 JSON 文件读取慢一点，UI 也不会卡住。

把线程想象成**两条并行的流水线**，互不干扰。

---

## 2. 安装环境

打开终端（Terminal），依次执行：

```powershell
# 安装 Pygame（用于 UI 窗口）
pip install pygame

# 安装 pyee（用于事件广播，C 队友需要）
pip install pyee

# 安装 requests（用于从摄像头服务拉取画面）
pip install requests

# 如果提示 pip 不是命令，用这个：
python -m pip install pygame pyee requests

# 验证是否安装成功（没有报错就 OK）
python -c "import pygame; print('Pygame 版本:', pygame.version.ver)"
```

---

## 3. 项目文件结构

你的代码都放在 `ui/` 文件夹下。C 队友的代码也会放在这里。

```
Real_fps/
├── ui/                       ← 你和 C 的工作目录
│   ├── __init__.py           ← 让 ui/ 成为一个 Python 包（内容可为空）
│   ├── config.py             ← 你和 C 共用的颜色、位置常量
│   ├── core.py               ← 你的核心文件：UI 主循环
│   ├── radar.py              ← C 负责：雷达组件
│   ├── hud.py                ← C 负责：HUD 面板
│   ├── effects.py            ← C 负责：命中动画
│   ├── demo_emitter.py       ← C 负责：模拟器测试脚本
│   └── assets.py             ← C 负责：字体等资源加载
├── D_mouse.py                ← D 队友的鼠标监听模块
├── main.py                   ← 之后主程序会从这里启动
├── readme.md                 ← 项目说明
└── requirement.txt           ← 依赖清单（已更新）
```

**请先在 `Real_fps` 文件夹下手动创建 `ui` 文件夹。**

---

## 4. 第一步：创建空白窗口

先跑通最简单的 Pygame 程序，确保环境没问题。

创建一个文件 `ui/test_window.py`（这只是练习，后面会删掉）：

```python
# ui/test_window.py
# 这是你的第一个 Pygame 程序

import pygame  # 导入 Pygame 库

# ====== 初始化 ======
pygame.init()  # 初始化 Pygame（必须写这行）

# 设置窗口大小：宽 1280 像素，高 720 像素
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# 创建一个窗口，返回一个 "表面"（Surface）
# Surface 就是画板，你在上面画东西
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))

# 设置窗口标题
pygame.display.set_caption("Real FPS - UI Test")

# ====== 游戏循环 ======
running = True  # 控制循环是否继续

while running:  # 只要 running 为 True，就不断循环
    # ---- 1. 处理事件 ----
    for event in pygame.event.get():  # 取出所有待处理的事件
        if event.type == pygame.QUIT:  # 如果用户点了关闭按钮
            running = False  # 退出循环
        elif event.type == pygame.KEYDOWN:  # 如果用户按了键盘
            if event.key == pygame.K_ESCAPE:  # 按的是 ESC 键
                running = False

    # ---- 2. 绘制画面 ----
    screen.fill((0, 0, 0))  # 用黑色填充整个窗口

    # ---- 3. 刷新显示 ----
    pygame.display.flip()  # 把画好的内容显示到屏幕上

# ====== 退出 ======
pygame.quit()  # 关闭 Pygame
```

**运行：**

```powershell
python ui/test_window.py
```

你会看到一个黑色窗口。按 ESC 或点关闭按钮可以退出。

> 💡 **逐行解释：**
> - `pygame.init()` → 打开 Pygame 的"电源开关"
> - `pygame.display.set_mode((宽, 高))` → 创建一个窗口
> - `screen.fill((R, G, B))` → 用颜色填充窗口。`(0,0,0)` 是黑色，`(255,0,0)` 是红色
> - `pygame.display.flip()` → 把画好的内容显示出来（就像翻书一样）
> - `pygame.event.get()` → 获取所有事件（鼠标、键盘、窗口操作）
> - `pygame.quit()` → 关闭 Pygame

---

## 5. 第二步：在窗口上画东西

现在来画一些有用的东西：**圆形（准星）、矩形（目标框）、文字（HUD）**。

创建一个新文件 `ui/test_draw.py`（练习用）：

```python
# ui/test_draw.py
# 学习如何在窗口上画各种图形

import pygame
import sys

# ====== 初始化 ======
pygame.init()

WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Real FPS - Drawing Test")
clock = pygame.time.Clock()  # 时钟，用于控制帧率

# ====== 颜色常量 ======
# RGB = 红绿蓝，每个值 0~255
COLOR_GREEN = (0, 255, 100)     # 准星绿色
COLOR_RED = (255, 50, 50)       # 锁定红色
COLOR_WHITE = (255, 255, 255)   # 白色文字
COLOR_BLACK = (0, 0, 0)         # 黑色背景
COLOR_HUD_BG = (0, 0, 0, 160)   # 半透明黑（注意：pygame 里需要特殊处理）

# ====== 字体 ======
# 创建字体对象，第一个参数是字体名，None 表示用默认字体
# 第二个参数是字号
font_large = pygame.font.Font(None, 48)   # 大号字体（48 像素）
font_small = pygame.font.Font(None, 28)   # 小号字体（28 像素）

# ====== 游戏循环 ======
running = True
frame_count = 0  # 用来计数帧数

while running:
    # ---- 处理事件 ----
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    # ---- 清空画面 ----
    screen.fill(COLOR_BLACK)

    # ========== 1. 画准星（十字线 + 圆环） ==========
    center_x, center_y = WIDTH // 2, HEIGHT // 2  # 画面中心
    crosshair_size = 20  # 准星大小

    # pygame.draw.circle(画板, 颜色, (圆心x, 圆心y), 半径, 线宽)
    # 线宽=0 是实心圆，>0 是空心圆
    pygame.draw.circle(screen, COLOR_GREEN, (center_x, center_y), 15, 2)  # 外圈空心圆
    pygame.draw.circle(screen, COLOR_GREEN, (center_x, center_y), 2, 0)   # 中心实心点

    # 画十字线：两条线，水平和垂直
    # pygame.draw.line(画板, 颜色, 起点, 终点, 线宽)
    pygame.draw.line(screen, COLOR_GREEN, (center_x - 25, center_y), (center_x - 18, center_y), 2)  # 左横线
    pygame.draw.line(screen, COLOR_GREEN, (center_x + 18, center_y), (center_x + 25, center_y), 2)  # 右横线
    pygame.draw.line(screen, COLOR_GREEN, (center_x, center_y - 25), (center_x, center_y - 18), 2)  # 上竖线
    pygame.draw.line(screen, COLOR_GREEN, (center_x, center_y + 18), (center_x, center_y + 25), 2)  # 下竖线

    # ========== 2. 画目标框 ==========
    # 模拟一个目标框：左上角(600,300) 右下角(680,420)
    target_rect = pygame.Rect(600, 300, 80, 120)  # (x, y, 宽, 高)
    pygame.draw.rect(screen, COLOR_RED, target_rect, 2)  # 2 像素宽的红色框

    # ========== 3. 画 HUD 文字 ==========
    # font.render(文字, 抗锯齿, 颜色) → 返回一个文字"图片"
    # 然后通过 blit 把这个"图片"贴到画板上

    # 左上角：Score
    score_text = font_large.render("SCORE: 100", True, COLOR_WHITE)
    screen.blit(score_text, (20, 20))  # (x, y) 是文字左上角的位置

    # 左上角：Targets
    targets_text = font_small.render("TARGETS: 3", True, COLOR_WHITE)
    screen.blit(targets_text, (20, 70))

    # 左上角：FPS
    fps = int(clock.get_fps())  # clock.get_fps() 返回当前帧率
    fps_text = font_small.render(f"FPS: {fps}", True, COLOR_WHITE)
    screen.blit(fps_text, (20, 100))

    # 底部居中：系统状态
    status_text = font_small.render("MODE: tracking  |  SERIAL: connected", True, COLOR_WHITE)
    text_rect = status_text.get_rect(center=(WIDTH // 2, HEIGHT - 30))
    screen.blit(status_text, text_rect)

    # ---- 刷新 ----
    pygame.display.flip()
    clock.tick(60)  # 控制帧率在 60 FPS
    frame_count += 1

pygame.quit()
sys.exit()
```

**运行：** `python ui/test_draw.py`

你应该会看到：
- 绿色准星在画面正中央
- 红色矩形框模拟目标
- 左上角显示 SCORE、TARGETS、FPS
- 底部显示系统状态

> 💡 **核心函数总结：**
>
> | 函数 | 作用 | 参数示例 |
> |------|------|----------|
> | `pygame.draw.circle(surface, color, center, radius, width)` | 画圆 | `(screen, (0,255,0), (640,360), 15, 2)` |
> | `pygame.draw.rect(surface, color, rect, width)` | 画矩形 | `(screen, (255,0,0), Rect(600,300,80,120), 2)` |
> | `pygame.draw.line(surface, color, start, end, width)` | 画线 | `(screen, (0,255,0), (0,0), (100,100), 2)` |
> | `font.render(text, antialias, color)` | 创建文字"图片" | `(font.render("Hello", True, (255,255,255)))` |
> | `surface.blit(source, position)` | 贴图 | `screen.blit(text, (20, 20))` |
> | `clock.tick(fps)` | 控制帧率 | `clock.tick(60)` 每秒最多 60 帧 |

---

## 6. 第三步：理解帧率和时钟

`clock.tick(60)` 做了两件事：
1. **限制速度**：让循环每秒最多执行 60 次（60 FPS）
2. **返回时间**：返回上一帧到这一帧经过的毫秒数

为什么需要限制帧率？
- 不限制的话，程序会跑得飞快，CPU 占用 100%
- 限制后，画面流畅且 CPU 占用低

```python
clock = pygame.time.Clock()

while running:
    dt = clock.tick(60)  # dt = 距上一帧的毫秒数，约 16ms
    # 用 dt 做动画：移动距离 = 速度 × dt/1000
```

---

## 7. 第四步：读取 JSON 文件

这是你工作中最重要的部分：**从 JSON 文件中读取主程序写好的状态数据**。

### 7.1 什么是 JSON 文件读取

```python
import json

# 假设有一个文件 state.json，内容如下：
# {"score": {"value": 100, "delta": 0}, "mode": "tracking"}

# 读取方式：
with open("state.json", "r", encoding="utf-8") as f:
    text = f.read()       # text 是字符串
    data = json.loads(text)  # data 是 Python 字典

# 现在你可以像用字典一样用 data：
print(data["score"]["value"])  # 输出 100
```

### 7.2 异常处理很重要

如果 JSON 文件不存在、或者内容写坏了，程序会崩溃。所以要用 `try/except`：

```python
import json

def read_status():
    """读取状态 JSON 文件，失败时返回空字典"""
    try:
        with open("state.json", "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except FileNotFoundError:
        print("警告：state.json 不存在")
        return {}
    except json.JSONDecodeError:
        print("警告：state.json 格式错误")
        return {}
```

**这就是你 UI 模块读取状态的方式。** 主程序（我）会定时更新 `state.json`，你定时读取它。

### 7.3 主程序会写入的 JSON 结构

主程序会写一个 `state.json` 文件，格式如下（你不需要记，需要时来查）：

```json
{
    "timestamp": 1717320000.0,
    "system_state": {"mode": "playing", "msg": "normal"},
    "fire_state": {"fired": false},
    "score": {"value": 120, "delta": 10, "reason": "hit"},
    "targets": [
        {"id": 3, "class": "person", "conf": 0.94, "bbox": [600, 300, 680, 420], "cx": 640, "cy": 360}
    ],
    "serial": {"status": "OK", "msg": "connected"}
}
```

各字段含义：
- `system_state.mode`：当前状态 `idle` / `playing` / `paused` / `over`
- `fire_state.fired`：是否刚开火（触发闪光动画）
- `score.value`：当前分数，`score.delta`：本帧加了多少分
- `targets`：所有检测到的目标列表
- `serial.status`：串口状态

---

## 8. 第五步：线程 — 让程序同时做多件事

### 8.1 为什么需要线程

你的渲染循环需要每秒刷新 60 次。如果每次刷新都去读硬盘上的 JSON 文件，速度会很慢。

解决方案：**开一个后台线程专门读 JSON**，读完后通过**队列**把结果传给主循环。

### 8.2 什么是队列（Queue）

队列就像一根**管道**：
- 一个线程把数据放进管道（`put`）
- 另一个线程从管道取出数据（`get`）

```python
import queue

q = queue.Queue()

# 线程 A（生产者）
q.put("hello")

# 线程 B（消费者）
data = q.get()  # data = "hello"
```

### 8.3 线程基础

```python
import threading
import time

def background_work():
    """这个函数会在后台运行"""
    count = 0
    while True:
        print(f"后台工作中... {count}")
        count += 1
        time.sleep(1)  # 等 1 秒

# 创建并启动线程
# target=函数名（注意：不要加括号）
# daemon=True 表示"守护线程"，主程序退出时自动结束
thread = threading.Thread(target=background_work, daemon=True)
thread.start()

# 主程序继续做别的事
for i in range(5):
    print(f"主程序工作中... {i}")
    time.sleep(0.5)

# 程序结束后，daemon 线程会自动退出
```

### 8.4 在你的 UI 中的用法

你会创建两个后台线程：
1. **JSON 读取线程**：每 50ms 读一次 `state.json`，结果放入队列
2. **摄像头拉取线程**（见下文）：每 33ms 从 FastAPI 拉取一帧画面

主循环只从队列取数据，不做文件 IO 或网络请求。

---

## 8.5 摄像头画面从哪来？

> ⚠️ **重要：摄像头画面不放在 state.json 里！**
> 它走独立的 FastAPI 服务，UI 通过 HTTP 拉取 JPEG 图片。

### camera_share.py 是什么？

队友在项目根目录下提供了一个 `camera_share.py`，它是一个**独立的摄像头服务**：

```
camera_share.py
  └── FastAPI 服务 (端口 8010)
       └── GET /snapshot → 返回最新摄像头帧的 JPEG 图片
```

它做的事情：
1. 打开你的摄像头（USB 摄像头或笔记本内置摄像头）
2. 在后台线程中持续采集画面
3. 当你访问 `http://127.0.0.1:8010/snapshot` 时，返回最新一帧的 JPEG

### 如何启动它？

你需要**另开一个终端**，先启动摄像头服务：

```powershell
# 终端 1：启动摄像头服务
uvicorn camera_share:app --port 8010 --host 127.0.0.1 --reload
```

看到输出 `摄像头服务已启动` 就说明成功了。

### 你的 UI 怎么拿到画面？

你的 `core.py` 已经集成了摄像头拉取线程。它会：
1. 每 33ms 访问一次 `http://127.0.0.1:8010/snapshot`
2. 拿到 JPEG → 解码为 numpy 数组 → 放入队列
3. 主循环从队列取出 → 转为 Pygame Surface → 铺满全屏

整个流程：

```
camera_share.py         你的 UI (core.py)
  │                          │
  │ 启动后持续采集摄像头      │
  │                          │
  │   GET /snapshot ◄─────── │ 每 33ms 拉取一次
  │   ──── JPEG ──────────► │
  │                          │ 解码 → 转为 Surface
  │                          │ → blit 到屏幕背景
```

### 测试步骤

```powershell
# 终端 1：启动摄像头服务
uvicorn camera_share:app --port 8010 --host 127.0.0.1 --reload

# 终端 2：启动状态模拟器
python ui/demo_emitter.py

# 终端 3：启动 UI
python -c "from ui.core import UI; UI(fullscreen=False).start()"
```

这样你就能看到**摄像头画面作为背景 + 准星/HUD 叠加在上面**的效果了。

### 如果摄像头启动失败怎么办？

- 检查摄像头是否被其他程序占用（如 Zoom、OBS）
- 尝试换个 USB 口
- 如果还是没有画面，UI 会显示黑色背景 + 提示文字，不会崩溃
- 可以在 `camera_share.py` 中修改 `camera_id=0` 为 `camera_id=1` 试试另一个摄像头

---

## 9. 第六步：最终的 UI 核心代码

现在把上面所有知识整合起来。你只需要写三个文件：

### 文件 1：`ui/__init__.py`

```python
# ui/__init__.py
# 这个文件让 ui 文件夹成为一个 Python 包
# 里面什么都不用写，但文件必须存在
```

### 文件 2：`ui/config.py`

这是你和 C 队友**共用**的颜色和位置配置。C 的雷达、HUD 也会从这里读颜色。

```python
# ui/config.py
# 所有 UI 相关的配置常量
# B 和 C 共用这个文件，确保颜色、位置统一

# ====== 窗口设置 ======
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS_TARGET = 60          # 目标帧率

# ====== 颜色 ======
# RGB 颜色：每个值范围 0-255
# (R, G, B) 或 (R, G, B, A) — A 是透明度（Pygame 中需要特殊支持）
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 255, 100)       # 准星/正常状态
COLOR_RED = (255, 50, 50)         # 锁定/警告状态
COLOR_YELLOW = (255, 200, 0)      # 目标锁定过渡色
COLOR_HUD_BG = (0, 0, 0)          # HUD 背景（纯黑，通过透明度 Surface 实现）
HUD_BG_ALPHA = 160                # HUD 背景透明度（0=全透明，255=不透明）

# ====== 布局位置 ======
CROSSHAIR_SIZE = 20     # 准星大小
RADAR_RADIUS = 75        # 雷达半径
RADAR_MARGIN = 20        # 雷达距右下角边距

HUD_MARGIN = 20          # HUD 左上角边距
HUD_LINE_HEIGHT = 35     # HUD 每行高度

# ====== JSON 轮询设置 ======
STATUS_FILE = "state.json"       # 主程序会写入这个文件
JSON_POLL_INTERVAL = 0.05        # 每 50ms 读一次 JSON

# ====== 动画设置 ======
FLASH_DURATION_MS = 300          # 命中闪光持续时间（毫秒）
POPUP_FADEIN_MS = 200            # 提示淡入时间
POPUP_HOLD_MS = 1000             # 提示保持时间
POPUP_FADEOUT_MS = 400           # 提示淡出时间
```

### 文件 3：`ui/core.py` — **最重要的文件**

这是你的主 UI 类。**每一行都有注释，请仔细阅读。**

```python
# ui/core.py
# Real FPS — 主 UI 模块
# 这个文件包含 UI 类，负责：
#   1. 打开 Pygame 窗口
#   2. 后台读取 JSON 状态文件（不阻塞主循环）
#   3. 在窗口上绘制准星、目标框、
#      并调用 C 的雷达、HUD、动画组件
#   4. 支持摄像头画面作为背景

import pygame
import json
import threading
import queue
import time
import sys
import os
import cv2          # 用于解码摄像头 JPEG → numpy
import numpy as np  # 用于图像数据处理

# 导入配置文件
from ui.config import *

# ==============================================
#   UI 类
# ==============================================

class UI:
    """主 UI 类。
    
    用法：
        ui = UI()
        ui.start()   # 开始渲染（这个方法会阻塞，直到窗口关闭）
    """
    
    def __init__(self, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, fullscreen=True):
        """初始化 UI。
        
        参数：
            width: 窗口宽度（像素）
            height: 窗口高度（像素）
            fullscreen: 是否全屏
        """
        self.width = width
        self.height = height
        self.fullscreen = fullscreen
        
        # ---- 数据容器 ----
        # 最新的 JSON 状态（由后台线程更新）
        self.latest_state = {}
        # 最新的摄像头帧（由后台线程更新）
        self.latest_frame = None
        
        # ---- 线程安全队列 ----
        # 后台线程把数据放进队列，主循环从队列取出
        self.event_q = queue.Queue()
        
        # ---- 线程控制 ----
        # threading.Event() 是一个开关
        # .set() = 打开（告诉线程停止）
        # .clear() = 关闭（告诉线程继续工作）
        self._stop_reader = threading.Event()
        
        # ---- 动画相关 ----
        self.clock = pygame.time.Clock()
        self.prev_time = time.time()
        
        # ---- 渲染组件占位 ----
        # C 队友会实现这些类，你拿到后在这里初始化
        # 暂时用 None，等 C 交付后替换
        self.radar = None     # 以后: Radar(...)
        self.hud = None       # 以后: HUD(...)
        self.effects = None   # 以后: Effects(...)
        
        print("[UI] 初始化完成")
    
    # ==========================================
    #   后台线程：JSON 读取
    # ==========================================
    
    def _start_json_reader(self):
        """启动 JSON 读取后台线程。
        
        这个线程每 50ms 读取一次 state.json，
        把内容放进队列，主循环取走。
        """
        def reader_loop():
            """后台循环（在独立线程中运行）"""
            while not self._stop_reader.is_set():
                try:
                    # 尝试读取 JSON 文件
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        text = f.read()
                    # 把文本放进队列，主循环会取走
                    self.event_q.put(("json_text", text))
                except FileNotFoundError:
                    # 文件还不存在，忽略（第一次运行时的正常情况）
                    pass
                except json.JSONDecodeError:
                    # 文件内容损坏，忽略
                    print("[UI] JSON 解析错误")
                    self.event_q.put(("json_text", '{"system_state":{"mode":"error","msg":"JSON parse error"}}'))
                except Exception as e:
                    # 其他错误
                    print(f"[UI] JSON 读取错误: {e}")
                
                # 等待 50ms 再读下一次
                # 不要一直读，否则 CPU 会很高
                time.sleep(JSON_POLL_INTERVAL)
        
        # 创建并启动线程
        # daemon=True: 主程序退出时，这个线程自动结束
        thread = threading.Thread(target=reader_loop, daemon=True)
        thread.start()
        print("[UI] JSON 读取线程已启动")
    
    # ==========================================
    #   后台线程：摄像头画面拉取（从 FastAPI）
    # ==========================================
    
    def _start_camera_reader(self):
        """启动摄像头画面拉取线程。
        
        从 camera_share.py 的 FastAPI 服务拉取 JPEG 图片，
        解码后放入队列供主循环使用。
        
        camera_share 运行方式（需另开终端）：
            uvicorn camera_share:app --port 8010 --host 127.0.0.1 --reload
        """
        import requests  # 注意：需要 pip install requests
        import io
        import numpy as np
        
        CAMERA_URL = "http://127.0.0.1:8010/snapshot"
        
        def reader_loop():
            """后台循环（在独立线程中运行）"""
            fail_count = 0
            while not self._stop_reader.is_set():
                try:
                    # 从 FastAPI 拉取 JPEG 图片
                    resp = requests.get(CAMERA_URL, timeout=1.0)
                    if resp.status_code == 200:
                        # 把 JPEG 字节解码为 numpy 数组（BGR 格式）
                        img_array = np.frombuffer(resp.content, dtype=np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        if frame is not None:
                            # 把 BGR 转为 RGB（Pygame 用 RGB）
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            self.event_q.put(("camera_frame", frame_rgb))
                            fail_count = 0
                        else:
                            fail_count += 1
                    else:
                        fail_count += 1
                except requests.ConnectionError:
                    fail_count += 1
                    if fail_count == 1:  # 只在第一次报错
                        print("[UI] 摄像头服务未启动，请运行: uvicorn camera_share:app --port 8010")
                except Exception as e:
                    fail_count += 1
                    if fail_count == 1:
                        print(f"[UI] 摄像头拉取错误: {e}")
                
                # 每 33ms 拉取一帧（≈30 FPS）
                time.sleep(0.033)
        
        thread = threading.Thread(target=reader_loop, daemon=True)
        thread.start()
        print("[UI] 摄像头拉取线程已启动")
    
    # ==========================================
    #   主循环
    # ==========================================
    
    def start(self):
        """启动 UI（这个方法会阻塞，直到窗口关闭）。"""
        # ---- 初始化 Pygame ----
        pygame.init()
        
        # 创建窗口
        # FULLSCREEN = 全屏，0 = 窗口模式
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        pygame.display.set_caption("Real FPS")
        
        # ---- 启动后台线程 ----
        self._start_json_reader()   # 开始读取 JSON
        self._start_camera_reader() # 开始拉取摄像头画面
        
        # ---- 进入主循环 ----
        print("[UI] 进入主循环")
        self._main_loop()
        
        # ---- 退出 ----
        pygame.quit()
        print("[UI] 已退出")
    
    def stop(self):
        """请求 UI 停止（信号方式）。"""
        self._stop_reader.set()  # 告诉后台线程停止
    
    def _main_loop(self):
        """UI 主循环。
        
        这个循环每秒执行约 60 次。
        每次做三件事：
            1. 处理事件（从队列中取数据）
            2. 更新动画状态
            3. 绘制画面
        """
        running = True
        
        while running:
            # ====== 1. 处理 Pygame 事件（键盘、鼠标、窗口） ======
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
            
            # ====== 2. 处理后台线程发来的数据 ======
            # 一次性取出队列中所有待处理的消息
            try:
                while True:
                    # get_nowait() 不阻塞，没有消息就抛异常
                    evt_type, payload = self.event_q.get_nowait()
                    
                    if evt_type == "json_text":
                        self._apply_json(payload)
                    elif evt_type == "camera_frame":
                        self.latest_frame = payload
                    # 以后可以加更多消息类型
            except queue.Empty:
                # 队列为空，说明没有新消息，继续
                pass
            
            # ====== 3. 计算时间差 ======
            # dt = 上一帧到这一帧的毫秒数
            # 用于动画：让动画速度不受帧率影响
            now = time.time()
            dt_ms = (now - self.prev_time) * 1000
            self.prev_time = now
            
            # ====== 4. 更新动画 ======
            # 以后 C 的 effects 会在这里更新
            # if self.effects:
            #     self.effects.update(dt_ms, self.latest_state)
            
            # ====== 5. 绘制画面 ======
            self._render()
            
            # ====== 6. 刷新显示 ======
            pygame.display.flip()
            
            # ====== 7. 控制帧率 ======
            # clock.tick(FPS_TARGET) 会等待足够的时间，
            # 让循环正好每秒执行 FPS_TARGET 次
            self.clock.tick(FPS_TARGET)
        
        # 退出主循环后，清理
        self.stop()
    
    # ==========================================
    #   JSON 解析
    # ==========================================
    
    def _apply_json(self, text):
        """解析 JSON 文本并更新状态。
        
        如果解析失败，保留上一帧的状态，
        并在 system_state 中标记错误。
        """
        try:
            if text:
                self.latest_state = json.loads(text)
        except json.JSONDecodeError:
            print("[UI] JSON 解析失败，使用上一帧状态")
            # 给状态加一个错误标记（不覆盖原有状态）
            if "system_state" not in self.latest_state:
                self.latest_state["system_state"] = {}
            self.latest_state["system_state"]["mode"] = "error"
            self.latest_state["system_state"]["msg"] = "JSON parse error"
    
    # ==========================================
    #   渲染（核心绘制逻辑）
    # ==========================================
    
    def _render(self):
        """绘制一帧画面。
        
        绘制顺序（从下到上）：
            1. 摄像头背景（从 FastAPI 拉取的画面）
            2. 目标框
            3. 准星
            4. HUD（C 负责）
            5. 雷达（C 负责）
            6. 动画效果（C 负责）
        """
        state = self.latest_state  # 简写
        
        # ---- 1. 背景：摄像头画面 or 黑色 ----
        if self.latest_frame is not None:
            # 把 numpy 数组（RGB）转为 Pygame Surface
            # latest_frame 是 RGB 格式的 numpy 数组
            frame_surface = pygame.surfarray.make_surface(
                self.latest_frame.swapaxes(0, 1)
            )
            # 缩放到窗口大小
            frame_surface = pygame.transform.scale(
                frame_surface, (self.width, self.height)
            )
            self.screen.blit(frame_surface, (0, 0))
        else:
            # 没有摄像头画面时，显示黑色背景 + 提示
            self.screen.fill(COLOR_BLACK)
            if not hasattr(self, '_camera_warned'):
                font = pygame.font.Font(None, 36)
                warn = font.render("等待摄像头画面... 请启动 camera_share.py", True, COLOR_WHITE)
                warn_rect = warn.get_rect(center=(self.width//2, self.height//2))
                self.screen.blit(warn, warn_rect)
                self._camera_warned = True
        
        # ---- 2. 目标框（从 JSON 读取） ----
        # 从 JSON 中读取 targets 列表，为每个目标画框
        targets = state.get("targets", [])
        for target in targets:
            bbox = target.get("bbox")
            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                rect = pygame.Rect(x1, y1, x2 - x1, y2 - y1)
                
                # 所有目标都用绿色框
                pygame.draw.rect(self.screen, COLOR_GREEN, rect, 2)
                
                # 在框上方显示目标 ID 和置信度
                label = f"ID:{target.get('id', '?')} {target.get('conf', 0):.2f}"
                if 'font_small' in dir(self):
                    text = self.font_small.render(label, True, COLOR_GREEN)
                    self.screen.blit(text, (x1, y1 - 20))
        
        # ---- 3. 准星（画面正中央，始终绿色） ----
        center_x, center_y = self.width // 2, self.height // 2
        cs = CROSSHAIR_SIZE
        
        # 准星颜色固定为绿色，只在开火时闪烁一下
        crosshair_color = COLOR_GREEN
        
        # 外圈
        pygame.draw.circle(self.screen, crosshair_color, (center_x, center_y), 15, 2)
        # 中心点
        pygame.draw.circle(self.screen, crosshair_color, (center_x, center_y), 2, 0)
        # 十字线
        pygame.draw.line(self.screen, crosshair_color, (center_x - cs - 5, center_y), (center_x - 18, center_y), 2)
        pygame.draw.line(self.screen, crosshair_color, (center_x + 18, center_y), (center_x + cs + 5, center_y), 2)
        pygame.draw.line(self.screen, crosshair_color, (center_x, center_y - cs - 5), (center_x, center_y - 18), 2)
        pygame.draw.line(self.screen, crosshair_color, (center_x, center_y + 18), (center_x, center_y + cs + 5), 2)
        
        # ---- 4. HUD 信息（直接绘制，方便 C 队友参考） ----
        try:
            font_small = pygame.font.Font(None, 28)
            font_large = pygame.font.Font(None, 48)
            
            # 左上：Score
            score_val = state.get("score", {}).get("value", 0)
            score_surf = font_large.render(f"SCORE: {score_val}", True, COLOR_WHITE)
            self.screen.blit(score_surf, (HUD_MARGIN, HUD_MARGIN))
            
            # 左上：Targets
            target_count = len(targets)
            targets_surf = font_small.render(f"TARGETS: {target_count}", True, COLOR_WHITE)
            self.screen.blit(targets_surf, (HUD_MARGIN, HUD_MARGIN + 40))
            
            # 左上：FPS
            fps = int(self.clock.get_fps())
            fps_surf = font_small.render(f"FPS: {fps}", True, COLOR_WHITE)
            self.screen.blit(fps_surf, (HUD_MARGIN, HUD_MARGIN + 70))
            
            # 底部居中：系统状态
            sys_mode = state.get("system_state", {}).get("mode", "idle")
            sys_msg = state.get("system_state", {}).get("msg", "")
            serial_status = state.get("serial", {}).get("status", "N/A")
            status_text = f"MODE: {sys_mode.upper()}  |  SERIAL: {serial_status}"
            if sys_msg:
                status_text += f"  |  {sys_msg}"
            
            status_surf = font_small.render(status_text, True, COLOR_WHITE)
            status_rect = status_surf.get_rect(center=(self.width // 2, self.height - 30))
            self.screen.blit(status_surf, status_rect)
            
        except Exception as e:
            print(f"[UI] HUD 渲染错误: {e}")
        
        # ---- 5. 调用 C 的组件（以后接入） ----
        # if self.radar:
        #     self.radar.render(self.screen, targets, locked_id)
        # if self.hud:
        #     self.hud.render(self.screen, state, fps)
        # if self.effects:
        #     self.effects.render(self.screen)
    
    # ==========================================
    #   工具方法
    # ==========================================
    
    def get_state(self, key, default=None):
        """安全地获取 JSON 状态中的某个字段。
        
        用法：
            mode = ui.get_state("system_state", {}).get("mode", "idle")
        """
        return self.latest_state.get(key, default)


# ==============================================
#   直接运行此文件时的测试入口
# ==============================================

if __name__ == "__main__":
    print("=== Real FPS UI 测试模式 ===")
    print("按 ESC 或关闭窗口退出")
    print()
    print("提示：请先运行 ui/demo_emitter.py 来模拟主程序输出")
    print()
    
    ui = UI(fullscreen=False)  # 窗口模式，方便调试
    ui.start()
```

---

## 10. 第七步：demo_emitter.py — 自己模拟测试

写完 UI 后，你需要一个**模拟主程序**来测试。这个文件 C 队友会负责完善，但你先用下面这个简化版来验证窗口能打开、准星能显示。

```python
# ui/demo_emitter.py
# 模拟主程序，每隔几秒输出不同的 JSON 状态
# 运行方式：python ui/demo_emitter.py
# 然后在另一个终端运行你的 UI（或者在同一终端运行后按 Ctrl+C 停止）

import json
import time
import os
import sys

# 让 Python 能找到 ui 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def write_status(data):
    """把状态字典写入 state.json"""
    with open("state.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def demo_loop():
    """模拟主程序状态变化"""
    print("=== Demo Emitter 启动 ===")
    print("每 3 秒切换一次状态场景")
    print("按 Ctrl+C 停止\n")
    
    # 场景 1：空闲（没有目标）
    scene_idle = {
        "timestamp": time.time(),
        "system_state": {"mode": "idle", "msg": "等待目标"},
        "fire_state": {"fired": False},
        "score": {"value": 0, "delta": 0, "reason": ""},
        "targets": [],
        "serial": {"status": "OK", "msg": "connected"}
    }
    
    # 场景 2：追踪（一个目标）
    scene_tracking = {
        "timestamp": time.time(),
        "system_state": {"mode": "playing", "msg": "目标已发现"},
        "fire_state": {"fired": False},
        "score": {"value": 0, "delta": 0, "reason": ""},
        "targets": [
            {"id": 1, "class": "person", "conf": 0.85, "bbox": [580, 300, 700, 420], "cx": 640, "cy": 360}
        ],
        "serial": {"status": "OK", "msg": "connected"}
    }
    
    # 场景 3：开火命中
    scene_firing = {
        "timestamp": time.time(),
        "system_state": {"mode": "playing", "msg": "命中！"},
        "fire_state": {"fired": True},
        "score": {"value": 50, "delta": 50, "reason": "hit"},
        "targets": [
            {"id": 1, "class": "person", "conf": 0.94, "bbox": [610, 310, 670, 390], "cx": 640, "cy": 350}
        ],
        "serial": {"status": "OK", "msg": "connected"}
    }
    
    # 场景 4：串口断开
    scene_error = {
        "timestamp": time.time(),
        "system_state": {"mode": "over", "msg": "串口连接断开"},
        "fire_state": {"fired": False},
        "score": {"value": 50, "delta": 0, "reason": ""},
        "targets": [],
        "serial": {"status": "ERROR", "msg": "disconnected"}
    }
    
    scenes = [scene_idle, scene_tracking, scene_firing, scene_error]
    scene_names = ["空闲", "追踪", "开火命中", "串口断开"]
    
    try:
        while True:
            for i, scene in enumerate(scenes):
                print(f"  场景 {i+1}: {scene_names[i]}")
                scene["timestamp"] = time.time()
                write_status(scene)
                time.sleep(3)  # 每个场景持续 3 秒
    except KeyboardInterrupt:
        print("\nDemo Emitter 已停止")

if __name__ == "__main__":
    demo_loop()
```

**测试步骤：**

```powershell
# 终端 1：启动摄像头服务（可选，没有也不影响测试）
uvicorn camera_share:app --port 8010 --host 127.0.0.1 --reload

# 终端 2：启动模拟器
python ui/demo_emitter.py

# 终端 3：启动 UI
python -c "from ui.core import UI; UI(fullscreen=False).start()"
```

> 摄像头服务不是必须的。没有它 UI 会显示黑色背景 + 提示文字，准星和 HUD 依然正常工作。

---

## 11. 常见错误与解决

### ❌ `ModuleNotFoundError: No module named 'pygame'`
→ 没有安装 Pygame。运行 `pip install pygame`

### ❌ `FileNotFoundError: state.json`
→ 正常，第一次运行还没有状态文件。先启动 `demo_emitter.py`

### ❌ 窗口一闪就关闭
→ 检查代码中是否有缩进错误（Python 对缩进敏感）。
   在终端中运行 Python 看报错信息。

### ❌ 画面卡顿 / FPS 低
→ 确保 `clock.tick(60)` 在主循环里。
   检查后台线程是否在循环里做了耗时操作。

### ❌ `pygame.error: video system not initialized`
→ 忘记写 `pygame.init()` 或者在 `pygame.quit()` 之后调用了 Pygame 函数。

### ❌ 四个角出现奇怪的线
→ 可能是准星或目标框的位置计算错了，检查坐标值。

---

## 给你的学习建议

1. **先运行 test_window.py** — 确保 Pygame 能用
2. **再运行 test_draw.py** — 理解绘图函数
3. **然后运行 core.py** — 看看实际 UI 的样子
4. **配合 demo_emitter.py** — 观察 JSON 状态变化时 UI 的变化
5. **最后和 C 对接** — 把 C 的雷达、HUD、动画组件集成进来

记住：**先让程序跑起来，再追求完美。** 有任何一个画面能显示，你就成功了一半。

有问题随时找我！
