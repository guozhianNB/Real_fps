# ui/core.py — Real FPS 主 UI 模块
#
# 功能：
#   1. 打开 Pygame 窗口
#   2. 后台线程读取 state.json + 拉取摄像头画面
#   3. 显示摄像头背景、准星、目标框
#   4. 通过 UDP 实时接收开火事件
#   5. 调用雷达、HUD、动画组件
#   6. 在右下角显示 3D 第一人称持枪视图（预渲染）
#
# 运行：
#   from ui.core import UI
#   UI(fullscreen=False).start()

import pygame
import json
import threading
import queue
import time
import cv2
import numpy as np

from ui.config import *
from ui.radar import Radar
from ui.hud import HUD
from ui.effects import Effects
from ui.gun_view import GunView

STATUS_FILE = "state.json"
FIRE_EVENT = pygame.USEREVENT + 1   # UDP 开火事件的自定义编号
CAMERA_TIMEOUT = 1.0                # 摄像头 HTTP 请求超时


class UI:
    """主 UI 类。调用 start() 后一直运行，直到窗口关闭。"""

    def __init__(self, fullscreen=True):
        self.fullscreen = fullscreen

        # 数据容器（后台线程写，主循环读）
        self.latest_state = {}
        self.latest_frame = None
        self.event_q = queue.Queue()
        self._stop = threading.Event()

        # 动画相关
        self.clock = pygame.time.Clock()
        self.prev_time = time.time()

        self.radar = None
        self.hud = None
        self.effects = None
        self.gun_surf = None
        self.gun_frames = []
        self.gun_muzzle_frames = []
        self._gun_breath = 0.0
        self._recoil_timer = 0.0
        self._recoil_duration = 500.0
        self._muzzle_timer = 0.0

        print("[UI] 初始化完成，准备起飞 🚀")

    # --------------------------------------------------
    #  启动后台线程
    # --------------------------------------------------

    def _start_json_reader(self):
        """后台：每 50ms 读一次 state.json"""
        def loop():
            while not self._stop.is_set():
                try:
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        self.event_q.put(("json", f.read()))
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                time.sleep(0.05)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _start_camera_reader(self):
        """后台：每 33ms 拉取一帧摄像头画面"""
        import requests

        def loop():
            while not self._stop.is_set():
                try:
                    resp = requests.get(
                        "http://127.0.0.1:8010/snapshot",
                        timeout=CAMERA_TIMEOUT,
                    )
                    if resp.status_code == 200:
                        arr = np.frombuffer(resp.content, dtype=np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            self.event_q.put(("camera", rgb))
                except Exception:
                    pass
                time.sleep(0.033)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _start_fire_listener(self):
        """后台：UDP 监听开火事件"""
        from fire_notifier import FireListener

        def on_fire(event):
            pygame.event.post(pygame.event.Event(FIRE_EVENT, event))

        self._fire_listener = FireListener(callback=on_fire)
        self._fire_listener.start()

    # --------------------------------------------------
    #  启动 UI（阻塞，直到窗口关闭）
    # --------------------------------------------------

    def start(self):
        pygame.init()

        # --- ① 先获取目标分辨率 ---
        info = pygame.display.Info()
        self._ww = info.current_w if self.fullscreen else SCREEN_WIDTH
        self._wh = info.current_h if self.fullscreen else SCREEN_HEIGHT

        # --- ② 预渲染枪械动画序列（缓动归位） ---
        self.gun_surf = None
        self.gun_frames = []        # recoil 动画帧列表
        self._gun_breath = 0.0
        self._recoil_timer = 0.0
        self._recoil_duration = 500.0
        self._gun_w = int(self._wh * 0.65)   # 自适应：宽 = 65% 屏幕高
        self._gun_h = self._gun_w
        try:
            _old = pygame.display.set_mode((self._gun_w, self._gun_h),
                                           pygame.OPENGL | pygame.HIDDEN)
            gv = GunView(self._gun_w, self._gun_h,
                         model_path="ui/models/gun.obj",
                         cam_dist=2.5, cam_pitch=-10, cam_yaw=5)

            # 预渲染枪械动画帧 + 对应枪口火焰帧
            NUM_FRAMES = 10
            recoil_dist, recoil_pitch = 2.2, -6
            normal_dist, normal_pitch = 2.5, -10
            self.gun_surf = gv.render(0)
            self.gun_muzzle_frames = []
            for i in range(NUM_FRAMES):
                t = i / (NUM_FRAMES - 1)
                ease = 1 - (1 - t) ** 2
                d = normal_dist + (recoil_dist - normal_dist) * (1 - ease)
                p = normal_pitch + (recoil_pitch - normal_pitch) * (1 - ease)
                gv.cam_dist = d
                gv.cam_pitch = p
                self.gun_frames.append(gv.render(0))
                self.gun_muzzle_frames.append(gv.render(0, muzzle=True))

            gv.cleanup()
            pygame.display.quit()
            pygame.display.init()
            print(f"[枪械] 预渲染 {NUM_FRAMES} 帧动画, 尺寸 {self._gun_w}x{self._gun_h}")
        except Exception as e:
            print(f"[枪械] 预渲染失败: {e}")

        # --- ③ 创建主显示（普通 Pygame） ---
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode((self._ww, self._wh), flags)
        pygame.display.set_caption("Real FPS")

        # 以实际生效的窗口尺寸为准
        self._ww, self._wh = self.screen.get_size()
        print(f"[UI] 实际分辨率: {self._ww}x{self._wh}")

        from ui.radar import B_SCOPE_W, B_SCOPE_H
        self.radar = Radar(self._ww - B_SCOPE_W - RADAR_MARGIN, RADAR_MARGIN)
        self.hud = HUD()
        self.effects = Effects()

        self._start_json_reader()
        self._start_camera_reader()
        self._start_fire_listener()

        print(f"[UI] 进入主循环 ({self._ww}x{self._wh})")
        self._main_loop()

        self._stop.set()
        if hasattr(self, '_fire_listener'):
            self._fire_listener.stop()
        pygame.quit()
        print("[UI] 已退出")

    # --------------------------------------------------
    #  主循环
    # --------------------------------------------------

    def _main_loop(self):
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    running = False
                elif e.type == FIRE_EVENT:
                    self._recoil_timer = self._recoil_duration
                    self._muzzle_timer = 80.0
                    if self.effects:
                        self.effects.add_hit_flash(
                            e.__dict__.get("hit_zone", ""),
                            e.__dict__.get("score_delta", 0))

            try:
                while True:
                    t, v = self.event_q.get_nowait()
                    if t == "json" and v.strip():
                        try:
                            self.latest_state = json.loads(v)
                        except json.JSONDecodeError:
                            pass
                    elif t == "camera":
                        self.latest_frame = v
            except queue.Empty:
                pass

            now = time.time()
            dt_ms = (now - self.prev_time) * 1000
            self.prev_time = now
            if self.effects:
                self.effects.update(dt_ms)
            # 后坐力衰减
            if self._recoil_timer > 0:
                self._recoil_timer = max(0, self._recoil_timer - dt_ms)
            if self._muzzle_timer > 0:
                self._muzzle_timer = max(0, self._muzzle_timer - dt_ms)
            self._render(dt_ms)
            pygame.display.flip()
            self.clock.tick(FPS_TARGET)

    # --------------------------------------------------
    #  绘制（纯 Pygame 2D，直接绘制到 screen）
    # --------------------------------------------------

    def _render(self, dt_ms=16):
        s = self.screen
        st = self.latest_state

        # 背景
        if self.latest_frame is not None:
            surf = pygame.surfarray.make_surface(
                self.latest_frame.swapaxes(0, 1))
            s.blit(pygame.transform.scale(surf, (self._ww, self._wh)), (0, 0))
        else:
            s.fill(COLOR_BLACK)

        # 缩放
        cs = st.get("camera_size")
        sx = self._ww / cs[0] if cs and len(cs) == 2 and cs[0] > 0 else 1.0
        sy = self._wh / cs[1] if cs and len(cs) == 2 and cs[1] > 0 else 1.0

        # 目标框
        for t in st.get("targets", []):
            b = t.get("bbox")
            if b and len(b) == 4:
                r = pygame.Rect(int(b[0]*sx), int(b[1]*sy),
                                int((b[2]-b[0])*sx), int((b[3]-b[1])*sy))
                pygame.draw.rect(s, COLOR_GREEN, r, 2)

        # 准星
        cx, cy = self._ww // 2, self._wh // 2
        c = CROSSHAIR_SIZE
        pygame.draw.circle(s, COLOR_GREEN, (cx, cy), 15, 2)
        pygame.draw.circle(s, COLOR_GREEN, (cx, cy), 2, 0)
        for dx, dy in [(-c-5, 0), (18, 0), (0, -c-5), (0, 18)]:
            pygame.draw.line(s, COLOR_GREEN, (cx+dx, cy+dy),
                             (cx+dx+(20 if dx else 0), cy+dy+(20 if dy else 0)), 2)

        # HUD
        try:
            from ui.assets import get_font_large, get_font_small
            fl, fs = get_font_large(), get_font_small()
            s.blit(fl.render(f"SCORE: {st.get('score',{}).get('value',0)}",
                             True, COLOR_WHITE), (HUD_MARGIN, HUD_MARGIN))
            s.blit(fs.render(f"FPS: {int(self.clock.get_fps())}",
                             True, COLOR_WHITE), (HUD_MARGIN, HUD_MARGIN+50))
            txt = f"MODE: {st.get('system_state',{}).get('mode','idle').upper()}  |  " \
                  f"SERIAL: {st.get('serial',{}).get('status','N/A')}"
            s.blit(fs.render(txt, True, COLOR_WHITE),
                   fs.render(txt, True, COLOR_WHITE).get_rect(
                       center=(self._ww//2, self._wh-30)))
        except Exception:
            pass

        # 组件
        targets = st.get("targets", [])
        if self.radar:
            self.radar.render(s, targets, 16)
        if self.hud:
            self.hud.render(s, st, int(self.clock.get_fps()), 16)
        if self.effects:
            self.effects.render(s)

        # 枪械（右下角贴边，后坐力逐帧动画）
        if self.gun_surf is not None:
            self._gun_breath += dt_ms
            off = np.sin(self._gun_breath * 0.0025) * 3
            gx = self._ww - self._gun_w
            gy = self._wh - self._gun_h + off
            if self._recoil_timer > 0 and self.gun_frames:
                t = self._recoil_timer / self._recoil_duration
                idx = int((1 - t) * (len(self.gun_frames) - 1))
                idx = max(0, min(len(self.gun_frames) - 1, idx))
                s.blit(self.gun_frames[idx], (gx, gy))
                # 枪口火焰帧（3D 渲染，添加混合）
                if (self._muzzle_timer > 0 and self.gun_muzzle_frames
                        and idx < len(self.gun_muzzle_frames)):
                    m_alpha = int((self._muzzle_timer / 80.0) * 200)
                    self.gun_muzzle_frames[idx].set_alpha(max(0, min(200, m_alpha)))
                    s.blit(self.gun_muzzle_frames[idx], (gx, gy),
                           special_flags=pygame.BLEND_ADD)
                    self.gun_muzzle_frames[idx].set_alpha(255)
            else:
                s.blit(self.gun_surf, (gx, gy))


# ====== 测试入口 ======
if __name__ == "__main__":
    print("=== Real FPS UI ===")
    print("按 ESC 退出")
    # fullscreen=True 全屏，False 窗口
    UI(fullscreen=True).start()
