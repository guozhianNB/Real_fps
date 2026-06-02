# A — YOLO 视觉识别模块

> 你是团队主程，视觉部分你自己搞定，这份文档只是**接口规格**，确保输出和 B/C/D 对接。

---

## 职责

1. 捕获摄像头或屏幕画面
2. 运行 YOLOv8 推理，检测目标
3. 计算目标中心点与屏幕中心的偏移
4. 把结果写入 `state.json`（B 轮询消费）
5. 响应 `GAME_START` / `GAME_PAUSE` / `GAME_OVER` 控制检测启停

---

## 技术选型

| 组件 | 推荐库 | 说明 |
|------|--------|------|
| 模型 | `ultralytics YOLOv8n/s` | Nano 跑 CPU，Small 跑 GPU |
| 画面捕获 | `mss` 或 `cv2.VideoCapture` | 屏幕截图或 USB 摄像头 |
| 加速 | ONNX / TensorRT（可选） | 需要更高 FPS 时再上 |

---

## 输出协议（写入 state.json）

每帧推理完成后，更新 `state.json` 的以下字段（其他字段由 A_main 写）：

```json
{
    "timestamp": 1717320000.0,
    "targets": [
        {
            "id": 1,
            "class": "person",
            "conf": 0.94,
            "bbox": [600, 300, 680, 420],
            "cx": 640,
            "cy": 360,
            "dx_screen": 0,
            "dy_screen": -20
        }
    ],
    "target_count": 1
}
```

字段说明：
- `targets[].cx, cy` — 目标中心在画面中的像素坐标
- `targets[].dx_screen, dy_screen` — 目标中心到画面中心的偏移（像素）
- `target_count` — 当前帧通过置信度阈值的目标总数

---

## 建议接口

```python
class VisionDetector:
    def __init__(self, model_path="yolov8n.pt", conf=0.5, 
                 capture_width=1280, capture_height=720):
        ...

    def start(self):      # 开始检测（独立线程）
    def stop(self):       # 停止检测，释放摄像头
    def get_result(self): # 获取最新一帧结果 → dict 或 None
```

---

## 注意事项

- 推理在**独立线程**中运行，不阻塞主循环
- 目标 FPS：≥ 15（CPU Nano），≥ 30（GPU Small）
- 如果目标数 = 0，`targets` 写空列表 `[]`
- 本模块不负责分数、锁定、开火等逻辑——那些是 A_main 的事
