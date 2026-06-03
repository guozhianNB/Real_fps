# A — 主程序编排

> 这是整个系统的**大脑**。你负责把 B（UI）、C（UI 组件）、D（键鼠）、Vision（YOLO）、Serial（串口）全部粘起来。

---

## 职责总览

```
                 ┌──────────────────┐
                 │   D_mouse        │  ← 提供 dx, dy, left_click
                 └───────┬──────────┘
                         │ get_delta()
                         ▼
┌──────────────────┐   ┌──────────────┐   ┌──────────┐
│  vision/vision.py│──►│   main.py    │──►│  Serial  │  → 串口指令
│  HumanTracker    │   │  (状态机)     │   │ (串口)   │
│  process_frame() │   └──────┬───────┘   └──────────┘
└──────────────────┘          │ write state.json
                              ▼
                       ┌─────────────┐
                       │  ui/ (B+C)  │  ← 每 50ms 轮询 state.json
                       │  准星/雷达   │
                       │  HUD/动画   │
                       └─────────────┘
```

---

## 主循环伪代码

```python
def main_loop():
    while game_running:
        # 1. 输入
        dx, dy, left_click = ml.get_delta()

        # 2. 角度计算
        angle_x = clamp(last_angle_x + dx * SENSITIVITY, 0, 180)
        angle_y = clamp(last_angle_y + dy * SENSITIVITY, 0, 180)

        # 3. 串口发送
        serial.send(f"X:{angle_x:.0f},Y:{angle_y:.0f}")

        # 4. 视觉结果
        vision_result = vision.get_result()

        # 5. 状态计算（锁定、得分、开火）
        state = compute_state(vision_result, left_click)

        # 6. 写入 JSON（B 轮询）
        write_state_json(state)

        # 7. 控制帧率
        clock.tick(60)
```

---

## 状态机

```
                    GAME_START
                        │
                        ▼
               ┌────────────────┐
               │    playing     │
               │  (正常运行)     │
               └────┬──────┬────┘
                    │      │
           P 键广播 │      │ Esc 广播
                    │      │
                    ▼      ▼
          ┌──────────┐  ┌──────────┐
          │  paused  │  │   over   │
          │ (暂停)    │  │ (结束)    │
          └────┬─────┘  └──────────┘
               │
           P 键广播 │
               ▼
          ┌──────────┐
          │ playing  │
          │ (恢复)    │
          └──────────┘
```

主程序订阅 D 的 pyee 事件：

```python
ml.emitter.on("GAME_PAUSE", self.on_pause)
ml.emitter.on("GAME_CONTINUE", self.on_continue)
ml.emitter.on("GAME_OVER", self.on_game_over)
```

---

## state.json 完整字段（你负责写全部）

```json
{
    "timestamp": 1717320000.0,
    "system_state": { "mode": "tracking", "msg": "normal" },
    "aim_state": { "on_target": true, "hit_zone": "body", "target_id": 3, "conf": 0.94 },
    "fire_state": { "ready": true, "fired": false, "cooldown_ms": 0 },
    "target_lock": { "locked": true, "target_id": 3, "cx": 640, "cy": 360, "distance": 18.2 },
    "score": { "value": 120, "delta": 10, "reason": "headshot" },
    "targets": [
        { "id": 3, "class": "person", "conf": 0.94, "bbox": [600, 300, 680, 420], "cx": 640, "cy": 360 }
    ],
    "serial": { "status": "OK", "msg": "connected" }
}
```

各字段计算逻辑：

| 字段 | 谁提供 | 计算方式 |
|------|--------|----------|
| `system_state.mode` | 你 | 状态机当前状态 |
| `aim_state.on_target` | 你 | 目标中心与准星距离 < 阈值 |
| `aim_state.hit_zone` | 你 | 目标 bbox 上 1/3 = head，否则 body |
| `fire_state.ready` | 你 | 锁定且冷却结束 |
| `fire_state.fired` | 你 | left_click 为 True 且 ready |
| `target_lock.locked` | 你 | 同一目标连续 tracking > N 帧 |
| `score` | 你 | fired 时 +10（body）/+50（head） |
| `targets` | Vision | YOLO 输出 |
| `serial` | 你 | 串口最后通信状态 |

---

## 评分逻辑

```python
SCORE_TABLE = {
    "body": 10,
    "head": 50,
}

SCORE_COOLDOWN_MS = 300  # 同一次开火不重复计分

score_value = 0
last_score_time = 0

def update_score(hit_zone, now_ms):
    global score_value, last_score_time
    if now_ms - last_score_time < SCORE_COOLDOWN_MS:
        return 0, ""
    points = SCORE_TABLE.get(hit_zone, 0)
    if points > 0:
        score_value += points
        last_score_time = now_ms
        return points, hit_zone
    return 0, ""
```

---

## 实际项目结构

```
Real_fps/
├── main.py                    ← 入口：主循环 + 状态机 + 评分逻辑
├── start.py                   ← 启动器（一键启动摄像头服务 + 主程序）
├── A_serial.py                ← 串口通信封装
├── vision/                    ← 视觉模块（已实现）
│   ├── camera_share.py        ← FastAPI 摄像头共享服务（端口 8010）
│   ├── vision.py              ← YOLO 人体跟踪 + 分析（HumanTracker + process_frame）
│   └── get_camera.py          ← 获取摄像头画面的工具函数
├── ui/                        ← B + C 的 UI 模块（需手动创建）
├── D_mouse.py                 ← D 的鼠标模块（待实现）
├── 教学参考文档/               ← 各模块教学文档
├── readme.md
└── requirement.txt
```

> ⚠️ **注意：**
> - Vision 模块在 `vision/` 文件夹下，调用时用 `from vision.vision import HumanTracker`
> - 摄像头服务用 `uvicorn vision.camera_share:app ...`（带 `vision.` 前缀）
> - 画面获取已封装在 `vision/get_camera.py` 中：`get_camera_frame()`、`get_camera_size()`

---

## 启动顺序

```python
def main():
    # 1. 初始化各模块
    ml = MouseListener(...)       # D
    vision = VisionDetector(...)  # 你自己的
    serial = SerialController(...) # 你自己的

    # 2. 订阅 D 的事件
    ml.emitter.on("GAME_PAUSE", ...)
    ml.emitter.on("GAME_OVER", ...)

    # 3. 发送 GAME_START
    ml.start()
    vision.start()

    # 4. 进入主循环
    main_loop(ml, vision, serial)

    # 5. 清理
    ml.stop()
    vision.stop()
    serial.close()
```
