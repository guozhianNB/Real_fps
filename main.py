'''
主程序 — Real FPS 后端引擎
============================

职责：
  1. 初始化摄像头、YOLO 跟踪器、串口、鼠标监听器
  2. 主循环：视觉分析 → 开火检测 → 写入 state.json → 串口控制
  3. 通过 UDP 广播实时通知 UI 开火事件

通信架构：
  - state.json  → 只传递"状态"（模式、目标列表、分数、串口状态）
  - UDP 广播    → 实时传递"事件"（开火、命中），不经过 JSON

vision 返回 JSON 格式:
  {
      "num": 人数,
      "box": {
          id: [[head_x1,head_y1,head_x2,head_y2],           # 头部矩形
               [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]]           # 身体四边形
      },
      "aim": {
          "head": [瞄到头部的 id],
          "body": [瞄到身体的 id]
      }
  }

state.json 格式:
  {
      "timestamp": 1717320000.0,
      "system_state": {"mode": "playing", "msg": "normal"},
      "score": {"value": 120},
      "targets": [{"id": 3, "bbox": [600, 300, 680, 420]}],
      "camera_size":(1080,960)
      "serial": {"status": "OK", "msg": "connected"}
  }

UDP 事件格式（由 fire_notifier.py 发送）:
  {"event": "fire", "hit_zone": "head", "score_delta": 50, "timestamp": ...}

各字段含义：
  system_state.mode → idle / playing / paused / over
  score.value       → 当前分数
  targets           → 所有检测到的目标列表
  serial.status     → 串口状态 OK / ERROR

UI 显示由 ui/core.py（Pygame）独立进程完成，本程序仅负责后端计算。
'''

import json
import math
import time
import sys
from pathlib import Path
import numpy as np
import cv2
import pyee
from vision.vision import HumanTracker, get_camera_size
from fire_notifier import send_fire, send_kill, close_sender, ReloadDoneListener, close_reload_sender
from A_serial import SerialController
from mouse import MouseListener

# ====== 人脸识别初始化 ======
try:
    from ultralytics import YOLO
    from vision.face_rec import load_model, detect_faces_yolo, FACE_SIZE
    _face_yolo = YOLO(str(Path("vision/model/yolov11n-face.pt")))
    _face_recognizer, _face_labels, _face_threshold = load_model(
        "LBPH", Path("vision/model"))
    print(f"[人脸] 识别就绪，已知 {len(_face_labels)} 人")
except Exception as e:
    _face_yolo = None
    _face_recognizer = None
    _face_labels = {}
    print(f"[人脸] 未加载（不影响游戏）: {e}")

# ============================================================
#  常量
# ============================================================

STATE_FILE = "state.json"

# 鼠标灵敏度
PITCH = 1.0   # 俯仰（Y 轴）
YAW = 1.0     # 水平（X 轴）

# 串口
SERIAL_PORT = None        # None=自动检测，可指定如 "COM3"
SERIAL_BAUDRATE = 115200

# 开火冷却
FIRE_COOLDOWN_MS = 100    # 两次开火最短间隔（毫秒）

# 模式
MODE_IDLE = "idle"
MODE_PLAYING = "playing"
MODE_PAUSED = "paused"
MODE_OVER = "over"


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


# ============================================================
#  state.json 写入工具
# ============================================================
# state.json 只传递"状态"（模式、目标列表、串口状态）
# "事件"（开火）走独立的 UDP 广播，实时通知 UI

