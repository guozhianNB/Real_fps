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
import time
import sys
import pyee
from vision.vision import HumanTracker, get_camera_size
from fire_notifier import send_fire, close_sender
from A_serial import SerialController
from mouse import MouseListener

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


# ============================================================
#  state.json 写入工具
# ============================================================
# state.json 只传递"状态"（模式、目标列表、串口状态）
# "事件"（开火）走独立的 UDP 广播，实时通知 UI

def write_state(system_state, score_value=0,
                targets=None, serial_status="OK", serial_msg="connected"):
    """写入 state.json。开火事件已独立到 UDP，不在此传递。"""
    state = {
        "timestamp": time.time(),
        "system_state": system_state,
        "score": {"value": score_value},
        "targets": targets or [],
        "serial": {"status": serial_status, "msg": serial_msg},
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
    v_x = 0  # 累积水平视角
    v_y = 0  # 累积俯仰视角

    # 1d. 鼠标监听器（后台线程自动启动，start() 后开始采集）
    ml = MouseListener(
        sensitivity=1.0, deadzone=2,
        smooth_window=3, center_lock=True,
    )
    game_running = True
    current_mode = MODE_PLAYING  # 初始为 playing

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

    # 发射 GAME_START（所有模块就绪）
    emitter.emit("GAME_START")
    ml.start()

    # ===================== 2. 主循环 =====================

    print("[状态] 进入主循环（显示由 Pygame UI 独立渲染）")
    print("  按键:  P=暂停/继续  Esc=退出  Ctrl+C=强制退出")

    score_value = 0
    last_hit_time = 0

    try:
        while game_running:
            now_ms = time.time() * 1000

            # ---- 2a. 鼠标输入 ----
            dx, dy, left_pressed = ml.get_delta()

            # ---- 2b. 视觉分析 ----
            data = tracker.get_analysis(aim_point)

            # ---- 2c. 开火检测 ----
            on_target = (
                data["num"] > 0
                and (len(data["aim"]["head"]) > 0 or len(data["aim"]["body"]) > 0)
            )
            # 左键按下 + 准星指向目标 → 开火

            if left_pressed and on_target and (now_ms - last_hit_time) >= FIRE_COOLDOWN_MS:
                last_hit_time = now_ms

                if len(data["aim"]["head"]) > 0:
                    hit_zone = "head"
                    score_delta = 50
                else:
                    hit_zone = "body"
                    score_delta = 10

                score_value += score_delta
                print(f"[击中] {hit_zone}  +{score_delta}  总分:{score_value}")

                # UDP 实时通知 UI
                send_fire(hit_zone=hit_zone, score_delta=score_delta)
            # 左键按下 + 没有击中 → 开火，但不加分（可用于训练瞄准）
            elif left_pressed and not on_target and (now_ms - last_hit_time) >= FIRE_COOLDOWN_MS:
                last_hit_time = now_ms
                print("[开火] 未击中目标")
                send_fire(hit_zone=None, score_delta=0)

            # ---- 2d. 目标列表（用于写入 state.json） ----
            targets_json = []
            for tid_str, box_data in data["box"].items():
                # box_data[0] = 头部矩形 [x1,y1,x2,y2]
                targets_json.append({
                    "id": int(tid_str),
                    "bbox": box_data[0],
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
            )

            # ---- 2g. 视角控制（鼠标位移 → 云台误差） ----
            if current_mode == MODE_PLAYING:
                v_x += dx * YAW
                v_y += dy * PITCH
                if serial and serial.connected:
                    serial.send_errors(int(v_x), int(v_y))

            time.sleep(0.03)

    except KeyboardInterrupt:
        print("\n[中断] 用户强制退出")
    finally:
        ml.stop()
        if serial:
            serial.close()
        tracker.release()
        close_sender()
        print("[退出] 程序已终止")

















if __name__ == "__main__":
    main()