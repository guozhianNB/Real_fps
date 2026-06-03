# B 的工作 —— 左上 HUD & 底部状态栏 & 准心

> 👋 你好！你的工作是让 UI 更好看。你已经看过 `B_pygame.md`，现在需要动手改代码。改完后通知 A 测试。

---

## 📁 项目文件目录

```
Real_fps/
├── ui/
│   ├── core.py          ← ★ 主 UI 循环，准星在这里画
│   ├── hud.py           ← ★ 记分板、底部状态栏在这里
│   ├── radar.py         ← 雷达组件（C 负责）
│   ├── effects.py       ← 命中动画
│   ├── config.py        ← 颜色、尺寸常量
│   ├── assets.py        ← 字体工具
│   ├── gun_view.py      ← 3D 枪械（不需要你管）
│   └── demo_reader.py   ← 自测工具
├── vision/              ← 视觉模块（不用管）
├── main.py              ← 后端引擎（不用管）
├── fire_notifier.py     ← UDP 通信（不用管）
└── 教学参考文档/
    ├── B_pygame.md      ← 你的学习资料
    └── B_work.md        ← ★ 就是这个文件
```

---

## 📋 你的 UI 修改清单

| 组件 | 文件 | 函数位置 | 现状 |
|------|------|---------|------|
| 记分板（分数 / FPS / 目标数） | `ui/hud.py` | `HUD.render()` | 左上角白字，半透明黑底 |
| 底部状态栏（MODE / SERIAL） | `ui/hud.py` | `HUD.render()` | 底部居中白字 |
| 准心 | `ui/core.py` | `_render()` 中"准星"段落 | 绿色圆圈+十字线 |

---

## 1. 记分板（Scoreboard）

### 当前代码位置
`ui/hud.py` 中的 `HUD.render()` 方法。

### 可以怎么改

**A. 加背景框美化**
当前是一个半透明黑矩形。可以改成：
- 毛玻璃效果（半透明+带边框+圆角）
- 左上角加一个游戏 Logo / 图标
- 分数用大号加粗数字，目标数用小号文字
- 分数变化时做一个 0.3s 的数字滚动动画

**示例代码（毛玻璃效果）：**
```python
# 替换当前的 panel = alpha_surface(...)
# 用 pygame.draw.rect 画圆角矩形（模拟）
panel_w, panel_h = 280, 160
panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
# 填充半透明黑
pygame.draw.rect(panel, (0, 0, 0, 160), (0, 0, panel_w, panel_h), border_radius=12)
# 边框
pygame.draw.rect(panel, (0, 255, 100, 80), (0, 0, panel_w, panel_h), 2, border_radius=12)
surface.blit(panel, (HUD_MARGIN - 8, HUD_MARGIN - 8))
```

**B. 贴图方案**
做一个精美的记分板图片（PNG），让 A 把它复制到 `ui/assets/` 下，然后在代码里用 `pygame.image.load()` 加载作为背景。替换掉代码中 `alpha_surface()` 创建背景的部分。

```
ui/assets/
├── scoreboard_bg.png    ← 记分板背景图
├── crosshair.png        ← 准星贴图
└── status_bg.png        ← 底部状态栏背景
```

**C. 信息布局创意**
```
┌──────────────────────┐
│  🔫 SCORE: 1250      │  ← 大号，左边加个枪图标 emoji
│  ──────────────      │  ← 分隔线
│  👥 TARGETS: 3       │
│  ⚡ FPS: 60          │
└──────────────────────┘
```

### 修改方法
把 `hud.py` 发给 AI，说：
> 我要你修改 `HUD.render()` 方法。记分板做成左上角半透明圆角面板，带绿色细边框。分数用大号加粗字体，分数变化时闪烁金色。FPS 低于 30 显示红色警告。目标数旁边加个 emoji `👥`。

---

## 2. 底部状态栏

### 当前代码位置
`ui/hud.py` 的 `HUD.render()` 底部部分。

