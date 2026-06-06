import pygame

# 定义颜色
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)

# 补全 HUD 类（让界面能显示）
class HUD:
    def __init__(self):
        self.font = pygame.font.SysFont(None, 40)

    def render(self, screen, state, fps, dt):
        # 显示分数
        score = state["score"]["value"]
        score_text = self.font.render(f"分数: {score}", True, COLOR_WHITE)
        screen.blit(score_text, (20, 20))

        # 显示 FPS
        fps_text = self.font.render(f"FPS: {fps}", True, COLOR_WHITE)
        screen.blit(fps_text, (20, 70))

        # 显示状态
        mode = state["system_state"]["mode"]
        mode_text = self.font.render(f"模式: {mode}", True, COLOR_WHITE)
        screen.blit(mode_text, (20, 120))

        # 显示串口状态
        serial = state["serial"]["status"]
        serial_text = self.font.render(f"串口: {serial}", True, COLOR_WHITE)
        screen.blit(serial_text, (20, 170))

# ==================== 你原来的主程序 ====================
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 400))
    pygame.display.set_caption("HUD 测试")
    clock = pygame.time.Clock()

    hud = HUD()
    mock_state = {
        "score": {"value": 100},
        "targets": [{"id": 1}],
        "system_state": {"mode": "playing"},
        "serial": {"status": "OK"},
    }

    timer = 0
    running = True
    while running:
        dt = clock.tick(60)
        timer += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False

        # 每 3 秒自动加 50 分
        if timer > 3000:
            timer = 0
            mock_state["score"]["value"] += 50

        screen.fill(COLOR_BLACK)
        hud.render(screen, mock_state, int(clock.get_fps()), dt)
        pygame.display.flip()

    pygame.quit()