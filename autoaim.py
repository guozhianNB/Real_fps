"""
autoaim.py — PID 自动瞄准模块

当进入锁定模式（locked_id != None）后，取代鼠标控制舵机云台，
通过 PID 算法将准心对准锁定目标的中心位置。
"""

import time


class AutoAimPID:
    """PID 自动瞄准控制器。

    将目标在画面上的像素偏差转换为云台角度修正量 (delta_yaw, delta_pitch)，
    直接累加到 main.py 的 v_x / v_y 上。
    """

    def __init__(self, kp=0.18, ki=0.008, kd=0.06,
                 max_output=3.0, max_integral=8.0):
        """
        参数：
            kp: 比例增益
            ki: 积分增益（消除稳态误差）
            kd: 微分增益（抑制震荡）
            max_output:  单次最大角度修正 (°)
            max_integral: 积分限幅
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_output = max_output
        self.max_integral = max_integral

        self._prev_err_x = 0.0
        self._prev_err_y = 0.0
        self._integral_x = 0.0
        self._integral_y = 0.0
        self._last_time = None

    def reset(self):
        """重置 PID 状态（切换锁定目标时调用，防止积分突变）。"""
        self._prev_err_x = 0.0
        self._prev_err_y = 0.0
        self._integral_x = 0.0
        self._integral_y = 0.0
        self._last_time = None

    def compute(self, target_cx, target_cy, aim_cx, aim_cy, dt=None):
        """计算舵机角度修正量。

        参数：
            target_cx, target_cy: 目标中心在画面的像素坐标
            aim_cx, aim_cy:       准心（画面中心）像素坐标
            dt:                   距上次调用的时间（秒），None 自动计算

        返回：
            (delta_yaw, delta_pitch)  角度修正值，可直接加到 v_x / v_y
        """
        now = time.time()
        if dt is None:
            if self._last_time is not None:
                dt = now - self._last_time
            else:
                dt = 0.03  # 默认 30ms
            dt = max(dt, 0.005)  # 最小 5ms
        self._last_time = now

        # 误差：目标在画面上的像素偏移
        err_x = target_cx - aim_cx   # + → 目标偏右，yaw 需增大
        err_y = target_cy - aim_cy   # + → 目标偏下，pitch 需增大

        # --- 比例项 ---
        p_x = self.kp * err_x
        p_y = self.kp * err_y

        # --- 积分项（带限幅）---
        self._integral_x += err_x * dt * self.ki
        self._integral_y += err_y * dt * self.ki
        self._integral_x = max(-self.max_integral, min(self.max_integral, self._integral_x))
        self._integral_y = max(-self.max_integral, min(self.max_integral, self._integral_y))
        i_x = self._integral_x
        i_y = self._integral_y

        # --- 微分项 ---
        d_x = self.kd * (err_x - self._prev_err_x) / dt if dt > 0 else 0
        d_y = self.kd * (err_y - self._prev_err_y) / dt if dt > 0 else 0

        self._prev_err_x = err_x
        self._prev_err_y = err_y

        out_x = p_x + i_x + d_x
        out_y = p_y + i_y + d_y

        # 输出限幅
        out_x = max(-self.max_output, min(self.max_output, out_x))
        out_y = max(-self.max_output, min(self.max_output, out_y))

        return out_x, out_y
