import requests
import cv2
import numpy as np


def list_available_cameras(max_index=10):
    """扫描可用摄像头设备，返回 [(index, name), ...] 列表。

    尝试打开每个索引的摄像头，能成功读到帧的认为可用。
    max_index — 最大扫描索引（默认 10，涵盖多数情况）。
    """
    available = []
    for i in range(max_index):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                # 尝试读一帧确认确实可用
                ret, _ = cap.read()
                if ret:
                    # 尝试获取设备名称（部分驱动支持）
                    backend = cap.getBackendName()
                    name = f"Camera {i} ({backend})"
                    available.append((i, name))
                cap.release()
        except Exception:
            pass
    return available


def get_camera_size():
    """查询摄像头图片的尺寸信息，返回 (width, height)。"""
    try:
        resp = requests.get("http://127.0.0.1:8010/size")
        data = resp.json()
        return data["width"], data["height"]
    except Exception as e:
        print(f"查询摄像头尺寸失败: {e}")
        return None, None

def get_camera_frame():
    """获取当前摄像头画面，返回 cv2 图像。"""
    try:
        resp = requests.get("http://127.0.0.1:8010/snapshot")
        jpeg_bytes = resp.content
        data = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return frame
    except Exception as e:
        print(f"获取摄像头画面失败: {e}")
        return None