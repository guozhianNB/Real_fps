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
'''

import json
import time
from pathlib import Path
import numpy as np
import pyee
import cv2
from vision.vision import HumanTracker, get_camera_size
from vision.get_camera import get_camera_frame


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

    # 1c. 广播 GAME_START（此时摄像头 & 跟踪器均已就绪）
    state = pyee.EventEmitter()
    state.on("GAME_START", start_game)
    state.on("GAME_PAUSE", on_pause)
    state.on("GAME_CONTINUE", on_continue)
    state.on("GAME_OVER", on_game_over)
    state.emit("GAME_START")

    # ===============2.主循环====================
    print("[状态] 进入主循环，按 Ctrl+C 退出")
    try:
        while True:
            data = tracker.get_analysis(aim_point)
            if True:  # onfire() #D队员的开火检测，模拟正在开火                      TODO: 替换为实际的开火检测逻辑
                #检测击杀
                if data["num"] > 0:
                    if data["aim"]["head"] or data["aim"]["body"]:
                        print("[击中] 检测到击中目标！")
                        for tid in data["aim"]["head"]:
                            print(f"  - 击中头部: id={tid}")
                        for tid in data["aim"]["body"]:
                            print(f"  - 击中身体: id={tid}")
                    else:
                        print("[未击中] 没有检测到击中目标。")
                else:
                    print("[未击中] 没有检测到任何目标。")
            
            # 显示帧,调试用，正式发布时可以注释掉
            frame = get_camera_frame()
            if frame is not None:
                cv2.circle(frame, aim_point, 5, (0, 255, 0), -1)  # 准心绿点
                cv2.imshow("Frame", frame)
            # waitKey 必须调用，否则 OpenCV 窗口不会刷新
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
            time.sleep(0.03)  # 控制分析频率
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        tracker.release()
        print("\n[退出] 程序已终止")

















if __name__ == "__main__":
    main()