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
from ui.kill_feed import KillFeed
from fire_notifier import send_reload_done

STATUS_FILE = "state.json"
FIRE_EVENT = pygame.USEREVENT + 1
INSPECT_EVENT = pygame.USEREVENT + 2
RELOAD_EVENT = pygame.USEREVENT + 3
KILL_EVENT = pygame.USEREVENT + 4
CAMERA_TIMEOUT = 1.0


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
        self.gun_inspect_frames = []
        self._gun_breath = 0.0
        self._recoil_timer = 0.0
        self._recoil_duration = 500.0
        self._muzzle_timer = 0.0
        self._inspect_phase = 0
        self._inspect_timer = 0.0
        self._reload_phase = 0
        self._reload_timer = 0.0
        self._reload_gun = "ak"
        self._reload_sound_played = set()
        self.gun_reload_frames = []
        self.kill_feed = KillFeed()
        self.sfx = None

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
        """后台：持续拉取摄像头画面（无 sleep，随摄像头帧率跑）"""
        import requests

        def loop():
            while not self._stop.is_set():
                try:
                    resp = requests.get(
                        "http://127.0.0.1:8010/snapshot",
                        timeout=0.5,
                    )
                    if resp.status_code == 200:
                        arr = np.frombuffer(resp.content, dtype=np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            self.event_q.put(("camera", rgb))
                except Exception:
                    pass  # 失败立刻重试，不 sleep

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _start_fire_listener(self):
        """后台：UDP 监听开火/验视/换弹事件"""
        from fire_notifier import FireListener

        def on_fire(event):
            ev = event.get("event")
            if ev == "inspect":
                pygame.event.post(pygame.event.Event(INSPECT_EVENT, event))
            elif ev == "reload_start":
                pygame.event.post(pygame.event.Event(RELOAD_EVENT, event))
            elif ev == "kill":
                pygame.event.post(pygame.event.Event(KILL_EVENT, event))
            else:
                pygame.event.post(pygame.event.Event(FIRE_EVENT, event))

        self._fire_listener = FireListener(callback=on_fire)
        self._fire_listener.start()

    # --------------------------------------------------
    #  加载闪屏
    # --------------------------------------------------

    @staticmethod
    def _show_loading_screen():
        """显示 "加载中..." 窗口，确保用户不会看到黑屏。"""
        try:
            w, h = 500, 200
            pygame.display.set_mode((w, h))
            pygame.display.set_caption("Real FPS")
            screen = pygame.display.get_surface()
            screen.fill((0, 0, 0))
            try:
                from ui.assets import get_font_large, get_font_small
                font = get_font_large()
                font_sub = get_font_small()
            except Exception:
                font = pygame.font.Font(None, 48)
                font_sub = pygame.font.Font(None, 24)
            text = font.render("加载中...", True, (0, 255, 100))
            sub = font_sub.render("正在初始化，请稍候", True, (100, 255, 150))
            screen.blit(text, (w // 2 - text.get_width() // 2, 60))
            screen.blit(sub, (w // 2 - sub.get_width() // 2, 120))
            pygame.display.flip()
            # 消费启动期间积累的事件，防止窗口假死
            pygame.event.pump()
        except Exception:
            pass

    # --------------------------------------------------
    #  启动 UI（阻塞，直到窗口关闭）
    # --------------------------------------------------

    def start(self):
        pygame.init()

        # --- ① 先获取目标分辨率（在创建任何窗口前） ---
        info = pygame.display.Info()
        self._ww = info.current_w if self.fullscreen else SCREEN_WIDTH
        self._wh = info.current_h if self.fullscreen else SCREEN_HEIGHT

        # --- ② 加载闪屏 ---
        self._show_loading_screen()

        # --- ② 预渲染枪械动画序列（缓动归位） ---
        self.gun_surf = None
        self.gun_frames = []        # recoil 动画帧列表
        self._gun_breath = 0.0
        self._recoil_timer = 0.0
        self._recoil_duration = 500.0
        self._gun_w = int(self._wh * 0.9)   # 自适应：宽 = 90% 屏幕高（留足验视空间）
        self._gun_h = self._gun_w
        try:
            _old = pygame.display.set_mode((self._gun_w, self._gun_h),
                                           pygame.OPENGL | pygame.HIDDEN)
            gv = GunView(self._gun_w, self._gun_h,
                         model_path="ui/models/gun.obj",
                         cam_dist=4, cam_pitch=-8, cam_yaw=5)

            # 预渲染: 后坐力动画帧 + 枪口火焰帧
            NUM_FRAMES = 10
            recoil_dist, recoil_pitch = 3.7, -4
            normal_dist, normal_pitch = 4.0, -8
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

            # 预渲染: 验视动画帧（转横→持住→归位）
            INSPECT_FRAMES = 30  # 每段各 5+20+5
            inspect_dist, inspect_pitch, inspect_yaw = 6.0, -8, 85
            for i in range(INSPECT_FRAMES):
                t = i / (INSPECT_FRAMES - 1)
                if t < 1/6:       # Phase 1: 转入 (0→1/6)
                    pt = t * 6
                    ease = 1 - (1 - pt) ** 2
                elif t < 5/6:     # Phase 2: 持住 (1/6→5/6)
                    ease = 1.0
                else:             # Phase 3: 转回 (5/6→1)
                    pt = (t - 5/6) * 6
                    ease = 1 - pt ** 2  # 从1→0，验视→正常
                d = normal_dist + (inspect_dist - normal_dist) * ease
                p = normal_pitch + (inspect_pitch - normal_pitch) * ease
                y = 5 + (inspect_yaw - 5) * ease
                gv.cam_dist = d
                gv.cam_pitch = p
                gv.cam_yaw = y
                self.gun_inspect_frames.append(gv.render(0))

            # 预渲染: 换弹动画帧（抬起→换弹→拉栓→回正，总 3s）
            reload_pitch, reload_yaw = 20, 22
            bolt_yaw = -10       # 拉栓时 yaw 转到此角度（负=露出枪械右侧）
            RELOAD_FRAMES = 60
            for i in range(RELOAD_FRAMES):
                t = i / (RELOAD_FRAMES - 1)
                if t < 0.25:        # Phase 1: 抬起枪口
                    pt = t / 0.25
                    e = 1 - (1 - pt) ** 2          # ease out
                    p_ease, y_ease = e, e
                elif t < 0.50:      # Phase 2: 换弹（持住抬起位）
                    p_ease, y_ease = 1.0, 1.0
                elif t < 0.75:      # Phase 3: 拉栓（枪向右转，露出右侧）
                    pt = (t - 0.50) / 0.25
                    p_ease = 1.0
                    # yaw: 从 reload_yaw(22°) 摆到 bolt_yaw(-10°) 再回来
                    # 用 2π 的 cos 实现 0→1→0, 保证结束时回到 y_ease=1.0
                    swing = (1 - np.cos(2 * np.pi * pt)) / 2
                    y_ease = 1.0 + ((bolt_yaw - 5) / (reload_yaw - 5) - 1.0) * swing
                else:               # Phase 4: 回正
                    pt = (t - 0.75) / 0.25
                    e = 1 - pt ** 2                # ease in
                    p_ease, y_ease = e, e
                p = normal_pitch + (reload_pitch - normal_pitch) * p_ease
                y = 5 + (reload_yaw - 5) * y_ease
                gv.cam_pitch = p
                gv.cam_yaw = y
                self.gun_reload_frames.append(gv.render(0))

            gv.cleanup()
            pygame.display.quit()
            pygame.display.init()
            print(f"[枪械] 后坐力{NUM_FRAMES}帧 + 验视{INSPECT_FRAMES}帧 + 换弹{RELOAD_FRAMES}帧")
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
        from music.sfx import SFXPlayer
        self.sfx = SFXPlayer()

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
                    self._inspect_phase = 0  # 开火打断验视
                    if self.sfx:
                        self.sfx.play_fire(e.__dict__.get("gun", "ak"))
                    if self.effects:
                        self.effects.add_hit_flash(
                            e.__dict__.get("hit_zone", ""),
                            e.__dict__.get("score_delta", 0))
                elif e.type == INSPECT_EVENT:
                    if self._inspect_phase == 0:
                        self._inspect_phase = 1
                        self._inspect_timer = 0.0
                elif e.type == RELOAD_EVENT:
                    if self._reload_phase == 0:
                        self._reload_phase = 1
                        self._reload_timer = 0.0
                        self._reload_gun = e.__dict__.get("gun", "ak")
                        self._reload_sound_played.clear()
                        if self.sfx:
                            self.sfx.play_reload_part(self._reload_gun, "clipout")
                            self._reload_sound_played.add("clipout")
                elif e.type == KILL_EVENT:
                    self.kill_feed.add_kill(
                        e.__dict__.get("hit_zone", ""),
                        e.__dict__.get("score_delta", 0),
                        e.__dict__.get("target_id", 0),
                        e.__dict__.get("target_name", ""))
                    if self.sfx:
                        self.sfx.play_fire(e.__dict__.get("gun", "ak"))

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
            # 验视状态机
            if self._inspect_phase > 0:
                self._inspect_timer += dt_ms
                if self._inspect_phase == 1 and self._inspect_timer > 500:
                    self._inspect_phase = 2
                    self._inspect_timer = 0
                elif self._inspect_phase == 2 and self._inspect_timer > 2000:
                    self._inspect_phase = 3
                    self._inspect_timer = 0
                elif self._inspect_phase == 3 and self._inspect_timer > 500:
                    self._inspect_phase = 0
                    self._inspect_timer = 0
            # 换弹状态机（抬起0.4s → 换弹0.3s → 拉栓0.8s → 回正1.0s = 2.5s）
            if self._reload_phase > 0:
                self._reload_timer += dt_ms
                # 音效时序：clipout(0s) → 1s → addammo → 0.5s → boltpull
                if self.sfx:
                    if self._reload_phase == 3 and self._reload_timer >= 300 \
                            and "addammo" not in self._reload_sound_played:
                        self.sfx.play_reload_part(self._reload_gun, "addammo")
                        self._reload_sound_played.add("addammo")
                if self._reload_phase == 1 and self._reload_timer > 400:
                    self._reload_phase = 2
                    self._reload_timer = 0
                elif self._reload_phase == 2 and self._reload_timer > 300:
                    self._reload_phase = 3
                    self._reload_timer = 0
                elif self._reload_phase == 3 and self._reload_timer > 800:
                    self._reload_phase = 4
                    self._reload_timer = 0
                    if self.sfx and "boltpull" not in self._reload_sound_played:
                        self.sfx.play_reload_part(self._reload_gun, "boltpull")
                        self._reload_sound_played.add("boltpull")
                elif self._reload_phase == 4 and self._reload_timer > 1000:
                    self._reload_phase = 0
                    self._reload_timer = 0
                    self._reload_sound_played.clear()
                    send_reload_done()
            self.kill_feed.update(dt_ms)
            self._render(dt_ms)
            pygame.display.flip()
            self.clock.tick(FPS_TARGET)

    # --------------------------------------------------
    #  绘制（纯 Pygame 2D，直接绘制到 screen）
    # --------------------------------------------------

    def _render(self, dt_ms=16):
        s = self.screen
        st = self.latest_state

        # 背景 — 用 frombuffer 替代 surfarray，省掉 swapaxes 开销
        if self.latest_frame is not None:
            surf = pygame.image.frombuffer(
                self.latest_frame,
                (self.latest_frame.shape[1], self.latest_frame.shape[0]),
                "RGB",
            )
            s.blit(pygame.transform.scale(surf, (self._ww, self._wh)), (0, 0))
        else:
            s.fill(COLOR_BLACK)

        # 缩放
        cs = st.get("camera_size")
        sx = self._ww / cs[0] if cs and len(cs) == 2 and cs[0] > 0 else 1.0
        sy = self._wh / cs[1] if cs and len(cs) == 2 and cs[1] > 0 else 1.0

        # 目标框（存活=绿框，阵亡=半透明红叉）
        for t in st.get("targets", []):
            b = t.get("bbox")
            if not b or len(b) != 4:
                continue
            x1, y1, x2, y2 = int(b[0]*sx), int(b[1]*sy), int(b[2]*sx), int(b[3]*sy)
            if t.get("dead"):
                # 阵亡：半透明红叉
                w, h = x2 - x1, y2 - y1
                over = pygame.Surface((w, h), pygame.SRCALPHA)
                pygame.draw.line(over, (255, 50, 50, 100), (0, 0), (w, h), 3)
                pygame.draw.line(over, (255, 50, 50, 100), (w, 0), (0, h), 3)
                s.blit(over, (x1, y1))
            elif st.get("show_boxes", True):
                color = COLOR_RED if t.get("locked") else COLOR_GREEN
                pygame.draw.rect(s, color, (x1, y1, x2 - x1, y2 - y1), 2)

        # 准星
        cx, cy = self._ww // 2, self._wh // 2
        c = CROSSHAIR_SIZE
        pygame.draw.circle(s, COLOR_GREEN, (cx, cy), 15, 2)
        pygame.draw.circle(s, COLOR_GREEN, (cx, cy), 2, 0)
        for dx, dy in [(-c-5, 0), (18, 0), (0, -c-5), (0, 18)]:
            pygame.draw.line(s, COLOR_GREEN, (cx+dx, cy+dy),
                             (cx+dx+(20 if dx else 0), cy+dy+(20 if dy else 0)), 2)

        # ---- TARGET LOST 警告（目标丢失后闪烁 3 秒） ----
        tlost = st.get("target_lost_at", 0)
        if tlost and (time.time() - tlost) < 3.0:
            # 闪烁：每 400ms 交替
            if int(time.time() * 2.5) % 2 == 0:
                try:
                    from ui.assets import get_font_medium
                    fm = get_font_medium()
                    warn = fm.render("TARGET LOST", True, (0, 255, 100))
                    wr = warn.get_rect(center=(cx, cy + 50))
                    # 半透明绿色背景条
                    bg_rect = wr.inflate(20, 8)
                    bg = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
                    bg.fill((0, 40, 0, 120))
                    s.blit(bg, bg_rect)
                    s.blit(warn, wr)
                except Exception:
                    pass

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

        # 枪械（右下角贴边，后坐力/验视逐帧动画）
        if self.gun_surf is not None:
            self._gun_breath += dt_ms
            off = np.sin(self._gun_breath * 0.0025) * 3
            gx = self._ww - self._gun_w + 30
            gy = self._wh - self._gun_h + 30 + off

            if self._inspect_phase > 0 and self.gun_inspect_frames:
                # 验视动画
                total = self._inspect_timer
                phase = self._inspect_phase
                idx = 0
                n = len(self.gun_inspect_frames)
                if phase == 1:
                    idx = int((total / 500) * (n // 6))
                elif phase == 2:
                    idx = n // 6 + int((total / 2000) * (n * 4 // 6))
                elif phase == 3:
                    idx = n * 5 // 6 + int((total / 500) * (n // 6))
                idx = max(0, min(n - 1, idx))
                # 验视时窗口向左上偏移，呼吸幅度更大
                inspect_breath = np.sin(self._gun_breath * 0.003) * 5
                s.blit(self.gun_inspect_frames[idx],
                       (gx - 60, gy - 80 + inspect_breath))
            elif self._reload_phase > 0 and self.gun_reload_frames:
                total = self._reload_timer
                phase = self._reload_phase
                n = len(self.gun_reload_frames)  # 60
                q = n // 4  # 15
                durations = [400, 300, 800, 1000]
                dur = durations[phase - 1]
                idx = (phase - 1) * q + int((total / dur) * q)
                idx = max(0, min(n - 1, idx))
                s.blit(self.gun_reload_frames[idx], (gx, gy))
            elif self._recoil_timer > 0 and self.gun_frames:
                t = self._recoil_timer / self._recoil_duration
                idx = int((1 - t) * (len(self.gun_frames) - 1))
                idx = max(0, min(len(self.gun_frames) - 1, idx))
                s.blit(self.gun_frames[idx], (gx, gy))
                if (self._muzzle_timer > 0 and self.gun_muzzle_frames
                        and idx < len(self.gun_muzzle_frames)):
                    m_alpha = int((self._muzzle_timer / 80.0) * 200)
                    self.gun_muzzle_frames[idx].set_alpha(max(0, min(200, m_alpha)))
                    s.blit(self.gun_muzzle_frames[idx], (gx, gy),
                           special_flags=pygame.BLEND_ADD)
                    self.gun_muzzle_frames[idx].set_alpha(255)
            else:
                s.blit(self.gun_surf, (gx, gy))

        # 击杀通知
        if self.kill_feed:
            self.kill_feed.render(s)


# ====== 测试入口 ======
if __name__ == "__main__":
    print("=== Real FPS UI ===")
    print("按 ESC 退出")
    # fullscreen=True 全屏，False 窗口
    UI(fullscreen=True).start()
