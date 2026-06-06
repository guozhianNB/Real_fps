# ui/core.py — Real FPS 主 UI 模块（科幻美化版）
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
            pygame.event.pump()
        except Exception:
            pass

    # --------------------------------------------------
    #  启动 UI（阻塞，直到窗口关闭）
    # --------------------------------------------------

    def start(self):
        pygame.init()

        info = pygame.display.Info()
        self._ww = info.current_w if self.fullscreen else SCREEN_WIDTH
        self._wh = info.current_h if self.fullscreen else SCREEN_HEIGHT

        self._show_loading_screen()

        self.gun_surf = None
        self.gun_frames = []
        self._gun_breath = 0.0
        self._recoil_timer = 0.0
        self._recoil_duration = 500.0
        self._gun_w = int(self._wh * 0.9)
        self._gun_h = self._gun_w
        try:
            _old = pygame.display.set_mode((self._gun_w, self._gun_h),
                                           pygame.OPENGL | pygame.HIDDEN)
            gv = GunView(self._gun_w, self._gun_h,
                         model_path="ui/models/gun.obj",
                         cam_dist=4, cam_pitch=-8, cam_yaw=5)

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

            INSPECT_FRAMES = 30
            inspect_dist, inspect_pitch, inspect_yaw = 6.0, -8, 85
            for i in range(INSPECT_FRAMES):
                t = i / (INSPECT_FRAMES - 1)
                if t < 1/6:
                    pt = t * 6
                    ease = 1 - (1 - pt) ** 2
                elif t < 5/6:
                    ease = 1.0
                else:
                    pt = (t - 5/6) * 6
                    ease = 1 - pt ** 2
                d = normal_dist + (inspect_dist - normal_dist) * ease
                p = normal_pitch + (inspect_pitch - normal_pitch) * ease
                y = 5 + (inspect_yaw - 5) * ease
                gv.cam_dist = d
                gv.cam_pitch = p
                gv.cam_yaw = y
                self.gun_inspect_frames.append(gv.render(0))

            reload_pitch, reload_yaw = 20, 22
            bolt_yaw = -10
            RELOAD_FRAMES = 60
            for i in range(RELOAD_FRAMES):
                t = i / (RELOAD_FRAMES - 1)
                if t < 0.25:
                    pt = t / 0.25
                    e = 1 - (1 - pt) ** 2
                    p_ease, y_ease = e, e
                elif t < 0.50:
                    p_ease, y_ease = 1.0, 1.0
                elif t < 0.75:
                    pt = (t - 0.50) / 0.25
                    p_ease = 1.0
                    swing = (1 - np.cos(2 * np.pi * pt)) / 2
                    y_ease = 1.0 + ((bolt_yaw - 5) / (reload_yaw - 5) - 1.0) * swing
                else:
                    pt = (t - 0.75) / 0.25
                    e = 1 - pt ** 2
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

        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode((self._ww, self._wh), flags)
        pygame.display.set_caption("Real FPS")

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
                    self._inspect_phase = 0
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
            if self._recoil_timer > 0:
                self._recoil_timer = max(0, self._recoil_timer - dt_ms)
            if self._muzzle_timer > 0:
                self._muzzle_timer = max(0, self._muzzle_timer - dt_ms)
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
            if self._reload_phase > 0:
                self._reload_timer += dt_ms
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
    #  绘制（纯视觉美化，逻辑100%不变）
    # --------------------------------------------------

    def _render(self, dt_ms=16):
        s = self.screen
        st = self.latest_state

        if self.latest_frame is not None:
            surf = pygame.surfarray.make_surface(
                self.latest_frame.swapaxes(0, 1))
            s.blit(pygame.transform.scale(surf, (self._ww, self._wh)), (0, 0))
        else:
            s.fill((10, 12, 16))

        cs = st.get("camera_size")
        sx = self._ww / cs[0] if cs and len(cs) == 2 and cs[0] > 0 else 1.0
        sy = self._wh / cs[1] if cs and len(cs) == 2 and cs[1] > 0 else 1.0

        for t in st.get("targets", []):
            b = t.get("bbox")
            if not b or len(b) != 4:
                continue
            x1, y1, x2, y2 = int(b[0]*sx), int(b[1]*sy), int(b[2]*sx), int(b[3]*sy)
            if t.get("dead"):
                w, h = x2 - x1, y2 - y1
                over = pygame.Surface((w, h), pygame.SRCALPHA)
                pygame.draw.line(over, (255, 60, 60, 140), (0, 0), (w, h), 2)
                pygame.draw.line(over, (255, 60, 60, 140), (w, 0), (0, h), 2)
                s.blit(over, (x1, y1))
            elif st.get("show_boxes", True):
                color = (255, 80, 80) if t.get("locked") else (80, 255, 120)
                pygame.draw.rect(s, color, (x1, y1, x2 - x1, y2 - y1), 2)

        # ==========================
        # 【美化】科幻环形动态准星
        # ==========================
        cx, cy = self._ww // 2, self._wh // 2
        pygame.draw.circle(s, (220, 240, 255), (cx, cy), 16, 2)
        pygame.draw.circle(s, (255, 80, 80), (cx, cy), 4, 0)
        pygame.draw.circle(s, (255, 255, 255), (cx, cy), 18, 1)
        for a in [0, 90, 180, 270]:
            r = 22
            l = 10
            import math
            x = cx + math.cos(math.radians(a)) * r
            y = cy + math.sin(math.radians(a)) * r
            x2 = cx + math.cos(math.radians(a)) * (r + l)
            y2 = cy + math.sin(math.radians(a)) * (r + l)
            pygame.draw.line(s, (140, 220, 255), (x, y), (x2, y2), 2)

        tlost = st.get("target_lost_at", 0)
        if tlost and (time.time() - tlost) < 3.0:
            if int(time.time() * 3) % 2 == 0:
                try:
                    from ui.assets import get_font_medium
                    fm = get_font_medium()
                    warn = fm.render("TARGET LOST", True, (0, 255, 120))
                    wr = warn.get_rect(center=(cx, cy + 60))
                    bg_rect = wr.inflate(30, 12)
                    bg = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
                    bg.fill((0, 30, 10, 160))
                    s.blit(bg, bg_rect)
                    s.blit(warn, wr)
                except Exception:
                    pass

        try:
            from ui.assets import get_font_large, get_font_small
            fl, fs = get_font_large(), get_font_small()
            s.blit(fl.render(f"SCORE: {st.get('score',{}).get('value',0)}",
                             True, (220,230,240)), (HUD_MARGIN, HUD_MARGIN))
            s.blit(fs.render(f"FPS: {int(self.clock.get_fps())}",
                             True, (180,190,200)), (HUD_MARGIN, HUD_MARGIN+50))
            txt = f"MODE: {st.get('system_state',{}).get('mode','idle').upper()}  |  " \
                  f"SERIAL: {st.get('serial',{}).get('status','N/A')}"
            s.blit(fs.render(txt, True, (140,220,255)),
                   fs.render(txt, True, (140,220,255)).get_rect(
                       center=(self._ww//2, self._wh-30)))
        except Exception:
            pass

        targets = st.get("targets", [])
        if self.radar:
            self.radar.render(s, targets, 16)
        if self.hud:
            self.hud.render(s, st, int(self.clock.get_fps()), 16)
        if self.effects:
            self.effects.render(s)

        if self.gun_surf is not None:
            self._gun_breath += dt_ms
            off = np.sin(self._gun_breath * 0.0025) * 3
            gx = self._ww - self._gun_w + 30
            gy = self._wh - self._gun_h + 30 + off

            if self._inspect_phase > 0 and self.gun_inspect_frames:
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
                inspect_breath = np.sin(self._gun_breath * 0.003) * 5
                s.blit(self.gun_inspect_frames[idx],
                       (gx - 60, gy - 80 + inspect_breath))
            elif self._reload_phase > 0 and self.gun_reload_frames:
                total = self._reload_timer
                phase = self._reload_phase
                n = len(self.gun_reload_frames)
                q = n // 4
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

        if self.kill_feed:
            self.kill_feed.render(s)


# ====== 测试入口 ======
if __name__ == "__main__":
    print("=== Real FPS UI ===")
    print("按 ESC 退出")
    UI(fullscreen=True).start()