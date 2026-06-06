import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.config import *

class HUD:
    def __init__(self):
        pygame.font.init()
        self.font_large = pygame.font.Font(None, 52)
        self.font_small = pygame.font.Font(None, 34)
        self.flash_timer = 0
        self.last_score = 0
        self.pulse = 0

    def render(self, surface, state, fps, dt_ms=16):
        self.pulse += 0.05
        score = state.get("score", {}).get("value", 0)
        targets = state.get("targets", [])
        mode = state.get("system_state", {}).get("mode", "idle")
        serial = state.get("serial", {}).get("status", "N/A")
        ammo = state.get("ammo", 0)

        if score != self.last_score:
            self.flash_timer = 600
            self.last_score = score

        flash = self.flash_timer > 0
        self.flash_timer = max(0, self.flash_timer - dt_ms)
        sw, sh = surface.get_size()
        m = 22

        # --------------------------
        # 超级华丽霓虹计分面板
        # --------------------------
        panel_w = 290
        panel_h = 180
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)

        # 渐变赛博背景
        for i in range(panel_h):
            r = int(30 + 5 * (i / panel_h))
            g = int(10 + 15 * (i / panel_h))
            b = int(45 + 40 * (i / panel_h))
            pygame.draw.line(panel, (r, g, b, 190), (0, i), (panel_w, i))

        # 双重霓虹边框
        pygame.draw.rect(panel, (0, 210, 255, 255), (0, 0, panel_w, panel_h), 3, border_radius=14)
        pygame.draw.rect(panel, (255, 0, 180, 180), (4, 4, panel_w-8, panel_h-8), 2, border_radius=10)

        surface.blit(panel, (m, m))

        # --------------------------
        # 分数（渐变发光）
        # --------------------------
        glow_rad = 6 if flash else 3
        for dx in [-glow_rad, 0, glow_rad]:
            for dy in [-glow_rad, 0, glow_rad]:
                c = (255, 200, 0) if flash else (0, 220, 255)
                s = self.font_large.render(f"SCORE: {score}", True, c)
                surface.blit(s, (m + 12 + dx, m + 12 + dy))
        final = self.font_large.render(f"SCORE: {score}", True, (255,255,255))
        surface.blit(final, (m+12, m+12))

        # --------------------------
        # 弹药（发光警告）
        # --------------------------
        ammo_c = (255,40,60) if ammo < 10 else (0,255,140)
        for g in [-2,0,2]:
            t = self.font_small.render(f"AMMO: {ammo}", True, ammo_c)
            surface.blit(t, (m+14+g, m+64+g))
        surface.blit(self.font_small.render(f"AMMO: {ammo}", True, (255,255,255)), (m+14, m+64))

        # --------------------------
        # 目标
        # --------------------------
        t = self.font_small.render(f"TARGETS: {len(targets)}", True, (180,255,255))
        surface.blit(t, (m+14, m+96))

        # --------------------------
        # FPS
        # --------------------------
        fpsc = (255,200,0) if fps < 30 else (150,255,180)
        surface.blit(self.font_small.render(f"FPS: {fps}", True, fpsc), (m+14, m+128))

        # --------------------------
        # 底部超级状态栏
        # --------------------------
        text = f"MODE: {mode.upper()}    SERIAL: {serial}"
        status_c = (255,50,50) if mode == "error" else (0,255,220)

        for g in [-2,0,2]:
            surf = self.font_small.render(text, True, status_c)
            r = surf.get_rect(center=(sw//2 + g, sh - 36 + g))
            surface.blit(surf, r)

        surf = self.font_small.render(text, True, (255,255,255))
        r = surf.get_rect(center=(sw//2, sh-36))
        bar = pygame.Surface((surf.get_width()+40, 40), pygame.SRCALPHA)
        pygame.draw.rect(bar, (10,20,40,180), (0,0,bar.get_width(),40), border_radius=12)
        pygame.draw.rect(bar, (0,255,210,255), (0,0,bar.get_width(),40), 3, border_radius=12)
        surface.blit(bar, (r.x-20, sh-46))
        surface.blit(surf, r)

# ====== 独立测试（完全不动你的原有代码）======
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

        if timer > 3000:
            timer = 0
            mock_state["score"]["value"] += 50

        screen.fill(COLOR_BLACK)
        hud.render(screen, mock_state, int(clock.get_fps()), dt)
        pygame.display.flip()

    pygame.quit()