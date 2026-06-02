import tkinter as tk
import subprocess
##启动界面

window = tk.Tk()
window.title('Real_fps')   
window.geometry('400x300')

label = tk.Label(window, text='OMG!是RealFPS!!!', font=('Arial', 16))
label.pack(pady=50)

def start():
    window.destroy()  # 关闭启动界面
    subprocess.run(["python","main.py"])

b=tk.Button(window, text='点击启动!!', font=('Arial', 14), command=start)
b.pack(pady=20)
window.mainloop()