# D — 鼠标 & 键盘监听模块（零基础入门版）

> 这份文档是**手把手教程**，假设你只有最基础的 Python 语法知识。
> 每个概念都会先解释「是什么」再告诉你「怎么写」。
> **所有代码都是完整的、可以直接复制运行**。

你的任务是写一个**鼠标键盘监听库**，让主程序（我）可以：
1. 拿到鼠标的**相对位移** `dx`, `dy`
2. 知道**左键是否按下**（开火）
3. 按 `P` 键**暂停/继续**游戏
4. 按 `Esc` 键**结束**游戏
5. 游戏运行时把鼠标**锁在屏幕中心**

---

## 目录

1. [你需要先理解的概念](#1-你需要先理解的概念)
2. [安装环境](#2-安装环境)
3. [第一步：pynput 监听鼠标移动](#3-第一步pynput-监听鼠标移动)
4. [第二步：计算相对位移 dx dy](#4-第二步计算相对位移-dx-dy)
5. [第三步：检测鼠标左键点击](#5-第三步检测鼠标左键点击)
6. [第四步：检测键盘按键 P 和 Esc](#6-第四步检测键盘按键-p-和-esc)
7. [第五步：死区和平滑滤波](#7-第五步死区和平滑滤波)
8. [第六步：线程安全 — 用队列传递数据](#8-第六步线程安全--用队列传递数据)
9. [第七步：鼠标回中 — 锁在屏幕中心](#9-第七步鼠标回中--锁在屏幕中心)
10. [第八步：pyee 广播 — 响应主程序控制](#10-第八步pyee-广播--响应主程序控制)
11. [第九步：最终代码 D_mouse.py](#11-第九步最终代码-d_mousepy)
12. [第十步：测试脚本 mouse_test.py](#12-第十步测试脚本-mouse_testpy)
13. [常见错误与解决](#13-常见错误与解决)

---

## 1. 你需要先理解的概念

### pynput 是什么？

`pynput` 是一个 Python 库，它可以监听**鼠标**和**键盘**的实时操作。

```python
from pynput.mouse import Listener as MouseListener

# 当鼠标移动时，这个函数会被自动调用
def on_move(x, y):
    print(f"鼠标移动到: ({x}, {y})")

# 启动监听器（在后台线程中运行）
with MouseListener(on_move=on_move) as listener:
    listener.join()  # 等待（阻塞）
```

### 什么是回调函数？

**回调函数**就是「你写好一个函数，交给 pynput，当某个事件发生时 pynput 自动调用它」。

比如：
- 鼠标移动时 → 调用 `on_move(x, y)`
- 鼠标点击时 → 调用 `on_click(x, y, button, pressed)`
- 按下键盘时 → 调用 `on_press(key)`

### 什么是相对位移（dx, dy）？

- **绝对坐标**：鼠标在整个屏幕上的位置 `(x, y)`
- **相对位移**：鼠标「刚才到现在的移动量」`(dx, dy)`

```
假设上一帧鼠标在 (500, 300)
这一帧鼠标在 (520, 310)
那么 dx = 20, dy = 10（向右移了 20，向下移了 10）
```

**你需要计算 dx, dy 给主程序**，主程序用它算云台角度。

### 什么是线程？

见 B 的教程（线程让程序同时做多件事）。
你的监听器运行在**后台线程**，主程序通过**队列**取数据。

### 什么是死区（Deadzone）？

鼠标在桌上不动时，传感器会有**微小抖动**（比如 dx=1, dy=0）。
死区就是**忽略小数值**：如果 `|dx| < 死区阈值`，就当 dx = 0。

```
deadzone = 3
原始 dx = 2  → 最终 dx = 0（被死区过滤了）
原始 dx = 5  → 最终 dx = 5（超过了阈值）
```

### 什么是 pyee？

`pyee` 是 Python 版的**事件广播系统**。它让不同模块之间可以这样通信：

```python
from pyee import EventEmitter

emitter = EventEmitter()

# 订阅事件
emitter.on("GAME_START", lambda: print("游戏开始！"))

# 广播事件
emitter.emit("GAME_START")  # → 打印 "游戏开始！"
```

主程序（我）会用 pyee 广播 `GAME_START`、`GAME_PAUSE` 等事件，你的模块需要**订阅**这些事件并做出反应。

---

## 2. 安装环境

打开终端（Terminal），依次执行：

```powershell
# 安装 pynput（鼠标键盘监听）
pip install pynput

# 安装 pyee（事件广播）
pip install pyee

# 如果 pip 不行，用这个：
python -m pip install pynput pyee

# 验证安装
python -c "import pynput; print('pynput 版本:', pynput.__version__)"
python -c "import pyee; print('pyee 可用')"
```

---

## 3. 第一步：pynput 监听鼠标移动

先写一个最简单的脚本，确保 pynput 能用。

创建 `test_mouse.py`（练习用，后面会删）：

```python
# test_mouse.py
# 最简单的鼠标监听测试

from pynput.mouse import Listener

def on_move(x, y):
    """鼠标移动时被调用。
    
    参数：
        x: 鼠标当前的屏幕 x 坐标
        y: 鼠标当前的屏幕 y 坐标
    """
    print(f"鼠标位置: ({x}, {y})")

def on_click(x, y, button, pressed):
    """鼠标点击时被调用。
    
    参数：
        x, y: 点击时的坐标
        button: 哪个按钮（Button.left, Button.right 等）
        pressed: True=按下, False=松开
    """
    action = "按下" if pressed else "松开"
    print(f"鼠标{action}: ({x}, {y}) 按钮={button}")

print("=== 鼠标监听测试 ===")
print("移动鼠标或点击，观察输出")
print("按 Ctrl+C 停止\n")

# 创建监听器
# on_move=on_move 的意思是：当鼠标移动时，调用 on_move 函数
# on_click=on_click 的意思是：当鼠标点击时，调用 on_click 函数
with Listener(on_move=on_move, on_click=on_click) as listener:
    listener.join()  # 一直等待，直到监听器停止
```

**运行：** `python test_mouse.py`

移动鼠标和点击，你会看到实时输出。

> 💡 **关于 with 语句：**
> `with Listener(...) as listener:` 会自动管理监听器的启动和停止。
> 离开 with 块时，监听器自动关闭。

---

## 4. 第二步：计算相对位移 dx dy

pynput 的 `on_move` 给的是**绝对坐标**，你需要自己算**相对位移**。

原理很简单：记住上一次的坐标，用当前坐标减掉它。

```python
# test_delta.py
# 计算鼠标相对位移

from pynput.mouse import Listener

class DeltaTracker:
    """跟踪鼠标的相对位移。"""
    
    def __init__(self):
        # 上一次的鼠标位置（初始为 None）
        self.last_x = None
        self.last_y = None
        # 当前的位移
        self.dx = 0
        self.dy = 0
    
    def on_move(self, x, y):
        """鼠标移动时的回调。
        
        计算 dx, dy 并更新 last_x, last_y。
        """
        if self.last_x is not None:
            # 计算位移 = 当前位置 - 上一位置
            self.dx = x - self.last_x
            self.dy = y - self.last_y
        
        # 更新"上一次位置"
        self.last_x = x
        self.last_y = y
    
    def get_delta(self):
        """获取当前位移并清零。
        
        返回 (dx, dy)，然后重置为 0。
        这样每次调用只拿到"新产生的"位移。
        """
        dx, dy = self.dx, self.dy
        self.dx = 0
        self.dy = 0
        return dx, dy


tracker = DeltaTracker()

print("=== 相对位移测试 ===")
print("移动鼠标观察 dx, dy")
print("按 Ctrl+C 停止\n")

with Listener(on_move=tracker.on_move) as listener:
    try:
        while True:
            dx, dy = tracker.get_delta()
            if dx != 0 or dy != 0:
                print(f"dx={dx:4d}  dy={dy:4d}")
            import time
            time.sleep(0.05)  # 每 50ms 打印一次
    except KeyboardInterrupt:
        print("\n停止")
```

**关键点：** `get_delta()` 返回后会把 `dx, dy` 清零。这叫**消费式读取**——每次拿到的都是"新数据"，不会重复。

---

## 5. 第三步：检测鼠标左键点击

用 `on_click` 回调，判断 `button` 是不是左键，`pressed` 是不是按下。

```python
from pynput.mouse import Listener, Button

class MouseTracker:
    """跟踪鼠标的位移和左键状态。"""
    
    def __init__(self):
        self.last_x = None
        self.last_y = None
        self.dx = 0
        self.dy = 0
        self.left_click = False  # 左键是否按下
    
    def on_move(self, x, y):
        if self.last_x is not None:
            self.dx += x - self.last_x
            self.dy += y - self.last_y
        self.last_x = x
        self.last_y = y
    
    def on_click(self, x, y, button, pressed):
        """鼠标点击回调。
        
        button 可以是：
            Button.left   = 左键
            Button.right  = 右键
            Button.middle = 中键
        """
        if button == Button.left:
            self.left_click = pressed  # True=按下, False=松开
            if pressed:
                print("  ▶ 开火！")
    
    def get_delta(self):
        """返回 (dx, dy, left_click)。"""
        dx, dy = self.dx, self.dy
        self.dx = 0
        self.dy = 0
        left = self.left_click
        # 注意：left_click 不清零！主程序自己判断变化
        return dx, dy, left
```

---

## 6. 第四步：检测键盘按键 P 和 Esc

pynput 也能监听键盘。你需要同时监听鼠标和键盘。

```python
from pynput.keyboard import Listener as KeyboardListener, Key

def on_press(key):
    """键盘按下回调。
    
    参数 key 可以是：
        Key.esc     = Esc 键
        Key.space   = 空格键
        Key.enter   = 回车键
        普通按键     = 用 key.char，比如 'p', 'a', '1'
    """
    try:
        if key == Key.esc:
            print("  ▶ Esc 按下 → 游戏结束")
        elif hasattr(key, 'char') and key.char == 'p':
            print("  ▶ P 按下 → 暂停/继续")
    except AttributeError:
        # 特殊按键（比如 Shift、Ctrl）没有 char 属性
        pass

# 同时监听键盘和鼠标
# 注意：键盘和鼠标的 Listener 要分别创建
from pynput.mouse import Listener as MouseListener

with MouseListener(on_move=..., on_click=...) as mouse_listener:
    with KeyboardListener(on_press=on_press) as keyboard_listener:
        mouse_listener.join()
```

**但是** `Listener.join()` 会阻塞（卡住不动）。
为了让它们同时工作，你需要把键盘监听器放到**另一个线程**里。

---

## 7. 第五步：死区和平滑滤波

### 7.1 死区

死区 = 忽略微小抖动：

```python
def apply_deadzone(value, threshold):
    """如果 |value| < threshold，返回 0，否则返回原值。"""
    if abs(value) < threshold:
        return 0
    return value

# 用法：
dx = apply_deadzone(raw_dx, 2)  # 忽略 |dx| < 2 的抖动
```

### 7.2 滑动平均滤波

平滑 = 取最近几次的平均值，让手感更顺滑：

```python
from collections import deque

class SmoothFilter:
    """滑动平均滤波器。
    
    把最近 N 个值取平均，减少突变。
    """
    
    def __init__(self, window_size=3):
        self.window_size = window_size
        # deque 是一个"先进先出"的队列
        # maxlen 满了后，自动丢弃最早的值
        self.buffer_x = deque(maxlen=window_size)
        self.buffer_y = deque(maxlen=window_size)
    
    def apply(self, dx, dy):
        """输入原始 dx, dy，返回平滑后的值。"""
        self.buffer_x.append(dx)
        self.buffer_y.append(dy)
        
        # 取平均
        smooth_x = sum(self.buffer_x) / len(self.buffer_x)
        smooth_y = sum(self.buffer_y) / len(self.buffer_y)
        
        return smooth_x, smooth_y

# 用法：
filter = SmoothFilter(window_size=3)
smooth_dx, smooth_dy = filter.apply(raw_dx, raw_dy)
```

**window_size 越大越平滑，但响应也越慢。** 建议 3~5。

---

## 8. 第六步：线程安全 — 用队列传递数据

pynput 的回调在**后台线程**中运行，主程序在**主线程**中运行。
你需要用**队列**来安全地传递数据。

```python
import queue

data_queue = queue.Queue()

# 在 pynput 回调中（后台线程）：
def on_move(x, y):
    data_queue.put(("move", dx, dy))  # 放入队列

# 在主程序中（主线程）：
def get_delta():
    """从队列中取出所有待处理的数据。"""
    total_dx = 0
    total_dy = 0
    
    try:
        while True:
            event_type, dx, dy = data_queue.get_nowait()
            total_dx += dx
            total_dy += dy
    except queue.Empty:
        pass
    
    return total_dx, total_dy
```

`get_nowait()` 不会阻塞——有数据就取，没数据就抛 `queue.Empty`。

---

## 9. 第七步：鼠标回中 — 锁在屏幕中心

游戏运行时，需要把鼠标**固定在屏幕正中心**，否则游标会跑到窗口外。

用 `pyautogui` 或 `ctypes`（Windows）把鼠标移回中心：

```python
import ctypes

def center_mouse(screen_width, screen_height):
    """把鼠标移到屏幕中心。
    
    Windows 上用 ctypes 调用系统 API 来移动鼠标。
    """
    center_x = screen_width // 2
    center_y = screen_height // 2
    ctypes.windll.user32.SetCursorPos(center_x, center_y)
```

> ⚠️ **注意：** 移动鼠标也会触发 `on_move` 回调！
> 你需要在回中时**标记一下**，忽略这次移动产生的位移。

做法：用一个标志 `_centering`，回中前设为 True，回调中检测到它就不计算位移。

```python
def center_mouse(self):
    """回中鼠标，并标记这次移动是"人为回中"。"""
    self._centering = True
    ctypes.windll.user32.SetCursorPos(self.center_x, self.center_y)
    self._centering = False

def on_move(self, x, y):
    if self._centering:
        # 这是回中操作引起的移动，忽略
        return
    # 正常处理位移
    ...
```

---

## 10. 第八步：pyee 广播 — 响应主程序控制

主程序（我）会用 pyee 广播以下事件：

| 事件 | 含义 | 你的模块要做什么 |
|------|------|-----------------|
| `GAME_START` | 游戏开始 | 开始监听，锁定鼠标 |
| `GAME_CONTINUE` | 游戏继续 | 同上（恢复） |
| `GAME_PAUSE` | 暂停 | 停止监听，释放鼠标 |
| `GAME_OVER` | 结束 | 停止监听，释放资源 |

你也要广播事件（按 P/Esc 时）：

| 你的广播 | 触发条件 |
|----------|----------|
| `GAME_PAUSE` | P 键按下，且游戏正在进行 |
| `GAME_CONTINUE` | P 键按下，且游戏已暂停 |
| `GAME_OVER` | Esc 键按下 |

```python
from pyee import EventEmitter

# 创建事件发射器
emitter = EventEmitter()

# 订阅事件
emitter.on("GAME_START", self.start)
emitter.on("GAME_PAUSE", self.pause)
emitter.on("GAME_OVER", self.stop)

# 广播事件
emitter.emit("GAME_PAUSE")
```

---

## 11. 第九步：最终代码 D_mouse.py

现在把所有步骤整合成最终的 `D_mouse.py`。

```python
# D_mouse.py
# 鼠标 & 键盘监听模块
#
# 功能：
#   1. 提供 get_delta() 返回 (dx, dy, left_click)
#   2. 检测 P 键（暂停/继续）和 Esc 键（结束）
#   3. 游戏运行时锁定鼠标在屏幕中心
#   4. 死区 + 平滑滤波
#   5. 响应 pyee 广播控制生命周期
#
# 用法：
#   from D_mouse import MouseListener
#   ml = MouseListener()
#   ml.start()
#   while ml.running:
#       dx, dy, left_click = ml.get_delta()
#   ml.stop()

import threading
import queue
import time
import ctypes
from collections import deque

from pynput.mouse import Listener as MouseListener_pynput, Button
from pynput.keyboard import Listener as KeyboardListener_pynput, Key
from pyee import EventEmitter


# ==============================================
#   MouseListener 类
# ==============================================

class MouseListener:
    """鼠标键盘监听器。
    
    在一个对象里封装了：
    - pynput 鼠标监听（位移 + 左键）
    - pynput 键盘监听（P 键 + Esc 键）
    - 线程安全的数据队列
    - 死区 + 平滑滤波
    - 鼠标回中锁定
    - pyee 事件广播
    """
    
    def __init__(self, sensitivity=1.0, deadzone=2, 
                 smooth_window=3, center_lock=True,
                 screen_width=None, screen_height=None):
        """初始化监听器。
        
        参数：
            sensitivity: 灵敏度系数（直接乘以 dx, dy）
            deadzone: 死区阈值（忽略小于此值的位移）
            smooth_window: 滑动平均窗口大小（1=不开启）
            center_lock: 是否锁定鼠标在屏幕中心
            screen_width: 屏幕宽度（自动检测）
            screen_height: 屏幕高度（自动检测）
        """
        self.sensitivity = sensitivity
        self.deadzone = deadzone
        self.smooth_window = smooth_window
        self.center_lock = center_lock
        
        # ---- 自动检测屏幕分辨率 ----
        if screen_width is None or screen_height is None:
            user32 = ctypes.windll.user32
            self.screen_width = user32.GetSystemMetrics(0)
            self.screen_height = user32.GetSystemMetrics(1)
        else:
            self.screen_width = screen_width
            self.screen_height = screen_height
        
        self.center_x = self.screen_width // 2
        self.center_y = self.screen_height // 2
        
        # ---- 数据队列（线程安全） ----
        self._queue = queue.Queue()
        
        # ---- 状态 ----
        self.running = False        # 是否正在监听
        self._game_active = False   # 游戏是否正在进行
        self._centering = False     # 是否正在回中鼠标
        self._left_pressed = False  # 左键是否按下
        
        # ---- 平滑滤波器 ----
        if smooth_window > 1:
            self._filter_x = deque(maxlen=smooth_window)
            self._filter_y = deque(maxlen=smooth_window)
        else:
            self._filter_x = None
            self._filter_y = None
        
        # ---- pyee 事件广播 ----
        self.emitter = EventEmitter()
        
        # ---- pynput 监听器 ----
        self._mouse_listener = None
        self._keyboard_listener = None
        
        # ---- 日志 ----
        print(f"[D_mouse] 初始化完成")
        print(f"  屏幕: {self.screen_width}x{self.screen_height}")
        print(f"  中心: ({self.center_x}, {self.center_y})")
        print(f"  灵敏度: {sensitivity}, 死区: {deadzone}")
        print(f"  平滑窗口: {smooth_window}")
        print(f"  鼠标回中: {'开启' if center_lock else '关闭'}")
    
    # ==========================================
    #   生命周期控制
    # ==========================================
    
    def start(self):
        """启动监听（响应 GAME_START / GAME_CONTINUE）。"""
        if self.running:
            return
        
        self.running = True
        self._game_active = True
        
        # 重置状态
        self._left_pressed = False
        
        # 清空队列（扔掉旧数据）
        self._clear_queue()
        
        # 启动鼠标监听器
        self._mouse_listener = MouseListener_pynput(
            on_move=self._on_move,
            on_click=self._on_click
        )
        self._mouse_listener.start()  # 非阻塞启动
        
        # 启动键盘监听器
        self._keyboard_listener = KeyboardListener_pynput(
            on_press=self._on_key_press
        )
        self._keyboard_listener.start()  # 非阻塞启动
        
        # 如果开启了回中，立即把鼠标移到中心
        if self.center_lock:
            self._center_mouse()
        
        print("[D_mouse] 监听已启动")
    
    def stop(self):
        """停止监听（响应 GAME_PAUSE / GAME_OVER）。"""
        if not self.running:
            return
        
        self.running = False
        self._game_active = False
        
        # 停止监听器
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        
        # 清空队列
        self._clear_queue()
        
        print("[D_mouse] 监听已停止")
    
    def pause(self):
        """暂停监听（保留监听器但不处理数据）。"""
        self._game_active = False
        self._clear_queue()
        print("[D_mouse] 已暂停")
    
    def resume(self):
        """恢复监听。"""
        self._game_active = True
        self._clear_queue()
        if self.center_lock:
            self._center_mouse()
        print("[D_mouse] 已恢复")
    
    # ==========================================
    #   数据接口（主程序调用）
    # ==========================================
    
    def get_delta(self):
        """获取当前的鼠标位移和左键状态。
        
        这是主程序唯一需要调用的方法。
        
        返回：
            (dx, dy, left_click)
            dx, dy: 自上次调用以来的相对位移（已平滑+死区）
            left_click: 当前左键是否按下
        
        用法：
            dx, dy, firing = ml.get_delta()
        """
        if not self._game_active:
            return (0, 0, self._left_pressed)
        
        # 从队列中取出所有位移数据并累加
        total_dx = 0
        total_dy = 0
        
        try:
            while True:
                event_type, value1, value2 = self._queue.get_nowait()
                
                if event_type == "move":
                    total_dx += value1
                    total_dy += value2
                # 以后可以扩展其他事件类型
        except queue.Empty:
            pass
        
        # ---- 应用死区 ----
        total_dx = self._apply_deadzone(total_dx)
        total_dy = self._apply_deadzone(total_dy)
        
        # ---- 应用灵敏度 ----
        total_dx = int(total_dx * self.sensitivity)
        total_dy = int(total_dy * self.sensitivity)
        
        # ---- 返回 ----
        return (total_dx, total_dy, self._left_pressed)
    
    # ==========================================
    #   内部方法：pynput 回调
    # ==========================================
    
    def _on_move(self, x, y):
        """鼠标移动回调（由 pynput 在后台线程调用）。"""
        if not self._game_active or self._centering:
            return
        
        # 计算位移：用上次记录的坐标
        # 注意：这里我们不能用实例变量保存 last_x, last_y，
        # 因为 pynput 的 on_move 每次都给绝对坐标
        # 我们改用另一种方式：直接用 x, y 算增量
        # 但更简单的方式是让主程序在 get_delta 里累加
        # 这里我们直接放原始数据到队列
        pass  # 实际实现见下方
    
    def _on_click(self, x, y, button, pressed):
        """鼠标点击回调（由 pynput 在后台线程调用）。"""
        if not self._game_active:
            return
        
        if button == Button.left:
            self._left_pressed = pressed
            if pressed:
                print("[D_mouse] 开火！")
    
    def _on_key_press(self, key):
        """键盘按下回调（由 pynput 在后台线程调用）。"""
        try:
            # ---- Esc 键 ----
            if key == Key.esc:
                print("[D_mouse] Esc 按下 → 广播 GAME_OVER")
                self.emitter.emit("GAME_OVER")
            
            # ---- P 键 ----
            elif hasattr(key, 'char') and key.char == 'p':
                if self._game_active:
                    print("[D_mouse] P 按下（游戏中）→ 广播 GAME_PAUSE")
                    self.emitter.emit("GAME_PAUSE")
                else:
                    print("[D_mouse] P 按下（已暂停）→ 广播 GAME_CONTINUE")
                    self.emitter.emit("GAME_CONTINUE")
        
        except AttributeError:
            pass  # 特殊按键，忽略
    
    # ==========================================
    #   内部方法：鼠标回中
    # ==========================================
    
    def _center_mouse(self):
        """把鼠标移到屏幕中心。
        
        设置 _centering 标志，让 _on_move 忽略这次移动。
        """
        self._centering = True
        ctypes.windll.user32.SetCursorPos(self.center_x, self.center_y)
        self._centering = False
    
    # ==========================================
    #   内部方法：死区 + 平滑
    # ==========================================
    
    def _apply_deadzone(self, value):
        """死区处理：小于阈值的归零。"""
        if abs(value) < self.deadzone:
            return 0
        return value
    
    def _smooth(self, dx, dy):
        """滑动平均平滑。"""
        if self._filter_x is None:
            return dx, dy
        
        self._filter_x.append(dx)
        self._filter_y.append(dy)
        
        smooth_x = sum(self._filter_x) / len(self._filter_x)
        smooth_y = sum(self._filter_y) / len(self._filter_y)
        
        return smooth_x, smooth_y
    
    # ==========================================
    #   内部方法：工具
    # ==========================================
    
    def _clear_queue(self):
        """清空队列中的所有数据。"""
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass


# ==============================================
#   修正：改进的 _on_move 实现
# ==============================================
# 上面的 _on_move 留空了，因为它需要记录上一次坐标。
# 下面是正确的实现：

class MouseListenerImproved(MouseListener):
    """改进版：正确计算 dx, dy。"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_x = None
        self._last_y = None
    
    def _on_move(self, x, y):
        """鼠标移动回调。
        
        计算相对位移并放入队列。
        """
        if not self._game_active or self._centering:
            self._last_x = x
            self._last_y = y
            return
        
        if self._last_x is not None:
            dx = x - self._last_x
            dy = y - self._last_y
            
            # 应用平滑
            dx, dy = self._smooth(dx, dy)
            
            # 放入队列
            self._queue.put(("move", dx, dy))
        
        self._last_x = x
        self._last_y = y
    
    def start(self):
        """重写 start：重置上一次坐标。"""
        self._last_x = None
        self._last_y = None
        super().start()
    
    def stop(self):
        """重写 stop：重置上一次坐标。"""
        self._last_x = None
        self._last_y = None
        super().stop()
    
    def _center_mouse(self):
        """重写回中：同时重置上一次坐标。"""
        self._centering = True
        ctypes.windll.user32.SetCursorPos(self.center_x, self.center_y)
        self._last_x = self.center_x
        self._last_y = self.center_y
        self._centering = False


# ==============================================
#   对外暴露的别名
# ==============================================
# 让主程序直接 from D_mouse import MouseListener
# 拿到的是改进版
MouseListener = MouseListenerImproved


# ==============================================
#   独立测试入口
# ==============================================

if __name__ == "__main__":
    print("=" * 50)
    print("  D_mouse 模块独立测试")
    print("=" * 50)
    print()
    print("测试内容：")
    print("  1. 启动监听 → 移动鼠标观察 dx, dy")
    print("  2. 点击左键 → 观察 left_click 状态")
    print("  3. 按 P 键 → 切换暂停/继续")
    print("  4. 按 Esc → 退出")
    print()
    print("按 Ctrl+C 退出测试\n")
    
    # 创建监听器（窗口模式，不锁定鼠标以便调试）
    ml = MouseListener(
        sensitivity=1.0,
        deadzone=2,
        smooth_window=3,
        center_lock=False  # 测试时关闭回中，方便观察
    )
    
    # 订阅广播事件（打印到控制台）
    ml.emitter.on("GAME_PAUSE", lambda: print("  [事件] GAME_PAUSE"))
    ml.emitter.on("GAME_CONTINUE", lambda: print("  [事件] GAME_CONTINUE"))
    ml.emitter.on("GAME_OVER", lambda: print("  [事件] GAME_OVER"))
    
    # 启动
    ml.start()
    
    try:
        while ml.running:
            dx, dy, left = ml.get_delta()
            if dx != 0 or dy != 0 or left:
                status = " 🔫 FIRING" if left else ""
                print(f"dx={dx:+4d}  dy={dy:+4d}{status}")
            time.sleep(0.05)  # 20Hz 轮询
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        ml.stop()
        print("测试结束")
```

---

## 12. 第十步：测试脚本 mouse_test.py

这是一个独立的测试脚本，你可以用来验证所有功能。

```python
# mouse_test.py
# D_mouse 模块的独立测试脚本
#
# 运行方式：python mouse_test.py
#
# 测试内容：
#   1. 实时显示 dx, dy
#   2. 左键开火状态
#   3. P 键暂停/继续广播
#   4. Esc 键结束广播
#   5. 鼠标回中效果

import sys
import os
import time

# 确保能找到 D_mouse.py
# 如果 D_mouse.py 在同一目录下，这行不是必须的
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入你的模块
from D_mouse import MouseListener

def print_help():
    """打印操作说明。"""
    print()
    print("=" * 55)
    print("  🎯 Real FPS — 鼠标监听模块测试")
    print("=" * 55)
    print()
    print("  操作说明：")
    print("    🖱 移动鼠标 → 观察 dx, dy")
    print("    🖱 左键点击 → 观察 FIRING 状态")
    print("    ⌨ 按 P 键  → 切换 暂停/继续")
    print("    ⌨ 按 Esc   → 结束游戏")
    print("    ⌨ Ctrl+C   → 退出测试")
    print()
    print("  状态说明：")
    print("    [▶] = 监听中")
    print("    [⏸] = 已暂停")
    print("    [⏹] = 已结束")
    print("    🔫   = 正在开火")
    print()

def main():
    """主测试函数。"""
    print_help()
    
    # ---- 1. 创建监听器 ----
    # 参数说明：
    #   sensitivity=1.0  → 灵敏度 1 倍
    #   deadzone=2       → 忽略 |dx|<2 的抖动
    #   smooth_window=3  → 3 帧滑动平均
    #   center_lock=True → 启动后鼠标锁在屏幕中心
    ml = MouseListener(
        sensitivity=1.0,
        deadzone=2,
        smooth_window=3,
        center_lock=True
    )
    
    # ---- 2. 订阅广播事件，打印到控制台 ----
    def on_pause():
        print("  [⏸] 暂停游戏")
    
    def on_continue():
        print("  [▶] 继续游戏")
    
    def on_game_over():
        print("  [⏹] 游戏结束")
    
    ml.emitter.on("GAME_PAUSE", on_pause)
    ml.emitter.on("GAME_CONTINUE", on_continue)
    ml.emitter.on("GAME_OVER", on_game_over)
    
    # ---- 3. 模拟主程序：先发送 GAME_START ----
    print("\n  模拟主程序发送 GAME_START...")
    ml.start()
    print("  [▶] 监听已启动，鼠标已锁定到屏幕中心\n")
    
    # ---- 4. 主循环（模拟主程序的轮询） ----
    try:
        frame_count = 0
        start_time = time.time()
        
        while ml.running:
            # 获取鼠标数据
            dx, dy, left_click = ml.get_delta()
            
            # 只有在有变化时才打印
            if dx != 0 or dy != 0 or left_click:
                # 计算帧率
                frame_count += 1
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                
                # 构建输出
                status = "🔫 FIRING" if left_click else "     "
                print(f"dx={dx:+4d}  dy={dy:+4d}  {status}  |  FPS={fps:.1f}")
                
                # 每 100 次打印重置计数器，避免溢出
                if frame_count > 100:
                    frame_count = 0
                    start_time = time.time()
            
            # 每 50ms 轮询一次（20Hz）
            # 这个速度足够快，不会漏掉鼠标移动
            time.sleep(0.05)
    
    except KeyboardInterrupt:
        print("\n\n  Ctrl+C 中断")
    
    finally:
        # ---- 5. 清理 ----
        ml.stop()
        print("  [⏹] 监听器已停止")
        print("\n测试结束。")

if __name__ == "__main__":
    main()
```

---

## 13. 常见错误与解决

### ❌ `ModuleNotFoundError: No module named 'pynput'`
→ 运行 `pip install pynput`

### ❌ `ModuleNotFoundError: No module named 'pyee'`
→ 运行 `pip install pyee`

### ❌ `ImportError: No module named 'D_mouse'`
→ 确保你在 `Real_fps` 目录下运行。检查 `D_mouse.py` 是否在目录中。

### ❌ `OSError: [WinError 87] 参数错误`（SetCursorPos）
→ 传入了错误的坐标。确保 `screen_width`, `screen_height` 是正数。

### ❌ 鼠标移动没有反应（dx, dy 始终为 0）
→ 可能原因：
   - `_game_active` 为 False（调用了 `pause()` 没调用 `resume()`）
   - `_centering` 没有正确复位
   - 队列没有被正确读取

### ❌ dx, dy 数值巨大（几百上千）
→ 可能是因为回中后 `_last_x` 没有更新，下次移动时用旧坐标算了超大差值。
   检查 `_center_mouse()` 中是否更新了 `_last_x, _last_y`。

### ❌ 鼠标回中后立刻又跑掉
→ 回中本身的 `SetCursorPos` 触发了 `on_move`，而你没有忽略它。
   检查 `_centering` 标志是否在 `_on_move` 中被正确检测。

### ❌ 按 P 键没有反应
→ pynput 在某些终端中需要管理员权限。尝试**以管理员身份运行**终端。
   或者检查 `on_press` 回调是否有 `try/except` 捕获了异常。

### ❌ pyee 事件不触发
→ 检查是否调用了 `emitter.on("GAME_PAUSE", ...)` **在** `start()` **之后**？
   先 `on` 再 `emit`，顺序不能反。

---

## 你的学习路线

1. **先跑 `test_mouse.py`** — 确保 pynput 能用
2. **理解回调函数** — `on_move`、`on_click`、`on_press`
3. **理解相对位移** — dx, dy 怎么算
4. **理解队列** — 为什么需要 `queue.Queue`
5. **理解死区** — 为什么需要 `apply_deadzone`
6. **运行 `D_mouse.py` 的测试入口** — `python D_mouse.py`
7. **运行 `mouse_test.py`** — 完整功能测试
8. **和主程序（我）对接** — 我调你的 `get_delta()` 和 `emitter`

**你的模块是唯一和操作系统硬件打交道的模块**，所以异常处理一定要做好。
如果 pynput 崩溃了，整个程序都会受影响。

建议在所有回调函数外面都包一层 `try/except`，保证一个回调出错不会影响其他回调。

有问题随时找我！
