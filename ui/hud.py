# ui/hud.py — HUD 面板组件
#
# 显示分数、目标数、FPS、模式、串口状态。
# 可独立运行测试：python ui/hud.py

import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.assets import *


class HUD:
    """HUD 面板，显示游戏关键信息。"""

    def __init__(self):
        self.font_large = get_font_large()
        self.font_small = get_font_small()
        self.flash_timer = 0    # 分数变化闪烁
        self.last_score = 0     # 上一帧的分数（用于检测变化）

    def render(self, surface, state, fps, dt_ms=16):
        """绘制 HUD。

        参数：
            surface: Pygame Surface
            state:   state.json 解析后的字典
            fps:     当前帧率
            dt_ms:   距上一帧的毫秒数
        """
        score = state.get("score", {}).get("value", 0)
        targets = state.get("targets", [])
        mode = state.get("system_state", {}).get("mode", "idle")
        serial = state.get("serial", {}).get("status", "N/A")
        ammo = state.get("ammo", 0)

        # ---- 分数变化闪烁 ----
        if score != self.last_score:
            self.flash_timer = 500
            self.last_score = score

        score_color = COLOR_YELLOW if self.flash_timer > 0 else COLOR_WHITE
        self.flash_timer = max(0, self.flash_timer - dt_ms)

        # ---- 半透明背景 ----
        panel = alpha_surface(250, 155, COLOR_BLACK, HUD_BG_ALPHA)
        surface.blit(panel, (HUD_MARGIN - 5, HUD_MARGIN - 5))

        # ---- 分数 ----
        surf = self.font_large.render(f"SCORE: {score}", True, score_color)
        surface.blit(surf, (HUD_MARGIN, HUD_MARGIN))

        # ---- 弹药（低于 10 时变红警告） ----
        ammo_color = COLOR_RED if ammo < 10 else COLOR_WHITE
        surf = self.font_small.render(f"AMMO: {ammo}", True, ammo_color)
        surface.blit(surf, (HUD_MARGIN, HUD_MARGIN + 45))

        # ---- 目标数 ----
        surf = self.font_small.render(f"TARGETS: {len(targets)}", True, COLOR_WHITE)
        surface.blit(surf, (HUD_MARGIN, HUD_MARGIN + 75))

        # ---- FPS（<30 时变黄警告） ----
        fps_color = COLOR_YELLOW if fps < 30 else COLOR_WHITE
        surf = self.font_small.render(f"FPS: {fps}", True, fps_color)
        surface.blit(surf, (HUD_MARGIN, HUD_MARGIN + 105))

        # ---- 底部状态栏（模式 + 串口） ----
        text = f"MODE: {mode.upper()}  |  SERIAL: {serial}"
        surf = self.font_small.render(
            text, True,
            COLOR_RED if mode == "error" else COLOR_WHITE,
        )
        sw = surface.get_width()
        sh = surface.get_height()

        # 背景
        bg = alpha_surface(
            surf.get_width() + 20, surf.get_height() + 10,
            COLOR_BLACK, HUD_BG_ALPHA,
        )
        bg_rect = bg.get_rect(center=(sw // 2, sh - 30))
        surface.blit(bg, bg_rect)

        # 文字
        text_rect = surf.get_rect(center=(sw // 2, sh - 30))
        surface.blit(surf, text_rect)


# ====== 独立测试 ======
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 400))
    pygame.display.set_caption("HUD 测试")
    clock = pygame.time.Clock()

    hud = HUD()
    mock_state = {
        "score": {"value": 100},
        "targets": [{"id": 1}],
        "system_state": {"mode": "playing"},
        "serial": {"status": "OK"},
    }

    timer = 0
    running = True
    while running:
        dt = clock.tick(60)
        timer += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False

        # 每 3 秒自动加分，测试闪烁
        if timer > 3000:
            timer = 0
            mock_state["score"]["value"] += 50

        screen.fill(COLOR_BLACK)
        hud.render(screen, mock_state, int(clock.get_fps()), dt)
        pygame.display.flip()

    pygame.quit()
