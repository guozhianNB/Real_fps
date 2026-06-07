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

        # ---- 边框 ----
        pygame.draw.rect(surface, COLOR_GREEN, (x, y, w, h), 2)

        # ---- 网格线（方位参考） ----
        for i in range(1, 4):
            gx = x + (w * i) // 4
            pygame.draw.line(surface, (0, 180, 60, 80), (gx, y), (gx, y + h), 1)
        # ---- 距离参考线 ----
        gy = y + h // 3
        pygame.draw.line(surface, (0, 180, 60, 80), (x, gy), (x + w, gy), 1)
        gy = y + (h * 2) // 3
        pygame.draw.line(surface, (0, 180, 60, 80), (x, gy), (x + w, gy), 1)

        # ---- 扫描线（左右往复移动） ----
        self.scan_x += w * (dt_ms / 1000) * 0.6 * self.scan_dir
        if self.scan_x > w:
            self.scan_x = w
            self.scan_dir = -1
        elif self.scan_x < 0:
            self.scan_x = 0
            self.scan_dir = 1
        sx = x + self.scan_x
        # 渐变透明度
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

        # ---- 标签 ----
        label = self.font.render("B-SCOPE", True, COLOR_GREEN)
        label_y = max(0, y - 20)
        surface.blit(label, (x + w // 2 - label.get_width() // 2, label_y))


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
