# ui/config.py — 共用配置常量
# 所有 UI 组件共享的颜色、尺寸、时间常量

# ====== 窗口 ======
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FPS_TARGET = 60

# ====== 颜色 ======
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 255, 100)
COLOR_RED = (255, 50, 50)
COLOR_YELLOW = (255, 200, 0)
COLOR_HUD_BG = (0, 0, 0)
HUD_BG_ALPHA = 160

# ====== 准星 ======
CROSSHAIR_SIZE = 20

# ====== 雷达 ======
RADAR_RADIUS = 75
RADAR_MARGIN = 20

# ====== HUD ======
HUD_MARGIN = 20
HUD_LINE_HEIGHT = 35

# ====== 动画 ======
FLASH_DURATION_MS = 300           # 命中闪白持续时间
POPUP_FADEIN_MS = 200             # 得分弹出淡入
POPUP_HOLD_MS = 1000              # 得分弹出停留
POPUP_FADEOUT_MS = 400            # 得分弹出淡出
