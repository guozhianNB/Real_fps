# ui/core.py — Real FPS 主 UI 模块（终极华丽酷炫版）
import pygame
import json
import os
import threading
import queue
import time
import cv2
import numpy as np
import math

from ui.config import *
from ui.radar import Radar
from ui.hud import HUD
from ui.effects import Effects
from ui.gun_view import GunView
from ui.kill_feed import KillFeed
from ui.assets import get_font, get_font_large, get_font_medium
from fire_notifier import send_reload_done

STATUS_FILE = "state.json"
FIRE_EVENT = pygame.USEREVENT + 1
INSPECT_EVENT = pygame.USEREVENT + 2
RELOAD_EVENT = pygame.USEREVENT + 3
KILL_EVENT = pygame.USEREVENT + 4
CAMERA_TIMEOUT = 1.0


class UI:
    def __init__(self, fullscreen=True):
        self.fullscreen = fullscreen
        self.latest_state = {}
        self.latest_frame = None
        self.event_q = queue.Queue()
        self._stop = threading.Event()
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
        self._vignette_surf = None  # 暗角缓存，懒初始化
        self._crosshair_pulse = 0.0  # 准星开火脉冲 0~1

    def _get_vignette(self, w, h):
        """生成暗角渐变 Surface（径向渐变，中心透明边缘黑）。"""
        if self._vignette_surf is not None and self._vignette_surf.get_size() == (w, h):
            return self._vignette_surf
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        max_dist = math.sqrt(cx**2 + cy**2)
        for y in range(h):
            for x in range(w):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx*dx + dy*dy) / max_dist  # 0~1
                # 中心完全透明，边缘 alpha 逐渐加深
                alpha = int(pow(dist, 2.5) * 180)
                if alpha > 0:
                    surf.set_at((x, y), (0, 0, 0, min(255, alpha)))
        self._vignette_surf = surf
        return surf

    def _start_json_reader(self):
        def loop():
            while not self._stop.is_set():
                try:
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        self.event_q.put(("json", f.read()))
                except FileNotFoundError:
                    pass  # state.json 还没生成
                except Exception as e:
                    print(f"[UI] 读取 state.json 异常: {e}")
                time.sleep(0.05)
        threading.Thread(target=loop, daemon=True).start()

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
                    pass  # 网络/摄像头暂时不可用，下次重试

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _start_fire_listener(self):
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

    @staticmethod
    def _show_loading_screen():
        try:
            w, h = 500, 200
            pygame.display.set_mode((w, h))
            screen = pygame.display.get_surface()
            screen.fill((0,0,0))
            font = get_font(48)
            font_sub = get_font(24)
            text = font.render("加载中...", True, (0,255,100))
            sub = font_sub.render("UI 已升级：赛博朋克华丽版", True, (100,255,150))
            screen.blit(text, (w//2-text.get_width()//2,60))
            screen.blit(sub, (w//2-sub.get_width()//2,120))
            pygame.display.flip()
            pygame.event.pump()
        except Exception as e:
            print(f"[UI] 加载画面显示异常: {e}")

    def start(self):
        pygame.init()
        info = pygame.display.Info()
        self._ww = info.current_w if self.fullscreen else SCREEN_WIDTH
        self._wh = info.current_h if self.fullscreen else SCREEN_HEIGHT
        self._show_loading_screen()

        self.gun_surf = None
        self.gun_frames = []
        self._gun_w = int(self._wh * 0.9)
        self._gun_h = self._gun_w

        try:
            _old = pygame.display.set_mode((self._gun_w, self._gun_h), pygame.OPENGL | pygame.HIDDEN)
            gv = GunView(self._gun_w, self._gun_h, model_path="ui/models/gun.obj", cam_dist=4, cam_pitch=-8, cam_yaw=5)
            NUM_FRAMES = 10
            recoil_dist, recoil_pitch = 3.7, -4
            normal_dist, normal_pitch = 4.0, -8
            self.gun_surf = gv.render(0)
            self.gun_muzzle_frames = []
            for i in range(NUM_FRAMES):
                t = i/(NUM_FRAMES-1)
                ease = 1-(1-t)**2
                d = normal_dist + (recoil_dist-normal_dist)*(1-ease)
                p = normal_pitch + (recoil_pitch-normal_pitch)*(1-ease)
                gv.cam_dist = d
                gv.cam_pitch = p
                self.gun_frames.append(gv.render(0))
                self.gun_muzzle_frames.append(gv.render(0,muzzle=True))

            INSPECT_FRAMES = 30
            inspect_dist, inspect_pitch, inspect_yaw = 6.0,-8,85
            for i in range(INSPECT_FRAMES):
                t = i/(INSPECT_FRAMES-1)
                if t<1/6:
                    pt = t*6
                    ease = 1-(1-pt)**2
                elif t<5/6:
                    ease=1.0
                else:
                    pt=(t-5/6)*6
                    ease=1-pt**2
                d=normal_dist+(inspect_dist-normal_dist)*ease
                p=normal_pitch+(inspect_pitch-normal_pitch)*ease
                y=5+(inspect_yaw-5)*ease
                gv.cam_dist=d
                gv.cam_pitch=p
                gv.cam_yaw=y
                self.gun_inspect_frames.append(gv.render(0))

            reload_pitch,reload_yaw=20,22
            bolt_yaw=-10
            RELOAD_FRAMES=60
            for i in range(RELOAD_FRAMES):
                t=i/(RELOAD_FRAMES-1)
                if t<0.25:
                    pt=t/0.25
                    e=1-(1-pt)**2
                    p_ease,y_ease=e,e
                elif t<0.50:
                    p_ease,y_ease=1.0,1.0
                elif t<0.75:
                    pt=(t-0.50)/0.25
                    p_ease=1.0
                    swing=(1-np.cos(2*np.pi*pt))/2
                    y_ease=1.0+((bolt_yaw-5)/(reload_yaw-5)-1.0)*swing
                else:
                    pt=(t-0.75)/0.25
                    e=1-pt**2
                    p_ease,y_ease=e,e
                p=normal_pitch+(reload_pitch-normal_pitch)*p_ease
                y=5+(reload_yaw-5)*y_ease
                gv.cam_pitch=p
                gv.cam_yaw=y
                self.gun_reload_frames.append(gv.render(0))
            gv.cleanup()
            pygame.display.quit()
            pygame.display.init()
        except Exception as e:
            print(f"[枪械] 预渲染失败: {e}")

        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode((self._ww,self._wh),flags)
        pygame.display.set_caption("Real FPS - 赛博朋克UI")
        self._ww,self._wh = self.screen.get_size()

        from ui.radar import B_SCOPE_W,B_SCOPE_H
        self.radar = Radar(self._ww-B_SCOPE_W-RADAR_MARGIN,RADAR_MARGIN)
        self.hud = HUD()
        self.effects = Effects()
        from music.sfx import SFXPlayer
        self.sfx = SFXPlayer()
        self._bgm_volume = 0.5  # BGM 音量 0~1
        self._sfx_volume = 0.7  # SFX 音量

        self._start_json_reader()
        self._start_camera_reader()
        self._start_fire_listener()
        self._main_loop()

        self._stop.set()
        if hasattr(self,'_fire_listener'):
            self._fire_listener.stop()
        pygame.quit()

    def _main_loop(self):
        running=True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE):
                    running=False
                elif e.type==FIRE_EVENT:
                    self._recoil_timer=self._recoil_duration
                    self._muzzle_timer=80.0
                    self._inspect_phase=0
                    if self.sfx:
                        self.sfx.play_fire(e.__dict__.get("gun","ak"))
                    if self.effects:
                        self.effects.add_hit_flash(e.__dict__.get("hit_zone",""),e.__dict__.get("score_delta",0))
                    self._crosshair_pulse = 1.0  # 准星脉冲触发
                elif e.type==INSPECT_EVENT:
                    if self._inspect_phase==0:
                        self._inspect_phase=1
                        self._inspect_timer=0.0
                elif e.type==RELOAD_EVENT:
                    if self._reload_phase==0:
                        self._reload_phase=1
                        self._reload_timer=0.0
                        self._reload_gun=e.__dict__.get("gun","ak")
                        self._reload_sound_played.clear()
                        if self.sfx:
                            self.sfx.play_reload_part(self._reload_gun,"clipout")
                            self._reload_sound_played.add("clipout")
                elif e.type==KILL_EVENT:
                    hit_zone = e.__dict__.get("hit_zone","")
                    target_id = e.__dict__.get("target_id",0)
                    self.kill_feed.add_kill(hit_zone, e.__dict__.get("score_delta",0), target_id, e.__dict__.get("target_name",""))
                    # 击杀粒子：从 targets 中查该目标的屏幕坐标
                    if self.effects:
                        cs = self.latest_state.get("camera_size")
                        sx = self._ww / cs[0] if cs and len(cs)==2 and cs[0]>0 else 1.0
                        sy = self._wh / cs[1] if cs and len(cs)==2 and cs[1]>0 else 1.0
                        for t in self.latest_state.get("targets", []):
                            if t.get("id") == target_id:
                                b = t.get("bbox")
                                if b and len(b) == 4:
                                    cx = (b[0] + b[2]) // 2
                                    cy = (b[1] + b[3]) // 2
                                    px, py = int(cx * sx), int(cy * sy)
                                    self.effects.add_kill_effect(px, py, hit_zone)
                                break
                    # 击杀音效
                    if self.sfx:
                        sound_path = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "music", "sounds", "head_shot.mp3")
                        self.sfx.play(sound_path)
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_UP:
                        self._bgm_volume = min(1.0, self._bgm_volume + 0.1)
                        print(f"[音量] BGM: {self._bgm_volume:.1f}")
                        from fire_notifier import send_volume
                        send_volume(self._bgm_volume)
                    elif e.key == pygame.K_DOWN:
                        self._bgm_volume = max(0.0, self._bgm_volume - 0.1)
                        print(f"[音量] BGM: {self._bgm_volume:.1f}")
                        from fire_notifier import send_volume
                        send_volume(self._bgm_volume)

            try:
                while True:
                    t,v=self.event_q.get_nowait()
                    if t=="json" and v.strip():
                        try:
                            self.latest_state=json.loads(v)
                        except json.JSONDecodeError:
                            pass  # 半截 JSON 直接跳过
                    elif t=="camera":
                        self.latest_frame=v
            except queue.Empty:
                pass

            now=time.time()
            dt_ms=(now-self.prev_time)*1000
            self.prev_time=now
            if self.effects:
                self.effects.update(dt_ms)
            if self._recoil_timer>0:
                self._recoil_timer=max(0,self._recoil_timer-dt_ms)
            if self._muzzle_timer>0:
                self._muzzle_timer=max(0,self._muzzle_timer-dt_ms)

            if self._inspect_phase>0:
                self._inspect_timer+=dt_ms
                if self._inspect_phase==1 and self._inspect_timer>500:
                    self._inspect_phase=2
                    self._inspect_timer=0
                elif self._inspect_phase==2 and self._inspect_timer>2000:
                    self._inspect_phase=3
                    self._inspect_timer=0
                elif self._inspect_phase==3 and self._inspect_timer>500:
                    self._inspect_phase=0
                    self._inspect_timer=0

            if self._reload_phase>0:
                self._reload_timer+=dt_ms
                if self.sfx:
                    if self._reload_phase==3 and self._reload_timer>=300 and "addammo" not in self._reload_sound_played:
                        self.sfx.play_reload_part(self._reload_gun,"addammo")
                        self._reload_sound_played.add("addammo")
                if self._reload_phase==1 and self._reload_timer>400:
                    self._reload_phase=2
                    self._reload_timer=0
                elif self._reload_phase==2 and self._reload_timer>300:
                    self._reload_phase=3
                    self._reload_timer=0
                elif self._reload_phase==3 and self._reload_timer>800:
                    self._reload_phase=4
                    self._reload_timer=0
                    if self.sfx and "boltpull" not in self._reload_sound_played:
                        self.sfx.play_reload_part(self._reload_gun,"boltpull")
                        self._reload_sound_played.add("boltpull")
                elif self._reload_phase==4 and self._reload_timer>1000:
                    self._reload_phase=0
                    self._reload_timer=0
                    self._reload_sound_played.clear()
                    send_reload_done()

            self.kill_feed.update(dt_ms)
            # 准星脉冲衰减
            self._crosshair_pulse = max(0.0, self._crosshair_pulse - dt_ms / 150.0)
            self._render(dt_ms)
            pygame.display.flip()
            self.clock.tick(FPS_TARGET)

    def _render(self,dt_ms=16):
        s=self.screen
        st=self.latest_state

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
            s.fill((10,10,18))

        cs=st.get("camera_size")
        sx=self._ww/cs[0] if cs and len(cs)==2 and cs[0]>0 else 1.0
        sy=self._wh/cs[1] if cs and len(cs)==2 and cs[1]>0 else 1.0

        for t in st.get("targets",[]):
            b=t.get("bbox")
            if not b or len(b)!=4:
                continue
            x1,y1,x2,y2=int(b[0]*sx),int(b[1]*sy),int(b[2]*sx),int(b[3]*sy)
            w,h=x2-x1,y2-y1
            if t.get("dead"):
                over=pygame.Surface((w,h),pygame.SRCALPHA)
                pygame.draw.line(over,(255,60,80,160),(0,0),(w,h),3)
                pygame.draw.line(over,(255,60,80,160),(w,0),(0,h),3)
                s.blit(over,(x1,y1))
            elif st.get("show_boxes",True):
                locked = t.get("locked", False)
                color = (255,60,80) if locked else (0,255,100)
                corner_len = max(6, min(16, w // 6, h // 6))
                # 四角 bracket
                pts = [
                    (x1, y1, x1+corner_len, y1, x1, y1+corner_len),  # 左上
                    (x2, y1, x2-corner_len, y1, x2, y1+corner_len),  # 右上
                    (x1, y2, x1+corner_len, y2, x1, y2-corner_len),  # 左下
                    (x2, y2, x2-corner_len, y2, x2, y2-corner_len),  # 右下
                ]
                for ax, ay, bx, by, cx, cy in pts:
                    pygame.draw.line(s, color, (ax, ay), (bx, by), 2)
                    pygame.draw.line(s, color, (ax, ay), (cx, cy), 2)
                # 人名标签（框顶上方）
                name = t.get("name", "")
                if name and name != "Unknown":
                    try:
                        name_font = get_font(24)
                        name_surf = name_font.render(name, True, color)
                        # 标签背景
                        nw, nh = name_surf.get_size()
                        label_bg = pygame.Surface((nw+8, nh+4), pygame.SRCALPHA)
                        label_bg.fill((0,0,0,140))
                        s.blit(label_bg, (x1-4, y1-nh-8))
                        s.blit(name_surf, (x1, y1-nh-6))
                    except Exception:
                        pass

        # ==========================
        #  镜头暗角（径向渐变，中心亮边缘暗）
        # ==========================
        try:
            s.blit(self._get_vignette(self._ww, self._wh), (0, 0))
        except Exception:
            pass

        # ==========================
        # 【终极酷炫·赛博朋克准星】
        # ==========================
        cx, cy = self._ww // 2, self._wh // 2
        # pygame.draw.circle(s, (0, 255, 255), (cx, cy), 24, 3)
        # pygame.draw.circle(s, (255, 0, 180), (cx, cy), 28, 1)
        # pygame.draw.circle(s, (255, 40, 80), (cx, cy), 6, 0)
        # pygame.draw.circle(s, (255,255,255), (cx, cy), 2, 0)
        # 准星大小随开火脉冲缩放
        pulse = self._crosshair_pulse
        inner_r = 20 + pulse * 10   # 内圈从 20 扩大到 30
        outer_r = 32 + pulse * 12   # 外圈从 32 扩大到 44
        for angle in [0,90,180,270]:
            x1 = cx + math.cos(math.radians(angle)) * inner_r
            y1 = cy + math.sin(math.radians(angle)) * inner_r
            x2 = cx + math.cos(math.radians(angle)) * outer_r
            y2 = cy + math.sin(math.radians(angle)) * outer_r
            pygame.draw.line(s, (0,255,220), (x1,y1), (x2,y2), 3)
            pygame.draw.line(s, (255,0,160), (x1,y1), (x2,y2), 1)

        tlost=st.get("target_lost_at",0)
        if tlost and (time.time()-tlost)<3.0:
            if int(time.time()*3)%2==0:
                try:
                    fm = get_font_medium()
                    warn=fm.render("TARGET LOST",True,(0,255,120))
                    wr=warn.get_rect(center=(cx,cy+60))
                    bg_rect=wr.inflate(30,12)
                    bg=pygame.Surface(bg_rect.size,pygame.SRCALPHA)
                    bg.fill((0,30,10,160))
                    s.blit(bg,bg_rect)
                    s.blit(warn,wr)
                except Exception as e:
                    print(f"[UI] TARGET LOST 渲染异常: {e}")

        # ==========================
        #  游戏状态覆盖层（暂停/结束）
        # ==========================
        mode = st.get("system_state", {}).get("mode", "")
        if mode == "paused":
            # 半透明遮罩
            overlay = pygame.Surface((self._ww, self._wh), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            s.blit(overlay, (0, 0))
            try:
                font = get_font_large()
                txt = font.render("— PAUSED —", True, (0, 220, 255))
                tr = txt.get_rect(center=(self._ww // 2, self._wh // 2))
                s.blit(txt, tr)
                font2 = get_font(32)
                hint = font2.render("按 P 继续", True, (150, 200, 255))
                hr = hint.get_rect(center=(self._ww // 2, self._wh // 2 + 50))
                s.blit(hint, hr)
            except Exception:
                pass
        elif mode == "over":
            overlay = pygame.Surface((self._ww, self._wh), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            s.blit(overlay, (0, 0))
            try:
                font = get_font_large()
                txt = font.render("GAME OVER", True, (255, 60, 80))
                tr = txt.get_rect(center=(self._ww // 2, self._wh // 2 - 30))
                s.blit(txt, tr)
                score_val = st.get("score", {}).get("value", 0)
                font2 = get_font(48)
                score_txt = font2.render(f"最终得分: {score_val}", True, (255, 200, 0))
                sr = score_txt.get_rect(center=(self._ww // 2, self._wh // 2 + 30))
                s.blit(score_txt, sr)
            except Exception:
                pass

        # ==========================
        #  音量指示（右下角，仅变化时闪烁）
        # ==========================
        try:
            vol_font = get_font(24)
            vol_surf = vol_font.render(
                f"BGM {int(self._bgm_volume * 100)}%", True, (100, 200, 255))
            vr = vol_surf.get_rect(bottomright=(self._ww - 20, self._wh - 20))
            vol_bg = pygame.Surface((vol_surf.get_width() + 12, vol_surf.get_height() + 6), pygame.SRCALPHA)
            vol_bg.fill((0, 0, 0, 100))
            s.blit(vol_bg, (vr.x - 6, vr.y - 3))
            s.blit(vol_surf, vr)
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
            self._gun_breath+=dt_ms
            off=np.sin(self._gun_breath*0.0025)*3
            gx=self._ww-self._gun_w+30
            gy=self._wh-self._gun_h+30+off

            if self._inspect_phase>0 and self.gun_inspect_frames:
                total=self._inspect_timer
                phase=self._inspect_phase
                idx=0
                n=len(self.gun_inspect_frames)
                if phase==1:
                    idx=int((total/500)*(n//6))
                elif phase==2:
                    idx=n//6+int((total/2000)*(n*4//6))
                elif phase==3:
                    idx=n*5//6+int((total/500)*(n//6))
                idx=max(0,min(n-1,idx))
                inspect_breath=np.sin(self._gun_breath*0.003)*5
                s.blit(self.gun_inspect_frames[idx],(gx-60,gy-80+inspect_breath))
            elif self._reload_phase>0 and self.gun_reload_frames:
                total=self._reload_timer
                phase=self._reload_phase
                n=len(self.gun_reload_frames)
                q=n//4
                durations=[400,300,800,1000]
                dur=durations[phase-1]
                idx=(phase-1)*q+int((total/dur)*q)
                idx=max(0,min(n-1,idx))
                s.blit(self.gun_reload_frames[idx],(gx,gy))
            elif self._recoil_timer>0 and self.gun_frames:
                t=self._recoil_timer/self._recoil_duration
                idx=int((1-t)*(len(self.gun_frames)-1))
                idx=max(0,min(len(self.gun_frames)-1,idx))
                s.blit(self.gun_frames[idx],(gx,gy))
                if self._muzzle_timer>0 and self.gun_muzzle_frames and idx<len(self.gun_muzzle_frames):
                    m_alpha=int((self._muzzle_timer/80.0)*200)
                    self.gun_muzzle_frames[idx].set_alpha(max(0,min(200,m_alpha)))
                    s.blit(self.gun_muzzle_frames[idx],(gx,gy),special_flags=pygame.BLEND_ADD)
                    self.gun_muzzle_frames[idx].set_alpha(255)
            else:
                s.blit(self.gun_surf,(gx,gy))

        if self.kill_feed:
            self.kill_feed.render(s)

# ====== 测试入口 ======
if __name__ == "__main__":
    print("=== Real FPS UI ===")
    print("按 ESC 退出")
    UI(fullscreen=True).start()
    