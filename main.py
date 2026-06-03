'''
主程序
流程：
广播GAME_START->调用vision.py,返回json数据->处理...


vision返回JSON格式:
{
    "num":人数,
    "box":{
        id:[[(head_x1, head_y1), (head_x2, head_y2)],
            [(body_x1, body_y1), (body_x2, body_y2),(body_x3, body_y3),(body_x4, body_y4)]]
    }
    "aim":{
        "head":[瞄到头部的id],
        "body":[瞄到身体的id]
    }
}

main调用vision方法:
from vision.vision import HumanTracker, get_camera_size

tracker = HumanTracker()
cam_w, cam_h = get_camera_size()
aim = (cam_w // 2, cam_h // 2)

while True:
    data = tracker.get_analysis(aim)
    # 处理 data... 使用 data["box"], data["aim"] 等


通信架构：
  - state.json → 只传递"状态"（模式、目标列表、分数）
  - UDP 广播（端口 8099）→ 实时传递"事件"（开火、命中）
  UI 后台运行 FireListener，收到开火事件立刻触发动画

state.json格式:
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
system_state.mode：当前状态 idle / playing / paused / over
score.value：当前分数
targets：所有检测到的目标列表
serial.status：串口状态
'''

import json
import time
import os
from pathlib import Path
import numpy as np
import pyee
import cv2
from vision.vision import HumanTracker, get_camera_size
from vision.get_camera import get_camera_frame
from fire_notifier import send_fire, close_sender
from A_serial import SerialController
from mouse import MouseListener

# ============ state.json 写入工具 ============
# state.json 只传递"状态"（模式、目标列表、串口状态）
# "事件"（开火）走独立的 UDP 广播，实时通知 UI

STATE_FILE = "state.json"

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


# -------------- 游戏状态管理 ----------------
def start_game():
    print("[状态] 游戏开始")
    # 这里可以初始化一些全局资源，如串口连接、日志等

def on_pause():
    print("[状态] 游戏暂停")

def on_continue():
    print("[状态] 游戏继续")

def on_game_over():
    print("[状态] 游戏结束")

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
    exit(1)


# -------------- 主程序逻辑 ----------------
#=======标量=======
PITCH = 1 #俯仰灵敏度
YAW = 1 #水平灵敏度
#=================

def analysis(tracker, aim_point):
    """分析单帧数据并处理结果。"""
    data = tracker.get_analysis(aim_point)
    if data["num"] > 0:
        print(json.dumps(data, ensure_ascii=False))
    # 这里可以根据 data["box"] 和 data["aim"] 的内容来控制游戏逻辑

def main():
    '''游戏主程序入口：后端计算。'''

    # ===============1.初始化====================

    # 1a. 等待摄像头服务就绪后再开始游戏
    cam_w, cam_h = wait_for_camera()
    aim_point = (cam_w // 2, cam_h // 2)

    # 1b. 启动跟踪器并等待第一帧确认
    print("[等待] 正在启动 YOLO 跟踪器...")
    tracker = HumanTracker()
    
    # 1c. 其他初始化
    # serial = SerialController( baudrate=115200)  # TODO: 根据实际情况修改串口参数
    v_x=0
    v_y=0 #视角角度，

    # 1d. 键鼠监听初始化（后台线程已自动启动，等待 GAME_START）
    ml = MouseListener(sensitivity=1.0, deadzone=2, smooth_window=3, center_lock=True)
    game_running = True  # 控制主循环

    # 订阅键鼠事件
    def on_mouse_pause():
        ml.pause()
        on_pause()
    def on_mouse_continue():
        ml.resume()
        on_continue()
    def on_mouse_over():
        nonlocal game_running
        game_running = False
        ml.stop()
        on_game_over()

    ml.emitter.on("GAME_PAUSE", on_mouse_pause)
    ml.emitter.on("GAME_CONTINUE", on_mouse_continue)
    ml.emitter.on("GAME_OVER", on_mouse_over)

    # 最后. 广播 GAME_START（此时所有模块均已就绪）
    state = pyee.EventEmitter()
    state.on("GAME_START", start_game)
    state.on("GAME_PAUSE", on_pause)
    state.on("GAME_CONTINUE", on_continue)
    state.on("GAME_OVER", on_game_over)
    state.emit("GAME_START")

    # ★ 通知鼠标监听器开始采集
    ml.start()
    # ===============2.主循环====================
    print("[状态] 进入主循环，按 Ctrl+C 退出")

    # 游戏状态
    score_value = 0
    prev_fire_counter = 0
    last_hit_time = 0
    FIRE_COOLDOWN_MS = 100  # 两次开火最短间隔（毫秒），模拟射速

    try:
        while game_running:
            now_ms = time.time() * 1000

            # ---- 从鼠标监听器获取输入 ----
            dx, dy, left_pressed = ml.get_delta()

            # ---- 2a. 视觉分析 ----
            data = tracker.get_analysis(aim_point)

            # ---- 2b. 开火检测（使用鼠标左键） ----
            # 开火事件通过 UDP 实时通知 UI，不经过 state.json
            on_target = data["num"] > 0 and (
                len(data["aim"]["head"]) > 0 or len(data["aim"]["body"]) > 0
            )
            if left_pressed and on_target and (now_ms - last_hit_time) >= FIRE_COOLDOWN_MS:
                last_hit_time = now_ms

                # 判断命中部位
                if len(data["aim"]["head"]) > 0:
                    hit_zone = "head"
                    score_delta = 50
                else:
                    hit_zone = "body"
                    score_delta = 10

                score_value += score_delta
                print(f"[击中] {hit_zone}  +{score_delta}  总分:{score_value}")

                # ★ UDP 实时通知 UI，不阻塞，不经过 JSON
                send_fire(hit_zone=hit_zone, score_delta=score_delta)

            # ---- 2c. 写入 state.json（只含状态，不含事件） ----
            targets_json = []
            for tid_str, box_data in data["box"].items():
                targets_json.append({
                    "id": int(tid_str),
                    "bbox": box_data[0],
                })

            write_state(
                system_state={"mode": "playing", "msg": "normal"},
                score_value=score_value,
                targets=targets_json,
            )

            # ---- 2d. 显示帧（调试用） ----
            frame = get_camera_frame()
            if frame is not None:
                cv2.circle(frame, aim_point, 5, (0, 255, 0), -1)
                cv2.imshow("Frame", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

            # ---- 2e. 视角控制（使用鼠标位移） ----
            v_x += dx * YAW
            v_y += dy * PITCH
            # serial.send_errors(int(v_x), int(v_y))

            time.sleep(0.03)

    except KeyboardInterrupt:
        pass
    finally:
        ml.stop()
        cv2.destroyAllWindows()
        tracker.release()
        close_sender()  # 关闭 UDP 发送端
        print("\n[退出] 程序已终止")

















if __name__ == "__main__":
    main()