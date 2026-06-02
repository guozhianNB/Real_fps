import tkinter as tk
import subprocess
import time
import sys
##启动界面

window = tk.Tk()
window.title('Real_fps')   
window.geometry('400x300')

label = tk.Label(window, text='OMG!是RealFPS!!!', font=('Arial', 16))
label.pack(pady=50)

def start():
    window.destroy()  # 关闭启动界面

    # 用 uvicorn 在后台启动摄像头共享服务
    # 不捕获 stdout/stderr，避免管道阻塞导致卡死
    camera_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "camera_share:app",
         "--host", "127.0.0.1", "--port", "8010"],
        stdout=None, stderr=None
    )
    # 等待 uvicorn 就绪
    time.sleep(2)

    # 启动主程序（阻塞等待结束）
    subprocess.run([sys.executable, "vision.py"])

    # 主程序退出后关闭摄像头服务
    camera_process.terminate()
    camera_process.wait()
    print("摄像头服务已关闭，程序结束。")

b=tk.Button(window, text='点击启动!!', font=('Arial', 14), command=start)
b.pack(pady=20)
window.mainloop()