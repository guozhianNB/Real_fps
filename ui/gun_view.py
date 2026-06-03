# ui/gun_view.py — 3D 第一人称持枪视图（OpenGL）
#
# 使用 PyOpenGL 渲染一个简易枪管（圆柱体占位）到 Pygame Surface，
# 供 ui/core.py 绘制在画面右下角。
#
# 可独立测试：python ui/gun_view.py

import pygame
import os
import time
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

GUN_SIZE = 200


class GunView:
    """3D 枪械视图，渲染到 FBO → Pygame Surface。

    支持加载 Blender 导出的 .obj 模型（放入 ui/models/ 目录）。
    无模型时回退到圆柱体占位。
    """

    def __init__(self, w=GUN_SIZE, h=GUN_SIZE, model_path=None,
                 cam_dist=1, cam_pitch=-12, cam_yaw=5,
                 muzzle_pos=(25, -2, 0)):
        """
        参数：
            w, h:       渲染尺寸
            model_path: .obj 文件路径
            cam_dist:   相机到枪的距离（模型越大值越大）
            cam_pitch:  俯仰角（负=下俯）
            cam_yaw:    偏航角（正=右偏）
        """
        self.w, self.h = w, h
        self.cam_dist = cam_dist
        self.cam_pitch = cam_pitch
        self.cam_yaw = cam_yaw
        self.muzzle_pos = muzzle_pos
        self._ok = False
        self.fbo = None
        self.model = None
        try:
            self._setup_fbo()

            # 尝试加载 OBJ 模型
            if model_path and os.path.exists(model_path):
                from ui.obj_loader import OBJModel
                self.model = OBJModel(model_path)
                if self.model._ok:
                    # 自动检测枪口位置（最远 X 顶点）
                    self.muzzle_pos = self.model.get_muzzle_pos()
                    print(f"[枪械] 使用模型: {model_path}")
                    print(f"[枪械] 自动检测枪口: {self.muzzle_pos}")
                else:
                    self.model = None

            self._ok = True
            print(f"[枪械] FBO 就绪 {w}x{h}")
        except Exception as e:
            print(f"[枪械] 初始化失败: {e}")

    def _setup_fbo(self):
        """创建离屏 Framebuffer Object（含 alpha 通道）。"""
        # 颜色纹理 (RGBA 以便透明背景)
        self.color_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.color_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.w, self.h, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        # 深度缓冲
        self.depth_rbo = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth_rbo)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, self.w, self.h)

        # FBO
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, self.color_tex, 0)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                                  GL_RENDERBUFFER, self.depth_rbo)

        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"FBO 不完整, status=0x{status:x}")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def render(self, dt_ms=16, muzzle=False):
        """渲染一帧，返回 Pygame Surface（透明背景）。
        
        参数：
            dt_ms:   时间增量
            muzzle:  是否绘制 3D 枪口火焰
        """
        if not self._ok or self.fbo is None:
            return None
        self._show_muzzle = muzzle

        # ---- 渲染到 FBO ----
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.w, self.h)

        glClearColor(0, 0, 0, 0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # 透视
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(40, self.w / self.h, 0.1, 80.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # 无光照 + 纯色绘制（确保圆柱可见）
        glDisable(GL_LIGHTING)
        glEnable(GL_DEPTH_TEST)

        # 视角：使用可配置的相机参数
        glTranslatef(0.0, 0.04, -self.cam_dist)
        glRotatef(self.cam_pitch, 1, 0, 0)
        glRotatef(self.cam_yaw, 0, 1, 0)

        # 呼吸浮动
        breath = np.sin(time.time() * 2.5) * 0.008
        glTranslatef(0, breath, 0)

        # ---- 可选的枪口火焰（在枪口 3D 位置绘制发光球体） ----
        if getattr(self, '_show_muzzle', False):
            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glPushMatrix()
            glTranslatef(*self.muzzle_pos)  # 从模型顶点自动获取
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE)
            q = gluNewQuadric()
            glColor4f(1.0, 0.6, 0.1, 0.6)
            gluSphere(q, 0.6, 12, 8)
            glColor4f(1.0, 0.9, 0.3, 0.8)
            gluSphere(q, 0.35, 12, 8)
            glColor4f(1.0, 1.0, 0.8, 1.0)
            gluSphere(q, 0.15, 12, 8)
            gluDeleteQuadric(q)
            glDisable(GL_BLEND)
            glEnable(GL_DEPTH_TEST)
            glPopMatrix()

        # ---- 绘制枪械（有模型用模型，没有用圆柱体占位） ----
        if self.model and self.model._ok:
            # 使用导入的 OBJ 模型（材质纹理由 .mtl 控制）
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glLightfv(GL_LIGHT0, GL_POSITION, (5, 10, 15, 1))
            glLightfv(GL_LIGHT0, GL_AMBIENT, (0.3, 0.3, 0.3, 1))
            glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.8, 0.8, 0.8, 1))
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
            self.model.render()
            glDisable(GL_LIGHTING)
        else:
            # 回退：圆柱体占位
            glColor4f(0.45, 0.45, 0.45, 1.0)
            quadric = gluNewQuadric()
            gluQuadricDrawStyle(quadric, GLU_FILL)
            gluQuadricNormals(quadric, GLU_SMOOTH)
            gluCylinder(quadric, 0.05, 0.04, 0.3, 24, 1)
            gluDeleteQuadric(quadric)

            # 枪口
            glTranslatef(0, 0, 0.3)
            glColor4f(0.3, 0.3, 0.3, 1.0)
            q2 = gluNewQuadric()
            gluQuadricDrawStyle(q2, GLU_FILL)
            gluCylinder(q2, 0.045, 0.035, 0.08, 24, 1)
            gluDeleteQuadric(q2)

        # ---- 读取像素 (RGBA) ----
        glPixelStorei(GL_PACK_ALIGNMENT, 4)
        data = glReadPixels(0, 0, self.w, self.h, GL_RGBA, GL_UNSIGNED_BYTE)
        img = np.frombuffer(data, dtype=np.uint8).reshape(self.h, self.w, 4)
        img = np.flipud(img)

        # 解绑 FBO
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        surf = pygame.image.frombuffer(img.tobytes(), (self.w, self.h), "RGBA")
        return surf

    def get_muzzle_screen_pos(self, muzzle_3d):
        """将枪口 3D 坐标投影到 FBO 的 2D 像素坐标。"""
        if not self._ok:
            return None
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.w, self.h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(40, self.w / self.h, 0.1, 80.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glTranslatef(0.0, 0.04, -self.cam_dist)
        glRotatef(self.cam_pitch, 1, 0, 0)
        glRotatef(self.cam_yaw, 0, 1, 0)
        mv = glGetDoublev(GL_MODELVIEW_MATRIX)
        proj = glGetDoublev(GL_PROJECTION_MATRIX)
        vp = glGetIntegerv(GL_VIEWPORT)
        wx, wy, wz = gluProject(muzzle_3d[0], muzzle_3d[1], muzzle_3d[2],
                                mv, proj, vp)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        if wz < 1.0:
            return (int(wx), self.h - int(wy))
        return None

    def cleanup(self):
        """释放 OpenGL 资源。"""
        if not self._ok:
            return
        if self.model:
            self.model.cleanup()
        if self.fbo:
            glDeleteFramebuffers(1, [self.fbo])
        glDeleteRenderbuffers(1, [self.depth_rbo])
        glDeleteTextures([self.color_tex])


# ====== 独立测试 ======
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    pygame.init()
    _disp = pygame.display.set_mode((500, 500), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption("GunView 独立测试")

    gun = GunView(400, 400, cam_dist=2.5, cam_pitch=-10, cam_yaw=5)
    clock = pygame.time.Clock()
    running = True

    while running:
        dt = clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False

        surf = gun.render(dt)
        if surf is None:
            continue

        # 用 Pygame 2D 显示
        glViewport(0, 0, 500, 500)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, 500, 500, 0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClear(GL_COLOR_BUFFER_BIT)

        # 把 Surface 渲染为纹理
        data = pygame.image.tostring(surf, "RGBA", True)
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 400, 400, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glEnable(GL_TEXTURE_2D)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1); glVertex2f(50, 50)
        glTexCoord2f(1, 1); glVertex2f(450, 50)
        glTexCoord2f(1, 0); glVertex2f(450, 450)
        glTexCoord2f(0, 0); glVertex2f(50, 450)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        glDeleteTextures([tex])

        pygame.display.flip()

    gun.cleanup()
    pygame.quit()
