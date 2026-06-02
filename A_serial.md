# A — 串口通信模块

> 负责把鼠标位移换算成的角度值，通过串口发给单片机控制舵机云台。

---

## 职责

1. 打开/关闭串口
2. 发送角度指令 `X:角度,Y:角度\n`
3. 接收单片机返回的状态
4. 断线重连 / 超时处理
5. 向 `state.json` 写入串口状态

---

## 串口协议（初版）

```
发送: "X:120,Y:90\n"
      X = 水平角度 (0-180)
      Y = 俯仰角度 (0-180)
      末尾必须加换行符 \n

接收: "OK\n" 或 "ERROR:消息\n"

扩展指令:
  "RESET\n"     → 回中
  "STOP\n"      → 急停
  "STATUS?\n"   → 查询状态
```

---

## 建议接口

```python
import serial
import serial.tools.list_ports
import threading
import time

class SerialController:
    def __init__(self, port=None, baudrate=115200, timeout=0.1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.connected = False
        self.last_status = "disconnected"
        self.last_msg = ""
        self._lock = threading.Lock()

    def open(self):
        """打开串口。如果没指定端口，自动扫描。"""
        if self.port is None:
            self.port = self._auto_detect()
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self.connected = True
            self.last_status = "OK"
            self.last_msg = "connected"
            print(f"[Serial] 已连接: {self.port}")
        except Exception as e:
            self.connected = False
            self.last_status = "ERROR"
            self.last_msg = str(e)
            print(f"[Serial] 连接失败: {e}")

    def send_angles(self, angle_x, angle_y):
        """发送角度指令。
        
        参数：
            angle_x: 水平角度 (0-180)
            angle_y: 俯仰角度 (0-180)
        """
        angle_x = max(0, min(180, int(angle_x)))
        angle_y = max(0, min(180, int(angle_y)))
        cmd = f"X:{angle_x},Y:{angle_y}\n"
        self._write(cmd)

    def send_command(self, cmd):
        """发送自定义指令。"""
        self._write(cmd + "\n")

    def get_status(self):
        """获取串口状态，供写入 state.json。"""
        return {
            "status": "OK" if self.connected else "ERROR",
            "msg": self.last_msg
        }

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False

    # ---- 内部方法 ----

    def _write(self, data):
        with self._lock:
            if not self.ser or not self.ser.is_open:
                self.connected = False
                self.last_status = "ERROR"
                self.last_msg = "port closed"
                return
            try:
                self.ser.write(data.encode())
                # 非阻塞读回显
                if self.ser.in_waiting:
                    resp = self.ser.readline().decode().strip()
                    if resp != "OK":
                        self.last_msg = resp
            except Exception as e:
                self.connected = False
                self.last_status = "ERROR"
                self.last_msg = str(e)

    @staticmethod
    def _auto_detect():
        """自动扫描 Arduino/STM32 串口。"""
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if "Arduino" in p.description or "STM32" in p.description \
               or "USB Serial" in p.description:
                return p.device
        # 没找到已知设备，返回第一个可用串口
        return ports[0].device if ports else None
```

---

## 角度映射

```python
# 从鼠标 dx, dy 到舵机角度
SENSITIVITY = 0.5       # 每 1 像素 dx 转 0.5 度
ANGLE_MIN = 0
ANGLE_MAX = 180

current_angle_x = 90    # 初始居中
current_angle_y = 90

def mouse_to_angle(dx, dy):
    global current_angle_x, current_angle_y
    current_angle_x += dx * SENSITIVITY
    current_angle_y += dy * SENSITIVITY
    current_angle_x = max(ANGLE_MIN, min(ANGLE_MAX, current_angle_x))
    current_angle_y = max(ANGLE_MIN, min(ANGLE_MAX, current_angle_y))
    return current_angle_x, current_angle_y
```

---

## 状态汇报（写入 state.json）

主循环每帧更新 `serial` 字段：

```python
state["serial"] = serial_controller.get_status()
```

B 的 UI 据此显示 `SERIAL: OK` 或 `SERIAL: ERROR`。

---

## 依赖

```powershell
pip install pyserial
```
