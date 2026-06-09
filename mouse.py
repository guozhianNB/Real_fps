"""
鼠标 & 键盘监听模块（独立线程运行）

功能：
  1. 后台线程持续监听鼠标移动，提供 get_delta() → (dx, dy, left_pressed)
  2. 检测左键点击（开火）
  3. 按 P 键 → emitter 广播 GAME_PAUSE / GAME_CONTINUE
  4. 按 Esc → emitter 广播 GAME_OVER
  5. 收到主程序的 GAME_START 后才开始采集数据
  6. 鼠标自动回中锁定

用法（主程序）：
    from mouse import MouseListener

    ml = MouseListener()
    ml.emitter.on("GAME_OVER", lambda: print("游戏结束"))

    ml.start()           # 收到 GAME_START 后调用
    dx, dy, fire = ml.get_delta()
    ml.stop()            # GAME_OVER 后调用
"""

import threading
import queue
import time
import ctypes
import ctypes.wintypes
from collections import deque

from pynput.mouse import Listener as MouseListener_pynput, Button
from pynput.keyboard import Listener as KeyboardListener_pynput, Key
from pyee import EventEmitter


# ---- 全局：空白光标相关 ----
class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon",    ctypes.c_bool),
        ("xHotspot", ctypes.c_uint32),
        ("yHotspot", ctypes.c_uint32),
        ("hbmMask",  ctypes.c_void_p),
        ("hbmColor", ctypes.c_void_p),
    ]

_BLANK_CURSOR = None
_BLANK_BITMAP = None
_CURSOR_HIDDEN = False

def _make_blank_cursor():
    """创建全透明空白光标（全局共享）。"""
    global _BLANK_CURSOR, _BLANK_BITMAP
    if _BLANK_CURSOR is not None:
        return True
    _BLANK_BITMAP = ctypes.windll.gdi32.CreateBitmap(1, 1, 1, 1, None)
    if not _BLANK_BITMAP:
        return False
    info = ICONINFO(False, 0, 0, _BLANK_BITMAP, _BLANK_BITMAP)
    _BLANK_CURSOR = ctypes.windll.user32.CreateIconIndirect(ctypes.byref(info))
    return _BLANK_CURSOR is not None

def hide_system_cursor():
    """隐藏鼠标指针。"""
    global _CURSOR_HIDDEN
    _make_blank_cursor()
    # ShowCursor 计数器减到负
    while ctypes.windll.user32.ShowCursor(False) >= 0:
        pass
    # 替换系统箭头
    if _BLANK_CURSOR:
        ctypes.windll.user32.SetSystemCursor(_BLANK_CURSOR, 32512)  # OCR_NORMAL
    _CURSOR_HIDDEN = True

def show_system_cursor():
    """恢复鼠标指针。"""
    global _CURSOR_HIDDEN
    if not _CURSOR_HIDDEN:
        return
    # 恢复系统默认光标
    ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)  # SPI_SETCURSORS
    while ctypes.windll.user32.ShowCursor(True) < 0:
        pass
    _CURSOR_HIDDEN = False


