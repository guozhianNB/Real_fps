"""
摄像头共享服务 — 双分辨率版

两个接口：
  /snapshot        → 全分辨率 (1920x1080), quality=85  → UI 显示
  /snapshot_thumb  → 缩略图   (640x480),   quality=70  → YOLO 推理

端口: 8010
启动: uvicorn vision.camera_share:app --port 8010 --host 127.0.0.1
"""

import cv2
import threading
import time

from fastapi import FastAPI, HTTPException, Response

# ============================================================
#  摄像头参数
# ============================================================
CAM_W = 1920           # 采集宽度（全分辨率，供 UI 清晰显示）
CAM_H = 1080           # 采集高度
THUMB_W = 640          # 缩略图宽度（YOLO 推理用）
THUMB_H = 480          # 缩略图高度
SNAPSHOT_QUALITY = 85  # 全分辨率 JPEG 质量（85 肉眼几乎无损，体积小 70%）
THUMB_QUALITY = 70     # 缩略图 JPEG 质量


# --------------------------
# 1. 摄像头管理器
# --------------------------
class CameraManager:
    def __init__(self, camera_id=0):
        # 用 DSHOW 后端，让 CAP_PROP_BUFFERSIZE 生效
        self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.cap.isOpened():
            raise RuntimeError("无法打开摄像头！请检查设备是否被其他程序占用。")

        # 设置 MJPG 格式降低 USB 带宽，再设目标分辨率
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('M', 'J', 'P', 'G'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"摄像头分辨率: 目标 {CAM_W}x{CAM_H} → 实际 {actual_w}x{actual_h}")

        # 丢弃前 10 帧，清空驱动内部缓冲区（解决 Windows 缓冲旧帧问题）
        for _ in range(10):
            self.cap.read()
        print("已清空摄像头内部缓冲区 (丢弃 10 帧)")

        self.frame_queue = []
        self.thumb_queue = []  # 缩略图缓存
        self.lock = threading.Lock()

        # —— JPEG 字节缓存（每帧只编码一次，避免重复消耗） ——
        self._jpeg_cache = None       # 全分辨率 JPEG 字节
        self._jpeg_thumb_cache = None # 缩略图 JPEG 字节
        self._jpeg_frame_id = 0       # 已缓存的帧序号
        self._frame_counter = 0       # 自增帧计数器

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print("摄像头服务已启动，后台采集线程运行中...")

    def _encode_jpeg(self, frame, quality):
        """编码一张帧为 JPEG 字节。"""
        success, buf = cv2.imencode(
            ".jpg", frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), quality],
        )
        return buf.tobytes() if success else None

    def _capture_loop(self):
        """后台线程：持续读取摄像头，同时生成缩略图并预编码 JPEG。"""
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self._frame_counter += 1
                thumb = cv2.resize(frame, (THUMB_W, THUMB_H),
                                   interpolation=cv2.INTER_LINEAR)
                # 预编码 JPEG（只需编一次，所有 HTTP 请求复用）
                jpeg_full = self._encode_jpeg(frame, SNAPSHOT_QUALITY)
                jpeg_thumb = self._encode_jpeg(thumb, THUMB_QUALITY)

                with self.lock:
                    self.frame_queue.clear()
                    self.frame_queue.append(frame)
                    self.thumb_queue.clear()
                    self.thumb_queue.append(thumb)
                    self._jpeg_cache = jpeg_full
                    self._jpeg_thumb_cache = jpeg_thumb
                    self._jpeg_frame_id = self._frame_counter
            else:
                time.sleep(0.01)

    def get_latest_frame(self):
        """返回最新一帧全分辨率副本。"""
        with self.lock:
            if self.frame_queue:
                return self.frame_queue[0].copy()
            return None

    def get_latest_thumb(self):
        """返回最新缩略图副本。"""
        with self.lock:
            if self.thumb_queue:
                return self.thumb_queue[0].copy()
            return None

    def get_jpeg(self):
        """返回已缓存的 JPEG 字节（全分辨率），线程安全。"""
        with self.lock:
            return self._jpeg_cache, self._jpeg_frame_id

    def get_jpeg_thumb(self):
        """返回已缓存的 JPEG 字节（缩略图），线程安全。"""
        with self.lock:
            return self._jpeg_thumb_cache, self._jpeg_frame_id

    def get_size(self):
        """返回全分辨率尺寸。"""
        with self.lock:
            if self.frame_queue:
                h, w = self.frame_queue[0].shape[:2]
                return w, h
        return 0, 0

    def release(self):
        """释放摄像头资源。"""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.cap.release()
        print("摄像头资源已释放。")

    def release(self):
        """释放摄像头资源。"""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.cap.release()
        print("摄像头资源已释放。")


camera_manager = None
camera_error = None


# --------------------------
# 2. FastAPI 应用
# --------------------------
app = FastAPI(title="共享摄像头服务", description="双分辨率: 全帧 UI / 缩略图 YOLO")


def _get_camera_manager():
    global camera_manager
    if camera_manager is None:
        raise HTTPException(status_code=503, detail=camera_error or "摄像头服务尚未就绪")
    return camera_manager


@app.on_event("startup")
def startup_event():
    global camera_manager, camera_error
    try:
        camera_manager = CameraManager(camera_id=0)
        camera_error = None
    except Exception as exc:
        camera_manager = None
        camera_error = str(exc)
        print(f"摄像头初始化失败：{exc}")


@app.on_event("shutdown")
def shutdown_event():
    global camera_manager
    if camera_manager is not None:
        camera_manager.release()
        camera_manager = None


@app.get("/size")
def get_camera_size():
    """返回全分辨率尺寸，供其他程序查询。"""
    manager = _get_camera_manager()
    w, h = manager.get_size()
    if w == 0:
        raise HTTPException(status_code=503, detail="当前没有可用的摄像头画面")
    return {"width": w, "height": h}


@app.get("/snapshot")
async def get_camera_snapshot():
    """全分辨率 JPEG — 直接返回缓存，零编码开销。"""
    manager = _get_camera_manager()
    jpeg_bytes, fid = manager.get_jpeg()
    if jpeg_bytes is None:
        raise HTTPException(status_code=503, detail="当前没有可用的摄像头画面")
    return Response(content=jpeg_bytes, media_type="image/jpeg")


@app.get("/snapshot_thumb")
async def get_camera_snapshot_thumb():
    """缩略图 JPEG — 直接返回缓存，零编码开销。"""
    manager = _get_camera_manager()
    jpeg_bytes, fid = manager.get_jpeg_thumb()
    if jpeg_bytes is None:
        raise HTTPException(status_code=503, detail="当前没有可用的摄像头画面")
    return Response(content=jpeg_bytes, media_type="image/jpeg")