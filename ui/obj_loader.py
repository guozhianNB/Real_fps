# ui/obj_loader.py — OBJ/MTL 模型加载器
#
# 支持 .obj + .mtl 材质。Blender 导出时勾选 Triangles + Include Normals。
# .mtl 文件需与 .obj 放在同一目录下。
#
# 用法：
#   model = OBJModel("ui/models/gun.obj")
#   model.render()

import os
import pygame
import numpy as np
from OpenGL.GL import *


def _load_mtl(mtl_path, tex_dir):
    """解析 .mtl，返回 {材质名: 属性字典}，含纹理路径。"""
    materials = {}
    current = None
    if not os.path.exists(mtl_path):
        return materials

    with open(mtl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if not parts:
                continue
            cmd = parts[0]

            if cmd == "newmtl":
                current = parts[1]
                materials[current] = {
                    "Ka": (0.2, 0.2, 0.2),
                    "Kd": (0.6, 0.6, 0.6),
                    "Ks": (0.0, 0.0, 0.0),
                    "Ns": 32.0,
                    "map_Kd": None,
                }
            elif current and cmd == "Ka":
                materials[current]["Ka"] = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif current and cmd == "Kd":
                materials[current]["Kd"] = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif current and cmd == "Ks":
                materials[current]["Ks"] = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif current and cmd == "Ns":
                materials[current]["Ns"] = float(parts[1])
            elif current and cmd == "map_Kd":
                tex_path = os.path.join(tex_dir, parts[1])
                if os.path.exists(tex_path):
                    materials[current]["map_Kd"] = tex_path

    return materials


def _load_texture(filepath):
    """用 Pygame 加载图片并创建 OpenGL 纹理，返回纹理 ID。"""
    try:
        img = pygame.image.load(filepath)
        data = pygame.image.tostring(img, "RGBA", True)
        w, h = img.get_size()
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        return tex
    except Exception as e:
        print(f"[纹理] 加载失败 {filepath}: {e}")
        return 0


class OBJModel:
    """加载并渲染 .obj 格式的 3D 模型（含 MTL 材质 + 纹理）。"""

    def __init__(self, filepath):
        self.filepath = filepath
        self.display_list = None
        self._ok = False
        self.materials = {}
        self._tex_ids = {}  # 材质名 → OpenGL 纹理 ID

        if not os.path.exists(filepath):
            print(f"[OBJ] 文件不存在: {filepath}")
            return

        try:
            base_dir = os.path.dirname(filepath)
            self.materials, groups = self._parse_obj(filepath, base_dir)
            self._load_textures()
            self._compile(groups)
            self._ok = True
            n = sum(len(g["faces"]) for g in groups)
            print(f"[OBJ] 已加载: {os.path.basename(filepath)} ({n} 三角形, {len(self.materials)} 材质)")
            for mname, mat in self.materials.items():
                tex_info = f", 纹理={mat['map_Kd']}" if mat.get("map_Kd") else ""
                print(f"  材质 [{mname}]: Kd={mat['Kd']}{tex_info}")
        except Exception as e:
            print(f"[OBJ] 加载失败: {e}")

    def _load_textures(self):
        """加载所有材质的纹理到 OpenGL。"""
        for mname, mat in self.materials.items():
            tex_path = mat.get("map_Kd")
            if tex_path:
                tex_id = _load_texture(tex_path)
                if tex_id:
                    self._tex_ids[mname] = tex_id

    def _parse_obj(self, filepath, base_dir):
        """解析 .obj，返回 (材质表, 分组列表)。"""
        vertices, normals, texcoords = [], [], []
        materials = {}
        groups = []
        current_mat = None

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if not parts:
                    continue
                cmd = parts[0]

                if cmd == "v":
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif cmd == "vn":
                    normals.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif cmd == "vt":
                    texcoords.append([float(parts[1]), float(parts[2])])
                elif cmd == "mtllib":
                    mtl_file = os.path.join(base_dir, parts[1])
                    print(f"[OBJ] 尝试加载 MTL: {mtl_file}")
                    materials = _load_mtl(mtl_file, base_dir)
                    if materials:
                        print(f"[OBJ] MTL 加载成功: {len(materials)} 个材质")
                    else:
                        print(f"[OBJ] MTL 为空或未找到")
                elif cmd == "usemtl":
                    current_mat = parts[1]
                    groups.append({"mat_name": current_mat, "faces": []})
                elif cmd == "f":
                    if not groups:
                        groups.append({"mat_name": None, "faces": []})
                    face = []
                    for p in parts[1:]:
                        vals = p.split("/")
                        vi = int(vals[0]) - 1
                        ti = int(vals[1]) - 1 if len(vals) >= 2 and vals[1] else -1
                        ni = int(vals[2]) - 1 if len(vals) >= 3 and vals[2] else -1
                        face.append((vi, ni, ti))
                    if len(face) == 3:
                        groups[-1]["faces"].append(face)

        self._verts = np.array(vertices, dtype=np.float32)
        self._norms = np.array(normals, dtype=np.float32)
        self._texcs = np.array(texcoords, dtype=np.float32) if texcoords else np.array([])
        return materials, groups

    def _compile(self, groups):
        """编译 OpenGL 显示列表，含材质颜色和纹理。"""
        self.display_list = glGenLists(1)
        glNewList(self.display_list, GL_COMPILE)

        for g in groups:
            mat = self.materials.get(g["mat_name"])
            tex_id = self._tex_ids.get(g["mat_name"], 0)

            if tex_id:
                glEnable(GL_TEXTURE_2D)
                glBindTexture(GL_TEXTURE_2D, tex_id)
                glColor4f(1, 1, 1, 1)
            elif mat:
                kd = mat["Kd"]
                glColor4f(kd[0], kd[1], kd[2], 1.0)
                glDisable(GL_TEXTURE_2D)
            else:
                glColor4f(0.6, 0.6, 0.6, 1.0)
                glDisable(GL_TEXTURE_2D)

            for face in g["faces"]:
                glBegin(GL_TRIANGLES)
                for vi, ni, ti in face:
                    if ni >= 0:
                        glNormal3fv(self._norms[ni])
                    if ti >= 0 and len(self._texcs) > 0:
                        glTexCoord2f(self._texcs[ti][0], self._texcs[ti][1])
                    glVertex3fv(self._verts[vi])
                glEnd()

        glDisable(GL_TEXTURE_2D)
        glEndList()

    def get_muzzle_pos(self):
        """从模型顶点中找到枪口位置（Z 最小值 = 枪管尖端，Blender Forward=-Z）。"""
        if not self._ok or len(self._verts) == 0:
            return (0, 0, 0)
        idx = int(np.argmin(self._verts[:, 2]))
        return tuple(self._verts[idx])

    def render(self):
        if not self._ok:
            return
        glCallList(self.display_list)

    def cleanup(self):
        if self.display_list is not None:
            glDeleteLists(self.display_list, 1)
        for tex_id in self._tex_ids.values():
            glDeleteTextures([tex_id])
