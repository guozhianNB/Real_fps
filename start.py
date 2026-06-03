"""
start.py — Real FPS 一键启动器

启动流程：
  1. Tkinter 启动界面（可选择模式）
  2. 后台启动摄像头共享服务 (uvicorn)
  3. 启动后端引擎 (main.py) + 可选启动 Pygame UI (ui/core.py)
  4. 退出时关闭所有子进程
"""

import tkinter as tk
import subprocess
import time
import sys
import os


def start():
    """启动游戏（关闭启动界面 → 启动服务 → 启动主程序）。"""
    window.destroy()

    # ---- 1. 启动摄像头共享服务 ----
    print("[启动] 正在启动摄像头服务...")
    camera_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "vision.camera_share:app",
         "--host", "127.0.0.1", "--port", "8010"],
        stdout=None, stderr=None,
    )
    time.sleep(2)  # 等待 uvicorn 就绪

    # ---- 2. 可选：启动 Pygame UI ----
    ui_process = None
    if _launch_ui.get():
        print("[启动] 正在启动 Pygame UI...")
        ui_process = subprocess.Popen(
            [sys.executable, "-m", "ui.core"],
            stdout=None, stderr=None,
        )

    # ---- 3. 启动后端引擎 ----
    print("[启动] 正在启动后端引擎...")
    subprocess.run([sys.executable, "main.py"])

    # ---- 4. 清理 ----
    print("[关闭] 正在停止所有服务...")
    if ui_process:
        ui_process.terminate()
        ui_process.wait()
    camera_process.terminate()
    camera_process.wait()
    print("[完成] 程序已退出。")


# ====== Tkinter 启动界面 ======
window = tk.Tk()
window.title("Real FPS Launcher")
window.geometry("420x320")
window.resizable(False, False)

# ====== 全局状态（必须在 Tk() 之后创建） ======
_launch_ui = tk.BooleanVar(value=False)  # 默认 不启动 UI

# 标题
tk.Label(
    window, text="🎯 Real FPS",
    font=("Arial", 22, "bold"),
).pack(pady=(30, 5))

tk.Label(
    window, text="一键启动游戏",
    font=("Arial", 12),
    fg="gray",
).pack(pady=(0, 25))

# 选项：是否启动 UI
ui_check = tk.Checkbutton(
    window,
    text="同时启动 Pygame UI（显示摄像头画面、准星、雷达等）",
    variable=_launch_ui,
    font=("Arial", 10),
)
ui_check.pack(pady=5)

# 提示
tk.Label(
    window,
    text="提示：不启动 UI 时，后端引擎仍会正常运行\n"
         "可单独运行 python -m ui.core 来打开 UI",
    font=("Arial", 9),
    fg="gray",
    justify="left",
).pack(pady=(5, 20))

# 启动按钮
tk.Button(
    window, text="🚀 启动 !!",
    font=("Arial", 14, "bold"),
    width=15, height=1,
    command=start,
).pack(pady=10)

# 退出按钮
tk.Button(
    window, text="退出",
    font=("Arial", 10),
    width=10,
    command=window.destroy,
).pack(pady=5)

window.mainloop()