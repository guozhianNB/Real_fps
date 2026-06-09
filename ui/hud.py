import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.config import *
from ui.assets import get_font

class HUD:
    def __init__(self):
        pygame.font.init()
        self.font_label = get_font(22)    # 标签：小字（≈原34的65%）
        self.font_value = get_font(40)    # 数值：大字（≈原52的77%）
        self.font_small = get_font(20)    # 辅助信息
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
        # 计分面板（半透明渐变背景）
        # --------------------------
        panel_w = 290
        panel_h = 200
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)

        # 深色半透明背景
        for i in range(panel_h):
            r = int(20 + 8 * (i / panel_h))
            g = int(12 + 10 * (i / panel_h))
            b = int(30 + 25 * (i / panel_h))
            pygame.draw.line(panel, (r, g, b, 180), (0, i), (panel_w, i))

        # 简洁边框（单层霓虹）
        pygame.draw.rect(panel, (0, 210, 255, 200), (0, 0, panel_w, panel_h), 2, border_radius=12)

        surface.blit(panel, (m, m))

        # --------------------------
        #  工具：投影文字渲染
        # --------------------------
        def shadow_text(font, text, color, x, y, shadow_color=(0,0,0), shadow_off=2):
            """绘制带投影的文字（只渲染 2 次，不发虚）。"""
            shadow = font.render(text, True, shadow_color)
            surface.blit(shadow, (x + shadow_off, y + shadow_off))
            main = font.render(text, True, color)
            surface.blit(main, (x, y))

        # ============================
        #  得分  标签+数值
        # ============================
        score_color = (255, 200, 0) if flash else (0, 220, 255)
        shadow_text(self.font_label, "得分", (150, 200, 255), m + 14, m + 14)
        # 数值紧随其后，大字突出
        sv = self.font_value.render(str(score), True, score_color)
        sv_shadow = self.font_value.render(str(score), True, (0, 0, 0))
        label_w = self.font_label.size("得分")[0]
        sv_x = m + 14 + label_w + 10
        sv_y = m + 10
        surface.blit(sv_shadow, (sv_x + 2, sv_y + 2))
        surface.blit(sv, (sv_x, sv_y))

        # 分数变化时闪高亮横线
        if flash:
            line_y = sv_y + self.font_value.get_height() + 4
            pygame.draw.line(surface, (255, 200, 0, 200), (m + 14, line_y), (m + panel_w - 16, line_y), 2)

        # ============================
        #  弹药  标签+数值 + 进度条
        # ============================
        MAX_AMMO = 30
        ammo_color = (255, 40, 60) if ammo < 10 else (0, 255, 140)

        ammo_label_y = m + 72
        shadow_text(self.font_label, "弹药", (150, 200, 255), m + 14, ammo_label_y)
        # 数值
        av = self.font_value.render(str(ammo), True, ammo_color)
        av_shadow = self.font_value.render(str(ammo), True, (0, 0, 0))
        label_w2 = self.font_label.size("弹药")[0]
        av_x = m + 14 + label_w2 + 10
        av_y = ammo_label_y - 4
        surface.blit(av_shadow, (av_x + 2, av_y + 2))
        surface.blit(av, (av_x, av_y))

        # 弹药进度条
        bar_w = panel_w - 24
        bar_h = 6
        bar_x = m + 14
        bar_y = m + 118
        fill_ratio = max(0, min(1, ammo / MAX_AMMO))
        if ammo > 15:
            bar_color = (0, 255, 100)
        elif ammo < 5:
            bar_color = (255, 40, 60)
        else:
            t = (ammo - 5) / 10.0
            r = int(255 - t * 200)
            g = int(200 + t * 55)
            bar_color = (max(0, r), min(255, g), 60)
        bar_bg = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        bar_bg.fill((40, 40, 50, 200))
        surface.blit(bar_bg, (bar_x, bar_y))
        if fill_ratio > 0:
            fill_w = int(bar_w * fill_ratio)
            bar_fill = pygame.Surface((fill_w, bar_h))
            bar_fill.fill(bar_color)
            surface.blit(bar_fill, (bar_x, bar_y))
        pygame.draw.rect(surface, (120, 120, 140, 180), (bar_x, bar_y, bar_w, bar_h), 1)

        # 分隔线
        sep_y = bar_y + bar_h + 16
        pygame.draw.line(surface, (60, 60, 80, 150), (m + 14, sep_y), (m + panel_w - 14, sep_y), 1)

        # ============================
        #  目标  /  FPS  同一行左右
        # ============================
        target_y = sep_y + 12
        shadow_text(self.font_small, f"目标: {len(targets)}", (180, 255, 255), m + 14, target_y)
        fps_color = (255, 200, 0) if fps < 30 else (150, 255, 180)
        fps_txt = f"FPS: {fps}"
        fps_x = m + panel_w - 16 - self.font_small.size(fps_txt)[0]
        shadow_text(self.font_small, fps_txt, fps_color, fps_x, target_y)

        # --------------------------
        # 底部状态栏（中文标签 + 投影）
        # --------------------------
        mode_label = "暂停" if mode == "paused" else "游戏中" if mode == "playing" else "结束" if mode == "over" else mode.upper()
        serial_label = "已连接" if serial == "OK" else serial
        text = f"模式: {mode_label}    串口: {serial_label}"
        status_color = (255, 50, 50) if mode == "error" else (0, 255, 220)
        text_surf = self.font_label.render(text, True, status_color)
        tr = text_surf.get_rect(center=(sw // 2, sh - 30))

        # 暗色背景条
        bar_w = text_surf.get_width() + 50
        bar_h = 36
        bar = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        bar.fill((8, 12, 24, 170))
        pygame.draw.rect(bar, (0, 220, 255, 180), (0, 0, bar_w, bar_h), 2, border_radius=8)
        surface.blit(bar, (tr.x - 25, tr.y - 8))

        # 文字 + 投影
        shadow = self.font_label.render(text, True, (0, 0, 0))
        surface.blit(shadow, (tr.x + 1, tr.y + 1))
        surface.blit(text_surf, tr)

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