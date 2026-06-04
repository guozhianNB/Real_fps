"""
bgm.py — 背景音乐播放模块

基于 pygame.mixer.music，支持循环播放、淡入淡出、暂停恢复。

用法：
    from music.bgm import BGMPlayer

    bgm = BGMPlayer()
    bgm.load("bgm_combat.mp3")       # 自动从 music/bgm/ 目录加载
    bgm.play(loops=-1, fade_ms=2000) # 无限循环 + 2秒淡入
    bgm.pause()
    bgm.resume()
    bgm.set_volume(0.5)
    bgm.stop()
"""

import os
import pygame

# BGM 文件夹路径（相对于本文件所在目录）
_BGM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bgm")


class BGMPlayer:
    """背景音乐播放器，基于 pygame.mixer.music。

    默认自动初始化 pygame.mixer（若尚未初始化），
    可在外部先用 pygame.mixer.init(frequency=44100, ...) 精细配置。
    """

    def __init__(self, init_mixer=True, buffer=2048):
        """
        参数：
            init_mixer: 若 True 且 mixer 未初始化，自动初始化（默认 44100Hz）
            buffer:     mixer 缓冲区大小（影响延迟）
        """
        if init_mixer and not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16,
                              channels=2, buffer=buffer)
        self.bgm_dir = _BGM_DIR

    # --------------------------------------------------
    #  基本播放控制
    # --------------------------------------------------

    def load(self, filepath):
        """加载音乐文件（支持 mp3/ogg/wav 等）。

        参数：
            filepath: 文件名（自动从 bgm_dir 加载）或完整路径
        """
        path = os.path.join(self.bgm_dir, filepath) \
            if not os.path.isabs(filepath) and '/' not in filepath and '\\' not in filepath \
            else filepath
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"[BGM] 文件未找到: {abs_path}")
        pygame.mixer.music.load(abs_path)
        print(f"[BGM] 已加载: {os.path.basename(abs_path)}")

    def play(self, loops=-1, start=0.0, fade_ms=0):
        """开始播放。

        参数：
            loops:  循环次数，-1 = 无限循环，0 = 播一次
            start:  从第几秒开始播放
            fade_ms: 淡入毫秒数
        """
        pygame.mixer.music.play(loops=loops, start=start, fade_ms=fade_ms)
        status = "∞ 循环" if loops == -1 else f"{loops + 1} 次"
        print(f"[BGM] 开始播放 ({status})")

    def stop(self):
        """停止播放。"""
        pygame.mixer.music.stop()
        print("[BGM] 已停止")

    def pause(self):
        """暂停播放。"""
        pygame.mixer.music.pause()
        print("[BGM] 已暂停")

    def resume(self):
        """恢复暂停。"""
        pygame.mixer.music.unpause()
        print("[BGM] 恢复播放")

    def fadeout(self, fade_ms=1000):
        """淡出并停止。

        参数：
            fade_ms: 淡出毫秒数
        """
        pygame.mixer.music.fadeout(fade_ms)
        print(f"[BGM] 淡出中 ({fade_ms}ms)")

    # --------------------------------------------------
    #  音量
    # --------------------------------------------------

    def set_volume(self, volume):
        """设置音量 (0.0 ~ 1.0)。"""
        volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(volume)
        print(f"[BGM] 音量: {volume:.1f}")

    def get_volume(self):
        """获取当前音量 (0.0 ~ 1.0)。"""
        return pygame.mixer.music.get_volume()

    # --------------------------------------------------
    #  状态查询
    # --------------------------------------------------

    def is_playing(self):
        """是否正在播放（含淡出中）。"""
        return pygame.mixer.music.get_busy()

    def get_pos(self):
        """获取当前播放位置（毫秒），未播放时返回 -1。"""
        return pygame.mixer.music.get_pos()

    # --------------------------------------------------
    #  便捷切换
    # --------------------------------------------------

    def switch(self, filepath, loops=-1, fade_in=1000, fade_out=500):
        """切换曲目（旧曲淡出 → 新曲淡入）。

        参数：
            filepath: 新音乐文件路径
            loops:    新曲循环次数
            fade_in:  新曲淡入毫秒
            fade_out: 旧曲淡出毫秒
        """
        self.fadeout(fade_out)
        # 等旧曲淡出完再加载新曲
        pygame.time.wait(fade_out + 50)
        self.load(filepath)
        self.play(loops=loops, fade_ms=fade_in)

    # --------------------------------------------------
    #  资源释放
    # --------------------------------------------------

    def close(self):
        """卸载音乐并释放 mixer 资源。"""
        self.stop()
        # pygame.mixer.music.unload()  # Python 3.7+ 可用
        print("[BGM] 已释放")
