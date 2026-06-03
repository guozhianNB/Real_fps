# ui/demo_reader.py — UI 组件自测入口
#
# 模拟主程序写 state.json + UDP 开火，让你独立测试全部组件。
# 无需启动 main.py 或摄像头服务即可看到效果。
#
# 运行：python ui/demo_reader.py

import pygame
import json
import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.radar import Radar
from ui.hud import HUD
from ui.effects import Effects
from fire_notifier import FireListener, send_fire


class MockWriter:
    """模拟主程序：按场景循环写 state.json + 发送 UDP 开火。"""

    def __init__(self):
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        scenes = [
            {
                "system_state": {"mode": "idle"},
                "score": {"value": 0},
                "targets": [],
                "serial": {"status": "OK"},
            },
            {
                "system_state": {"mode": "playing"},
                "score": {"value": 0},
                "targets": [{"id": 1, "bbox": [620, 240, 780, 420]}],
                "serial": {"status": "OK"},
            },
            {
                "system_state": {"mode": "playing", "msg": "命中！"},
                "score": {"value": 50},
                "targets": [{"id": 1, "bbox": [600, 320, 680, 400]}],
                "serial": {"status": "OK"},
            },
            {
                "system_state": {"mode": "over", "msg": "串口断开"},
                "score": {"value": 50},
                "targets": [],
                "serial": {"status": "ERROR"},
            },
        ]
        idx = 0
        while not self._stop.is_set():
            s = scenes[idx % 4].copy()
            s["timestamp"] = time.time()
            try:
                with open("state.json", "w") as f:
                    json.dump(s, f)
            except Exception:
                pass

            # 在第 3 个场景触发开火
            if idx % 4 == 2:
                send_fire(hit_zone="head", score_delta=50)

            idx += 1
            time.sleep(2.5)


def read_status():
    """读取 state.json，失败返回空字典。"""
    try:
        with open("state.json") as f:
            return json.loads(f.read())
    except Exception:
        return {}


def main():
    print("=== UI 自测 ===")
    print("模拟主程序循环写 state.json + UDP 开火")
    print()

    # 启动模拟写入器
    writer = MockWriter()
    writer.start()

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("UI 自测 — 每 2.5s 切换场景")
    clock = pygame.time.Clock()

    # UDP 开火事件 → Pygame 事件
    FIRE = pygame.USEREVENT + 1

    def on_fire(event):
        pygame.event.post(pygame.event.Event(FIRE, event))

    listener = FireListener(callback=on_fire)
    listener.start()

    # 组件
    from ui.radar import B_SCOPE_W, B_SCOPE_H
    radar = Radar(
        SCREEN_WIDTH - B_SCOPE_W - RADAR_MARGIN,
        RADAR_MARGIN,
    )
    hud = HUD()
    effects = Effects()

    running = True
    last_state = {}

    while running:
        dt = clock.tick(FPS_TARGET)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False
            elif e.type == FIRE:
                effects.add_hit_flash(
                    e.__dict__.get("hit_zone", ""),
                    e.__dict__.get("score_delta", 0),
                )

        # 读 state.json
        state = read_status() or last_state
        last_state = state

        # 更新动画
        effects.update(dt)

        # 绘制
        screen.fill(COLOR_BLACK)

        targets = state.get("targets", [])

        # 准星
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        cs = CROSSHAIR_SIZE
        pygame.draw.circle(screen, COLOR_GREEN, (cx, cy), 15, 2)
        pygame.draw.circle(screen, COLOR_GREEN, (cx, cy), 2, 0)
        pygame.draw.line(screen, COLOR_GREEN, (cx - cs - 5, cy), (cx - 18, cy), 2)
        pygame.draw.line(screen, COLOR_GREEN, (cx + 18, cy), (cx + cs + 5, cy), 2)
        pygame.draw.line(screen, COLOR_GREEN, (cx, cy - cs - 5), (cx, cy - 18), 2)
        pygame.draw.line(screen, COLOR_GREEN, (cx, cy + 18), (cx, cy + cs + 5), 2)

        # 目标框
        for t in targets:
            bbox = t.get("bbox")
            if bbox and len(bbox) == 4:
                rect = pygame.Rect(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
                pygame.draw.rect(screen, COLOR_GREEN, rect, 2)

        # 组件
        radar.render(screen, targets, dt_ms=dt)
        hud.render(screen, state, int(clock.get_fps()), dt)
        effects.render(screen)

        pygame.display.flip()

    writer.stop()
    listener.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
