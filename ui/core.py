# ui/core.py — Real FPS 主 UI 模块（终极华丽酷炫版）
import pygame
import json
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

    def _start_json_reader(self):
        def loop():
            while not self._stop.is_set():
                try:
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        self.event_q.put(("json", f.read()))
                except:
                    pass
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
                    pass  # 失败立刻重试，不 sleep

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
            font = pygame.font.Font(None,48)
            font_sub = pygame.font.Font(None,24)
            text = font.render("加载中...", True, (0,255,100))
            sub = font_sub.render("UI 已升级：赛博朋克华丽版", True, (100,255,150))
            screen.blit(text, (w//2-text.get_width()//2,60))
            screen.blit(sub, (w//2-sub.get_width()//2,120))
            pygame.display.flip()
            pygame.event.pump()
        except:
            pass

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
                    self.kill_feed.add_kill(e.__dict__.get("hit_zone",""),e.__dict__.get("score_delta",0),e.__dict__.get("target_id",0),e.__dict__.get("target_name",""))
                    if self.sfx:
                        self.sfx.play_fire(e.__dict__.get("gun","ak"))

            try:
                while True:
                    t,v=self.event_q.get_nowait()
                    if t=="json" and v.strip():
                        try:
                            self.latest_state=json.loads(v)
                        except:
                            pass
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
            if t.get("dead"):
                w,h=x2-x1,y2-y1
                over=pygame.Surface((w,h),pygame.SRCALPHA)
                pygame.draw.line(over,(255,60,80,160),(0,0),(w,h),3)
                pygame.draw.line(over,(255,60,80,160),(w,0),(0,h),3)
                s.blit(over,(x1,y1))
            elif st.get("show_boxes",True):
                color=(255,60,80) if t.get("locked") else (80,255,120)
                pygame.draw.rect(s,color,(x1,y1,x2-x1,y2-y1),2)

        # ==========================
        # 【终极酷炫·赛博朋克准星】
        # ==========================
        cx, cy = self._ww // 2, self._wh // 2
        pygame.draw.circle(s, (0, 255, 255), (cx, cy), 24, 3)
        pygame.draw.circle(s, (255, 0, 180), (cx, cy), 28, 1)
        pygame.draw.circle(s, (255, 40, 80), (cx, cy), 6, 0)
        pygame.draw.circle(s, (255,255,255), (cx, cy), 2, 0)
        for angle in [0,90,180,270]:
            x1 = cx + math.cos(math.radians(angle)) * 20
            y1 = cy + math.sin(math.radians(angle)) * 20
            x2 = cx + math.cos(math.radians(angle)) * 32
            y2 = cy + math.sin(math.radians(angle)) * 32
            pygame.draw.line(s, (0,255,220), (x1,y1), (x2,y2), 3)
            pygame.draw.line(s, (255,0,160), (x1,y1), (x2,y2), 1)

        tlost=st.get("target_lost_at",0)
        if tlost and (time.time()-tlost)<3.0:
            if int(time.time()*3)%2==0:
                try:
                    from ui.assets import get_font_medium
                    fm=get_font_medium()
                    warn=fm.render("TARGET LOST",True,(0,255,120))
                    wr=warn.get_rect(center=(cx,cy+60))
                    bg_rect=wr.inflate(30,12)
                    bg=pygame.Surface(bg_rect.size,pygame.SRCALPHA)
                    bg.fill((0,30,10,160))
                    s.blit(bg,bg_rect)
                    s.blit(warn,wr)
                except:
                    pass

        targets=st.get("targets",[])
        if self.radar:
            self.radar.render(s,targets,16)
        if self.hud:
            self.hud.render(s,st,int(self.clock.get_fps()),16)
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
    