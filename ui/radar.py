# ui/radar.py — 雷达组件
#
# 在画面角落显示一个小雷达，标示目标方位。
# 可独立运行测试：python ui/radar.py

import pygame
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.assets import get_font_small


class Radar:
    """雷达组件，在画面一角绘制环形雷达扫描效果。"""

    def __init__(self, cx, cy, r=RADAR_RADIUS):
        self.cx, self.cy, self.r = cx, cy, r
        self.scan_angle = 0          # 扫描线当前角度
        self.blink_timer = 0         # 亮点闪烁计时
        self.font = get_font_small()

    def render(self, surface, targets, dt_ms=16):
        """绘制雷达。

        参数：
            surface: 要绘制到的 Pygame Surface
            targets: state.json 中的 targets 列表
            dt_ms:   距离上一帧的毫秒数
        """
        cx, cy, r = self.cx, self.cy, self.r

        # ---- 半透明背景圆 ----
        bg = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(bg, (0, 0, 0, 120), (r, r), r)
        pygame.draw.circle(bg, COLOR_GREEN, (r, r), r, 2)
        surface.blit(bg, (cx - r, cy - r))

        # ---- 十字线 ----
        pygame.draw.line(surface, COLOR_GREEN, (cx - r, cy), (cx + r, cy), 1)
        pygame.draw.line(surface, COLOR_GREEN, (cx, cy - r), (cx, cy + r), 1)

        # ---- 扫描线 ----
        self.scan_angle += 120 * (dt_ms / 1000)
        if self.scan_angle >= 360:
            self.scan_angle -= 360
        rad = math.radians(self.scan_angle)
        pygame.draw.line(
            surface, COLOR_GREEN,
            (cx, cy),
            (cx + r * math.cos(rad), cy + r * math.sin(rad)),
            1,
        )

        # ---- 目标点（闪烁） ----
        self.blink_timer += dt_ms
        scx, scy = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2

        for t in targets:
            # 取 bbox 中心作为目标位置
            bbox = t.get("bbox", [])
            if len(bbox) == 4:
                tx = (bbox[0] + bbox[2]) / 2
                ty = (bbox[1] + bbox[3]) / 2
            else:
                tx, ty = scx, scy

            dx = tx - scx
            dy = ty - scy
            d = math.hypot(dx, dy)
            if d > 0:
                s = min(r * 0.8 / d, 1.0)
                px, py = cx + dx * s, cy + dy * s
            else:
                px, py = cx, cy

            if (self.blink_timer % 400) < 200:
                pygame.draw.circle(surface, COLOR_GREEN, (int(px), int(py)), 4)

        # ---- 标签 ----
        label = self.font.render("RADAR", True, COLOR_GREEN)
        surface.blit(label, (cx - label.get_width() // 2, cy - r - 20))


# ====== 独立测试 ======
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((400, 500))
    pygame.display.set_caption("Radar 测试")
    clock = pygame.time.Clock()

    radar = Radar(200, 300)
    # 模拟目标
    mock_targets = [
        {"id": 1, "bbox": [640, 360, 720, 480]},
        {"id": 2, "bbox": [600, 200, 680, 360]},
    ]

    running = True
    while running:
        dt = clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False

        screen.fill(COLOR_BLACK)
        radar.render(screen, mock_targets, dt_ms=dt)
        pygame.display.flip()

    pygame.quit()
