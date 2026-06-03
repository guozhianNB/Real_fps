# ui/test_draw.py
# 学习如何在窗口上画各种图形

import pygame
import sys

# ====== 初始化 ======
pygame.init()

WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Real FPS - Drawing Test")
clock = pygame.time.Clock()  # 时钟，用于控制帧率

# ====== 颜色常量 ======
# RGB = 红绿蓝，每个值 0~255
COLOR_GREEN = (0, 255, 100)     # 准星绿色
COLOR_RED = (255, 50, 50)       # 锁定红色
COLOR_WHITE = (255, 255, 255)   # 白色文字
COLOR_BLACK = (0, 0, 0)         # 黑色背景
COLOR_HUD_BG = (0, 0, 0, 160)   # 半透明黑（注意：pygame 里需要特殊处理）

# ====== 字体 ======
# 创建字体对象，第一个参数是字体名，None 表示用默认字体
# 第二个参数是字号
font_large = pygame.font.Font(None, 48)   # 大号字体（48 像素）
font_small = pygame.font.Font(None, 28)   # 小号字体（28 像素）

# ====== 游戏循环 ======
running = True
frame_count = 0  # 用来计数帧数

while running:
    # ---- 处理事件 ----
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    # ---- 清空画面 ----
    screen.fill(COLOR_BLACK)

    # ========== 1. 画准星（十字线 + 圆环） ==========
    center_x, center_y = WIDTH // 2, HEIGHT // 2  # 画面中心
    crosshair_size = 20  # 准星大小

    # pygame.draw.circle(画板, 颜色, (圆心x, 圆心y), 半径, 线宽)
    # 线宽=0 是实心圆，>0 是空心圆
    pygame.draw.circle(screen, COLOR_GREEN, (center_x, center_y), 15, 2)  # 外圈空心圆
    pygame.draw.circle(screen, COLOR_GREEN, (center_x, center_y), 2, 0)   # 中心实心点

    # 画十字线：两条线，水平和垂直
    # pygame.draw.line(画板, 颜色, 起点, 终点, 线宽)
    pygame.draw.line(screen, COLOR_GREEN, (center_x - 25, center_y), (center_x - 18, center_y), 2)  # 左横线
    pygame.draw.line(screen, COLOR_GREEN, (center_x + 18, center_y), (center_x + 25, center_y), 2)  # 右横线
    pygame.draw.line(screen, COLOR_GREEN, (center_x, center_y - 25), (center_x, center_y - 18), 2)  # 上竖线
    pygame.draw.line(screen, COLOR_GREEN, (center_x, center_y + 18), (center_x, center_y + 25), 2)  # 下竖线

    # ========== 2. 画目标框 ==========
    # 模拟一个目标框：左上角(600,300) 右下角(680,420)
    target_rect = pygame.Rect(600, 300, 80, 120)  # (x, y, 宽, 高)
    pygame.draw.rect(screen, COLOR_RED, target_rect, 2)  # 2 像素宽的红色框

    # ========== 3. 画 HUD 文字 ==========
    # font.render(文字, 抗锯齿, 颜色) → 返回一个文字"图片"
    # 然后通过 blit 把这个"图片"贴到画板上

    # 左上角：Score
    score_text = font_large.render("SCORE: 100", True, COLOR_WHITE)
    screen.blit(score_text, (20, 20))  # (x, y) 是文字左上角的位置

    # 左上角：Targets
    targets_text = font_small.render("TARGETS: 3", True, COLOR_WHITE)
    screen.blit(targets_text, (20, 70))

    # 左上角：FPS
    fps = int(clock.get_fps())  # clock.get_fps() 返回当前帧率
    fps_text = font_small.render(f"FPS: {fps}", True, COLOR_WHITE)
    screen.blit(fps_text, (20, 100))

    # 底部居中：系统状态
    status_text = font_small.render("MODE: tracking  |  SERIAL: connected", True, COLOR_WHITE)
    text_rect = status_text.get_rect(center=(WIDTH // 2, HEIGHT - 30))
    screen.blit(status_text, text_rect)

    # ---- 刷新 ----
    pygame.display.flip()
    clock.tick(60)  # 控制帧率在 60 FPS
    frame_count += 1

pygame.quit()
sys.exit()