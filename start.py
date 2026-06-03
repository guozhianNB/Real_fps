"""
start.py — Real FPS 启动器
"""

import tkinter as tk
from tkinter import ttk
import subprocess
import time
import sys
import os


def launch():
    """启动所选模式。"""
    mode = _mode.get()
    window.destroy()

    # 1. 启动摄像头服务
    print("[启动] 正在启动摄像头服务...")
    camera_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "vision.camera_share:app",
         "--host", "127.0.0.1", "--port", "8010", "--log-level", "warning"],
        stdout=None, stderr=None,
    )
    time.sleep(2)

    if mode == "register":
        # 人脸注册
        subprocess.run([sys.executable, "register.py"])
    else:
        # 游戏模式
        ui_process = None
        if _launch_ui.get():
            print("[启动] 正在启动 Pygame UI...")
            ui_process = subprocess.Popen(
                [sys.executable, "-m", "ui.core"],
                stdout=None, stderr=None,
            )
        print("[启动] 正在启动后端引擎...")
        subprocess.run([sys.executable, "main.py"])
        if ui_process:
            ui_process.terminate()
            ui_process.wait()

    camera_process.terminate()
    camera_process.wait()
    print("[完成] 程序已退出。")


# ====== Tkinter 启动界面 ======
window = tk.Tk()
window.title("Real FPS Launcher")
window.geometry("440x360")
window.resizable(False, False)

# 全局变量
_mode = tk.StringVar(value="game")
_launch_ui = tk.BooleanVar(value=True)

# 标题
tk.Label(window, text="🎯 Real FPS", font=("Arial", 22, "bold")).pack(pady=(25, 5))
tk.Label(window, text="选择启动模式", font=("Arial", 12), fg="gray").pack(pady=(0, 20))

# 模式选择
frame = tk.Frame(window)
frame.pack()
tk.Radiobutton(frame, text="🎮 游戏模式", variable=_mode, value="game",
               font=("Arial", 12), command=lambda: None).pack(anchor="w", pady=4)
tk.Radiobutton(frame, text="📷 人脸注册", variable=_mode, value="register",
               font=("Arial", 12), command=lambda: None).pack(anchor="w", pady=4)

# 游戏模式选项
ui_check = tk.Checkbutton(window, text="同时启动 Pygame UI",
                          variable=_launch_ui, font=("Arial", 10))
ui_check.pack(pady=(15, 5))

tk.Label(window, text="不启动 UI 时可单独运行 python -m ui.core",
         font=("Arial", 8), fg="gray").pack(pady=(0, 15))

tk.Button(window, text="🚀 启动", font=("Arial", 14, "bold"),
          width=12, height=1, command=launch).pack(pady=5)
tk.Button(window, text="退出", font=("Arial", 10), width=8,
          command=window.destroy).pack(pady=5)

window.mainloop()