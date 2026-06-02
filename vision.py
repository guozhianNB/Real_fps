from ultralytics import YOLO
from pathlib import Path
import cv2
import numpy as np
import urllib.request
import threading
import time
from collections import defaultdict

#
MODEL_PATH = Path(__file__).resolve().parent / "model" / "yolo26n-pose.pt"
CAMERA_PATH = "http://127.0.0.1:8010/snapshot"

# ---------- 人体关键点索引（COCO 格式）----------
NOSE = 0
LEFT_EYE = 1
RIGHT_EYE = 2
LEFT_EAR = 3
RIGHT_EAR = 4
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_WRIST = 9
RIGHT_WRIST = 10
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_KNEE = 13
RIGHT_KNEE = 14
LEFT_ANKLE = 15
RIGHT_ANKLE = 16


class HumanTracker:
    """使用 YOLO 跟踪模式持续追踪人体，并提供最新的跟踪结果。"""

    def __init__(self, camera_url: str = CAMERA_PATH, model_path: str = MODEL_PATH):
        self.camera_url = camera_url
        self.model = YOLO(str(model_path))

        # 当前最新帧与跟踪结果
        self.latest_frame: np.ndarray | None = None
        self.latest_result = None
        self.lock = threading.Lock()

        # 跟踪 ID -> 累积的轨迹点（用于稳定显示）
        self.trajectories: dict[int, list] = defaultdict(list)

        self.running = True
        self.thread = threading.Thread(target=self._track_loop, daemon=True)
        self.thread.start()

    def _grab_frame(self) -> np.ndarray | None:
        """从摄像头共享服务拉取最新帧。"""
        try:
            with urllib.request.urlopen(self.camera_url, timeout=5) as resp:
                data = np.asarray(bytearray(resp.read()), dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            return None

    def _track_loop(self):
        """后台循环：持续拉取帧 → YOLO track → 保存结果。"""
        while self.running:
            frame = self._grab_frame()
            if frame is None:
                time.sleep(0.03)
                continue

            # YOLO 跟踪模式：只跟踪人（class=0）
            results = self.model.track(
                frame,
                persist=True,       # 保持跨帧 ID 一致
                classes=[0],        # 只跟踪 person 类别
                verbose=False,
                device="cpu",
            )

            with self.lock:
                self.latest_frame = frame
                self.latest_result = results[0] if results else None

                # 更新轨迹（保留最近 30 个点）
                if self.latest_result and self.latest_result.boxes:
                    ids = getattr(self.latest_result.boxes, "id", None)
                    if ids is not None:
                        centers = self.latest_result.boxes.xywh
                        for box_id, box_wh in zip(ids, centers):
                            tid = int(box_id)
                            cx, cy = float(box_wh[0]), float(box_wh[1])
                            self.trajectories[tid].append((cx, cy))
                            # 只保留最近 30 帧的轨迹
                            if len(self.trajectories[tid]) > 30:
                                self.trajectories[tid].pop(0)

            time.sleep(0.01)

    def get_latest(self):
        """线程安全地获取最新帧和跟踪结果。"""
        with self.lock:
            return self.latest_frame, self.latest_result, dict(self.trajectories)

    def release(self):
        """停止后台线程。"""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)