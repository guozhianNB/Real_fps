
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
CAMERA_PATH = "http://127.0.0.1:8010/snapshot"
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
            return self.latest_frame, self.latest_result, dict(self.trajectories) #分别返回最新帧、跟踪结果和轨迹字典

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


def main():
    # 检查模型文件是否存在
    if not Path(MODEL_PATH).exists():
        print(f"[错误] 模型文件未找到: {MODEL_PATH}")
        print("请将 yolo26n-pose.pt 放在 model/ 目录下")
        input("按 Enter 退出...")
        return

    # 读取摄像头画面尺寸
    cam_w, cam_h = get_camera_size()
    if cam_w and cam_h:
        print(f"摄像头画面尺寸: {cam_w} x {cam_h}")
    else:
        print("[警告] 无法获取摄像头尺寸，将使用默认窗口大小")

    aim_point = (cam_w // 2, cam_h // 2)                        # 准心位置，以画面中心为目标点

    print("正在启动 YOLO 人体跟踪器...")
    
    tracker = HumanTracker(camera_url=CAMERA_PATH, model_path=MODEL_PATH)

    cv2.namedWindow("RealFPS - YOLO Track", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("RealFPS - YOLO Track", cam_w , cam_h )

    print("跟踪中... 按 'q' 或 ESC 退出")

    try:
        while True:
            frame, result, trajectories = tracker.get_latest()
            if frame is None:
                time.sleep(0.05)
                continue

            # 在帧上绘制跟踪方框
            if result and result.boxes:
                # 关键点坐标
                kp = result.keypoints.xy.cpu().numpy()  

                # 获取跟踪 ID 列表（第一帧可能为 None）
                box_ids = getattr(result.boxes, "id", None)

                '''person = [
                    [id,
                        [head_x1, head_y1, head_x2, head_y2],  # 头部框
                        [(x,y),(x,y),(x,y),(x,y)]   # 身体框
                    ],...
                ]
                '''
                person=[]
                for i, box in enumerate(kp):
                    try:
                        points = []
                        for p in range(0, 17):
                            x, y = int(box[p][0]), int(box[p][1])
                            points.append((x, y))
                            cv2.circle(frame, (x, y), 3, (0, 255, 255), -1)

                        # 处理头部框
                        w = abs(points[LEFT_EAR][0] - points[RIGHT_EAR][0])
                        h = abs((2 * points[NOSE][1] - points[LEFT_EYE][1] - points[RIGHT_EYE][1])) * 2
                        if w > 0 and h > 0:
                            # OpenCV: y 向下增大，所以 head_y2（下巴）> head_y1（头顶）
                            head_x1 = int(min(points[LEFT_EAR][0], points[RIGHT_EAR][0]) + w * 0.1)
                            head_y1 = int(points[NOSE][1] - h * 1.0)   # 头顶（y 更小）
                            head_x2 = int(max(points[LEFT_EAR][0], points[RIGHT_EAR][0]) - w * 0.1)
                            head_y2 = int(points[NOSE][1] + h * 0.7)   # 下巴（y 更大）
                        else:
                            head_x1, head_y1, head_x2, head_y2 = 0, 0, 0, 0
                        cv2.rectangle(frame, (head_x1, head_y1), (head_x2, head_y2), (0, 255, 255), 2)
                        if body_aim(aim_point, [(head_x1, head_y1), (head_x2, head_y1), (head_x2, head_y2), (head_x1, head_y2)]):
                            cv2.putText(frame, "AIM!", (head_x1, head_y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                            print("准心击中头部！")
                        # print(head_x1, head_y1, head_x2, head_y2,w,h)
                        # 安全获取 ID
                        tid = int(box_ids[i]) if box_ids is not None else -1

                        # 处理身体框
                        if body_aim(aim_point, [points[LEFT_SHOULDER], points[RIGHT_SHOULDER], points[RIGHT_HIP], points[LEFT_HIP]]):
                            cv2.putText(frame, "AIM!", (points[LEFT_SHOULDER][0], points[LEFT_SHOULDER][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                            print("准心击中身体！")
                        person.append([tid, [head_x1, head_y1, head_x2, head_y2], [points[LEFT_SHOULDER], points[RIGHT_SHOULDER], points[LEFT_HIP], points[RIGHT_HIP]]])
                    except Exception:
                        # 单个人体绘制出错不影响后续
                        continue
                        



            cv2.imshow("RealFPS - YOLO Track", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # q 或 ESC
                break

    finally:
        tracker.release()
        cv2.destroyAllWindows()
        print("程序已退出。")


if __name__ == "__main__":
    main()






# # 辅助函数：判断点是否在四边形内（用于判断目标点是否在框内）
# def body_aim(point, quad_points):
#     """
#     判断目标点是否在四个点组成的任意四边形内
#     point: 目标点坐标 (px, py)
#     quad_points: 四个点的列表 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
#     """
#     px, py = point
#     inside = False
    
#     # 射线法核心逻辑
#     p1x, p1y = quad_points[0]
#     for i in range(1, len(quad_points) + 1):
#         p2x, p2y = quad_points[i % len(quad_points)] # 遍历每一条边
        
#         # 判断射线是否穿过当前边
#         if py > min(p1y, p2y):
#             if py <= max(p1y, p2y):
#                 if px <= max(p1x, p2x):
#                     if p1y != p2y:
#                         xinters = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
#                     if p1x == p2x or px <= xinters:
#                         inside = not inside
#         p1x, p1y = p2x, p2y
        
#     return inside

