
from ultralytics import YOLO
from pathlib import Path
import cv2
import numpy as np
import http.client
import threading
import time
import json
from collections import defaultdict
from urllib.parse import urlparse

#
MODEL_PATH = Path(__file__).resolve().parent / "model" / "yolo26n-pose.pt"
CAMERA_PATH = "http://127.0.0.1:8010/snapshot_thumb"
CAMERA_SIZE_PATH = "http://127.0.0.1:8010/size"

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

        # 解析 URL，建立 HTTP 长连接复用
        parsed = urlparse(camera_url)
        self._http_conn = http.client.HTTPConnection(
            parsed.hostname, parsed.port, timeout=5
        )
        self._http_path = parsed.path or "/snapshot"

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
        """通过复用的 HTTP 连接拉取最新帧，避免端口耗尽。"""
        try:
            self._http_conn.request("GET", self._http_path)
            resp = self._http_conn.getresponse()
            data = np.asarray(bytearray(resp.read()), dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            # 连接断开时重建
            try:
                self._http_conn.close()
                parsed = urlparse(self.camera_url)
                self._http_conn = http.client.HTTPConnection(
                    parsed.hostname, parsed.port, timeout=5
                )
            except Exception:
                pass
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

    def get_analysis(self, aim_point):
        """获取最新帧的分析结果（JSON 格式字典）。

        注意：aim_point 是"全分辨率"坐标系下的准心坐标，
        而 YOLO 推理在缩略图 (640x480) 上进行，
        因此需要将 aim_point 等比缩放到缩略图坐标系。
        """
        frame, result, _ = self.get_latest()
        if frame is not None:
            h_thumb, w_thumb = frame.shape[:2]
        else:
            # 用相机 /size 接口获取全分辨率，/snapshot_thumb 固定 640x480
            w_thumb, h_thumb = 640, 480

        # 获取全分辨率尺寸（首次从相机服务查询，后续缓存）
        if not hasattr(self, '_cam_w') or not hasattr(self, '_cam_h'):
            self._cam_w, self._cam_h = get_camera_size()
            if not self._cam_w:
                self._cam_w, self._cam_h = 1920, 1080

        # 缩放 aim_point 到缩略图坐标系
        if self._cam_w > 0 and self._cam_h > 0:
            sx = w_thumb / self._cam_w
            sy = h_thumb / self._cam_h
            aim_scaled = (aim_point[0] * sx, aim_point[1] * sy)
        else:
            aim_scaled = aim_point

        return process_frame(frame, result, aim_scaled)

    def release(self):
        """停止后台线程并释放资源。"""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        try:
            self._http_conn.close()
        except Exception:
            pass

def body_aim(aim, quad):
    """判断准心是否落在四边形区域内（使用射线法）。"""
    ax, ay = aim
    n = len(quad)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = quad[i]
        xj, yj = quad[j]
        # 检查射线是否与边相交
        if ((yi > ay) != (yj > ay)) and (ax < (xj - xi) * (ay - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def get_camera_size():
    """从摄像头共享服务获取画面尺寸。"""
    try:
        parsed = urlparse(CAMERA_SIZE_PATH)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
        conn.request("GET", parsed.path)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        return data["width"], data["height"]
    except Exception as e:
        print(f"[警告] 获取摄像头尺寸失败: {e}")
        return None, None


def process_frame(frame, result, aim_point):
    """
    分析一帧 YOLO 检测结果，返回 JSON 格式字典。

    返回格式:
    {
        "num": 人数,
        "box": {
            id: [[head_x1, head_y1, head_x2, head_y2],        # 头部框
                 [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]]           # 身体四边形
        },
        "aim": {
            "head": [命中头部的 id 列表],
            "body": [命中身体的 id 列表]
        }
    }
    """
    data = {"num": 0, "box": {}, "aim": {"head": [], "body": []}}

    if frame is None or result is None or not result.boxes:
        return data

    kp = result.keypoints.xy.cpu().numpy()
    box_ids = getattr(result.boxes, "id", None)

    head_hit_ids = []
    body_hit_ids = []

    for i, box in enumerate(kp):
        try:
            # 提取 17 个关键点
            points = []
            for p in range(17):
                x, y = int(box[p][0]), int(box[p][1])
                points.append((x, y))

            tid = int(box_ids[i]) if box_ids is not None else -1

            # --- 头部框 ---
            w = abs(points[LEFT_EAR][0] - points[RIGHT_EAR][0])
            h = abs((2 * points[NOSE][1] - points[LEFT_EYE][1] - points[RIGHT_EYE][1])) * 2
            if w > 0 and h > 0:
                head_x1 = int(min(points[LEFT_EAR][0], points[RIGHT_EAR][0]) + w * 0.1)
                head_y1 = int(points[NOSE][1] - h * 1.0)
                head_x2 = int(max(points[LEFT_EAR][0], points[RIGHT_EAR][0]) - w * 0.1)
                head_y2 = int(points[NOSE][1] + h * 0.7)
                head_rect = [head_x1, head_y1, head_x2, head_y2]
            else:
                head_rect = [0, 0, 0, 0]

            # --- 身体四边形 ---
            body_quad = [
                [points[LEFT_SHOULDER][0], points[LEFT_SHOULDER][1]],
                [points[RIGHT_SHOULDER][0], points[RIGHT_SHOULDER][1]],
                [points[RIGHT_HIP][0], points[RIGHT_HIP][1]],
                [points[LEFT_HIP][0], points[LEFT_HIP][1]],
            ]

            # 存入 box
            data["box"][str(tid)] = [head_rect, body_quad]

            # --- 击中判定 ---
            if head_rect != [0, 0, 0, 0]:
                head_quad = [
                    (head_x1, head_y1), (head_x2, head_y1),
                    (head_x2, head_y2), (head_x1, head_y2)
                ]
                if body_aim(aim_point, head_quad):
                    head_hit_ids.append(tid)

            if body_aim(aim_point, body_quad):
                body_hit_ids.append(tid)

        except Exception:
            continue

    data["num"] = len(data["box"])
    data["aim"]["head"] = head_hit_ids
    data["aim"]["body"] = body_hit_ids
    return data


def main():
    """独立测试入口：启动跟踪器并持续输出分析结果。"""
    if not Path(MODEL_PATH).exists():
        print(f"[错误] 模型文件未找到: {MODEL_PATH}")
        return

    cam_w, cam_h = get_camera_size()
    if not cam_w or not cam_h:
        print("[警告] 无法获取摄像头尺寸，使用默认 640x480")
        cam_w, cam_h = 640, 480

    aim_point = (cam_w // 2, cam_h // 2)
    print(f"摄像头尺寸: {cam_w}x{cam_h}, 准心: {aim_point}")

    tracker = HumanTracker(CAMERA_PATH, MODEL_PATH)
    print("分析中... Ctrl+C 退出")

    try:
        while True:
            data = tracker.get_analysis(aim_point)
            if data["num"] > 0:
                print(json.dumps(data, ensure_ascii=False))
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        tracker.release()
        print("\n已退出。")


if __name__ == "__main__":
    main()

