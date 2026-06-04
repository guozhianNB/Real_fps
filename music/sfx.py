"""
sfx.py — 音效播放模块

基于 pygame.mixer.Sound，用于播放开火、换弹等短音效。
音效文件按枪械分目录存放：

    music/sounds/<gun_name>/
        fire_01.mp3, fire_02.mp3, ...   # 开火音效（随机播放）
        clipout.wav                     # 退弹匣
        boltpull.wav                    # 拉枪栓
        addammo.wav                     # 上弹匣

用法：
    from music.sfx import SFXPlayer

    sfx = SFXPlayer()
    sfx.play_fire("ak")        # 随机播 ak 的一发开火音效
    sfx.play_reload("ak")      # 按顺序播 clipout → boltpull → addammo
"""

import os
import random
import pygame

# Sounds 根目录
_SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")


class SFXPlayer:
    """音效播放器，基于 pygame.mixer.Sound，非阻塞。"""

    def __init__(self, init_mixer=True, buffer=2048):
        if init_mixer and not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16,
                              channels=16, buffer=buffer)
        self._cache = {}       # filepath → pygame.mixer.Sound
        self._sounds_dir = _SOUNDS_DIR

    # --------------------------------------------------
    #  内部：加载 & 缓存
    # --------------------------------------------------

    def _load(self, filepath):
        """加载并缓存音效文件。"""
        abs_path = os.path.abspath(filepath)
        if not os.path.exists(abs_path):
            return None
        if abs_path not in self._cache:
            try:
                self._cache[abs_path] = pygame.mixer.Sound(abs_path)
            except Exception as e:
                print(f"[SFX] 加载失败: {abs_path} — {e}")
                return None
        return self._cache[abs_path]

    def _gun_dir(self, gun_name):
        """返回某枪械的音效目录。"""
        return os.path.join(self._sounds_dir, gun_name)

    # --------------------------------------------------
    #  开火音效（随机）
    # --------------------------------------------------

    def play_fire(self, gun_name="ak"):
        """随机播放一发开火音效。

        参数：
            gun_name: 枪械名，对应 music/sounds/<gun_name>/ 目录
        """
        gdir = self._gun_dir(gun_name)
        if not os.path.isdir(gdir):
            return

        # 收集所有 fire_*.mp3 / fire_*.wav
        candidates = [f for f in os.listdir(gdir)
                      if f.lower().startswith("fire_")
                      and f.lower().endswith((".mp3", ".wav"))]
        if not candidates:
            return

        chosen = os.path.join(gdir, random.choice(candidates))
        sound = self._load(chosen)
        if sound:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(sound)

    # --------------------------------------------------
    #  换弹音效（单个部件播放，由状态机控制时序）
    # --------------------------------------------------

    def play_reload_part(self, gun_name, part):
        """播放换弹的某一部件音效。

        参数：
            gun_name: 枪械名
            part: "clipout" / "addammo" / "boltpull"
        """
        gdir = self._gun_dir(gun_name)
        if not os.path.isdir(gdir):
            return
        for ext in (".wav", ".mp3"):
            path = os.path.join(gdir, f"{part}{ext}")
            if os.path.exists(path):
                sound = self._load(path)
                if sound:
                    ch = pygame.mixer.find_channel(True)
                    if ch:
                        ch.play(sound)
                break

    def play_reload(self, gun_name="ak"):
        """播放换弹音效序列（全部同时播，旧接口保留兼容）。"""
        for part in ("clipout", "boltpull", "addammo"):
            self.play_reload_part(gun_name, part)

    # --------------------------------------------------
    #  通用播放
    # --------------------------------------------------

    def play(self, filepath):
        """直接播放指定音效文件。

        参数：
            filepath: 音效文件路径（相对或绝对）
        """
        sound = self._load(filepath)
        if sound:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(sound)

    # --------------------------------------------------
    #  音量 & 释放
    # --------------------------------------------------

    def set_volume(self, volume):
        """全局音效音量 (0.0 ~ 1.0)。"""
        for s in self._cache.values():
            try:
                s.set_volume(volume)
            except Exception:
                pass

    def close(self):
        """释放所有缓存的音效。"""
        for s in self._cache.values():
            try:
                s.stop()
            except Exception:
                pass
        self._cache.clear()
        print("[SFX] 已释放")
