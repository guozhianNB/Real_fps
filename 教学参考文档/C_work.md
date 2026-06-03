# C 的工作 —— B-scope 雷达 & 目标框 & 画面氛围

> 👋 你好！你的工作是提升画面细节。你已经看过 `C_ui_assist.md`，现在需要对已有组件做美术升级。改完后通知 A 测试。

---

## 📁 项目文件目录

```
Real_fps/
├── ui/
│   ├── core.py          ← ★ 主 UI 循环，目标框在这里画
│   ├── hud.py           ← 记分板（B 负责）
│   ├── radar.py         ← ★ 雷达组件在这里
│   ├── effects.py       ← 命中动画
│   ├── config.py        ← 颜色、尺寸常量
│   ├── assets.py        ← 字体工具
│   ├── gun_view.py      ← 3D 枪械（不需要你管）
│   └── demo_reader.py   ← ★ 自测工具
├── vision/              ← 视觉模块（不用管）
├── main.py              ← 后端引擎（不用管）
├── fire_notifier.py     ← UDP 通信（不用管）
└── 教学参考文档/
    ├── C_ui_assist.md   ← 你的学习资料
    └── C_work.md        ← ★ 就是这个文件
```

---

## 📋 你的 UI 修改清单

| 组件 | 文件 | 函数位置 | 现状 |
|------|------|---------|------|
| B-scope 雷达 | `ui/radar.py` | `Radar.render()` | 200×200 矩形，绿色扫描线+点 |
| 人头绿框 | `ui/core.py` | `_render()` 中"目标框"段落 | 绿色矩形框 |

---

> ⚠️ **注意：3D 枪械模型（gun_view.py, obj_loader.py）属于 A 的工作，不需要你修改。**

---

## 1. B-scope 雷达

### 当前效果
右上角 200×200 矩形，绿色扫描线左右扫，目标点闪烁。

### 可以怎么改

**A. 加 UI 装饰**
当前雷达非常朴素。可以加：
- 方位标签：顶部标注 N / S / E / W（或者 0° 90° 180° 270°）
- 距离刻度：左侧画小刻度线或文字（近 / 中 / 远）
- 网格线加亮或改成虚线
- 边框改成圆角 + 发光效果

**给 AI 的提示词：**
> 修改 `Radar.render()` 方法。在雷达方框四周添加方位标签：顶部写 `N`，底部写 `S`，左侧写 `W`，右侧写 `E`，用绿色小字。左侧边框画三个距离刻度短线。边框改成发光效果：先画一个宽 4px 的亮绿边框，再在外面画一层宽 2px 的半透明绿框。

**B. 扫描线美化**
当前是一条绿色竖线。可以改成：
- 渐变透明度：上到下从 0→255→0
- 尾迹效果：扫描线后面拖一条逐渐变淡的尾迹（保留最近几帧的扫描线位置，依次变淡绘制）
- 扫描线颜色随状态变化：锁定目标时变红

**C. 目标标记美化**
当前是绿色小圆点。可以改成：
- 目标用三角形或菱形标记（尖端指向目标方向）
- 不同距离用不同大小：远=小，近=大
- 目标闪烁时加一个扩散光圈动画

**D. 贴图方案**
你也可以画一个精美的雷达边框 PNG 作为背景贴图：
```python
# 替换背景绘制
bg_img = pygame.image.load("ui/assets/radar_bg.png")
bg_img = pygame.transform.scale(bg_img, (w, h))
surface.blit(bg_img, (x, y))
```

---

## 2. 人头绿框（目标框）

### 当前代码位置
`ui/core.py` 的 `_render()` 中"目标框"段落。

```python
for t in st.get("targets", []):
    b = t.get("bbox")
    if b and len(b) == 4:
        r = pygame.Rect(int(b[0]*sx), int(b[1]*sy),
                        int((b[2]-b[0])*sx), int((b[3]-b[1])*sy))
        pygame.draw.rect(s, COLOR_GREEN, r, 2)
```

### 可以怎么改

**A. 框体美化**
当前是 2px 绿色矩形框。可以改成：
- 只画四个角，不画完整边框（看起来更干净）
- 框线带呼吸动画（透明度循环）
- 头部框和身体框用不同方案（头部=绿框，身体=底部半透明条）

**示例代码（四角框）：**
```python
# 替换 pygame.draw.rect
l, t, r, b = r.left, r.top, r.right, r.bottom
corner = 10  # 角长度
c = COLOR_GREEN
# 左上角
pygame.draw.line(s, c, (l, t), (l + corner, t), 2)
pygame.draw.line(s, c, (l, t), (l, t + corner), 2)
# 右上角
pygame.draw.line(s, c, (r, t), (r - corner, t), 2)
pygame.draw.line(s, c, (r, t), (r, t + corner), 2)
# 左下角
pygame.draw.line(s, c, (l, b), (l + corner, b), 2)
pygame.draw.line(s, c, (l, b), (l, b - corner), 2)
# 右下角
pygame.draw.line(s, c, (r, b), (r - corner, b), 2)
pygame.draw.line(s, c, (r, b), (r, b - corner), 2)
```

