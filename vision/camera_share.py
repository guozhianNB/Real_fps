###############################################
'''
摄像头共享服务：提供一个独立的 FastAPI 应用，持续采集摄像头画面并按需提供最新帧的 JPEG 图片接口。
端口:8010
uvicorn camera_share:app --port 8010 --host 127.0.0.1 --reload

'''


import cv2
import threading
import time

from fastapi import FastAPI, HTTPException, Response

# --------------------------
# 1. 全局单例：摄像头管理器
# --------------------------
class CameraManager:
    def __init__(self, camera_id=0, width=1920, height=1080):
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.cap.isOpened():
            raise RuntimeError("无法打开摄像头！请检查设备是否被其他程序占用。")

        # 自动寻找摄像头能支持的最高分辨率
        candidates = [(3840, 2160), (2560, 1440), (1920, 1080),
                      (1280, 720), (640, 480)]
        best_w, best_h = 640, 480
        for cw, ch in candidates:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cw)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ch)
            rw = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            rh = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if (rw, rh) == (cw, ch):
                best_w, best_h = cw, ch
                break
            # 也保存扫到的最优值
            if rw * rh > best_w * best_h:
                best_w, best_h = rw, rh

        # 重新设为最佳分辨率
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, best_w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, best_h)
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"摄像头分辨率: 最佳 {best_w}x{best_h} → 实际 {actual_w}x{actual_h}")

        self.frame_queue = []
        self.lock = threading.Lock()
        self.running = True

        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print("摄像头服务已启动，后台采集线程运行中...")

    def _capture_loop(self):
        """后台线程：持续读取摄像头并保留最新帧。"""
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame_queue.clear()
                    self.frame_queue.append(frame)
            else:
                time.sleep(0.01)

    def get_latest_frame(self):
        """返回最新一帧的副本。"""
        with self.lock:
            if self.frame_queue:
                return self.frame_queue[0].copy()
            return None

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
# 2. FastAPI 应用与路由
# --------------------------
app = FastAPI(title="共享摄像头服务", description="提供按需拍照的摄像头图片接口")


def _get_camera_manager():  # 获取全局摄像头管理器实例，若未就绪则抛出异常
    global camera_manager
    if camera_manager is None:
        raise HTTPException(status_code=503, detail=camera_error or "摄像头服务尚未就绪")
    return camera_manager


@app.on_event("startup")    #服务器启动时初始化摄像头管理器
def startup_event():
    """启动时初始化摄像头，但允许服务在摄像头不可用时仍能启动。"""
    global camera_manager, camera_error
    try:
        camera_manager = CameraManager(camera_id=0)
        camera_error = None
    except Exception as exc:
        camera_manager = None
        camera_error = str(exc)
        print(f"摄像头初始化失败：{exc}")

@app.on_event("shutdown")       #服务器关闭时释放摄像头资源
def shutdown_event():
    """服务器关闭时优雅释放摄像头"""
    global camera_manager
    if camera_manager is not None:
        camera_manager.release()
        camera_manager = None

@app.get("/size")         #提供摄像头图片尺寸的接口，返回 JSON 格式的宽高信息
def get_camera_size():
    """返回摄像头图片的尺寸信息，供其他程序查询。"""
    manager = _get_camera_manager()
    frame = manager.get_latest_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="当前没有可用的摄像头画面")
    height, width = frame.shape[:2]
    return {"width": width, "height": height}


def _encode_frame(frame, quality=95):       #将帧编码为 JPEG 格式的字节流
    success, buffer = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), quality],
    )
    if not success:
        raise HTTPException(status_code=500, detail="摄像头图片编码失败")
    return buffer.tobytes()


@app.get("/snapshot")       #提供摄像头图片的接口，返回 JPEG 格式的图片数据
async def get_camera_snapshot():
    """返回当前摄像头的 JPEG 图片，供其他程序直接拉取。"""
    manager = _get_camera_manager()
    frame = manager.get_latest_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="当前没有可用的摄像头画面")

    jpeg_bytes = _encode_frame(frame)
    return Response(content=jpeg_bytes, media_type="image/jpeg")
'''
启动 uvicorn vision.camera_share:app --port 8010 --reload
如何获得当前摄像头画面：
   - 直接访问接口获取 JPEG 图片：
   - 通过 HTTP GET 请求访问 http://127.0.0.1:8010/snapshot
   - 代码示例（Python）：


import requests

resp = requests.get("http://127.0.0.1:8010/snapshot")
jpeg_bytes = resp.content   # ← 同样的 JPEG 二进制数据

# 字节 → numpy 数组 → cv2 图像
data = np.frombuffer(jpeg_bytes, dtype=np.uint8)
frame = cv2.imdecode(data, cv2.IMREAD_COLOR)   # ← 这就是 cv2 的 BGR 图像了

   '''