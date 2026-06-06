"""
start.py — Real FPS 启动器
"""

import tkinter as tk
from tkinter import ttk
import subprocess
import time
import sys
import os

# 添加项目根目录到 sys.path（兼容直接运行）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def scan_cameras():
    """扫描可用摄像头，更新下拉菜单。"""
    from vision.get_camera import list_available_cameras

    _camera_combo["values"] = []
    _camera_combo.set("扫描中...")
    window.update()

    cameras = list_available_cameras(max_index=10)
    if cameras:
        # 显示为 "索引 - 名称"
        labels = [f"{idx} - {name}" for idx, name in cameras]
        _camera_combo["values"] = labels
        # 优先选之前选中的摄像头
        prev = _camera_var.get()
        if prev in labels:
            _camera_combo.set(prev)
        else:
            _camera_combo.set(labels[0])
            _camera_var.set(labels[0])
        _scan_status.config(text=f"找到 {len(cameras)} 个摄像头", fg="green")
    else:
        _camera_combo.set("未检测到摄像头")
        _scan_status.config(text="未检测到摄像头", fg="red")


def launch():
    """启动所选模式。"""
    mode = _mode.get()
    selected_camera = _camera_var.get()

    # 解析摄像头索引
    camera_id = 0
    if selected_camera and selected_camera not in ("扫描中...", "未检测到摄像头"):
        try:
            camera_id = int(selected_camera.split(" - ")[0])
        except (ValueError, IndexError):
            pass

    window.destroy()

    print(f"[启动] 正在启动摄像头服务 (Camera #{camera_id})...")
    env = os.environ.copy()
    env["CAMERA_ID"] = str(camera_id)
    env["CAMERA_EXPOSURE"] = _exposure_var.get()
    camera_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "vision.camera_share:app",
         "--host", "127.0.0.1", "--port", "8010", "--log-level", "warning"],
        stdout=None, stderr=None, env=env,
    )
    time.sleep(2)

    if mode == "register":
        subprocess.run([sys.executable, "register.py"])
    else:
        ui_process = None
        if _launch_ui.get():
            print("[启动] 正在启动 Pygame UI...")
            ui_process = subprocess.Popen(
                [sys.executable, "-m", "ui.core"],
                stdout=None, stderr=None,
            )
        game_opt = _game_opt.get()
        print(f"[启动] 正在启动后端引擎 (方案 {game_opt})...")
        subprocess.run([sys.executable, "main.py", game_opt])
        if ui_process:
            ui_process.terminate()
            ui_process.wait()

    camera_process.terminate()
    camera_process.wait()
    print("[完成] 程序已退出。")


def _on_mode_change():
    """切换模式时显示/隐藏游戏选项。"""
    if _mode.get() == "game":
        _game_frame.pack(pady=(10, 5))
        _ui_check_frame.pack(pady=(5, 0))
        _ui_hint.pack(pady=(0, 10))
    else:
        _game_frame.pack_forget()
        _ui_check_frame.pack_forget()
        _ui_hint.pack_forget()


# ====== Tkinter 启动界面 ======
window = tk.Tk()
window.title("Real FPS Launcher")
window.geometry("500x580")
window.resizable(False, False)

_mode = tk.StringVar(value="game")
_launch_ui = tk.BooleanVar(value=True)
_game_opt = tk.StringVar(value="A")
_camera_var = tk.StringVar()

# 标题
tk.Label(window, text="🎯 Real FPS", font=("Arial", 22, "bold")).pack(pady=(25, 5))
tk.Label(window, text="选择启动模式", font=("Arial", 12), fg="gray").pack(pady=(0, 15))

# 模式选择
mode_frame = tk.Frame(window)
mode_frame.pack()
tk.Radiobutton(mode_frame, text="🎮 游戏模式", variable=_mode, value="game",
               font=("Arial", 12), command=_on_mode_change).pack(anchor="w", pady=3)
tk.Radiobutton(mode_frame, text="📷 人脸注册", variable=_mode, value="register",
               font=("Arial", 12), command=_on_mode_change).pack(anchor="w", pady=3)

# ====== 摄像头选择 ======
cam_frame = tk.Frame(window)
cam_frame.pack(pady=(15, 5))
tk.Label(cam_frame, text="📹 摄像头：", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
_camera_combo = ttk.Combobox(cam_frame, textvariable=_camera_var,
                             state="readonly", width=30, font=("Arial", 10))
_camera_combo.pack(side=tk.LEFT, padx=5)
_camera_combo.set("正在扫描...")

tk.Button(cam_frame, text="🔄 刷新", font=("Arial", 9),
          command=scan_cameras).pack(side=tk.LEFT, padx=2)

_scan_status = tk.Label(window, text="", font=("Arial", 9), fg="gray")
_scan_status.pack()

# ====== 曝光/快门设置 ======
exp_frame = tk.Frame(window)
exp_frame.pack(pady=(5, 5))
tk.Label(exp_frame, text="🔆 快门速度：", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
_exposure_var = tk.StringVar(value="-6 (1/64s)")
_exposure_combo = ttk.Combobox(exp_frame, textvariable=_exposure_var,
                               state="readonly", width=18, font=("Arial", 10))
_exposure_combo["values"] = [
    "-4 (1/16s)  较亮·易糊",
    "-5 (1/32s)  ",
    "-6 (1/64s)  推荐",
    "-7 (1/128s) ",
    "-8 (1/256s) 最清晰·需强光",
]
_exposure_combo.pack(side=tk.LEFT, padx=5)
_exp_hint = tk.Label(window, text="数值越小越亮但运动模糊越重，越大越清晰但需更亮光线",
                     font=("Arial", 8), fg="gray")
_exp_hint.pack(pady=(0, 5))

# 游戏选项容器（默认显示） 
_game_frame = tk.Frame(window)
_game_frame.pack(pady=(10, 5))
tk.Label(_game_frame, text="游戏方案：", font=("Arial", 10, "bold")).pack(anchor="w")
opt_frame = tk.Frame(_game_frame)
opt_frame.pack()
for opt_text, opt_val in [("方案 A", "A"), ("方案 B", "B"), ("方案 C", "C")]:
    tk.Radiobutton(opt_frame, text=opt_text, variable=_game_opt, value=opt_val,
                   font=("Arial", 10)).pack(side=tk.LEFT, padx=8)

_ui_check_frame = tk.Frame(window)
_ui_check_frame.pack(pady=(5, 0))
ui_check = tk.Checkbutton(_ui_check_frame, text="同时启动 Pygame UI",
                           variable=_launch_ui, font=("Arial", 10))
ui_check.pack()

_ui_hint = tk.Label(window, text="不启动 UI 时可单独运行 python -m ui.core",
                    font=("Arial", 8), fg="gray")
_ui_hint.pack(pady=(0, 10))

tk.Button(window, text="🚀 启动", font=("Arial", 14, "bold"),
          width=12, height=1, command=launch).pack(pady=5)
tk.Button(window, text="退出", font=("Arial", 10), width=8,
          command=window.destroy).pack(pady=5)

_on_mode_change()

# 窗口显示后自动扫描摄像头
window.after(200, scan_cameras)
window.mainloop()