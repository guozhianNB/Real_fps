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
import random
import math

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
            center=(surface.get_width() // 2, surface.get_height() // 2 - 80)
        )
        surface.blit(wrapper, rect)


# ============================================================
#  粒子系统 — 击杀爆发
# ============================================================

class Particle:
    """单个粒子：位置、速度、生命、颜色、大小。"""

    def __init__(self, x, y, vx, vy, color, size=4, life_ms=600):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.life_ms = life_ms
        self.elapsed = 0

    def update(self, dt):
        self.elapsed += dt
        t = self.elapsed / self.life_ms
        # 速度衰减 + 轻微重力
        self.vx *= 0.96
        self.vy *= 0.96
        self.vy += 0.05  # 重力
        self.x += self.vx
        self.y += self.vy
        return t < 1.0

    def render(self, surface):
        t = self.elapsed / self.life_ms
        if t >= 1.0:
            return
        alpha = int(255 * (1 - t))
        size = max(1, int(self.size * (1 - t * 0.5)))
        c = (*self.color[:3], max(0, min(255, alpha)))
        pygame.draw.circle(surface, c, (int(self.x), int(self.y)), size)


class ParticleBurst(BaseEffect):
    """粒子爆发效果：在一点向四周飞散粒子。"""

    def __init__(self, x, y, zone="", count=25):
        super().__init__(800)  # 800ms 总时长
        self.particles = []
        # 颜色：头部=红橙，身体=绿
        if zone == "head":
            colors = [(255, 80, 40), (255, 150, 30), (255, 200, 60)]
        else:
            colors = [(0, 255, 100), (50, 255, 50), (100, 255, 150)]

        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(2, 7)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 2  # 轻微向上偏
            color = random.choice(colors)
            size = random.uniform(2, 6)
            life = random.uniform(400, 800)
            self.particles.append(Particle(x, y, vx, vy, color, size, life))

    def update(self, dt):
        if not super().update(dt):
            return False
        self.particles = [p for p in self.particles if p.update(dt)]
        return len(self.particles) > 0

    def render(self, surface):
        for p in self.particles:
            p.render(surface)


class Effects:
    """动画管理器，管理所有活跃动画。"""

    def __init__(self):
        self.active_effects = []

    def add_hit_flash(self, zone="", delta=0):
        """添加命中反馈（全屏闪白 + 得分弹出）。

        参数：
            zone:  "head" / "body" / ""
            delta: 得分值
        """
        if delta > 0:
            self.active_effects.append(HitFlash())
            reason = "headshot" if zone == "head" else "hit"
            self.active_effects.append(ScorePopup(delta, reason))

    def add_kill_effect(self, x, y, zone=""):
        """在指定屏幕位置生成击杀粒子爆发。

        参数：
            x, y:  目标在屏幕上的像素坐标
            zone:  "head"=红色粒子  "body"=绿色粒子
        """
        self.active_effects.append(ParticleBurst(x, y, zone))

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
