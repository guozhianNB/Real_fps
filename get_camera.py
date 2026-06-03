import requests
import cv2
import numpy as np


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