**给 AI 的提示词：**
> 修改 core.py 中绘制目标框的代码。改成四角框：每个角画两条长度 12px 的线段，不画完整的四条边。框线颜色用亮绿 `(0, 255, 100)`，宽度 2px。头部框的颜色用亮绿，身体框的颜色用暗绿 `(0, 180, 60)`。

**B. 信息标签**
在框顶部显示目标信息：
- 目标 ID：`#1`
- 距离估算：`12m`
- 命中部位提示：锁定头部时框变红

**C. 锁定指示**
当准星对准目标时：
- 框线变红加粗
- 框的四个角出现锁定动画（从角向中心延伸）
- 框外出现一个圆环进度指示器

---


## 3. 整体画面氛围

**A. 画面暗角（Vignette）**
在画面四角叠加半透明黑色，模拟真实镜头效果：

```python
# 在 _render() 最后加
vignette = pygame.Surface((self._ww, self._wh), pygame.SRCALPHA)
# 四个角画黑色径向渐变（简化为四个角画半透明矩形）
for corner_x, corner_y in [(0, 0), (self._ww - 200, 0),
                            (0, self._wh - 200), (self._ww - 200, self._wh - 200)]:
    pygame.draw.rect(vignette, (0, 0, 0, 60),
                     (corner_x, corner_y, 200, 200), border_radius=100)
s.blit(vignette, (0, 0))
```

**B. 开火窗口震颤（Screen Shake）**
当开火事件发生时，整个画面短暂抖动，增强射击手感。

**实现思路：**
开火时设置一个震颤偏移量 `(offset_x, offset_y)`，每帧衰减到 0。在绘制所有内容后，用 `screen.blit()` 把整个画面按偏移量错位绘制。

**具体步骤：**

1. 在 `UI.__init__()` 中加状态变量：
```python
self._shake_timer = 0.0
self._shake_intensity = 0.0
```

2. 在 `_main_loop()` 的 FIRE_EVENT 中触发：
```python
elif e.type == FIRE_EVENT:
    self._shake_timer = 150.0       # 震颤持续 150ms
    self._shake_intensity = 8.0     # 最大偏移 8 像素
    # ... 原有的 recoil_timer 等代码
```

3. 在 `_render()` **最末尾**（所有内容画完后）加震颤逻辑：
```python
# 画面震颤（放在 _render 最后）
if self._shake_timer > 0:
    intensity = self._shake_intensity * (self._shake_timer / 150.0)
    # 随机方向
    sx = int(np.random.uniform(-intensity, intensity))
    sy = int(np.random.uniform(-intensity, intensity))
    # 把整个画面截取并偏移（需要先把 screen 内容复制到临时 surface）
    shake_surf = self.screen.copy()
    self.screen.fill(COLOR_BLACK)
    self.screen.blit(shake_surf, (sx, sy))
    self._shake_timer -= dt_ms  # 注意：需要把 dt_ms 传进来或设为成员
```

4. 别忘了在 `_main_loop` 每帧更新 timer：
```python
if self._shake_timer > 0:
    self._shake_timer = max(0, self._shake_timer - dt_ms)
```

**给 AI 的提示词：**
> 给 UI 添加开火画面震颤效果。在 `UI.__init__` 加 `self._shake_timer = 0` 和 `self._shake_intensity = 8`。在 FIRE_EVENT 中设置 timer=150ms。在 `_render()` 最后，如果 timer>0，把 screen 内容复制到临时 surface，以随机偏移量重新 blit 回去。timer 在每帧更新时递减。

**进阶效果：**
- 连续开火时震颤叠加（不重置，而是累加 intensity）
- 震颤时画面略微模糊（需要 `pygame.transform` 缩放模拟）


---

## 🛠 测试方法

```powershell
python ui/demo_reader.py
```
这个工具会模拟主程序循环写 state.json + 触发开火事件，不需要摄像头和 main.py 就能看到所有 UI 效果。

---

## 💡 配色参考

| 元素 | 颜色 | RGB |
|------|------|-----|
| 雷达 / 目标框 | 亮绿 | `(0, 255, 100)` |
| 锁定目标 | 红 | `(255, 50, 50)` |
| 雷达网格 | 暗绿 | `(0, 180, 60)` |
| 边框半透明 | 绿透 | `(0, 255, 100, 60)` |
| 暗角 | 黑透 | `(0, 0, 0, 60)` |
