# B — Pygame UI 渲染教程

> 👋 你好！这份教程是为你准备的，**不需要你有 Pygame 经验**。
> 每学一个知识点，你就能往最终的 UI 靠近一步。
> **遇到困难很正常，每解决一个 bug 你的编程能力就提高了一截 💪**

---

## 📖 目录

1. [先搞懂几个概念](#1-先搞懂几个概念)
2. [安装环境](#2-安装环境)
3. [项目里已经有什么](#3-项目里已经有什么)
4. [第一步：打开一个窗口](#4-第一步打开一个窗口)
5. [第二步：在窗口上画东西](#5-第二步在窗口上画东西)
6. [第三步：读取 JSON 文件](#6-第三步读取-json-文件)
7. [第四步：实时接收开火事件（UDP）](#7-第四步实时接收开火事件udp)
8. [第五步：线程不卡顿](#8-第五步线程不卡顿)
9. [第六步：摄像头画面做背景](#9-第六步摄像头画面做背景)
10. [第七步：完整的 UI 核心代码](#10-第七步完整的-ui-核心代码)
11. [常见问题](#11-常见问题)

---

## 1. 先搞懂几个概念

### 什么是 Pygame？

Pygame 帮你做三件事：
1. **开一个窗口** — 就像打开画图软件
2. **在窗口上画图** — 画圆、画方块、写文字
3. **知道用户在干嘛** — 按键盘了？点鼠标了？

```python
import pygame
pygame.init()                            # 开机
screen = pygame.display.set_mode((800, 600))  # 窗口
pygame.display.flip()                    # 显示
```

### 什么是游戏循环？

所有实时程序都这样工作：

```python
while True:
    处理输入        # 用户按了什么键？
    更新状态        # 分数变了没？动画到哪了？
    绘制画面        # 画到窗口上
    等一小会儿      # 控制速度，别跑太快
```

这个循环每秒跑 60 次，看起来就是流畅的动画。

### 什么是 Surface？

**Surface = 画板**

- `screen` 就是整个窗口的画板
- 你也可以创建**独立的小画板**，画好东西再贴到大画板上
- 贴图用 `blit`（读作"布利特"）

```python
# 创建一个小画板
my_surface = pygame.Surface((200, 200))
# 在小画板上画个圆
pygame.draw.circle(my_surface, (0, 255, 0), (100, 100), 50)
# 贴到主窗口上
screen.blit(my_surface, (100, 100))
```

### 什么是事件？

事件就是"发生了什么"：
- 用户点了关闭 → `pygame.QUIT`
- 用户按了键盘 → `pygame.KEYDOWN`
- 用户动了鼠标 → `pygame.MOUSEMOTION`

你通过 `pygame.event.get()` 一次性取出所有待处理的事件。

---

## 2. 安装环境

```powershell
pip install pygame requests opencv-python numpy
```

装好后验证一下（没有报错就 OK）：

```powershell
python -c "import pygame; print('Pygame 版本:', pygame.version.ver)"
```

---

## 3. 项目里已经有什么

先看看你的工作目录，心里有个底：

```
Real_fps/
├── ui/                     ← 你和 C 的工作目录（还没创建，现在就去建！）
├── vision/                 ← 视觉模块（别人写好的，你直接调用）
│   ├── camera_share.py     ← 摄像头服务（提供画面）
│   ├── vision.py           ← YOLO 人体跟踪
│   └── get_camera.py       ← 获取摄像头画面的工具
├── main.py                 ← 主程序（写 state.json 的人）
├── fire_notifier.py        ← 开火事件 UDP 广播（你要用它）
├── mouse.py                ← 鼠标监听模块
├── start.py                ← 一键启动
└── 教学参考文档/            ← 你们的学习资料
```

> 🎯 **你的任务：** 写 `ui/core.py`，打开 Pygame 窗口，显示摄像头背景、准星、目标框，调用 C 的组件。

**现在就去 `Real_fps` 文件夹下创建一个 `ui` 文件夹。**

---

## 4. 第一步：打开一个窗口

创建一个文件 `ui/test_window.py`，先确认 Pygame 能跑：

```python
# ui/test_window.py
import pygame
import sys

pygame.init()
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("我的第一个窗口 🎉")
clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    screen.fill((0, 0, 0))        # 黑色背景
    pygame.display.flip()         # 刷新
    clock.tick(60)                # 每秒 60 帧

pygame.quit()
sys.exit()
```

```powershell
python ui/test_window.py
```

看到一个黑色窗口了吗？🎉 如果没有，检查是不是在 `Real_fps` 目录下运行的。

---

## 5. 第二步：在窗口上画东西

现在学怎么画准星、目标框、文字。创建一个 `ui/test_draw.py`：

```python
# ui/test_draw.py
import pygame
import sys

pygame.init()
WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("画图练习 🎨")
clock = pygame.time.Clock()

# 定义颜色（RGB，每个值 0~255）
GREEN = (0, 255, 100)
RED   = (255, 50, 50)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# 字体
font_large = pygame.font.Font(None, 48)
font_small = pygame.font.Font(None, 28)

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    screen.fill(BLACK)

    # ====== 画准星（画面正中央）======
    cx, cy = WIDTH // 2, HEIGHT // 2
    pygame.draw.circle(screen, GREEN, (cx, cy), 15, 2)       # 外圈
    pygame.draw.circle(screen, GREEN, (cx, cy), 2, 0)        # 中心点
    # 十字线
    pygame.draw.line(screen, GREEN, (cx - 25, cy), (cx - 18, cy), 2)
    pygame.draw.line(screen, GREEN, (cx + 18, cy), (cx + 25, cy), 2)
    pygame.draw.line(screen, GREEN, (cx, cy - 25), (cx, cy - 18), 2)
    pygame.draw.line(screen, GREEN, (cx, cy + 18), (cx, cy + 25), 2)

    # ====== 画目标框（模拟一个人）======
    rect = pygame.Rect(600, 300, 80, 120)
    pygame.draw.rect(screen, RED, rect, 2)

    # ====== 写文字 ======
    score_text = font_large.render("SCORE: 100", True, WHITE)
    screen.blit(score_text, (20, 20))

    fps = int(clock.get_fps())
    fps_text = font_small.render(f"FPS: {fps}", True, WHITE)
    screen.blit(fps_text, (20, 70))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
```

> 💡 **核心函数速查：**
>
> | 你要做什么 | 怎么写 |
> |-----------|--------|
> | 画空心圆 | `pygame.draw.circle(画板, 颜色, 圆心, 半径, 线宽)` |
> | 画矩形框 | `pygame.draw.rect(画板, 颜色, Rect(x,y,w,h), 线宽)` |
> | 画直线 | `pygame.draw.line(画板, 颜色, 起点, 终点, 线宽)` |
> | 写文字 | `字体.render("文字", True, 颜色)` → `画板.blit(文字图片, 位置)` |
> | 贴图 | `画板.blit(要贴的东西, (x, y))` |

---

## 6. 第三步：读取 JSON 文件

主程序（`main.py`）会不断地把**当前状态**写到 `state.json` 里。你的 UI 需要定时去读它。

### state.json 长什么样

```json
{
    "timestamp": 1717320000.0,
    "system_state": {"mode": "playing", "msg": "normal"},
    "score": {"value": 120},
    "targets": [
        {"id": 3, "bbox": [600, 300, 680, 420]}
    ],
    "serial": {"status": "OK", "msg": "connected"}
}
```

### 怎么读

```python
import json

def read_status():
    """读取 state.json，失败时返回空字典"""
    try:
        with open("state.json", "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return {}           # 文件还没生成，正常
    except json.JSONDecodeError:
        return {}           # 文件写坏了，忽略
```

> ⚠️ **注意：开火事件不在 JSON 里！** 开火是事件，走 UDP 实时通知（见下一节）。

---

## 7. 第四步：实时接收开火事件（UDP）

开火是**事件**，不是状态。如果放在 JSON 里轮询，最快也要 50ms 才能发现，动画就会延迟。

解决方案：**UDP 广播**。主程序开火的瞬间发一个数据包，你的 UI 立刻收到。

### 怎么用

```python
from fire_notifier import FireListener

# 创建监听器（后台线程自动运行）
listener = FireListener(callback=my_callback)
listener.start()

# 回调函数（开火时被自动调用）
def my_callback(event):
    hit_zone = event.get("hit_zone", "")        # "head" 或 "body"
    score_delta = event.get("score_delta", 0)   # 50 或 10
    print(f"🔥 开火！{hit_zone} +{score_delta}")
```

### 在 Pygame 里用的标准做法

因为回调在**后台线程**运行，不能直接操作 Pygame，所以用 `pygame.event.post()` 把事件转到主循环：

```python
import pygame
from fire_notifier import FireListener

FIRE_EVENT = pygame.USEREVENT + 1  # 自定义事件编号

def on_fire(event):
    """后台线程收到 UDP 开火 → 转到 Pygame 主循环"""
    pygame.event.post(pygame.event.Event(FIRE_EVENT, event))

fire_listener = FireListener(callback=on_fire)
fire_listener.start()

# 在主循环中：
for event in pygame.event.get():
    if event.type == FIRE_EVENT:
        hit_zone = event.__dict__.get("hit_zone", "")
        score_delta = event.__dict__.get("score_delta", 0)
        # 触发命中闪光 + 得分弹出
        effects.add_hit_flash(hit_zone, score_delta)
```

---

## 8. 第五步：线程不卡顿

如果每帧都去读硬盘文件，程序会卡。解决方案：**后台线程读 JSON，主循环只管画**。

### 用队列（Queue）在线程之间传数据

```python
import threading
import queue
import json
import time

event_q = queue.Queue()  # 线程安全的管道

def json_reader():
    """后台线程：每 50ms 读一次 state.json"""
    while True:
        try:
            with open("state.json", "r") as f:
                text = f.read()
            event_q.put(("json", text))   # 放入队列
        except FileNotFoundError:
            pass
        time.sleep(0.05)

# 启动后台线程
thread = threading.Thread(target=json_reader, daemon=True)
thread.start()

# 主循环中：
while running:
    try:
        while True:
            msg_type, payload = event_q.get_nowait()
            if msg_type == "json":
                state = json.loads(payload)  # 解析 JSON
    except queue.Empty:
        pass
    # ... 画画面 ...
```

---

## 9. 第六步：摄像头画面做背景

项目已经提供了现成的工具函数，你直接调用就行：

```python
from vision.get_camera import get_camera_frame
import cv2

frame = get_camera_frame()
if frame is not None:
    # BGR → RGB（Pygame 用 RGB）
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    # numpy 数组 → Pygame Surface
    surf = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
    surf = pygame.transform.scale(surf, (WIDTH, HEIGHT))
    screen.blit(surf, (0, 0))
```

> 💡 **没有摄像头怎么办？** UI 不会崩溃，会显示黑色背景 + 提示文字。

---

## 10. 第七步：完整的 UI 核心代码

把前面所有知识整合起来。这是你的最终作品——**`ui/core.py`**。

每一行都有注释，**看不懂的地方先跳过，跑起来再说**。

```python
# ui/core.py
# Real FPS — 主 UI 模块
#
# 功能：
#   1. 打开 Pygame 窗口
#   2. 后台线程读取 state.json + 拉取摄像头画面
#   3. 显示摄像头背景、准星、目标框
#   4. 通过 UDP 实时接收开火事件
#   5. 调用 C 的雷达、HUD、动画组件
#
# 运行：
#   from ui.core import UI
#   UI(fullscreen=False).start()

import pygame
import json
import threading
import queue
import time
import cv2
import numpy as np
from pathlib import Path

# ====== 配置常量（直接写在这里，简单明了）======
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
CROSSHAIR_SIZE = 20
HUD_MARGIN = 20

COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 255, 100)
COLOR_RED = (255, 50, 50)

STATUS_FILE = "state.json"
FIRE_EVENT = pygame.USEREVENT + 1  # UDP 开火事件的自定义编号


class UI:
    """主 UI 类。调用 start() 后一直运行，直到窗口关闭。"""

    def __init__(self, fullscreen=False):
        self.fullscreen = fullscreen

        # 数据容器（后台线程写，主循环读）
        self.latest_state = {}
        self.latest_frame = None
        self.event_q = queue.Queue()
        self._stop = threading.Event()

        # 动画相关
        self.clock = pygame.time.Clock()
        self.prev_time = time.time()

        # C 的组件（暂时 None，等你集成）
        self.radar = None
        self.hud = None
        self.effects = None

        print("[UI] 初始化完成，准备起飞 🚀")

    # --------------------------------------------------
    #  启动后台线程
    # --------------------------------------------------

    def _start_json_reader(self):
        """后台：每 50ms 读一次 state.json"""
        def loop():
            while not self._stop.is_set():
                try:
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        self.event_q.put(("json", f.read()))
                except FileNotFoundError:
                    pass
                except json.JSONDecodeError:
                    pass
                time.sleep(0.05)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _start_camera_reader(self):
        """后台：每 33ms 拉取一帧摄像头画面"""
        import requests

        def loop():
            while not self._stop.is_set():
                try:
                    resp = requests.get("http://127.0.0.1:8010/snapshot", timeout=1.0)
                    if resp.status_code == 200:
                        arr = np.frombuffer(resp.content, dtype=np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            self.event_q.put(("camera", rgb))
                except Exception:
                    pass
                time.sleep(0.033)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _start_fire_listener(self):
        """后台：UDP 监听开火事件"""
        from fire_notifier import FireListener

        def on_fire(event):
            pygame.event.post(pygame.event.Event(FIRE_EVENT, event))

        self._fire_listener = FireListener(callback=on_fire)
        self._fire_listener.start()

    # --------------------------------------------------
    #  启动 UI（阻塞，直到窗口关闭）
    # --------------------------------------------------

    def start(self):
        pygame.init()

        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT), flags
        )
        pygame.display.set_caption("Real FPS")

        # 启动后台线程
        self._start_json_reader()
        self._start_camera_reader()
        self._start_fire_listener()

        print("[UI] 进入主循环")
        self._main_loop()

        # 清理
        self._stop.set()
        if hasattr(self, '_fire_listener'):
            self._fire_listener.stop()
        pygame.quit()
        print("[UI] 已退出")

    # --------------------------------------------------
    #  主循环
    # --------------------------------------------------

    def _main_loop(self):
        running = True

        while running:
            # ---- 1. 处理 Pygame 事件 ----
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == FIRE_EVENT:
                    # 收到 UDP 开火事件！
                    if self.effects:
                        hit_zone = event.__dict__.get("hit_zone", "")
                        score_delta = event.__dict__.get("score_delta", 0)
                        self.effects.add_hit_flash(hit_zone, score_delta)

            # ---- 2. 处理后台线程发来的数据 ----
            try:
                while True:
                    typ, payload = self.event_q.get_nowait()
                    if typ == "json":
                        self.latest_state = json.loads(payload)
                    elif typ == "camera":
                        self.latest_frame = payload
            except queue.Empty:
                pass

            # ---- 3. 更新时间 ----
            now = time.time()
            dt_ms = (now - self.prev_time) * 1000
            self.prev_time = now

            # ---- 4. 更新动画 ----
            if self.effects:
                self.effects.update(dt_ms)

            # ---- 5. 绘制 ----
            self._render()

            # ---- 6. 刷新 ----
            pygame.display.flip()
            self.clock.tick(FPS)

    # --------------------------------------------------
    #  绘制
    # --------------------------------------------------

    def _render(self):
        state = self.latest_state

        # ---- 背景：摄像头画面或黑色 ----
        if self.latest_frame is not None:
            surf = pygame.surfarray.make_surface(
                self.latest_frame.swapaxes(0, 1)
            )
            surf = pygame.transform.scale(surf, (SCREEN_WIDTH, SCREEN_HEIGHT))
            self.screen.blit(surf, (0, 0))
        else:
            self.screen.fill(COLOR_BLACK)

        # ---- 目标框 ----
        targets = state.get("targets", [])
        for t in targets:
            bbox = t.get("bbox")
            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                rect = pygame.Rect(x1, y1, x2 - x1, y2 - y1)
                pygame.draw.rect(self.screen, COLOR_GREEN, rect, 2)

        # ---- 准星 ----
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        cs = CROSSHAIR_SIZE
        pygame.draw.circle(self.screen, COLOR_GREEN, (cx, cy), 15, 2)
        pygame.draw.circle(self.screen, COLOR_GREEN, (cx, cy), 2, 0)
        pygame.draw.line(self.screen, COLOR_GREEN, (cx - cs - 5, cy), (cx - 18, cy), 2)
        pygame.draw.line(self.screen, COLOR_GREEN, (cx + 18, cy), (cx + cs + 5, cy), 2)
        pygame.draw.line(self.screen, COLOR_GREEN, (cx, cy - cs - 5), (cx, cy - 18), 2)
        pygame.draw.line(self.screen, COLOR_GREEN, (cx, cy + 18), (cx, cy + cs + 5), 2)

        # ---- HUD 信息 ----
        try:
            font_large = pygame.font.Font(None, 48)
            font_small = pygame.font.Font(None, 28)

            score = state.get("score", {}).get("value", 0)
            text = font_large.render(f"SCORE: {score}", True, COLOR_WHITE)
            self.screen.blit(text, (HUD_MARGIN, HUD_MARGIN))

            fps = int(self.clock.get_fps())
            text = font_small.render(f"FPS: {fps}", True, COLOR_WHITE)
            self.screen.blit(text, (HUD_MARGIN, HUD_MARGIN + 50))

            mode = state.get("system_state", {}).get("mode", "idle")
            serial = state.get("serial", {}).get("status", "N/A")
            text = font_small.render(
                f"MODE: {mode.upper()}  |  SERIAL: {serial}", True, COLOR_WHITE
            )
            rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 30))
            self.screen.blit(text, rect)
        except Exception:
            pass

        # ---- 调用 C 的组件 ----
        if self.radar:
            self.radar.render(self.screen, targets, dt_ms=16)
        if self.hud:
            self.hud.render(self.screen, state, int(self.clock.get_fps()), 16)
        if self.effects:
            self.effects.render(self.screen)


# ====== 测试入口 ======
if __name__ == "__main__":
    print("=== Real FPS UI ===")
    print("按 ESC 退出")
    UI(fullscreen=False).start()
```

---

## 11. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: No module named 'pygame'` | 没装 Pygame | `pip install pygame` |
| `FileNotFoundError: state.json` | 还没启动主程序 | 先运行 `python start.py`，或自己建一个 |
| 窗口一闪就关 | 代码有语法错误 | 看终端报错信息 |
| 画面卡顿 FPS 低 | 主循环里有耗时操作 | 确保文件读取和网络请求在后台线程 |
| 没有摄像头画面 | 没启动摄像头服务 | 运行 `uvicorn vision.camera_share:app --port 8010` |
| 开火动画不触发 | UDP 监听没启动 | 检查 `FireListener` 是否调了 `start()` |

---

## 🎯 你的学习路线

1. **运行 `ui/test_window.py`** — 确保 Pygame 能用 ✅
2. **运行 `ui/test_draw.py`** — 学会画准星、目标框 ✅
3. **理解 `state.json` 怎么读** — 第 6 节
4. **理解 `FireListener` 怎么用** — 第 7 节
5. **运行 `ui/core.py`** — 看到完整的 UI 🎉
6. **和 C 对接** — 把 C 的雷达、HUD、动画组件集成进来
7. **一起配合 `main.py` 和 `start.py` 测试完整流程**

**记住：先让程序跑起来，再追求完美。能看到窗口显示出来，你就成功了 80%！💪**
