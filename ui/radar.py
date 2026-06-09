# ui/radar.py — B-scope 雷达组件
#
# B-scope 特点：
#   - 矩形区域，不是圆形
#   - X 轴 = 方位角（目标左右位置）
#   - Y 轴 = 距离（越远显示越靠上）
#   - 扫描线左右往复移动
#
# 可独立运行测试：python ui/radar.py

import pygame
import sys
import os
from collections import deque
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.assets import get_font_small

# B-scope 尺寸
B_SCOPE_W = 200
B_SCOPE_H = 200


class Radar:
    """B-scope 雷达组件，矩形扫描显示目标方位和距离。"""

    def __init__(self, cx, cy, w=B_SCOPE_W, h=B_SCOPE_H):
        self.cx, self.cy = cx, cy          # 左上角坐标
        self.w, self.h = w, h
        self.scan_x = 0                     # 扫描线当前 X 位置 (0~w)
        self.scan_dir = 1                   # 扫描方向: 1=右, -1=左
        self.blink_timer = 0
        self.font = get_font_small()

        # 距离归一化参考值（depth=100 ≈ 中等距离）
        self.max_depth_ref = 350.0

        # 扫描线尾迹（保存最近 10 帧位置）
        self._scan_trail = deque(maxlen=10)

    def render(self, surface, targets, dt_ms=16):
        """绘制 B-scope 雷达。

        参数：
            surface: Pygame Surface
            targets: state.json 中的 targets 列表（需含 cx, cy, depth）
            dt_ms:   距上一帧毫秒数
        """
        x, y = self.cx, self.cy
        w, h = self.w, self.h

        # ---- 半透明背景 ----
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        surface.blit(bg, (x, y))

        # ---- 发光边框 ----
        # 外层光晕（宽 2px 半透明绿，向外扩展 3px）
        glow_pad = 3
        pygame.draw.rect(
            surface, (0, 255, 100, 60),
            (x - glow_pad, y - glow_pad, w + glow_pad * 2, h + glow_pad * 2),
            2, border_radius=6,
        )
        # 内层亮绿边框（宽 4px）
        pygame.draw.rect(surface, COLOR_GREEN, (x, y, w, h), 4, border_radius=4)

        # ---- 左侧距离刻度短线 ----
        tick_len = 8
        for i in range(1, 4):
            ty = y + (h * i) // 4
            pygame.draw.line(surface, COLOR_GREEN, (x, ty), (x + tick_len, ty), 2)

        # ---- 网格线（方位参考：虚线效果由透明度实现）----
        for i in range(1, 4):
            gx = x + (w * i) // 4
            pygame.draw.line(surface, (0, 180, 60, 80), (gx, y), (gx, y + h), 1)
        # ---- 距离参考线 ----
        for i in range(1, 3):
            gy = y + (h * i) // 3
            pygame.draw.line(surface, (0, 180, 60, 80), (x, gy), (x + w, gy), 1)

        # ---- 扫描线尾迹（从旧到新依次变亮）----
        trail_len = len(self._scan_trail)
        for idx, old_sx in enumerate(self._scan_trail):
            progress = (idx + 1) / trail_len if trail_len > 0 else 0
            trail_alpha = int(80 * progress)  # 最旧≈0，最新≈80
            if trail_alpha < 8:
                continue
            trail_surf = pygame.Surface((2, h), pygame.SRCALPHA)
            for i in range(h):
                # 顶部亮、底部暗的渐变 + 尾迹淡出
                fade = 1.0 - i / h
                ta = int(trail_alpha * fade)
                trail_surf.set_at((0, i), (0, 255, 100, max(0, ta)))
            surface.blit(trail_surf, (old_sx, y))

        # ---- 扫描线（当前帧）----
        self.scan_x += w * (dt_ms / 1000) * 0.6 * self.scan_dir
        if self.scan_x > w:
            self.scan_x = w
            self.scan_dir = -1
        elif self.scan_x < 0:
            self.scan_x = 0
            self.scan_dir = 1
        sx = x + self.scan_x
        self._scan_trail.append(sx)
        scan_surf = pygame.Surface((3, h), pygame.SRCALPHA)
        for i in range(h):
            alpha = int(120 * (1 - i / h))
            scan_surf.set_at((1, i), (0, 255, 100, max(0, alpha)))
        surface.blit(scan_surf, (sx, y))

        # ---- 目标点 ----
        self.blink_timer += dt_ms
        visible = (self.blink_timer % 500) < 250  # 闪烁

        sw = surface.get_width()
        sh = surface.get_height()
        scx = sw / 2  # 当前屏幕中心（方位参考）

        for t in targets:
            depth = t.get("depth", 0)
            tx = t.get("cx", scx)

            # X 轴：目标水平位置相对于屏幕中心，映射到雷达宽度
            rel_x = (tx - scx) / (sw / 2)  # -1 ~ 1
            px = x + w / 2 + rel_x * (w / 2 - 10)
            px = max(x + 4, min(x + w - 4, px))

            # Y 轴：depth 越小（越远）→ 显示越靠上（Y 越小）
            # depth = 肩中到鼻子的距离，远距离人 depth 小
            norm_depth = min(depth / self.max_depth_ref, 1.0)
            # 翻转：远（norm_depth≈0）→ 靠上，近（norm_depth≈1）→ 靠下
            py = y + 10 + norm_depth * (h - 20)
            py = max(y + 4, min(y + h - 4, py))

            # 画目标点（存活=圆点，击杀=绿色小叉）
            if t.get("dead"):
                # 击杀目标：绿色小叉，不闪烁
                s = 6
                cx_i, cy_i = int(px), int(py)
                pygame.draw.line(surface, COLOR_GREEN, (cx_i - s, cy_i - s), (cx_i + s, cy_i + s), 2)
                pygame.draw.line(surface, COLOR_GREEN, (cx_i + s, cy_i - s), (cx_i - s, cy_i + s), 2)
            elif visible:
                color = COLOR_YELLOW if t.get("locked") else COLOR_GREEN
                pygame.draw.circle(surface, color, (int(px), int(py)), 5)
                pygame.draw.circle(surface, color, (int(px), int(py)), 8, 1)

        # 标签已移除（简洁化）


# ====== 独立测试 ======
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((400, 500))
    pygame.display.set_caption("B-scope Radar 测试")
    clock = pygame.time.Clock()

    radar = Radar(50, 50)
    # 模拟目标（带 cx, cy, depth）
    mock_targets = [
        {"id": 1, "cx": 640, "cy": 360, "depth": 80.0},
        {"id": 2, "cx": 500, "cy": 280, "depth": 40.0},
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
