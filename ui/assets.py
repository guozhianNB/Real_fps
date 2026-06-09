# ui/assets.py — 资源工具
# 字体缓存、半透明画板工具

import os
import pygame

# ====== 中文字体（全局生效） ======
_CN_FONT_PATH = None
_asset_dir = os.path.dirname(os.path.abspath(__file__))
# 优先使用项目自定义字体
_custom_font = os.path.join(_asset_dir, "asset", "font.ttf")
if os.path.exists(_custom_font):
    _CN_FONT_PATH = _custom_font
else:
    for _p in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
               "C:/Windows/Fonts/yahei.ttf"]:
        if os.path.exists(_p):
            _CN_FONT_PATH = _p
            break

# ====== 字体缓存 ======
_font_cache = {}

def get_font(size, bold=False):
    """获取指定大小的字体（带缓存）。"""
    key = (size, bold)
    if key not in _font_cache:
        if _CN_FONT_PATH:
            font = pygame.font.Font(_CN_FONT_PATH, size)
        else:
            font = pygame.font.Font(None, size)
        font.set_bold(bold)
        _font_cache[key] = font
    return _font_cache[key]

def get_font_small():
    """小号字体 (28px)。"""
    return get_font(28)

def get_font_large():
    """大号字体 (48px)。"""
    return get_font(48)

def get_font_medium():
    """中等字体 (36px)。"""
    return get_font(36)

def get_font_huge():
    """超大号粗体 (72px)。"""
    return get_font(72, bold=True)


# ====== 半透明画板工具 ======

def alpha_surface(w, h, color, alpha):
    """创建半透明 Surface。"""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((*color, alpha))
    return surf
