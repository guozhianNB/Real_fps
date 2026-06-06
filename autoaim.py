"""
autoaim.py — 恒速自动瞄准模块（跳帧+方向锁定）

控制策略：
  - 每 skip_frames+1 帧判断一次方向
  - 方向带锁定计数：连续 N 次判定反向才真正切换
    避免检测噪声导致的频繁方向翻转
  - 判断后将 move_speed 均摊到后续每一帧输出
"""


class AutoAimPID:
    """恒速接近控制器（跳帧+方向锁定）。"""

    def __init__(self, move_speed=0.45, deadband_px=20,
                 deadband_hysteresis=1.6, skip_frames=1,
                 direction_hold=2):
        """
        参数：
            move_speed: 每轮总移动速度 (°)
            deadband_px: 死区像素半径
            deadband_hysteresis: 滞后系数
            skip_frames: 两次方向判断之间的帧间隔
            direction_hold: 方向锁定计数 — 必须连续多少次
                            看到反向才实际切换（防噪声翻转）
        """
        self.move_speed = abs(move_speed)
        self.deadband_px = deadband_px
        self.deadband_hysteresis = deadband_hysteresis
        self.skip_frames = skip_frames
        self.direction_hold = direction_hold

        self._frame_count = 0
        self._in_deadband_x = False
        self._in_deadband_y = False
        self._step_x = 0.0
        self._step_y = 0.0
        self._steps_left = 0

        # 方向锁定计数器
        self._dir_x = 0       # +1 / -1 / 0
        self._dir_y = 0
        self._hold_x = 0      # 剩余锁定帧数
        self._hold_y = 0

    def reset(self):
        """重置状态（切换锁定目标时调用）。"""
        self._frame_count = 0
        self._in_deadband_x = False
        self._in_deadband_y = False
        self._step_x = 0.0
        self._step_y = 0.0
        self._steps_left = 0
        self._dir_x = 0
        self._dir_y = 0
        self._hold_x = 0
        self._hold_y = 0

    def _decide_direction(self, err, in_deadband, direction, hold_counter):
        """判断单轴方向（带死区滞后 + 方向锁定）。"""
        exit_th = self.deadband_px * self.deadband_hysteresis

        # --- 死区判断 ---
        if in_deadband:
            if abs(err) >= exit_th:
                in_deadband = False
                wanted = 1 if err > 0 else -1
            else:
                return 0.0, in_deadband, direction, hold_counter
        else:
            if abs(err) < self.deadband_px:
                in_deadband = True
                return 0.0, in_deadband, direction, hold_counter
            else:
                wanted = 1 if err > 0 else -1

        # --- 方向锁定 ---
        if direction == 0:
            # 首次设定方向 → 立即生效
            direction = wanted
            hold_counter = 0
        elif wanted == direction:
            # 方向未变 → 减少锁定计数
            hold_counter = max(0, hold_counter - 1)
        else:
            # 方向变了 → 增加锁定计数
            hold_counter += 1
            if hold_counter >= self.direction_hold:
                # 锁定计数达标 → 真正切换
                direction = wanted
                hold_counter = 0

        return self.move_speed * direction, in_deadband, direction, hold_counter

    def compute(self, target_cx, target_cy, aim_cx, aim_cy, dt=None,
                current_vx=0.0, current_vy=0.0):
        """计算舵机角度修正量。"""
        self._frame_count += 1

        # ====== 计算帧 ======
        if self._frame_count % (self.skip_frames + 1) == 0:
            err_x = target_cx - aim_cx
            err_y = target_cy - aim_cy

            total_x, self._in_deadband_x, self._dir_x, self._hold_x = \
                self._decide_direction(err_x, self._in_deadband_x,
                                       self._dir_x, self._hold_x)
            total_y, self._in_deadband_y, self._dir_y, self._hold_y = \
                self._decide_direction(err_y, self._in_deadband_y,
                                       self._dir_y, self._hold_y)

            steps = self.skip_frames + 1
            self._step_x = total_x / steps
            self._step_y = total_y / steps
            self._steps_left = steps

        # ====== 每帧输出一小步 ======
        if self._steps_left > 0:
            self._steps_left -= 1
            return self._step_x, self._step_y
        return 0.0, 0.0
