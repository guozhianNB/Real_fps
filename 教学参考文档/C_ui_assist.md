# C — UI 组件教程

> 👋 你好！你和 B 一起做 UI。B 负责**搭舞台**（窗口、背景、准星），你负责**往舞台上放道具**。
> 具体来说：你写**雷达**、**HUD 面板**、**命中动画**，以及**自测工具**。
> **每个文件都能独立运行测试，不需要依赖任何人——这是你最大的优势！💪**

---

## 📖 目录

1. [先搞懂几个概念](#1-先搞懂几个概念)
2. [安装环境](#2-安装环境)
3. [认识项目结构](#3-认识项目结构)
4. [文件 1：config.py（共用配置）](#4-文件-1-configpy共用配置)
5. [文件 2：assets.py（资源工具）](#5-文件-2-assetspy资源工具)
6. [文件 3：radar.py（雷达组件）](#6-文件-3-radarpy雷达组件)
7. [文件 4：hud.py（HUD 面板）](#7-文件-4-hudpyhud-面板)
8. [文件 5：effects.py（命中动画）](#8-文件-5-effectspy命中动画)
9. [文件 6：demo_reader.py（自测入口）](#9-文件-6-demo_readerpy自测入口)
10. [和 B 对接](#10-和-b-对接)
11. [常见问题](#11-常见问题)

---

## 1. 先搞懂几个概念

### Surface（画板）

Pygame 里，**Surface** 就是一块画板。`screen` 是最大的画板（整个窗口），你也可以创建小画板：

```python
my_surf = pygame.Surface((200, 200))
pygame.draw.circle(my_surf, (0,255,0), (100,100), 50)
screen.blit(my_surf, (100, 100))
```

你的工作方式就是：**在自己的小画板上画好雷达、HUD，然后交给 B 贴到主窗口上。**

### 透明度（Alpha）

```python
s = pygame.Surface((100, 100), pygame.SRCALPHA)
pygame.draw.circle(s, (0, 0, 0, 128), (50, 50), 30)
```

### 时间轴动画

用**时间差 dt（毫秒）**来控制，不依赖帧率：

```python
alpha = max(0, 255 - dt * (255 / 1000))
```

---

## 2. 安装环境

```powershell
pip install pygame requests opencv-python numpy
python -c "import pygame; print('Pygame:', pygame.version.ver)"
```

---

## 3. 认识项目结构

```
Real_fps/
├── ui/
│   ├── __init__.py         ← 空文件
│   ├── config.py           ← 颜色、位置常量
│   ├── assets.py           ← 字体加载工具
│   ├── radar.py            ← 你写：雷达 ⭐
│   ├── hud.py              ← 你写：HUD ⭐
│   ├── effects.py          ← 你写：动画 ⭐
│   ├── demo_reader.py      ← 你写：自测 ⭐
│   └── core.py             ← B 写：主循环
├── vision/                 ← 视觉模块
├── fire_notifier.py        ← 开火事件 UDP
├── main.py / start.py
└── 教学参考文档/
```

> 先去 `Real_fps` 下创建 `ui/` 文件夹！

---

## 4. 文件 1：config.py（共用配置）

```python
# ui/config.py
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS_TARGET = 60
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 255, 100)
COLOR_RED = (255, 50, 50)
COLOR_YELLOW = (255, 200, 0)
COLOR_HUD_BG = (0, 0, 0)
HUD_BG_ALPHA = 160
CROSSHAIR_SIZE = 20
RADAR_RADIUS = 75
RADAR_MARGIN = 20
HUD_MARGIN = 20
HUD_LINE_HEIGHT = 35
FLASH_DURATION_MS = 300
POPUP_FADEIN_MS = 200
POPUP_HOLD_MS = 1000
POPUP_FADEOUT_MS = 400
```

---

## 5. 文件 2：assets.py（资源工具）

```python
# ui/assets.py
import pygame
_font_cache = {}
def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
        _font_cache[key] = font
    return _font_cache[key]
def get_font_small(): return get_font(28)
def get_font_large(): return get_font(48)
def get_font_huge(): return get_font(72, bold=True)
def alpha_surface(w, h, color, alpha):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((*color, alpha))
    return surf
```

---

## 6. 文件 3：radar.py（雷达组件）

```python
# ui/radar.py
import pygame, math, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.config import *
from ui.assets import get_font_small

class Radar:
    def __init__(self, cx, cy, r=RADAR_RADIUS):
        self.cx, self.cy, self.r = cx, cy, r
        self.scan_angle = 0
        self.blink_timer = 0
        self.font = get_font_small()
    def render(self, surface, targets, dt_ms=16):
        cx, cy, r = self.cx, self.cy, self.r
        bg = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(bg, (0,0,0,120), (r,r), r)
        pygame.draw.circle(bg, COLOR_GREEN, (r,r), r, 2)
        surface.blit(bg, (cx-r, cy-r))
        pygame.draw.line(surface, COLOR_GREEN, (cx-r, cy), (cx+r, cy), 1)
        pygame.draw.line(surface, COLOR_GREEN, (cx, cy-r), (cx, cy+r), 1)
        self.scan_angle += 120 * (dt_ms / 1000)
        if self.scan_angle >= 360: self.scan_angle -= 360
        rad = math.radians(self.scan_angle)
        pygame.draw.line(surface, COLOR_GREEN, (cx, cy), (cx+r*math.cos(rad), cy+r*math.sin(rad)), 1)
        self.blink_timer += dt_ms
        scx, scy = SCREEN_WIDTH/2, SCREEN_HEIGHT/2
        for t in targets:
            dx = t.get("cx", scx) - scx
            dy = t.get("cy", scy) - scy
            d = math.hypot(dx, dy)
            if d > 0:
                s = min(r * 0.8 / d, 1.0)
                px, py = cx + dx*s, cy + dy*s
            else: px, py = cx, cy
            if (self.blink_timer % 400) < 200:
                pygame.draw.circle(surface, COLOR_GREEN, (int(px), int(py)), 4)
        label = self.font.render("RADAR", True, COLOR_GREEN)
        surface.blit(label, (cx - label.get_width()//2, cy - r - 20))

if __name__ == "__main__":
    pygame.init()
    s = pygame.display.set_mode((400, 500))
    clock = pygame.time.Clock()
    r = Radar(200, 300)
    ts = [{"id": 1, "cx": 640, "cy": 360}, {"id": 2, "cx": 600, "cy": 200}]
    run = True
    while run:
        dt = clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE): run = False
        s.fill(COLOR_BLACK)
        r.render(s, ts, dt_ms=dt)
        pygame.display.flip()
    pygame.quit()
```

---

## 7. 文件 4：hud.py（HUD 面板）

```python
# ui/hud.py
import pygame, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.config import *
from ui.assets import *

class HUD:
    def __init__(self):
        self.font_large = get_font_large()
        self.font_small = get_font_small()
        self.flash_timer = 0
        self.last_score = 0
    def render(self, surface, state, fps, dt_ms=16):
        score = state.get("score", {}).get("value", 0)
        targets = state.get("targets", [])
        mode = state.get("system_state", {}).get("mode", "idle")
        serial = state.get("serial", {}).get("status", "N/A")
        if score != self.last_score:
            self.flash_timer = 500
            self.last_score = score
        sc = COLOR_YELLOW if self.flash_timer > 0 else COLOR_WHITE
        self.flash_timer = max(0, self.flash_timer - dt_ms)
        panel = alpha_surface(250, 120, COLOR_BLACK, HUD_BG_ALPHA)
        surface.blit(panel, (HUD_MARGIN-5, HUD_MARGIN-5))
        surf = self.font_large.render(f"SCORE: {score}", True, sc)
        surface.blit(surf, (HUD_MARGIN, HUD_MARGIN))
        surf = self.font_small.render(f"TARGETS: {len(targets)}", True, COLOR_WHITE)
        surface.blit(surf, (HUD_MARGIN, HUD_MARGIN+45))
        c = COLOR_YELLOW if fps < 30 else COLOR_WHITE
        surf = self.font_small.render(f"FPS: {fps}", True, c)
        surface.blit(surf, (HUD_MARGIN, HUD_MARGIN+75))
        text = f"MODE: {mode.upper()}  |  SERIAL: {serial}"
        surf = self.font_small.render(text, True, COLOR_RED if mode=="error" else COLOR_WHITE)
        sw = surface.get_width()
        bg = alpha_surface(surf.get_width()+20, surf.get_height()+10, COLOR_BLACK, HUD_BG_ALPHA)
        surface.blit(bg, bg.get_rect(center=(sw//2, surface.get_height()-30)))
        surface.blit(surf, surf.get_rect(center=(sw//2, surface.get_height()-30)))

if __name__ == "__main__":
    pygame.init()
    s = pygame.display.set_mode((800, 400))
    clock = pygame.time.Clock()
    hud = HUD()
    st = {"score": {"value": 100}, "targets": [{"id": 1}], "system_state": {"mode": "playing"}, "serial": {"status": "OK"}}
    tmr = 0
    run = True
    while run:
        dt = clock.tick(60)
        tmr += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE): run = False
        if tmr > 3000: tmr = 0; st["score"]["value"] += 50
        s.fill(COLOR_BLACK)
        hud.render(s, st, int(clock.get_fps()), dt)
        pygame.display.flip()
    pygame.quit()
```

---

## 8. 文件 5：effects.py（命中动画）

> ⚠️ 开火事件不走 JSON！通过 UDP 实时接收，调用 add_hit_flash() 触发。

```python
# ui/effects.py
import pygame, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.config import *
from ui.assets import get_font_large

class BaseEffect:
    def __init__(self, ms): self.duration_ms = ms; self.elapsed_ms = 0; self.active = True
    def update(self, dt):
        if not self.active: return False
        self.elapsed_ms += dt
        if self.elapsed_ms >= self.duration_ms: self.active = False; return False
        return True
    def render(self, surface): pass

class HitFlash(BaseEffect):
    def __init__(self): super().__init__(FLASH_DURATION_MS)
    def render(self, surface):
        if not self.active: return
        p = self.elapsed_ms / self.duration_ms
        a = int(80 * (1 - p))
        f = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        f.fill((255, 255, 255, max(0, min(255, a))))
        surface.blit(f, (0, 0))

class ScorePopup(BaseEffect):
    def __init__(self, delta, reason=""):
        super().__init__(POPUP_FADEIN_MS + POPUP_HOLD_MS + POPUP_FADEOUT_MS)
        self.text = f"+{delta}{' '+reason if reason else ''}"
        self.font = get_font_large()
    def render(self, surface):
        if not self.active: return
        fi, ho = POPUP_FADEIN_MS, POPUP_FADEIN_MS + POPUP_HOLD_MS
        if self.elapsed_ms < fi: a = int(255 * self.elapsed_ms / fi)
        elif self.elapsed_ms < ho: a = 255
        else: a = int(255 * (1 - (self.elapsed_ms - ho) / POPUP_FADEOUT_MS))
        a = max(0, min(255, a))
        t = self.font.render(self.text, True, COLOR_YELLOW)
        wa = pygame.Surface(t.get_size(), pygame.SRCALPHA); wa.blit(t, (0, 0)); wa.set_alpha(a)
        surface.blit(wa, wa.get_rect(center=(surface.get_width()//2, surface.get_height()//2 - 50)))

class Effects:
    def __init__(self): self.active_effects = []
    def add_hit_flash(self, zone="", delta=0):
        self.active_effects.append(HitFlash())
        if delta > 0: self.active_effects.append(ScorePopup(delta, "headshot" if zone=="head" else "hit"))
    def update(self, dt): self.active_effects = [e for e in self.active_effects if e.update(dt)]
    def render(self, surface):
        for e in self.active_effects: e.render(surface)

if __name__ == "__main__":
    pygame.init()
    s = pygame.display.set_mode((800, 500))
    clock = pygame.time.Clock()
    fx = Effects(); tmr = 0
    run = True
    while run:
        dt = clock.tick(60); tmr += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE): run = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE: fx.add_hit_flash("head", 50)
        if tmr > 3000: tmr = 0; fx.add_hit_flash("body", 10)
        fx.update(dt)
        s.fill(COLOR_BLACK)
        f = pygame.font.Font(None, 24)
        s.blit(f.render(f"空格触发 | 活跃: {len(fx.active_effects)}", True, COLOR_WHITE), (20, 20))
        fx.render(s)
        pygame.display.flip()
    pygame.quit()
```

---

## 9. 文件 6：demo_reader.py（自测入口）

模拟主程序写 state.json + UDP 开火，让你独立测试全部组件。

```python
# ui/demo_reader.py
import pygame, json, threading, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.config import *
from ui.radar import Radar
from ui.hud import HUD
from ui.effects import Effects
from fire_notifier import FireListener, send_fire

class MockWriter:
    def __init__(self): self._stop = threading.Event()
    def start(self): threading.Thread(target=self._loop, daemon=True).start()
    def stop(self): self._stop.set()
    def _loop(self):
        scenes = [
            {"system_state": {"mode": "idle"}, "score": {"value": 0}, "targets": [], "serial": {"status": "OK"}},
            {"system_state": {"mode": "playing"}, "score": {"value": 0}, "targets": [{"id": 1, "bbox": [620, 240, 780, 420]}], "serial": {"status": "OK"}},
            {"system_state": {"mode": "playing", "msg": "命中！"}, "score": {"value": 50}, "targets": [{"id": 1, "bbox": [600, 320, 680, 400]}], "serial": {"status": "OK"}},
            {"system_state": {"mode": "over", "msg": "串口断开"}, "score": {"value": 50}, "targets": [], "serial": {"status": "ERROR"}},
        ]
        idx = 0
        while not self._stop.is_set():
            s = scenes[idx % 4]; s["timestamp"] = time.time()
            with open("state.json", "w") as f: json.dump(s, f)
            if idx % 4 == 2: send_fire(hit_zone="head", score_delta=50)
            idx += 1; time.sleep(2.5)

def read_status():
    try:
        with open("state.json") as f: return json.loads(f.read())
    except: return {}

def main():
    print("=== UI 自测 ===")
    w = MockWriter(); w.start()
    pygame.init()
    W, H = 1280, 720
    s = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    FIRE = pygame.USEREVENT + 1
    def on_fire(e): pygame.event.post(pygame.event.Event(FIRE, e))
    lis = FireListener(callback=on_fire); lis.start()
    radar = Radar(W - RADAR_RADIUS - RADAR_MARGIN, H - RADAR_RADIUS - RADAR_MARGIN)
    hud = HUD(); fx = Effects()
    run, last = True, {}
    while run:
        dt = clock.tick(FPS_TARGET)
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE): run = False
            elif e.type == FIRE: fx.add_hit_flash(e.__dict__.get("hit_zone", ""), e.__dict__.get("score_delta", 0))
        st = read_status() or last; last = st
        fx.update(dt)
        s.fill(COLOR_BLACK)
        ts = st.get("targets", [])
        radar.render(s, ts, dt_ms=dt)
        hud.render(s, st, int(clock.get_fps()), dt)
        fx.render(s)
        pygame.display.flip()
    w.stop(); lis.stop(); pygame.quit()

if __name__ == "__main__": main()
```

---

## 10. 和 B 对接

写完后告诉 B，B 会做三件事：

### 1. 在 core.py 顶部加 import
```python
from ui.radar import Radar
from ui.hud import HUD
from ui.effects import Effects
```

### 2. 在 UI.__init__ 中创建实例
```python
self.radar = Radar(SCREEN_WIDTH - 75 - 20, SCREEN_HEIGHT - 75 - 20)
self.hud = HUD()
self.effects = Effects()
```

### 3. 在 _render 中调用
```python
if self.radar: self.radar.render(self.screen, targets, dt_ms=16)
if self.hud: self.hud.render(self.screen, state, fps, dt_ms=16)
if self.effects: self.effects.render(self.screen)
```

### 4. 开火事件：B 的 core.py 已集成 FireListener
收到 UDP 开火事件 → 自动调用 `effects.add_hit_flash(...)`

---

## 11. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| ModuleNotFoundError: No module named 'ui' | 运行目录不对 | 在 Real_fps 目录下运行 |
| 雷达不显示 | 位置坐标算错了 | 检查 Radar 的 cx, cy |
| 动画不播放 | 没调 update() | 确保每帧调 effects.update(dt) |
| import 报红波浪线 | VS Code 找不到 | 只要 `python ui/x.py` 能跑就不用管 |

---

## 🎯 你的学习路线

1. **复制 config.py 和 assets.py**
2. **运行 `python ui/radar.py`** → 看到雷达 ✅
3. **运行 `python ui/hud.py`** → 看到分数 ✅
4. **运行 `python ui/effects.py`** → 按空格闪白 ✅
5. **运行 `python ui/demo_reader.py`** → 三个组件一起出现 🎉
6. **告诉 B："我写好了！"**

每个文件都能独立运行。先跑起来，再优化。加油！💪
