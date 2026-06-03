"""
A_serial.py — 串口通信模块

⚠️ 文件名不能叫 serial.py，会和 pyserial 库冲突！
   import serial 会找到本地文件而非 pyserial 库。
   解决方案：命名为 A_serial.py，用 from A_serial import SerialController。

职责：
  1. 打开/关闭串口
  2. 发送云台舵机目标角度 "yaw,pitch\\n" 给单片机
  3. 单片机根据目标角度直接控制舵机
  4. 断线重连 / 超时处理
  5. 向 state.json 写入串口状态

串口协议：
  发送: "yaw,pitch\\n"
        yaw   = 水平角度 (-90 ~ 90)，正=右，负=左
        pitch = 俯仰角度 (-90 ~ 90)，正=下，负=上
        末尾必须加换行符 \\n

  例如云台控制：
    - 向右转 30°    → 发送 "30,0\\n"
    - 向上转 45°    → 发送 "0,-45\\n"
    - 回正          → 发送 "0,0\\n"

依赖：
  pip install pyserial
"""

import serial
import serial.tools.list_ports
import threading
import time


class SerialController:
    """串口控制器，发送目标角度给单片机舵机云台。"""

    def __init__(self, port=None, baudrate=115200, timeout=0.05):
        """
        初始化串口控制器，自动扫描并打开串口。

        参数：
            port: 串口名（如 COM3），None 时自动扫描
            baudrate: 波特率
            timeout: 读取超时（秒）

        抛出：
            RuntimeError: 没有找到可用串口，或打开失败
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.connected = False
        self.last_status = "disconnected"
        self.last_msg = ""
        self._lock = threading.Lock()
        self._last_send_time = 0
        self._min_interval = 0.01  # 最小发送间隔 10ms

        # ---- 初始化时自动寻找并打开串口 ----
        if self.port is None:
            self.port = self._auto_detect()
            if self.port is None:
                raise RuntimeError(
                    "[Serial] 未找到可用串口！请检查设备连接。\n"
                    "  可手动指定端口：SerialController(port='COM3')"
                )

        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
            self.connected = True
            self.last_status = "OK"
            self.last_msg = "connected"
            print(f"[Serial] 已连接: {self.port} @ {baudrate}bps")
        except Exception as e:
            raise RuntimeError(
                f"[Serial] 打开串口 {self.port} 失败: {e}"
            )

    # ---- 公共接口 ----

    def open(self):
        """（兼容旧代码）重新打开串口。"""
        if self.ser and self.ser.is_open:
            self.close()
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
            self.connected = True
            self.last_status = "OK"
            self.last_msg = "connected"
            print(f"[Serial] 已重连: {self.port}")
        except Exception as e:
            self.connected = False
            self.last_status = "ERROR"
            self.last_msg = str(e)
            print(f"[Serial] 重连失败: {e}")

    def send_angles(self, yaw, pitch):
        """发送舵机目标角度给单片机。

        参数：
            yaw:   水平角度 (-90 ~ 90)，正=右，负=左
            pitch: 俯仰角度 (-90 ~ 90)，正=下，负=上
        """
        # 限幅到 ±90°
        yaw = max(-90, min(90, int(round(yaw))))
        pitch = max(-90, min(90, int(round(pitch))))
        cmd = f"{yaw},{pitch}\n"
        self._write(cmd)

    def send_raw(self, raw_string):
        """发送原始字符串（自动追加换行）。"""
        self._write(raw_string + "\n")

    def get_status(self):
        """获取串口状态，供写入 state.json。"""
        return {
            "status": "OK" if self.connected else "ERROR",
            "msg": self.last_msg,
        }

    def close(self):
        """关闭串口。"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False
        print("[Serial] 已断开")

    def reconnect(self):
        """尝试重新连接。"""
        self.close()
        time.sleep(0.5)
        self.open()

    # ---- 内部方法 ----

    def _write(self, data):
        with self._lock:
            if not self.ser or not self.ser.is_open:
                self.connected = False
                self.last_status = "ERROR"
                self.last_msg = "port closed"
                return

            # 限频：防止发送太快导致缓冲区溢出
            now = time.time()
            if now - self._last_send_time < self._min_interval:
                return
            self._last_send_time = now

            try:
                self.ser.write(data.encode())
                # 非阻塞读取响应
                if self.ser.in_waiting:
                    resp = self.ser.readline().decode().strip()
                    if resp and resp != "OK":
                        self.last_msg = resp
            except Exception as e:
                self.connected = False
                self.last_status = "ERROR"
                self.last_msg = str(e)
                print(f"[Serial] 写入失败: {e}")

    @staticmethod
    def _auto_detect():
        """自动扫描 STM32 / Arduino / USB 串口设备。"""
        ports = serial.tools.list_ports.comports()
        for p in ports:
            desc = p.description.lower()
            if "stm32" in desc or "arduino" in desc or "usb serial" in desc:
                return p.device
        # 没找到已知设备，返回第一个可用串口
        return ports[0].device if ports else None


# ============================================================
#  快捷使用示例（配合视觉/鼠标模块）
# ============================================================
def example_usage():
    """
    典型使用流程：
        1. 从视觉模块计算目标角度 yaw, pitch
        2. 通过串口把目标角度发送给单片机
        3. 单片机直接控制舵机转到目标角度

    注意：SerialController() 初始化时已自动打开串口，无需手动调用 open()。
    """
    try:
        ser = SerialController()    # ← 自动扫描并打开串口
    except RuntimeError as e:
        print(e)
        return

    # 模拟目标角度
    yaw, pitch = 30, -45
    ser.send_angles(yaw, pitch)
    print(f"发送角度: yaw={yaw}, pitch={pitch}")
    ser.close()


if __name__ == "__main__":
    example_usage()
