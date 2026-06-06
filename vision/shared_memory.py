"""
shared_memory.py — 跨进程摄像头帧共享（零拷贝）

替代 HTTP 的帧传输方案，使用 multiprocessing.shared_memory：
  camera_share (生产者) → 写入共享内存 → vision / UI (消费者)

共享内存布局（每帧）：
  [0:8]    frame_counter (int64) — 每次写完帧后递增，作为"提交标记"
  [8:12]   width   (int32)
  [12:16]  height  (int32)
  [16:20]  channels (int32) — 固定 3
  [20:24]  data_size (int32) — frame 实际字节数
  [24:64]  reserved
  [64:]    frame data — numpy 原始 BGR 字节

两个共享内存块：
  camera_thumb  — 缩略图 640×480（YOLO 推理用）
  camera_full   — 全分辨率 1280×720（UI 显示用）
"""

import numpy as np
from multiprocessing import shared_memory

# ============================================================
#  常量
# ============================================================
HEADER_SIZE = 64          # 元数据区大小
THUMB_NAME = "camera_thumb"
FULL_NAME  = "camera_full"

# ---- 帧尺寸（必须与 camera_share.py 保持一致） ----
THUMB_W = 640
THUMB_H = 480
FULL_W  = 1280
FULL_H  = 720
CHANNELS = 3

THUMB_DATA_SIZE = THUMB_W * THUMB_H * CHANNELS  # 921,600
FULL_DATA_SIZE  = FULL_W  * FULL_H  * CHANNELS   # 2,764,800

THUMB_BLOCK_SIZE = HEADER_SIZE + THUMB_DATA_SIZE
FULL_BLOCK_SIZE  = HEADER_SIZE + FULL_DATA_SIZE


# ============================================================
#  生产者（camera_share.py 使用）
# ============================================================
def create_shared_memories():
    """创建共享内存块（由生产者进程调用）。"""
    try:
        shm_thumb = shared_memory.SharedMemory(
            name=THUMB_NAME, create=True, size=THUMB_BLOCK_SIZE)
    except FileExistsError:
        # 上次异常退出残留，清理后重建
        existing = shared_memory.SharedMemory(name=THUMB_NAME)
        existing.unlink()
        existing.close()
        shm_thumb = shared_memory.SharedMemory(
            name=THUMB_NAME, create=True, size=THUMB_BLOCK_SIZE)

    try:
        shm_full = shared_memory.SharedMemory(
            name=FULL_NAME, create=True, size=FULL_BLOCK_SIZE)
    except FileExistsError:
        existing = shared_memory.SharedMemory(name=FULL_NAME)
        existing.unlink()
        existing.close()
        shm_full = shared_memory.SharedMemory(
            name=FULL_NAME, create=True, size=FULL_BLOCK_SIZE)

    # 初始化 frame_counter = 0
    _write_counter(shm_thumb, 0)
    _write_counter(shm_full, 0)

    return shm_thumb, shm_full


def write_frame(shm, frame: np.ndarray):
    """将一帧写入共享内存。

    参数：
        shm:     SharedMemory 对象
        frame:   numpy BGR 数组 (H, W, 3)，uint8
    """
    h, w = frame.shape[:2]
    data_bytes = frame.tobytes()

    buf = shm.buf
    # 先写元数据
    buf[8:12]  = np.int32(w).tobytes()
    buf[12:16] = np.int32(h).tobytes()
    buf[16:20] = np.int32(3).tobytes()
    buf[20:24] = np.int32(len(data_bytes)).tobytes()
    # 再写帧数据
    buf[64:64 + len(data_bytes)] = data_bytes
    # 最后更新 counter（原子化"提交"）
    counter = np.frombuffer(buf[0:8], dtype=np.int64)[0] + 1
    buf[0:8] = np.int64(counter).tobytes()


def _write_counter(shm, counter):
    shm.buf[0:8] = np.int64(counter).tobytes()


# ============================================================
#  消费者（vision.py / ui 使用）
# ============================================================
class SharedMemoryReader:
    """从共享内存读取最新帧。"""

    def __init__(self, name: str, block_size: int):
        self._shm = shared_memory.SharedMemory(name=name, create=False)
        self._last_counter = -1
        self._block_size = block_size

    def read(self) -> np.ndarray | None:
        """读取最新帧。若无新帧返回 None。"""
        buf = self._shm.buf
        counter = np.frombuffer(buf[0:8], dtype=np.int64)[0]

        if counter == self._last_counter:
            return None  # 无新帧

        w   = np.frombuffer(buf[8:12],  dtype=np.int32)[0]
        h   = np.frombuffer(buf[12:16], dtype=np.int32)[0]
        # c = np.frombuffer(buf[16:20], dtype=np.int32)[0]
        size = np.frombuffer(buf[20:24], dtype=np.int32)[0]

        if size <= 0 or size > self._block_size - HEADER_SIZE:
            return None

        frame_data = bytes(buf[64:64 + size])
        self._last_counter = counter
        return np.frombuffer(frame_data, dtype=np.uint8).reshape(h, w, 3)

    def close(self):
        self._shm.close()


def open_thumb_reader() -> SharedMemoryReader:
    """打开缩略图共享内存读取器。"""
    return SharedMemoryReader(THUMB_NAME, THUMB_BLOCK_SIZE)


def open_full_reader() -> SharedMemoryReader:
    """打开全分辨率共享内存读取器。"""
    return SharedMemoryReader(FULL_NAME, FULL_BLOCK_SIZE)


# ============================================================
#  清理
# ============================================================
def unlink_all():
    """删除所有共享内存块（进程退出时调用）。"""
    for name in (THUMB_NAME, FULL_NAME):
        try:
            shm = shared_memory.SharedMemory(name=name)
            shm.unlink()
            shm.close()
        except FileNotFoundError:
            pass
