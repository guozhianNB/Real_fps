"""
register.py — 人脸注册图形界面

启动前需要先运行摄像头共享服务（由 start.py 自动完成）。
"""

import tkinter as tk
from tkinter import messagebox
import threading
import time
import os
from pathlib import Path

import requests
import cv2
import numpy as np
from PIL import Image, ImageTk

CAMERA_URL = "http://127.0.0.1:8010/snapshot"
INPUT_DIR = Path("vision/input_images")
INPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_frame():
    """从摄像头服务拉取一帧，返回 cv2 BGR 图像或 None。"""
    try:
        resp = requests.get(CAMERA_URL, timeout=2)
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


class RegisterApp:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("人脸注册")
        self.window.geometry("740x620")
        self.window.resizable(False, False)

        self.name_var = tk.StringVar()
        self.counter = 0
        self.running = True

        self._build_ui()
        self._start_preview()

    def _build_ui(self):
        left = tk.Frame(self.window)
        left.pack(side=tk.LEFT, padx=10, pady=10)

        self.preview_label = tk.Label(left, bg="black", width=400, height=360)
        self.preview_label.pack()

        ctrl = tk.Frame(left)
        ctrl.pack(pady=10)

        tk.Label(ctrl, text="姓名：", font=("Arial", 12)).pack(side=tk.LEFT)
        tk.Entry(ctrl, textvariable=self.name_var, font=("Arial", 12),
                 width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl, text="📸 拍照", font=("Arial", 11),
                  command=self._capture).pack(side=tk.LEFT, padx=5)

        right = tk.Frame(self.window)
        right.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

        tk.Label(right, text="已拍照片", font=("Arial", 14, "bold")).pack(pady=5)
        self.photo_list = tk.Listbox(right, width=30, height=18, font=("Arial", 10))
        self.photo_list.pack()

        tk.Button(right, text="🧠 训练模型", font=("Arial", 12, "bold"),
                  bg="#4CAF50", fg="white", command=self._train).pack(pady=10)

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(self.window, textvariable=self.status_var,
                 font=("Arial", 10), fg="gray").pack(side=tk.BOTTOM, pady=5)

    def _start_preview(self):
        """后台线程持续拉取摄像头画面更新预览。"""
        def loop():
            while self.running:
                frame = fetch_frame()
                if frame is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb).resize((480, 360))
                    imgtk = ImageTk.PhotoImage(img)
                    self.preview_label.imgtk = imgtk
                    self.preview_label.config(image=imgtk)
                time.sleep(0.05)
        threading.Thread(target=loop, daemon=True).start()

    def _capture(self):
        """拍照保存。"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请先输入姓名")
            return
        frame = fetch_frame()
        if frame is None:
            messagebox.showerror("错误", "无法获取摄像头画面")
            return
        self.counter += 1
        filename = f"{name}_{self.counter:03d}.png"
        filepath = INPUT_DIR / filename
        cv2.imencode('.png', frame)[1].tofile(str(filepath))
        self.photo_list.insert(tk.END, f"{filename}")
        self.photo_list.see(tk.END)
        self.status_var.set(f"已保存: {filename}")

    def _train(self):
        """启动训练。"""
        ret = messagebox.askyesno("确认", "确定开始训练模型吗？\n训练前请确保已拍完所有照片。")
        if not ret:
            return
        self.status_var.set("正在训练...")
        self.window.update()
        try:
            import vision.face_register
            vision.face_register.main()
            self.status_var.set("训练完成！")
            messagebox.showinfo("完成", "模型训练成功！")
        except Exception as e:
            self.status_var.set(f"训练失败: {e}")
            messagebox.showerror("错误", f"训练失败:\n{e}")

    def run(self):
        self.window.mainloop()
        self.running = False


if __name__ == "__main__":
    app = RegisterApp()
    app.run()
