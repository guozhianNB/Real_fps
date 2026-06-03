# ui/effects.py — 命中动画组件
#
# 提供 HitFlash（全屏闪白）和 ScorePopup（得分弹出）。
# 开火事件通过 UDP 实时接收（不经过 state.json），
# 调用 Effects.add_hit_flash() 触发动画。
#
# 可独立运行测试：python ui/effects.py  （空格模拟开火）

import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.assets import get_font_large


class BaseEffect:
    """动画基类。"""

    def __init__(self, ms):
        self.duration_ms = ms
        self.elapsed_ms = 0
        self.active = True

    def update(self, dt):
        """更新动画状态，返回是否继续活跃。"""
        if not self.active:
            return False
        self.elapsed_ms += dt
        if self.elapsed_ms >= self.duration_ms:
            self.active = False
            return False
        return True

    def render(self, surface):
        """子类实现具体绘制。"""
        pass


class HitFlash(BaseEffect):
    """全屏白色闪光（命中瞬间）。"""

    def __init__(self):
        super().__init__(FLASH_DURATION_MS)

    def render(self, surface):
        if not self.active:
            return
        progress = self.elapsed_ms / self.duration_ms
        alpha = int(80 * (1 - progress))
        flash = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        flash.fill((255, 255, 255, max(0, min(255, alpha))))
        surface.blit(flash, (0, 0))


class ScorePopup(BaseEffect):
    """得分弹出文字（"+50 headshot"），带淡入→停留→淡出。"""

    def __init__(self, delta, reason=""):
        total = POPUP_FADEIN_MS + POPUP_HOLD_MS + POPUP_FADEOUT_MS
        super().__init__(total)
        self.text = f"+{delta}{' ' + reason if reason else ''}"
        self.font = get_font_large()

    def render(self, surface):
        if not self.active:
            return

        fi = POPUP_FADEIN_MS
        ho = POPUP_FADEIN_MS + POPUP_HOLD_MS

        if self.elapsed_ms < fi:
            alpha = int(255 * self.elapsed_ms / fi)
        elif self.elapsed_ms < ho:
            alpha = 255
        else:
            fade = (self.elapsed_ms - ho) / POPUP_FADEOUT_MS
            alpha = int(255 * (1 - fade))

        alpha = max(0, min(255, alpha))

        text_surf = self.font.render(self.text, True, COLOR_YELLOW)
        # 用临时 Surface 控制透明度
        wrapper = pygame.Surface(text_surf.get_size(), pygame.SRCALPHA)
        wrapper.blit(text_surf, (0, 0))
        wrapper.set_alpha(alpha)

        rect = wrapper.get_rect(
            center=(surface.get_width() // 2, surface.get_height() // 2 - 50)
        )
        surface.blit(wrapper, rect)


class Effects:
    """动画管理器，管理所有活跃动画。"""

    def __init__(self):
        self.active_effects = []

    def add_hit_flash(self, zone="", delta=0):
        """添加命中反馈（得分弹出，无闪白）。

        参数：
            zone:  "head" / "body" / ""
            delta: 得分值
        """
        if delta > 0:
            reason = "headshot" if zone == "head" else "hit"
            self.active_effects.append(ScorePopup(delta, reason))

    def update(self, dt):
        """更新所有动画，移除已完成的。"""
        self.active_effects = [
            e for e in self.active_effects if e.update(dt)
        ]

    def render(self, surface):
        """绘制所有活跃动画。"""
        for e in self.active_effects:
            e.render(surface)


# ====== 独立测试 ======
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 500))
    pygame.display.set_caption("Effects 测试 — 空格触发开火")
    clock = pygame.time.Clock()

    fx = Effects()
    auto_timer = 0

    running = True
    while running:
        dt = clock.tick(60)
        auto_timer += dt

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                # 按空格模拟命中头部
                fx.add_hit_flash("head", 50)

        # 每 3 秒自动触发一次身体命中
        if auto_timer > 3000:
            auto_timer = 0
            fx.add_hit_flash("body", 10)

        fx.update(dt)

        screen.fill(COLOR_BLACK)

        # 提示文字
        info = pygame.font.Font(None, 24).render(
            f"空格触发 | 活跃动画: {len(fx.active_effects)}",
            True, COLOR_WHITE,
        )
        screen.blit(info, (20, 20))

        fx.render(screen)
        pygame.display.flip()

    pygame.quit()