### 可以怎么改

**A. 改成悬浮条**
- 底部居中一个扁条，半透明黑 + 绿色边框
- 左侧显示 MODE，右侧显示 SERIAL 状态
- 中间可以用小圆点分隔
- MODE 用颜色区分：playing=绿色, paused=黄色, over=红色

**B. 创意设计**
```
┌────────────────────────────────────┐
│  🎯 PLAYING        ●        🔗 OK │
└────────────────────────────────────┘
```

**C. 串口状态指示器**
- OK → 绿色圆点
- ERROR → 红色闪烁圆点
- disconnected → 灰色圆点

### 修改方法
> 修改 HUD 底部状态栏，做成一个扁长的半透明面板居中在屏幕底部。里面左右排列：MODE（彩色） | SERIAL（带绿/红圆点）。参考设计：`[PLAYING] ● [OK]`。

---

## 3. 准心

### 当前代码位置
`ui/core.py` 的 `_render()` 方法中"准星"段落。

### 可以怎么改

当前准心代码（大约 10 行）：
```python
cx, cy = self._ww // 2, self._wh // 2
c = CROSSHAIR_SIZE  # = 20
pygame.draw.circle(s, COLOR_GREEN, (cx, cy), 15, 2)
pygame.draw.circle(s, COLOR_GREEN, (cx, cy), 2, 0)
for dx, dy in [(-c-5, 0), (18, 0), (0, -c-5), (0, 18)]:
    pygame.draw.line(s, COLOR_GREEN, (cx+dx, cy+dy),
                     (cx+dx+(20 if dx else 0), cy+dy+(20 if dy else 0)), 2)
```

**A. 经典 FPS 准心（推荐）**
```
         ██
         ██
         ██
   ████████ ████████        ← 中间断开 5px 空隙
         ██
         ██
         ██
```
代码实现：
- 中心留出 5×5 的空隙（不画任何东西，方便瞄准）
- 上下左右各延伸两根线段：长 25px，宽 3px
- 绿色，每隔一根画透明一点（层次感）

**给 AI 的提示词：**
> 修改准星绘制代码。以屏幕中心点为准：上下左右各留出 5 像素空隙 → 然后画第一段长 15 像素、宽 4 像素的亮绿线 → 再隔 3 像素空隙 → 画第二段长 8 像素、宽 2 像素的暗绿线。整体像 `▌ ▐` 但十字方向都有。

**B. 动态准心**
- 开枪时准心扩散（外圈变大）
- 移动时准心略微放大
- 对准敌人时变红色
- 这个需要加状态变量，代码量稍大

**C. 贴图方案**
用 Photoshop / 任何画图工具画一个精美的准心 PNG（支持透明），保存到 `ui/assets/crosshair.png`。然后替换代码：

```python
# 替换所有 pygame.draw 的准心代码
crosshair_img = pygame.image.load("ui/assets/crosshair.png")
crosshair_img = pygame.transform.scale(crosshair_img, (64, 64))
s.blit(crosshair_img, (cx - 32, cy - 32))
```

这样 AI 生成的准心图或者你自己画的都可以直接用，效果远好于代码画的。

---

## 🛠 测试方法

改完代码后，独立运行 UI 测试：
```powershell
python ui/demo_reader.py
```
这个工具会模拟主程序写 state.json，不需要启动摄像头和 main.py。

如果要配合完整游戏测试，由 A 通过 start.py 一键启动。

---

## 💡 配色参考

| 元素 | 颜色 | RGB |
|------|------|-----|
| 准星 / 雷达 | 亮绿 | `(0, 255, 100)` |
| 警告 / 命中 | 红 | `(255, 50, 50)` |
| 分数闪烁 | 金黄 | `(255, 200, 0)` |
| HUD 背景 | 半透明黑 | `(0, 0, 0, 160)` |
| 边框 | 绿半透明 | `(0, 255, 100, 80)` |