class MouseListener:
    """鼠标键盘监听器，后台独立线程运行。

    设计：
      - pynput 监听器在 __init__ 时就启动（后台线程常驻）
      - 但 _game_active 初始为 False，不采集数据
      - start()  → 开始采集 + 鼠标回中（响应 GAME_START）
      - pause()  → 暂停采集（响应 GAME_PAUSE）
      - resume() → 恢复采集（响应 GAME_CONTINUE）
      - stop()   → 停止所有监听器（响应 GAME_OVER）
    """

    def __init__(self, sensitivity=1.0, deadzone=2,
                 smooth_window=3, center_lock=True,
                 screen_width=None, screen_height=None):
        self.sensitivity = sensitivity
        self.deadzone = deadzone
        self.smooth_window = smooth_window
        self.center_lock = center_lock

        # ---- 屏幕分辨率 ----
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
        self._game_active = False        # 是否正在采集数据
        self._centering = False          # 是否正在回中
        self._last_x = None              # 上一次鼠标绝对 x
        self._last_y = None              # 上一次鼠标绝对 y
        self._left_pressed = False       # 左键当前是否按下
        self._center_event = threading.Event()

        # ---- 回中节流（避免过频调用 SetCursorPos）----
        self._last_center_time = 0
        self._center_interval = 0.05  # 最小回中间隔 50ms

        # ---- 平滑滤波器 ----
        if smooth_window > 1:
            self._filter_x = deque(maxlen=smooth_window)
            self._filter_y = deque(maxlen=smooth_window)
        else:
            self._filter_x = None
            self._filter_y = None

        # ---- pyee 事件广播（主程序订阅） ----
        self.emitter = EventEmitter()

        # ---- 立即启动 pynput 监听器（后台线程） ----
        # 注意：虽然监听器启动了，但 _game_active=False，数据不会被采集
        self._mouse_listener = MouseListener_pynput(
            on_move=self._on_move,
            on_click=self._on_click
        )
        self._mouse_listener.start()

        self._keyboard_listener = KeyboardListener_pynput(
            on_press=self._on_key_press
        )
        self._keyboard_listener.start()

        print(f"[Mouse] 监听线程已启动（等待 GAME_START 后开始采集）")
        print(f"  屏幕: {self.screen_width}x{self.screen_height}")
        print(f"  回中: {'开启' if center_lock else '关闭'}")

    # ==========================================
    #   生命周期（由主程序调用/响应事件）
    # ==========================================

    def start(self):
        """开始采集数据（响应 GAME_START / GAME_CONTINUE）。"""
        self._game_active = True
        self._left_pressed = False
        self._last_x = None
        self._last_y = None
        self._clear_queue()
        if self.center_lock:
            self._center_mouse()
        hide_system_cursor()
        print("[Mouse] 开始采集")

    def pause(self):
        """暂停采集（响应 GAME_PAUSE）。"""
        self._game_active = False
        self._clear_queue()
        show_system_cursor()
        print("[Mouse] 已暂停")

    def resume(self):
        """恢复采集（响应 GAME_CONTINUE）。"""
        self._game_active = True
        self._clear_queue()
        self._last_x = None
        self._last_y = None
        if self.center_lock:
            self._center_mouse()
        hide_system_cursor()
        print("[Mouse] 已恢复")

    def stop(self):
        """完全停止监听器（响应 GAME_OVER）。"""
        self._game_active = False
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        self._clear_queue()
        show_system_cursor()
        print("[Mouse] 监听器已停止")

    # ==========================================
    #   数据接口（主程序调用）
    # ==========================================

    def get_delta(self):
        """获取自上次调用以来的鼠标位移和左键状态。

        返回：
            (dx, dy, left_pressed)
            dx, dy: 相对位移（已平滑 + 死区 + 灵敏度）
            left_pressed: 左键当前是否按下
        """
        if not self._game_active:
            return (0, 0, self._left_pressed)

        # 持续回中
        self._keep_centered()

        # 取出队列中所有位移并累加
        total_dx = 0
        total_dy = 0
        try:
            while True:
                evt, v1, v2 = self._queue.get_nowait()
                if evt == "move":
                    total_dx += v1
                    total_dy += v2
        except queue.Empty:
            pass

        # 死区
        total_dx = 0 if abs(total_dx) < self.deadzone else total_dx
        total_dy = 0 if abs(total_dy) < self.deadzone else total_dy

        # 灵敏度
        total_dx = int(total_dx * self.sensitivity)
        total_dy = int(total_dy * self.sensitivity)

        return (total_dx, total_dy, self._left_pressed)

    def is_firing(self):
        """快捷方式：左键是否按下。"""
        return self._left_pressed

    # ==========================================
    #   pynput 回调（在后台线程执行）
    # ==========================================

    def _on_move(self, x, y):
        """鼠标移动回调。"""
        if not self._game_active:
            self._last_x, self._last_y = x, y
            return

        if self._centering:
            self._last_x, self._last_y = x, y
            self._center_event.set()
            return

        if self._last_x is not None:
            dx = x - self._last_x
            dy = y - self._last_y
            dx, dy = self._smooth(dx, dy)
            self._queue.put(("move", dx, dy))

        self._last_x, self._last_y = x, y

    def _on_click(self, x, y, button, pressed):
        """鼠标点击回调。"""
        if button == Button.left:
            self._left_pressed = pressed

    def _on_key_press(self, key):
        """键盘按下回调。"""
        try:
            if key == Key.esc:
                print("[Mouse] Esc → 广播 GAME_OVER")
                self.emitter.emit("GAME_OVER")
            elif hasattr(key, 'char') and key.char == 'p':
                if self._game_active:
                    print("[Mouse] P → 广播 GAME_PAUSE")
                    self.emitter.emit("GAME_PAUSE")
                else:
                    print("[Mouse] P → 广播 GAME_CONTINUE")
                    self.emitter.emit("GAME_CONTINUE")
            elif hasattr(key, 'char') and key.char == 'j':
                if self._game_active:
                    print("[Mouse] J → 广播 GAME_INSPECT")
                    self.emitter.emit("GAME_INSPECT")
            elif hasattr(key, 'char') and key.char == 'r':
                if self._game_active:
                    print("[Mouse] R → 广播 GAME_RELOAD")
                    self.emitter.emit("GAME_RELOAD")
            elif hasattr(key, 'char') and key.char == 'x':
                if self._game_active:
                    print("[Mouse] X → 广播 GAME_LOCK")
                    self.emitter.emit("GAME_LOCK")
        except AttributeError:
            pass

    # ==========================================
    #   内部方法
    # ==========================================

    def _center_mouse(self):
        """把鼠标移到屏幕中心。"""
        self._center_event.clear()
        self._centering = True
        ctypes.windll.user32.SetCursorPos(self.center_x, self.center_y)
        self._center_event.wait(timeout=0.01)
        self._centering = False

    def _keep_centered(self):
        """持续回中检查（带节流，最低 50ms 间隔）。"""
        if not self.center_lock or not self._game_active:
            return

        now = time.time()
        if now - self._last_center_time < self._center_interval:
            return
        self._last_center_time = now

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        if abs(pt.x - self.center_x) > 1 or abs(pt.y - self.center_y) > 1:
            self._center_mouse()

    def _smooth(self, dx, dy):
        """滑动平均平滑。"""
        if self._filter_x is None:
            return dx, dy
        self._filter_x.append(dx)
        self._filter_y.append(dy)
        return (sum(self._filter_x) / len(self._filter_x),
                sum(self._filter_y) / len(self._filter_y))

    def _clear_queue(self):
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass


# ==============================================
#   独立测试入口
# ==============================================

if __name__ == "__main__":
    print("=" * 50)
    print("  Mouse 模块独立测试")
    print("=" * 50)
    print("  移动鼠标 / 左键点击 / P=暂停  Esc=退出")
    print()

    ml = MouseListener(sensitivity=1.0, deadzone=2,
                       smooth_window=3, center_lock=True)

    # 订阅事件
    ml.emitter.on("GAME_PAUSE", lambda: ml.pause())
    ml.emitter.on("GAME_CONTINUE", lambda: ml.resume())
    ml.emitter.on("GAME_OVER", lambda: setattr(ml, '_running', False))

    ml._running = True
    ml.start()  # 开始采集

    try:
        while ml._running:
            dx, dy, fire = ml.get_delta()
            if dx != 0 or dy != 0 or fire:
                status = " 🔫" if fire else ""
                print(f"dx={dx:+4d}  dy={dy:+4d}{status}")
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        ml.stop()
        print("测试结束")