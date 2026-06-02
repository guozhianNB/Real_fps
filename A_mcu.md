# A — 单片机舵机控制（PID 版）

> STM32F103C8T6 端代码，通过串口接收误差值，**PID 控制器**实时计算舵机角度并输出 PWM。

---

## 职责

1. 通过串口接收 `error_x,error_y\n` 格式误差值
2. **PID 控制器**根据误差计算舵机调整量
3. 输出 PWM 信号驱动两个舵机
4. 限幅（0-180°）、积分抗饱和
5. 逐字节串口接收，不丢帧

---

## 接线（STM32F103C8T6）

```
水平舵机 → PA8  (TIM1_CH1)
俯仰舵机 → PA0  (TIM2_CH1)
舵机电源 → 5V / GND（外部供电）
串口     → PA2(TX) PA3(RX) → USB 转串口模块
```

---

## 核心代码结构（main.c）

### PID 控制器

```c
// PID 结构体
typedef struct {
    float Kp, Ki, Kd;       // PID 参数
    float integral;         // 积分项
    float prev_error;       // 上一次误差（微分用）
    float output_limit;     // 输出限幅
    float integral_limit;   // 积分限幅（抗饱和）
} PID_t;

// 初始化
void PID_Init(PID_t *pid, float Kp, float Ki, float Kd, float limit);

// 计算：输入误差，输出角度调整量
float PID_Compute(PID_t *pid, float error, float dt);
```

### 串口协议解析

```
格式: "error_x,error_y\n"
      error_x — 水平误差（可正可负）
      error_y — 俯仰误差（可正可负）
      用 sscanf(line, "%d,%d", &e1, &e2) 解析
```

### 舵机 PWM

```
TIM 时钟: 72MHz / 720 prescaler = 100kHz
PWM 周期: 2000 ticks = 20ms = 50Hz
角度→脉宽: pulse = 50 + angle × 200/180
  0°   → 500μs  → 50  ticks
  90°  → 1500μs → 150 ticks
  180° → 2500μs → 250 ticks
```

### 主循环流程

```
每个 10ms 周期:
  1. 计算 dt = 距上次运算的时间差
  2. 如果收到新误差数据:
     a. 关中断读取 error_x, error_y
     b. PID_Compute(&pid_x, error_x, dt)
     c. PID_Compute(&pid_y, error_y, dt)
     d. 累积更新 servo_angle_x/y
     e. 限幅到 0-180°
     f. 设置 PWM 脉宽
  3. HAL_Delay(10)
```

---

## PID 参数调优

| 参数 | 默认值 | 作用 | 调大 | 调小 |
|------|--------|------|------|------|
| `Kp` | 1.0 | 比例 — 立即响应误差 | 反应快，可能超调 | 反应慢，更稳定 |
| `Ki` | 0.1 | 积分 — 消除稳态误差 | 静差消除快，易饱和 | 可能有残留静差 |
| `Kd` | 0.05 | 微分 — 抑制震荡 | 过冲抑制好，怕噪声 | 可能震荡 |
| `output_limit` | 5.0 | 每周期最大角度调整量 | 跟踪快，可能抖动 | 平滑但跟踪慢 |

### 调试建议

- **云台抖动/震荡** → 减小 `Kp` 或 `Kd`，增大 `output_limit`
- **跟踪太慢/滞后** → 增大 `Kp`，增大 `output_limit`
- **无法对准中心（有静差）** → 增大 `Ki`
- **积分饱和（回中过头）** → 减小 `Ki`，检查 `integral_limit`

---

## 文件位置

```
yuntai/
├── Core/
│   ├── Inc/main.h         ← 头文件
│   └── Src/main.c         ← PID 控制 + 串口接收 ← 主要修改文件
│   └── Src/stm32f1xx_hal_msp.c  ← GPIO/TIM/UART MSP 初始化
├── Drivers/                ← HAL 库
└── yuntai.ioc              ← CubeMX 工程
```
