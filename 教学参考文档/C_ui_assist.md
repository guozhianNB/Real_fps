# C — UI 辅助模块（零基础入门版）

> 这份文档是**手把手教程**，假设你只有最基础的 Python 语法知识。
> 每个概念都会先解释「是什么」再告诉你「怎么写」。
> **所有代码都是完整的、可以直接复制运行**。

你和 B 都是做 UI 的。B 负责**主窗口**（游戏循环、摄像头背景、准星、目标框），
你负责**UI 组件**（雷达、HUD 面板、命中动画）和**测试工具**。

> 💡 **简单理解：B 搭好了舞台，你往舞台上放道具。**

---

## 目录

1. [你需要先理解的概念](#1-你需要先理解的概念)
2. [安装环境](#2-安装环境)
3. [项目文件结构](#3-项目文件结构)
4. [文件 1：ui/config.py — 共用配置](#4-文件-1-uiconfigpy--共用配置)
5. [文件 2：ui/assets.py — 资源加载](#5-文件-2-uiassetspy--资源加载)
6. [文件 3：ui/radar.py — 雷达组件（独立可测试）](#6-文件-3-uiradarpy--雷达组件独立可测试)
7. [文件 4：ui/hud.py — HUD 面板](#7-文件-4-uihudpy--hud-面板)
8. [文件 5：ui/effects.py — 动画效果](#8-文件-5-uieffectspy--动画效果)
9. [文件 6：ui/demo_reader.py — 自测入口](#9-文件-6-uidemo_readerpy--自测入口)
10. [如何和 B 对接](#10-如何和-b-对接)
11. [常见错误与解决](#11-常见错误与解决)

---

## 1. 你需要先理解的概念

### 什么是 Surface（表面）？

在 Pygame 中，**Surface** 就是一块"画板"。你可以在上面画图、贴字。

- `screen` = 整个窗口的画板
- 你也可以创建**独立的画板**，在上面画好东西后，再贴到 `screen` 上

这就是你的工作方式：**在独立的 Surface 上画好雷达、HUD，然后交给 B 贴到窗口上**。

```python
# 创建一个 200x200 的独立画板
my_surface = pygame.Surface((200, 200))

# 在上面画东西
pygame.draw.circle(my_surface, (0, 255, 0), (100, 100), 50)

# 贴到主窗口上
screen.blit(my_surface, (100, 100))
```

### 什么是透明度（Alpha）？

透明度让一个像素"半透明"，能看到底下的内容。

在 Pygame 中，有两种透明度：
1. **Surface 整体透明度**：整个画板半透明
2. **每个像素的 Alpha**：不同的像素可以有不同的透明度（需要 `pygame.SRCALPHA`）

```python
# 创建一个支持每像素透明的 Surface
# SRCALPHA 让这个 Surface 的每个像素都有一个 Alpha 通道
s = pygame.Surface((100, 100), pygame.SRCALPHA)

# 画一个半透明的圆（255=不透明，0=全透明）
pygame.draw.circle(s, (0, 0, 0, 128), (50, 50), 30)
```

### 什么是时间轴动画？

动画就是**随时间变化画面**。比如"淡出"就是透明度随时间从 255 降到 0。

你的动画用**时间差（dt）**来控制，而不是用"第几帧"。
这样即使帧率波动，动画速度也是稳定的。

```python
# dt = 距离上一帧的毫秒数
# 每秒降 255 透明度（1 秒内从完全不透明到完全透明）
alpha = max(0, 255 - dt * (255 / 1000))
```

---

## 2. 安装环境

打开终端（Terminal），依次执行：

```powershell
# 安装 Pygame
pip install pygame

# 安装 requests（摄像头画面拉取）
pip install requests

# 安装 opencv-python（图像解码）
pip install opencv-python

# 如果 pip 不行，用这个：
python -m pip install pygame requests opencv-python

# 验证安装
python -c "import pygame; print('Pygame 版本:', pygame.version.ver)"
```

---

## 3. 项目文件结构

你和 B 的代码都在 `ui/` 文件夹下：

```
Real_fps/
├── ui/                         ← 你和 B 的工作目录（需手动创建）
│   ├── __init__.py             ← 空文件（让 ui/ 成为 Python 包）
│   ├── config.py               ← 颜色、位置、尺寸常量（和 B 共用）
│   ├── assets.py               ← 字体加载工具
│   ├── radar.py                ← 你写：雷达组件 ⭐ 主要
│   ├── hud.py                  ← 你写：HUD 面板 ⭐ 主要
│   ├── effects.py              ← 你写：命中/击杀动画 ⭐ 主要
│   ├── demo_reader.py          ← 你写：自测入口 ⭐ 主要
│   └── core.py                 ← B 写：UI 主循环
├── vision/                     ← 视觉模块（已实现，含有摄像头工具）
│   ├── camera_share.py         ← FastAPI 摄像头共享服务（端口 8010）
│   ├── vision.py               ← YOLO 人体跟踪
│   └── get_camera.py           ← 获取摄像头画面的工具函数
├── main.py                     ← 主程序入口
├── start.py                    ← 启动器
├── readme.md
└── requirement.txt
```

**请先在 `Real_fps` 文件夹下创建 `ui` 文件夹。**

---

## 4. 文件 1：`ui/config.py` — 共用配置

B 已经写好了这个文件。**你不需要改它，只需要 import 使用。**

但你要**理解它**：

```python
# ui/config.py
# 所有 UI 相关的配置常量
# B 和 C 共用这个文件，确保颜色、位置统一

# ====== 窗口设置 ======
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS_TARGET = 60

# ====== 颜色 ======
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 255, 100)     # 正常状态
COLOR_RED = (255, 50, 50)       # 锁定/警告
COLOR_YELLOW = (255, 200, 0)    # 过渡色
COLOR_HUD_BG = (0, 0, 0)
HUD_BG_ALPHA = 160

# ====== 布局 ======
CROSSHAIR_SIZE = 20
RADAR_RADIUS = 75
RADAR_MARGIN = 20
HUD_MARGIN = 20
HUD_LINE_HEIGHT = 35

# ====== 轮询 ======
STATUS_FILE = "state.json"
JSON_POLL_INTERVAL = 0.05

# ====== 动画 ======
FLASH_DURATION_MS = 300
POPUP_FADEIN_MS = 200
POPUP_HOLD_MS = 1000
POPUP_FADEOUT_MS = 400
```

在代码中这样使用：

```python
from ui.config import *

# 现在你可以直接用这些名字了
print(SCREEN_WIDTH)      # 1280
print(COLOR_GREEN)       # (0, 255, 100)
```

---

## 5. 文件 2：`ui/assets.py` — 资源加载

这个文件提供**字体加载**功能。Pygame 需要字体才能显示文字。

```python
# ui/assets.py
# 资源加载工具
# 提供统一的字体获取方式

import pygame

# ==============================================
#   字体缓存
# ==============================================
# 缓存已加载的字体，避免重复创建
# _font_cache 是一个字典，key=字号，value=Font 对象
_font_cache = {}

def get_font(size, bold=False):
    """获取指定大小的字体。
    
    参数：
        size: 字号（像素）
        bold: 是否加粗
    
    返回：
        pygame.font.Font 对象
    
    用法：
        font = get_font(28)
        text = font.render("Hello", True, (255, 255, 255))
    """
    # 创建缓存的 key：字号 + 是否加粗
    key = (size, bold)
    
    if key not in _font_cache:
        # 如果缓存中还没有这个字号，就创建一个
        # Font(None, size) 使用 Pygame 默认字体
        # Font("路径", size) 使用指定字体文件
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
        _font_cache[key] = font
    
    return _font_cache[key]


def get_font_small():
    """快捷方式：获取小号字体（28px）"""
    return get_font(28)


def get_font_large():
    """快捷方式：获取大号字体（48px）"""
    return get_font(48)


def get_font_huge():
    """快捷方式：获取超大号字体（72px）"""
    return get_font(72, bold=True)


# ==============================================
#   颜色工具
# ==============================================

def alpha_surface(width, height, color, alpha):
    """创建一个带透明度的纯色 Surface。
    
    参数：
        width, height: 尺寸
        color: RGB 颜色元组
        alpha: 透明度（0-255，0=全透明，255=不透明）
    
    返回：
        pygame.Surface 对象
    
    用法：
        bg = alpha_surface(200, 100, (0, 0, 0), 160)
        screen.blit(bg, (20, 20))
    """
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    surf.fill((*color, alpha))
    return surf
```

---

## 6. 文件 3：`ui/radar.py` — 雷达组件（独立可测试）

### 6.1 学习目标

- 画圆、画线
- 角度计算（数学的三角函数）
- 旋转动画
- 独立 Surface 的使用

### 6.2 完整代码

```python
# ui/radar.py
# 雷达组件
#
# 功能：
#   - 右下角小圆形雷达
#   - 旋转扫描线
#   - 显示目标位置（闪烁圆点）
#
# 这个文件可以独立运行测试！
#   python ui/radar.py

import pygame
import math
import sys
import os

# 让 Python 能找到 ui 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.assets import get_font_small

# ==============================================
#   Radar 类
# ==============================================

class Radar:
    """雷达组件。
    
    用法：
        radar = Radar(右下角x坐标, 右下角y坐标)
        radar.render(screen, targets, locked_target_id)
    """
    
    def __init__(self, center_x, center_y, radius=RADAR_RADIUS):
        """初始化雷达。
        
        参数：
            center_x: 雷达中心 x 坐标
            center_y: 雷达中心 y 坐标
            radius: 雷达半径（像素）
        """
        self.center_x = center_x
        self.center_y = center_y
        self.radius = radius
        
        # 扫描线角度（度），从 0 开始，每帧增加
        self.scan_angle = 0
        
        # 目标点的闪烁控制
        # 用时间（毫秒）来控制闪烁，而不是帧数
        self.blink_timer = 0
        
        # 字体
        self.font = get_font_small()
    
    def render(self, surface, targets, locked_target_id=None, dt_ms=16):
        """在给定 Surface 上绘制雷达。
        
        参数：
            surface: 要绘制到的 Pygame Surface
            targets: 目标列表（每个目标有 cx, cy, id）
            locked_target_id: 不使用（保留参数兼容）
            dt_ms: 距上一帧的毫秒数（用于动画）
        """
        cx, cy, r = self.center_x, self.center_y, self.radius
        
        # ---- 1. 画雷达底色 ----
        # 先画一个半透明黑色圆作为背景
        # 创建一个临时 Surface 来画半透明效果
        radar_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(radar_surf, (0, 0, 0, 120), (r, r), r)
        # 画边框
        pygame.draw.circle(radar_surf, COLOR_GREEN, (r, r), r, 2)
        # 贴到主 surface 上
        surface.blit(radar_surf, (cx - r, cy - r))
        
        # ---- 2. 画十字参考线 ----
        # 两条垂直的线，把雷达分成四象限
        pygame.draw.line(surface, COLOR_GREEN, (cx - r, cy), (cx + r, cy), 1)
        pygame.draw.line(surface, COLOR_GREEN, (cx, cy - r), (cx, cy + r), 1)
        
        # ---- 3. 更新扫描线角度 ----
        # 每秒转 120 度（速度适中）
        # dt_ms 是毫秒，除以 1000 变成秒
        self.scan_angle += 120 * (dt_ms / 1000)
        if self.scan_angle >= 360:
            self.scan_angle -= 360
        
        # ---- 4. 画扫描线 ----
        # 用三角函数把角度转成坐标
        # math.radians(角度) 把度转成弧度（Python 的数学函数用弧度）
        angle_rad = math.radians(self.scan_angle)
        end_x = cx + r * math.cos(angle_rad)
        end_y = cy + r * math.sin(angle_rad)
        pygame.draw.line(surface, COLOR_GREEN, (cx, cy), (end_x, end_y), 1)
        
        # ---- 5. 画目标点 ----
        # 更新闪烁计时
        self.blink_timer += dt_ms
        
        for target in targets:
            # 每个目标有 cx, cy（屏幕坐标）
            # 需要把屏幕坐标转换成雷达上的相对位置
            # 假设雷达覆盖整个屏幕范围
            # 屏幕中心 = (SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
            # 目标相对屏幕中心的偏移
            screen_cx = SCREEN_WIDTH / 2
            screen_cy = SCREEN_HEIGHT / 2
            
            t_cx = target.get("cx", screen_cx)
            t_cy = target.get("cy", screen_cy)
            
            # 计算偏移（屏幕中心到目标的方向）
            dx = t_cx - screen_cx
            dy = t_cy - screen_cy
            
            # 限制最大距离（防止超出雷达范围）
            max_dist = math.sqrt(screen_cx**2 + screen_cy**2)
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 0:
                # 缩放到雷达范围内
                scale = min(r * 0.8 / dist, 1.0)
                radar_x = cx + dx * scale
                radar_y = cy + dy * scale
            else:
                radar_x, radar_y = cx, cy
            
            # 所有目标统一绿色闪烁
            color = COLOR_GREEN
            blink_speed = 400  # 400ms 闪烁一次
            
            # 闪烁效果：当 (blink_timer % blink_speed) < blink_speed/2 时显示
            if (self.blink_timer % blink_speed) < (blink_speed // 2):
                # 画目标点
                pygame.draw.circle(surface, color, (int(radar_x), int(radar_y)), 4)
        
        # ---- 6. 画雷达标题 ----
        label = self.font.render("RADAR", True, COLOR_GREEN)
        surface.blit(label, (cx - label.get_width() // 2, cy - r - 20))


# ==============================================
#   独立测试入口
# ==============================================

def test_radar():
    """独立运行雷达测试。"""
    pygame.init()
    
    WIDTH, HEIGHT = 400, 500
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("雷达组件测试")
    clock = pygame.time.Clock()
    
    # 创建雷达（放在窗口中央偏下）
    radar = Radar(WIDTH // 2, HEIGHT // 2 + 30)
    
    # 模拟两个目标
    test_targets = [
        {"id": 1, "cx": 640, "cy": 360},
        {"id": 2, "cx": 600, "cy": 200},
    ]
    
    running = True
    while running:
        dt = clock.tick(60)  # dt 是毫秒
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        screen.fill(COLOR_BLACK)
        
        # 画说明
        font = pygame.font.Font(None, 24)
        text = font.render("目标1(640,360) 锁定 | 目标2(600,200) 普通", True, COLOR_WHITE)
        screen.blit(text, (20, 20))
        
        # 画雷达（锁定目标 ID=1）
        radar.render(screen, test_targets, locked_target_id=1, dt_ms=dt)
        
        pygame.display.flip()
    
    pygame.quit()


if __name__ == "__main__":
    print("=== 雷达组件独立测试 ===")
    print("按 ESC 退出\n")
    test_radar()
```

### 6.3 理解雷达的数学

雷达把**屏幕坐标**映射到**雷达小圆**上：

```
目标在 (640, 360)，屏幕中心在 (640, 360)
→ 偏移 (0, 0) → 雷达上在正中央

目标在 (800, 360)，屏幕中心在 (640, 360)
→ 偏移 (160, 0) → 雷达上在右边
```

这个映射就是用**比例缩放**实现的：把大屏幕的距离缩放到小雷达里。

### 6.4 独立测试

运行 `python ui/radar.py`，你应该看到一个绿色的雷达在闪烁，两个目标点以不同频率闪烁。

---

## 7. 文件 4：`ui/hud.py` — HUD 面板

### 7.1 学习目标

- 文字渲染和排版
- Surface 的 alpha 透明度
- 条件渲染（不同状态下显示不同颜色）

### 7.2 完整代码

```python
# ui/hud.py
# HUD 面板组件
#
# 功能：
#   - 左上角 Score 显示
#   - 左上角 Targets 计数
#   - 左上角 FPS 显示
#   - 底部状态栏
#
# 独立测试：python ui/hud.py

import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.assets import get_font_small, get_font_large, alpha_surface

# ==============================================
#   HUD 类
# ==============================================

class HUD:
    """HUD 面板组件。
    
    用法：
        hud = HUD()
        hud.render(screen, state, fps)
    """
    
    def __init__(self):
        """初始化 HUD。"""
        self.font_large = get_font_large()
        self.font_small = get_font_small()
        
        # Score 闪烁动画
        self.score_flash_timer = 0
        self.score_flash_duration = 500  # 闪烁持续 500ms
        self.last_score_value = 0
    
    def render(self, surface, state, fps, dt_ms=16):
        """在给定 Surface 上绘制 HUD。
        
        参数：
            surface: 要绘制到的 Pygame Surface
            state: 当前状态字典（从 JSON 解析）
            fps: 当前帧率（由 B 传入）
            dt_ms: 距上一帧的毫秒数
        """
        # ---- 1. 准备数据 ----
        score_data = state.get("score", {})
        score_value = score_data.get("value", 0)
        score_delta = score_data.get("delta", 0)
        
        targets = state.get("targets", [])
        target_count = len(targets)
        
        sys_state = state.get("system_state", {})
        mode = sys_state.get("mode", "idle")
        msg = sys_state.get("msg", "")
        
        serial = state.get("serial", {})
        serial_status = serial.get("status", "N/A")
        
        # ---- 2. 左上角面板背景 ----
        # 半透明黑色背景，让文字更清晰
        panel_width = 250
        panel_height = 120
        panel = alpha_surface(panel_width, panel_height, COLOR_BLACK, HUD_BG_ALPHA)
        surface.blit(panel, (HUD_MARGIN - 5, HUD_MARGIN - 5))
        
        # ---- 3. Score ----
        # 检查分数是否变化（触发闪烁）
        if score_value != self.last_score_value:
            self.score_flash_timer = self.score_flash_duration
            self.last_score_value = score_value
        
        # 决定 Score 颜色
        if self.score_flash_timer > 0:
            score_color = COLOR_YELLOW  # 闪烁时用黄色
            self.score_flash_timer -= dt_ms
        else:
            score_color = COLOR_WHITE
        
        score_surf = self.font_large.render(f"SCORE: {score_value}", True, score_color)
        surface.blit(score_surf, (HUD_MARGIN, HUD_MARGIN))
        
        # 如果有 delta，在旁边显示 +分
        if score_delta > 0:
            delta_surf = self.font_small.render(f"+{score_delta}", True, COLOR_YELLOW)
            surface.blit(delta_surf, (HUD_MARGIN + score_surf.get_width() + 10, HUD_MARGIN + 10))
        
        # ---- 4. Targets ----
        targets_surf = self.font_small.render(f"TARGETS: {target_count}", True, COLOR_WHITE)
        surface.blit(targets_surf, (HUD_MARGIN, HUD_MARGIN + 45))
        
        # ---- 5. FPS ----
        # FPS 低了就变黄，正常就白色
        fps_color = COLOR_YELLOW if fps < 30 else COLOR_WHITE
        fps_surf = self.font_small.render(f"FPS: {fps}", True, fps_color)
        surface.blit(fps_surf, (HUD_MARGIN, HUD_MARGIN + 75))
        
        # ---- 6. 底部状态栏 ----
        # 只有 error 时变红，其余一律白色
        if mode == "error":
            status_color = COLOR_RED
        else:
            status_color = COLOR_WHITE
        
        # 构建状态文本
        status_text = f"MODE: {mode.upper()}"
        if serial_status:
            status_text += f"  |  SERIAL: {serial_status}"
        if msg:
            status_text += f"  |  {msg}"
        
        status_surf = self.font_small.render(status_text, True, status_color)
        
        # 底部居中
        screen_width = surface.get_width()
        status_rect = status_surf.get_rect(center=(screen_width // 2, surface.get_height() - 30))
        
        # 给状态栏也加半透明背景
        bg_w = status_surf.get_width() + 20
        bg_h = status_surf.get_height() + 10
        bg = alpha_surface(bg_w, bg_h, COLOR_BLACK, HUD_BG_ALPHA)
        bg_rect = bg.get_rect(center=(screen_width // 2, surface.get_height() - 30))
        surface.blit(bg, bg_rect)
        
        surface.blit(status_surf, status_rect)


# ==============================================
#   独立测试入口
# ==============================================

def test_hud():
    """独立运行 HUD 测试。"""
    pygame.init()
    
    WIDTH, HEIGHT = 800, 400
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("HUD 组件测试")
    clock = pygame.time.Clock()
    
    hud = HUD()
    
    # 模拟状态
    test_state = {
        "score": {"value": 100, "delta": 0, "reason": ""},
        "targets": [
            {"id": 1, "cx": 640, "cy": 360}
        ],
        "system_state": {"mode": "tracking", "msg": "normal"},
        "serial": {"status": "OK", "msg": "connected"},
        "target_lock": {"locked": False}
    }
    
    # 让分数变化的计时器
    change_timer = 0
    
    running = True
    while running:
        dt = clock.tick(60)
        change_timer += dt
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # 每 3 秒模拟一次加分
        if change_timer > 3000:
            change_timer = 0
            test_state["score"]["value"] += 50
            test_state["score"]["delta"] = 50
        
        screen.fill(COLOR_BLACK)
        
        # 画一些说明
        font = pygame.font.Font(None, 24)
        info = font.render("每 3 秒模拟加分一次，观察 Score 闪烁", True, COLOR_WHITE)
        screen.blit(info, (20, 20))
        
        hud.render(screen, test_state, int(clock.get_fps()), dt)
        
        pygame.display.flip()
    
    pygame.quit()


if __name__ == "__main__":
    print("=== HUD 组件独立测试 ===")
    print("按 ESC 退出\n")
    test_hud()
```

---

## 8. 文件 5：`ui/effects.py` — 动画效果

### 8.1 学习目标

- 基于时间轴（dt）的动画
- 透明度渐变（淡入淡出）
- 缩放动画
- 管理多个同时运行的效果

### 8.2 完整代码

```python
# ui/effects.py
# 动画效果组件
#
# 功能：
#   - 命中闪光（全屏白色半透明闪烁）
#   - 得分弹出提示（+分数）
#
# 独立测试：python ui/effects.py

import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.assets import get_font_large, get_font_small

# ==============================================
#   效果基类
# ==============================================

class BaseEffect:
    """所有效果的基类。
    
    每个效果都有的功能：
    - active: 是否还在播放
    - update(dt_ms): 更新动画状态
    - render(surface): 绘制到画面
    """
    
    def __init__(self, duration_ms):
        self.duration_ms = duration_ms  # 总持续时间
        self.elapsed_ms = 0             # 已播放时间
        self.active = True              # 是否活跃
    
    def update(self, dt_ms):
        """更新动画状态。
        
        参数：
            dt_ms: 距上一帧的毫秒数
        
        返回：
            True 表示还在播放，False 表示已结束
        """
        if not self.active:
            return False
        
        self.elapsed_ms += dt_ms
        
        if self.elapsed_ms >= self.duration_ms:
            self.active = False  # 动画结束
            return False
        
        return True
    
    def render(self, surface):
        """子类实现具体的绘制逻辑。"""
        pass


# ==============================================
#   命中闪光效果
# ==============================================

class HitFlash(BaseEffect):
    """命中闪光：全屏白色半透明，然后淡出。
    
    触发条件：fire_state.fired == True
    持续 300ms：从 alpha=80 降到 alpha=0
    """
    
    def __init__(self):
        super().__init__(duration_ms=FLASH_DURATION_MS)
    
    def render(self, surface):
        """绘制闪光效果。"""
        if not self.active:
            return
        
        # 计算当前透明度
        # 进度 = 已过时间 / 总时间 (0.0 ~ 1.0)
        progress = self.elapsed_ms / self.duration_ms
        
        # 透明度从 80 线性降到 0
        alpha = int(80 * (1 - progress))
        alpha = max(0, min(255, alpha))
        
        # 创建一个全屏大小的半透明白色 Surface
        flash = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        flash.fill((255, 255, 255, alpha))
        surface.blit(flash, (0, 0))


# ==============================================
#   得分弹出提示
# ==============================================

class ScorePopup(BaseEffect):
    """得分弹出：在屏幕中央显示 "+分数"。
    
    生命周期：
      淡入 200ms → 保持 1000ms → 淡出 400ms
    """
    
    def __init__(self, score_delta, reason=""):
        super().__init__(duration_ms=POPUP_FADEIN_MS + POPUP_HOLD_MS + POPUP_FADEOUT_MS)
        self.score_delta = score_delta
        self.reason = reason
        self.text = f"+{score_delta}"
        if reason:
            self.text += f" {reason}"
        
        self.font = get_font_large()
    
    def render(self, surface):
        """绘制得分提示。"""
        if not self.active:
            return
        
        # 计算当前阶段
        fadein_end = POPUP_FADEIN_MS
        hold_end = fadein_end + POPUP_HOLD_MS
        fadeout_end = hold_end + POPUP_FADEOUT_MS
        
        alpha = 0
        
        if self.elapsed_ms < fadein_end:
            # 淡入阶段：alpha 0 → 255
            progress = self.elapsed_ms / fadein_end
            alpha = int(255 * progress)
        elif self.elapsed_ms < hold_end:
            # 保持阶段：alpha = 255
            alpha = 255
        elif self.elapsed_ms < fadeout_end:
            # 淡出阶段：alpha 255 → 0
            progress = (self.elapsed_ms - hold_end) / POPUP_FADEOUT_MS
            alpha = int(255 * (1 - progress))
        
        alpha = max(0, min(255, alpha))
        
        # 渲染文字
        text_surf = self.font.render(self.text, True, COLOR_YELLOW)
        
        # 创建带透明度的文字 Surface
        text_with_alpha = pygame.Surface(text_surf.get_size(), pygame.SRCALPHA)
        text_with_alpha.blit(text_surf, (0, 0))
        text_with_alpha.set_alpha(alpha)
        
        # 屏幕中央
        text_rect = text_with_alpha.get_rect(
            center=(surface.get_width() // 2, surface.get_height() // 2 - 50)
        )
        surface.blit(text_with_alpha, text_rect)


# ==============================================
#   Effects 管理器
# ==============================================

class Effects:
    """动画效果管理器。
    
    管理多个同时运行的效果（闪光、得分提示）。
    
    用法：
        effects = Effects()
        effects.update(dt_ms, state)   # 在主循环中每帧调用
        effects.render(surface)         # 在主循环中每帧调用
    """
    
    def __init__(self):
        self.active_effects = []  # 当前活跃的效果列表
        
        # 状态缓存（用于检测变化）
        self.prev_fired = False
        self.prev_score_delta = 0
    
    def update(self, dt_ms, state):
        """更新所有效果。
        
        参数：
            dt_ms: 距上一帧的毫秒数
            state: 当前状态字典
        """
        # ---- 1. 检测开火事件 ----
        fire_state = state.get("fire_state", {})
        fired = fire_state.get("fired", False)
        
        if fired and not self.prev_fired:
            # 刚开火！添加命中闪光效果
            self.active_effects.append(HitFlash())
        
        self.prev_fired = fired
        
        # ---- 2. 检测得分事件 ----
        score_data = state.get("score", {})
        score_delta = score_data.get("delta", 0)
        score_reason = score_data.get("reason", "")
        
        if score_delta > 0 and score_delta != self.prev_score_delta:
            # 加分了！添加得分提示
            self.active_effects.append(ScorePopup(score_delta, score_reason))
        
        self.prev_score_delta = score_delta
        
        # ---- 3. 更新所有效果 ----
        # 把已经结束的效果移除
        still_active = []
        for effect in self.active_effects:
            effect.update(dt_ms)
            if effect.active:
                still_active.append(effect)
        
        self.active_effects = still_active
    
    def render(self, surface):
        """绘制所有活跃效果。"""
        for effect in self.active_effects:
            effect.render(surface)


# ==============================================
#   独立测试入口
# ==============================================

def test_effects():
    """独立运行效果测试。"""
    pygame.init()
    
    WIDTH, HEIGHT = 800, 500
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("动画效果测试")
    clock = pygame.time.Clock()
    
    effects = Effects()
    
    # 模拟状态
    test_state = {
        "fire_state": {"fired": False},
        "score": {"value": 100, "delta": 0, "reason": ""}
    }
    
    # 计时器：每 3 秒触发一次事件
    timer = 0
    event_count = 0
    
    running = True
    while running:
        dt = clock.tick(60)
        timer += dt
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    # 按空格手动触发开火
                    test_state["fire_state"]["fired"] = True
        
        # 自动触发场景（每 3 秒）
        if timer > 3000:
            timer = 0
            event_count += 1
            
            # 开火 + 命中
            test_state["fire_state"]["fired"] = True
            test_state["score"]["delta"] = 10
            test_state["score"]["reason"] = "hit"
            test_state["score"]["value"] += 10
        
        # 重置单次事件
        if test_state["fire_state"]["fired"]:
            test_state["fire_state"]["fired"] = False
        if test_state["score"]["delta"] > 0:
            test_state["score"]["delta"] = 0
            test_state["score"]["reason"] = ""
        
        # 更新 + 绘制
        effects.update(dt, test_state)
        
        screen.fill(COLOR_BLACK)
        
        # 提示文字
        font = pygame.font.Font(None, 24)
        info_lines = [
            "按 SPACE 触发开火 + 命中闪光",
            "按 S 触发得分提示",
            "每 3 秒自动切换场景",
            f"活跃效果数: {len(effects.active_effects)}"
        ]
        for i, line in enumerate(info_lines):
            t每 3 秒自动触发一次text, (20, 20 + i * 25))
        
        effects.render(screen)
        
        pygame.display.flip()
    
    pygame.quit()


if __name__ == "__main__":
    print("=== 动画效果组件独立测试 ===")
    print("按 SPACE 触发开火闪光")
    print("按 S 触发得分提示")
    print("按 ESC 退出\n")
    test_effects()
```

---
i/demo_reader.py` — 自测入口

这是**你的自测工具**。它会：
1. 自动模拟主程序写出 `state.json`
2. 打开 Pygame 窗口
3. 显示你的雷达、HUD、动画效果

**B 也可以用这个文件测试整体 UI。**

> 💡 **关于摄像头画面：** 摄像头走独立的 FastAPI 服务（`vision/camera_share.py`，端口 8010），
> B 的 `core.py` 会通过 HTTP 拉取 JPEG 图片作为窗口背景。
> 你的组件（雷达、HUD、动画）始终叠加在背景之上，不需要关心摄像头画面本身。
>
> 如果你自测时需要获取摄像头画面，可以直接使用 `vision/get_camera.py` 提供的工具函数：
> ```python
> from vision.get_camera import get_camera_frame, get_camera_size
>
> w, h = get_camera_size()            # → (width, height)
> frame = get_camera_frame()          # → OpenCV BGR numpy 数组
> ```
> 启动摄像头服务：`uvicorn vision.camera_share:app --port 8010 --host 127.0.0.1 --reload`

```python
# ui/demo_reader.py
# 自测入口：模拟主程序 + 显示你的所有组件
#
# 运行方式：
#   python ui/demo_reader.py
#
# 这个脚本会：
#   1. 在后台不断写入 state.json（模拟主程序）
#   2. 打开一个 Pygame 窗口
#   3. 显示你的雷达、HUD、动画效果

import pygame
import json
import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.config import *
from ui.assets import get_font_small, get_font_large
from ui.radar import Radar
from ui.hud import HUD
from ui.effects import Effects

# ==============================================
#   模拟 JSON 写入器
# ==============================================

class MockStateWriter:
    """模拟主程序，定时更新 state.json。"""
    
    def __init__(self):
        self._stop = threading.Event()
    
    def start(self):
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()
    
    def stop(self):
        self._stop.set()
    
    def _loop(self):
        scenes = self._build_scenes()
        scene_idx = 0
        
        while not self._stop.is_set():
            scene = scenes[scene_idx % len(scenes)]
            scene["timestamp"] = time.time()
            
            with open("state.json", "w", encoding="utf-8") as f:
                json.dump(scene, f, indent=2)
            
            scene_idx += 1
            time.sleep(2.5)  # 每 2.5 秒切换一次场景
    
    def _build_scenes(self):
        return [
            # 场景 0：空闲
            {
                "system_state": {"mode": "idle", "msg": "等待目标"},
                "fire_state": {"fired": False},
                "score": {"value": 0, "delta": 0, "reason": ""},
                "targets": [],
                "serial": {"status": "OK", "msg": "connected"}
            },
            # 场景 1：追踪一个目标
            {
                "system_state": {"mode": "playing", "msg": "目标已发现"},
                "fire_state": {"fired": False},
                "score": {"value": 0, "delta": 0, "reason": ""},
                "targets": [
                    {"id": 1, "class": "person", "conf": 0.85, "bbox": [620, 240, 780, 420], "cx": 700, "cy": 330}
                ],
                "serial": {"status": "OK", "msg": "connected"}
            },
            # 场景 2：命中
            {
                "system_state": {"mode": "playing", "msg": "命中！"},
                "fire_state": {"fired": True},
                "score": {"value": 50, "delta": 50, "reason": "hit"},
                "targets": [
                    {"id": 1, "class": "person", "conf": 0.92, "bbox": [600, 320, 680, 400], "cx": 640, "cy": 360}
                ],
                "serial": {"status": "OK", "msg": "connected"}
            },
            # 场景 3：串口断开
            {
                "system_state": {"mode": "over", "msg": "串口连接断开"},
                "fire_state": {"fired": False},
                "score": {"value": 50, "delta": 0, "reason": ""},
                "targets": [],
                "serial": {"status": "ERROR", "msg": "disconnected"}
            },
        ]

# ==============================================
#   读取 state.json 的工具函数
# ==============================================

def read_status():
    """读取 state.json，失败时返回空字典。"""
    try:
        with open("state.json", "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ==============================================
#   主函数：自测入口
# ==============================================

def main():
    """自测入口。
    
    运行方式：python ui/demo_reader.py
    """
    print("=== Real FPS — UI 组件自测 ===")
    print("这个测试会：")
    print("  1. 自动模拟主程序写入 state.json")
    print("  2. 显示你的雷达、HUD、动画效果")
    print("  3. 每 2.5 秒切换一个场景")
    print()
    print("按 ESC 或关闭窗口退出\n")
    
    # 启动模拟写入器
    writer = MockStateWriter()
    writer.start()
    
    # 初始化 Pygame
    pygame.init()
    
    # 窗口模式（方便调试）
    WIDTH, HEIGHT = 1280, 720
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Real FPS — UI 组件自测")
    clock = pygame.time.Clock()
    
    # 初始化你的组件
    radar = Radar(WIDTH - RADAR_RADIUS - RADAR_MARGIN, HEIGHT - RADAR_RADIUS - RADAR_MARGIN)
    hud = HUD()
    effects = Effects()
    
    # 字体
    font_info = pygame.font.Font(None, 24)
    
    running = True
    last_state = {}
    last_fired = False
    
    while running:
        dt = clock.tick(FPS_TARGET)
        
        # ---- 处理事件 ----
        for event in pygame.event.get():
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # ---- 读取最新状态 ----
        state = read_status()
        if state:
            last_state = state
        else:
            state = last_state
        
        # ---- 更新效果 ----
        effects.update(dt, state)
        
        # ---- 绘制 ----
        screen.fill(COLOR_BLACK)
        
        # 画一些指引
        mode = state.get("system_state", {}).get("mode", "?")
        scene_info = font_info.render(f"当前场景: {mode}  |  场景每 2.5 秒自动切换", True, COLOR_WHITE)
        screen.blit(scene_info, (20, HEIGHT - 60))
        
        # 渲染组件
        targets = state.get("targets", [])
        locked_id = state.get("target_lock", {}).get("target_id")
        
        radar.render(screen, targets, locked_target_id=locked_id, dt_ms=dt)
        hud.render(screen, state, int(clock.get_fps()), dt)
        effects.render(screen)
        
        # ---- 刷新 ----
        pygame.display.flip()
    
        radar.render(screen, targets, dt_ms=dt)
        hud.render(screen, state, int(clock.get_fps()), dt)
        effects.render(screen)
        
        # ---- 刷新 ----
        pygame.display.flip()
    
    # ---- 清理 ----
    writer.stop()
    pygame.quit()
    print("测试结束")


if __name__ == "__main__":
    main(

B 的 `core.py` 中预留了三个空位，等你把组件交给他：

```python
# 在 UI.__init__() 中（B 的代码）：
self.radar = None     # ← 你给 B 代码后，改成 Radar(...)
self.hud = None       # ← 你给 B 代码后，改成 HUD(...)
self.effects = None   # ← 你给 B 代码后，改成 Effects(...)

# 在 UI._render() 中（B 的代码）：
# if self.radar:
#     self.radar.render(...)    ← 取消注释
# if self.hud:
#     self.hud.render(...)      ← 取消注释
# if self.effects:
#     self.effects.render(...)  ← 取消注释
```

**对接步骤：**

1. 你写完 `radar.py`、`hud.py`、`effects.py` 后，先自己用 `demo_reader.py` 测试
2. 确认没问题后，告诉 B："我的组件写好了"
3. B 在 `core.py` 顶部加 `from ui.radar import Radar` 等 import
4. B 在 `__init__` 中创建实例
5. B 在 `_render` 中调用渲染方法

**你的组件接口（B 会这样调用）：**

```python
# 雷达
self.radar.render(screen, targets, locked_target_id, dt_ms)

# HUD
self.hud.render(screen, state, fps, dt_ms)

# 效果
self.effects.update(dt_ms, state)
self.effects.render(screen)
```

---

## 11. 常见错误与解决

### ❌ `ModuleNotFoundError: No module named 'ui'`
→ 运行脚本时必须在 `Real_fps` 目录下。检查当前目录：`python -c "import os; print(os.getcwd())"`

### ❌ `AttributeError: 'NoneType' object has no attribute 'render'`
→ 你在调用组件前忘了创建它。检查是否调用了 `Radar(...)` 而不是 `radar = None`。

### ❌ 雷达不显示 / 位置不对
→ 检查 `Radar.__init__` 的 `center_x`, `center_y`。如果在测试时位置不对，调整传入的坐标。

### ❌ 动画效果不播放
→ 检查 `effects.update(dt, state)` 是否每帧都在调用。
   检查 `fire_state.fired` 是否从 `False` 变成了 `True`（你的 `prev_fired` 逻辑）。

### ❌ 画面闪烁
→ 检查是否忘记调 `pygame.display.flip()`。
   检查是否在 `render()` 里做了耗时操作。

### ❌ 文字模糊或锯齿
→ `font.render` 的第二个参数是"抗锯齿"。始终传 `True`。

### ❌ import 报红（VS Code 显示红色波浪线）
→ 这不一定是错误！VS Code 有时找不到模块但运行时正常。
   只要 `python ui/demo_reader.py` 能跑，就不用管。

---

## 你的学习路线

1. **先读一遍 B_pygame.md** — 了解 B 在做什么，你的组件要贴在哪里
2. **运行 ui/radar.py 的独立测试** — 确保 Pygame 能用
3. **运行 ui/hud.py 的独立测试** — 理解 HUD 的读取状态方式
4. **运行 ui/effects.py 的独立测试** — 理解时间轴动画
5. **运行 ui/demo_reader.py** — 把所有组件整合在一起
6. **和 B 对接** — 把你的组件交给他集成到主 UI

每个文件都能独立运行测试，**不需要依赖任何人的代码**。这是你最大的优势——可以自己做开发。

有问题随时找我！