def write_state(system_state, score_value=0,
                targets=None, serial_status="OK", serial_msg="connected",
                camera_size=None, ammo=0):
    """写入 state.json。开火事件已独立到 UDP，不在此传递。"""
    state = {
        "timestamp": time.time(),
        "system_state": system_state,
        "score": {"value": score_value},
        "targets": targets or [],
        "camera_size": camera_size or [0, 0],
        "serial": {"status": serial_status, "msg": serial_msg},
        "ammo": ammo,
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[警告] 写入 state.json 失败: {e}")


# ============================================================
#  摄像头就绪等待
# ============================================================

def wait_for_camera(max_retries=30, interval=0.5):
    """等待摄像头服务就绪，返回 (cam_w, cam_h) 或退出程序。"""
    print("[等待] 正在等待摄像头服务...")
    for attempt in range(1, max_retries + 1):
        cam_w, cam_h = get_camera_size()
        if cam_w and cam_h:
            print(f"[就绪] 摄像头已就绪，尺寸: {cam_w}x{cam_h}")
            return cam_w, cam_h
        print(f"  ...第 {attempt}/{max_retries} 次尝试")
        time.sleep(interval)
    print("[错误] 摄像头服务启动超时，请检查 uvicorn 是否正常运行。")
    sys.exit(1)


# ============================================================
#  串口初始化（带容错）
# ============================================================

def init_serial(port, baudrate):
    """尝试初始化串口，失败时返回 None（不阻塞启动）。"""
    try:
        ser = SerialController(port=port, baudrate=baudrate)
        return ser
    except RuntimeError as e:
        print(f"[警告] 串口初始化失败（游戏仍可运行）: {e}")
        return None


# ============================================================
#  主程序
# ============================================================

def main():
    """游戏主程序入口：后端计算。"""

    # ===================== 1. 初始化 =====================

    # 1a. 等待摄像头服务就绪
    cam_w, cam_h = wait_for_camera()
    aim_point = (cam_w // 2, cam_h // 2)

    # 1b. 启动 YOLO 跟踪器
    print("[等待] 正在启动 YOLO 跟踪器...")
    tracker = HumanTracker()

    # 1c. 初始化串口（非必须，失败不阻塞）
    serial = init_serial(SERIAL_PORT, SERIAL_BAUDRATE)
    v_x = 0  # 云台 yaw 角目标 (-90~90)
    v_y = 0  # 云台 pitch 角目标 (-90~90)

    # 1d. 鼠标监听器（后台线程自动启动，start() 后开始采集）
    ml = MouseListener(
        sensitivity=1.0, deadzone=2,
        smooth_window=3, center_lock=True,
    )
    game_running = True
    current_mode = MODE_PLAYING
    reloading = False
    ammo = 30

    # 1e. 游戏状态机 —— 统一管理状态转换
    emitter = pyee.EventEmitter()

    @emitter.on("GAME_START")
    def on_start():
        nonlocal current_mode
        current_mode = MODE_PLAYING
        print("[状态] 游戏开始")

    @emitter.on("GAME_PAUSE")
    def on_pause():
        nonlocal current_mode
        current_mode = MODE_PAUSED
        ml.pause()
        print("[状态] 游戏暂停")

    @emitter.on("GAME_CONTINUE")
    def on_continue():
        nonlocal current_mode
        current_mode = MODE_PLAYING
        ml.resume()
        print("[状态] 游戏继续")

    @emitter.on("GAME_OVER")
    def on_over():
        nonlocal game_running, current_mode
        current_mode = MODE_OVER
        game_running = False
        ml.stop()
        if serial:
            serial.close()
        print("[状态] 游戏结束")

    # 鼠标键盘事件 → 转发到统一状态机
    ml.emitter.on("GAME_PAUSE", lambda: emitter.emit("GAME_PAUSE"))
    ml.emitter.on("GAME_CONTINUE", lambda: emitter.emit("GAME_CONTINUE"))
    ml.emitter.on("GAME_OVER", lambda: emitter.emit("GAME_OVER"))
    ml.emitter.on("GAME_INSPECT", lambda: send_fire(event_type="inspect"))

    def on_reload():
        nonlocal reloading
        if not reloading:
            reloading = True
            print("[换弹] 开始换弹...")
            send_fire(event_type="reload_start")
    ml.emitter.on("GAME_RELOAD", on_reload)

    # 监听 UI 换弹完成信号
    def on_reload_done(event):
        nonlocal reloading, ammo
        reloading = False
        ammo = 30
        print(f"[换弹] 完成，弹药: {ammo}")
    reload_listener = ReloadDoneListener(callback=on_reload_done)
    reload_listener.start()

    # 发射 GAME_START（所有模块就绪）
    emitter.emit("GAME_START")
    ml.start()

    # ===================== 2. 主循环 =====================

    print("[状态] 进入主循环（显示由 Pygame UI 独立渲染）")
    print("  按键:  P=暂停/继续  Esc=退出  R=换弹  Ctrl+C=强制退出")

    score_value = 0
    last_hit_time = 0
    ammo = 30
    blacklist = set()
    face_registry = {}      # tracking_id → 人名
    face_attempts = {}      # tracking_id → 已尝试帧数
    seen_ids = set()
    FACE_MAX_ATTEMPTS = 30  # 最多尝试 30 帧

    def _recognize_new_face(tid, frame_bgr, kp_array, ids_array):
        """对新人进行人脸识别，30 帧内成功则标记人名，否则 Unknown。"""
        if _face_yolo is None or _face_recognizer is None:
            face_registry[tid] = f"#{tid}"
            return

        # 找到该 ID 对应的人体关键点索引
        indices = np.where(ids_array == tid)[0]
        if len(indices) == 0:
            return
        idx = indices[0]
        # NOSE = keypoint 0
        nose_x, nose_y = int(kp_array[idx][0][0]), int(kp_array[idx][0][1])
        if nose_x == 0 and nose_y == 0:
            return  # 关键点无效

        # 以鼻为中心扩展 m 像素
        m = max(
            abs(kp_array[idx][LEFT_EAR][0] - kp_array[idx][NOSE][0]),
            abs(kp_array[idx][NOSE][1] - (kp_array[idx][LEFT_EYE][1] + kp_array[idx][RIGHT_EYE][1]) / 2)*6
        )
        x1 = int(max(0, nose_x - m))
        y1 = int(max(0, nose_y - m))
        x2 = int(nose_x + m)
        y2 = int(nose_y + m)
        face_region = frame_bgr[y1:y2, x1:x2]
        if face_region.size == 0:
            return

        faces = detect_faces_yolo(face_region, _face_yolo)
        if not faces:
            face_attempts[tid] = face_attempts.get(tid, 0) + 1
            if face_attempts[tid] >= FACE_MAX_ATTEMPTS:
                face_registry[tid] = "Unknown"
                print(f"[人脸] ID#{tid} → Unknown（30 帧未识别）")
            return

        fx1, fy1, fx2, fy2 = max(faces, key=lambda r: (r[2]-r[0])*(r[3]-r[1]))
        face_roi = face_region[fy1:fy2, fx1:fx2]
        if face_roi.size == 0:
            return
        face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        face_gray = cv2.resize(face_gray, FACE_SIZE)
        label_id, conf = _face_recognizer.predict(face_gray)
        if conf <= _face_threshold:
            name = _face_labels.get(label_id, f"#{tid}")
            face_registry[tid] = name
            print(f"[人脸] ID#{tid} → {name} (置信度 {conf:.1f})")
        else:
            face_attempts[tid] = face_attempts.get(tid, 0) + 1
            if face_attempts[tid] >= FACE_MAX_ATTEMPTS:
                face_registry[tid] = "Unknown"
                print(f"[人脸] ID#{tid} → Unknown（30 帧未识别，最高置信度 {conf:.1f}）")

    try:
        while game_running:
            now_ms = time.time() * 1000

            # ---- 2a. 鼠标输入 ----
            dx, dy, left_pressed = ml.get_delta()

            # ---- 2b. 视觉分析 ----
            data = tracker.get_analysis(aim_point)

            # 检测新出现的 ID → 人脸识别（用 NOSE 关键点扩展）
            current_ids = {int(tid) for tid in data["box"].keys()}
            new_ids = current_ids - seen_ids
            if new_ids:
                frame_bgr, result, _ = tracker.get_latest()
                if frame_bgr is not None and result is not None and result.keypoints is not None:
                    kp_arr = result.keypoints.xy.cpu().numpy()
                    ids_arr = getattr(result.boxes, "id", None)
                    if ids_arr is not None:
                        ids_arr = ids_arr.cpu().numpy()
                        for tid in new_ids:
                            if tid not in face_registry:
                                _recognize_new_face(tid, frame_bgr, kp_arr, ids_arr)
            seen_ids = current_ids

            # 过滤黑名单：只保留未击杀的目标
            alive_head = [tid for tid in data["aim"]["head"] if tid not in blacklist]
            alive_body = [tid for tid in data["aim"]["body"] if tid not in blacklist]

            # ---- 2c. 开火检测 ----
            on_target = data["num"] > 0 and (len(alive_head) > 0 or len(alive_body) > 0)
            if not reloading and ammo and left_pressed and (now_ms - last_hit_time) >= FIRE_COOLDOWN_MS:
                last_hit_time = now_ms
                v_y += 10
                ammo -= 1
                if on_target:
                    if len(alive_head) > 0:
                        hit_zone = "head"
                        score_delta = 50
                        killed_id = alive_head[0]
                    else:
                        hit_zone = "body"
                        score_delta = 10
                        killed_id = alive_body[0]

                    score_value += score_delta
                    blacklist.add(killed_id)
                    name = face_registry.get(killed_id, f"#{killed_id}")
                    print(f"[击杀] {name} {hit_zone} +{score_delta}")

                    send_fire(hit_zone=hit_zone, score_delta=score_delta)
                    send_kill(hit_zone=hit_zone, score_delta=score_delta, target_id=killed_id, target_name=name)
                else:
                    # 左键按下 + 没有击中 → 开火，但不加分（可用于训练瞄准）
                    print("[开火] 未击中目标")
                    send_fire(hit_zone=None, score_delta=0)

            # ---- 2d. 目标列表（写入 state.json，阵亡含 dead 标记） ----
            targets_json = []
            for tid_str, box_data in data["box"].items():
                tid = int(tid_str)
                head_rect = box_data[0]
                body_quad = box_data[1]
                cx = (head_rect[0] + head_rect[2]) // 2
                cy = (head_rect[1] + head_rect[3]) // 2
                shoulder_mid_x = (body_quad[0][0] + body_quad[1][0]) / 2
                shoulder_mid_y = (body_quad[0][1] + body_quad[1][1]) / 2
                nose_x = (head_rect[0] + head_rect[2]) / 2
                nose_y = (head_rect[1] + head_rect[3]) / 2
                depth = math.sqrt(
                    (shoulder_mid_x - nose_x) ** 2 +
                    (shoulder_mid_y - nose_y) ** 2
                )
                targets_json.append({
                    "id": tid,
                    "bbox": head_rect,
                    "cx": cx,
                    "cy": cy,
                    "depth": round(depth, 1),
                    "dead": tid in blacklist,
                })

            # ---- 2e. 串口状态 ----
            if serial and serial.connected:
                ser_status = "OK"
                ser_msg = "connected"
            elif serial:
                ser_status = "ERROR"
                ser_msg = serial.last_msg
            else:
                ser_status = "ERROR"
                ser_msg = "not initialized"

            # ---- 2f. 写入 state.json ----
            write_state(
                system_state={"mode": current_mode, "msg": "normal"},
                score_value=score_value,
                targets=targets_json,
                serial_status=ser_status,
                serial_msg=ser_msg,
                camera_size=(cam_w, cam_h),
                ammo=ammo,
            )

            # ---- 2g. 视角控制（鼠标位移 → 云台角度） ----
            if current_mode == MODE_PLAYING:
                v_x += dx * YAW
                v_y += dy * PITCH
                v_x = max(-90, min(90, v_x))
                v_y = max(-90, min(90, v_y))
                if serial and serial.connected:
                    serial.send_angles(v_x, v_y)

            time.sleep(0.03)

    except KeyboardInterrupt:
        print("\n[中断] 用户强制退出")
    finally:
        ml.stop()
        if serial:
            serial.close()
        tracker.release()
        close_sender()
        close_reload_sender()
        reload_listener.stop()
        print("[退出] 程序已终止")

















if __name__ == "__main__":
    main()