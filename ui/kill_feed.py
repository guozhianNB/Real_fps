# ui/kill_feed.py — 击杀通知组件
#
# 在左下角显示最近击杀信息，每条持续 3 秒后淡出。

import pygame
from ui.config import *
from ui.assets import alpha_surface, get_font

KILL_DURATION = 3000
MAX_ENTRIES = 4


class KillFeed:
    """击杀通知，在左下角逐条显示。"""

    def __init__(self):
        self.entries = []  # [(text, timer_ms), ...]

    def add_kill(self, hit_zone, score_delta, target_id):
        """添加一条击杀信息。"""
        zone_text = "头部" if hit_zone == "head" else "身体"
        text = f"目标 #{target_id}  {zone_text}  +{score_delta}"
        self.entries.append([text, KILL_DURATION])
        if len(self.entries) > MAX_ENTRIES:
            self.entries.pop(0)

    def update(self, dt_ms):
        """每帧更新计时。"""
        for entry in self.entries:
            entry[1] -= dt_ms
        self.entries = [e for e in self.entries if e[1] > 0]

    def render(self, surface):
        """在左下角绘制击杀信息（半透明黑底）。"""
        if not self.entries:
            return
        font = get_font(22)
        y = surface.get_height() - 40
        for text, timer in reversed(self.entries):
            alpha = int(min(255, timer / 500 * 255))
            alpha = max(0, min(255, alpha))

            text_surf = font.render(text, True, COLOR_WHITE)
            text_surf.set_alpha(alpha)
            tw, th = text_surf.get_size()

            # 半透明黑底
            bg = alpha_surface(tw + 16, th + 6, COLOR_BLACK, 140)
            bg.set_alpha(alpha)
            surface.blit(bg, (HUD_MARGIN + 5, y - 3))

            surface.blit(text_surf, (HUD_MARGIN + 13, y))
            y -= 36
