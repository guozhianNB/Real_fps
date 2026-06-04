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

    print("[启动] 正在启动摄像头服务...")
    camera_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "vision.camera_share:app",
         "--host", "127.0.0.1", "--port", "8010", "--log-level", "warning"],
        stdout=None, stderr=None,
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
window.geometry("440x420")
window.resizable(False, False)

_mode = tk.StringVar(value="game")
_launch_ui = tk.BooleanVar(value=True)
_game_opt = tk.StringVar(value="A")

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
window.mainloop()