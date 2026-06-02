# A — 单片机舵机控制

> 这份文档是 Arduino/STM32 端的代码，负责解析串口指令并输出 PWM 控制舵机。

---

## 职责

1. 通过串口接收 `X:角度,Y:角度\n` 格式指令
2. 解析出水平和俯仰角度
3. 输出 PWM 信号驱动两个舵机
4. 限幅（0-180°）、平滑插值
5. 响应 `RESET`、`STOP`、`STATUS?` 指令

---

## 接线

```
舵机1（水平）→ 信号线 → Pin 9
舵机2（俯仰）→ 信号线 → Pin 10
舵机电源   → 5V / GND（外部供电，不接 Arduino 5V）
Arduino    → USB 连电脑
```

---

## Arduino 代码（servo_control.ino）

```cpp
#include <Servo.h>

// ====== 引脚定义 ======
const int PIN_SERVO_X = 9;   // 水平舵机
const int PIN_SERVO_Y = 10;  // 俯仰舵机

// ====== 舵机对象 ======
Servo servo_x;
Servo servo_y;

// ====== 角度状态 ======
int target_x = 90;   // 目标角度
int target_y = 90;
int current_x = 90;  // 当前实际角度（用于平滑）
int current_y = 90;

// ====== 平滑参数 ======
const int STEP_SIZE = 2;   // 每帧最大移动步长（越大越快）
const int INTERVAL_MS = 15; // 每 15ms 移动一步（≈ 66Hz）

// ====== 串口缓冲区 ======
String buffer = "";

void setup() {
    Serial.begin(115200);
    
    servo_x.attach(PIN_SERVO_X);
    servo_y.attach(PIN_SERVO_Y);
    
    // 回中
    servo_x.write(90);
    servo_y.write(90);
    
    Serial.println("OK");
}

void loop() {
    // ---- 1. 处理串口指令 ----
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n') {
            process_command(buffer);
            buffer = "";
        } else {
            buffer += c;
        }
    }
    
    // ---- 2. 平滑移动到目标角度 ----
    if (current_x < target_x) {
        current_x = min(current_x + STEP_SIZE, target_x);
    } else if (current_x > target_x) {
        current_x = max(current_x - STEP_SIZE, target_x);
    }
    
    if (current_y < target_y) {
        current_y = min(current_y + STEP_SIZE, target_y);
    } else if (current_y > target_y) {
        current_y = max(current_y - STEP_SIZE, target_y);
    }
    
    servo_x.write(current_x);
    servo_y.write(current_y);
    
    delay(INTERVAL_MS);
}

// ====== 指令解析 ======
void process_command(String cmd) {
    cmd.trim();
    
    // ---- 回中 ----
    if (cmd == "RESET") {
        target_x = 90;
        target_y = 90;
        Serial.println("OK");
        return;
    }
    
    // ---- 急停 ----
    if (cmd == "STOP") {
        // 保持当前位置不变
        Serial.println("OK");
        return;
    }
    
    // ---- 状态查询 ----
    if (cmd == "STATUS?") {
        Serial.print("OK:X:");
        Serial.print(current_x);
        Serial.print(",Y:");
        Serial.println(current_y);
        return;
    }
    
    // ---- 角度指令 "X:120,Y:90" ----
    int x_pos = cmd.indexOf("X:");
    int y_pos = cmd.indexOf("Y:");
    
    if (x_pos >= 0 && y_pos >= 0) {
        int x_val = cmd.substring(x_pos + 2, y_pos - 1).toInt();
        int y_val = cmd.substring(y_pos + 2).toInt();
        
        target_x = constrain(x_val, 0, 180);
        target_y = constrain(y_val, 0, 180);
        
        Serial.println("OK");
    } else {
        Serial.println("ERROR:invalid format");
    }
}
```

---

## 参数调优

| 参数 | 值 | 说明 |
|------|-----|------|
| `STEP_SIZE` | 2 | 每 15ms 移动角度数。越大响应越快，但可能抖动 |
| `INTERVAL_MS` | 15 | 平滑步进间隔。越小越平滑，但舵机可能跟不赢 |
| 波特率 | 115200 | 串口速度，确保和 Python 端一致 |

如果云台抖动：减小 `STEP_SIZE`
如果云台迟钝：增大 `STEP_SIZE`
