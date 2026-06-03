# ui/core.py — Real FPS 主 UI 模块
#
# 功能：
#   1. 打开 Pygame 窗口
#   2. 后台线程读取 state.json + 拉取摄像头画面
#   3. 显示摄像头背景、准星、目标框
#   4. 通过 UDP 实时接收开火事件
#   5. 调用雷达、HUD、动画组件
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

# ====== 配置 ======
from ui.config import *
from ui.radar import Radar
from ui.hud import HUD
from ui.effects import Effects

STATUS_FILE = "state.json"
FIRE_EVENT = pygame.USEREVENT + 1   # UDP 开火事件的自定义编号
CAMERA_TIMEOUT = 1.0                # 摄像头 HTTP 请求超时


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

        # C 的组件
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
                except (FileNotFoundError, json.JSONDecodeError):
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
                    resp = requests.get(
                        "http://127.0.0.1:8010/snapshot",
                        timeout=CAMERA_TIMEOUT,
                    )
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

        # 创建组件
        self.radar = Radar(
            SCREEN_WIDTH - RADAR_RADIUS - RADAR_MARGIN,
            SCREEN_HEIGHT - RADAR_RADIUS - RADAR_MARGIN,
        )
        self.hud = HUD()
        self.effects = Effects()

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
            self.clock.tick(FPS_TARGET)

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
        # 外圈
        pygame.draw.circle(self.screen, COLOR_GREEN, (cx, cy), 15, 2)
        # 中心点
        pygame.draw.circle(self.screen, COLOR_GREEN, (cx, cy), 2, 0)
        # 十字线
        pygame.draw.line(self.screen, COLOR_GREEN, (cx - cs - 5, cy), (cx - 18, cy), 2)
        pygame.draw.line(self.screen, COLOR_GREEN, (cx + 18, cy), (cx + cs + 5, cy), 2)
        pygame.draw.line(self.screen, COLOR_GREEN, (cx, cy - cs - 5), (cx, cy - 18), 2)
        pygame.draw.line(self.screen, COLOR_GREEN, (cx, cy + 18), (cx, cy + cs + 5), 2)

        # ---- HUD 信息 ----
        try:
            score = state.get("score", {}).get("value", 0)
            mode = state.get("system_state", {}).get("mode", "idle")
            serial = state.get("serial", {}).get("status", "N/A")

            # 使用字体工具
            from ui.assets import get_font_large, get_font_small

            font_large = get_font_large()
            font_small = get_font_small()

            score_text = font_large.render(f"SCORE: {score}", True, COLOR_WHITE)
            self.screen.blit(score_text, (HUD_MARGIN, HUD_MARGIN))

            fps_val = int(self.clock.get_fps())
            fps_text = font_small.render(f"FPS: {fps_val}", True, COLOR_WHITE)
            self.screen.blit(fps_text, (HUD_MARGIN, HUD_MARGIN + 50))

            status_text = font_small.render(
                f"MODE: {mode.upper()}  |  SERIAL: {serial}", True, COLOR_WHITE,
            )
            status_rect = status_text.get_rect(
                center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 30),
            )
            self.screen.blit(status_text, status_rect)

        except Exception:
            pass

        # ---- 调用组件 ----
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
