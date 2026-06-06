
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
import re
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None
    print("未安装 ultralytics，YOLOv11n-face.pt 检测不可用！请 pip install ultralytics")



# ====== 直接在这里设置输入输出路径 ======
# 输入图片文件夹，图片名即为人脸名
INPUT_DIR =  Path(__file__).resolve().parent / "input_images" # TODO: 修改为你的图片文件夹路径
# yolov11n-face.pt 路径
YOLO_MODEL_PATH = Path(__file__).resolve().parent / "model" / "yolov11n-face.pt"  # TODO: 修改为你的YOLO模型路径
# 输出数据集目录（每个人一个子文件夹）
OUTPUT_DIR = Path(__file__).resolve().parent / "dataset"
# =====================================


# 人脸图像统一缩放尺寸
FACE_SIZE = (200, 200)

# 用YOLOv11n-face.pt检测图片中的所有人脸，返回[x1, y1, x2, y2]列表
def detect_faces_yolo(img, yolo_model):
    results = yolo_model(img)
    faces = []
    for result in results:
        if hasattr(result, 'boxes'):
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                faces.append((x1, y1, x2, y2))
    return faces


def augment_face(gray_img):
    """对单张灰度人脸做数据增强，返回多张变体。"""
    h, w = gray_img.shape
    variants = [gray_img]  # 原图

    # 1. 水平镜像
    variants.append(cv2.flip(gray_img, 1))

    # 2. 小角度旋转 (±5°, ±10°)
    for angle in [-10, -5, 5, 10]:
        M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
        rotated = cv2.warpAffine(gray_img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        variants.append(rotated)

    # 3. 缩放 (±5%, ±10%)
    for scale in [0.9, 0.95, 1.05, 1.1]:
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(gray_img, (new_w, new_h))
        if scale < 1:
            # 放大回原尺寸（中心裁剪）
            x = (new_w - w) // 2
            y = (new_h - h) // 2
            resized = resized[max(0,-y):max(0,-y)+h, max(0,-x):max(0,-x)+w] if scale<1 else resized
        # 直接 resize 回标准尺寸（会在外部统一做，这里仅收集）
        variants.append(cv2.resize(resized, (w, h)))

    # 4. 亮度/对比度调整
    for alpha, beta in [(0.8, 20), (1.0, -20), (1.2, 10), (0.9, -10)]:
        adjusted = cv2.convertScaleAbs(gray_img, alpha=alpha, beta=beta)
        variants.append(adjusted)

    # 5. 高斯模糊（模拟远距离/失焦）
    for ksize in [(3,3), (5,5)]:
        blurred = cv2.GaussianBlur(gray_img, ksize, 0)
        variants.append(blurred)

    return variants



# 从指定文件夹批量读取图片，图片名为人脸名，自动处理并保存为标准人脸样本
def register_faces_from_folder(input_dir: Path, output_dir: Path):
    if YOLO is None:
        print("未安装 ultralytics，无法使用YOLOv11n-face.pt 检测人脸！")
        return
    yolo_model = YOLO(str(YOLO_MODEL_PATH))
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    input_images = list(input_dir.glob("*"))
    if not input_images:
        print(f"输入文件夹 {input_dir} 没有图片！")
        return

    def normalize_person_name(stem: str) -> str:
        """把文件名 stem 归一化为人名：
        - 如果文件名末尾是分隔符+数字（如 an_01, bob-2, lucy.03），去掉尾部数字和分隔符，返回前缀。
        - 否则直接返回原始 stem。
        """
        m = re.match(r"^(.*?)[_\-\. ]?(\d+)$", stem)
        if m:
            base = m.group(1)
            return base if base else stem
        return stem

    image_count = 0
    for img_path in input_images:
        if not img_path.is_file():
            continue
        # 取文件名（不含扩展名）作为人脸名，按规则归一化（an_01.jpg -> an）
        person_name = normalize_person_name(img_path.stem)
        person_dir = output_dir / person_name
        person_dir.mkdir(parents=True, exist_ok=True)

        img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print(f"无法读取图片: {img_path}")
            continue
        # 用YOLO检测人脸
        faces = detect_faces_yolo(img, yolo_model)
        if len(faces) == 0:
            print(f"未检测到人脸: {img_path}")
            continue
        
        for idx, (x1, y1, x2, y2) in enumerate(faces):
            face_roi = img[y1:y2, x1:x2]
            if face_roi.size == 0:
                continue
            face_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            face_roi = cv2.resize(face_roi, FACE_SIZE)
            # 数据增强：每张原图生成多张变体
            variants = augment_face(face_roi)
            for vi, variant in enumerate(variants):
                variant = cv2.resize(variant, FACE_SIZE)
                file_path = person_dir / f"{person_name}_{image_count+1:03d}_v{vi:02d}.png"
                cv2.imencode('.png', variant)[1].tofile(str(file_path))
                print(f"已保存: {file_path.name}")
                image_count += 1

    # 注册完毕 → 自动训练识别模型
    if image_count > 0:
        print(f"\n共注册 {image_count} 张人脸，正在训练 LBPH 模型...")
        from vision.face_rec import train_and_save_recognizer
        try:
            train_and_save_recognizer("LBPH", output_dir, output_dir.parent / "model")
            print("模型训练完成！")
        except Exception as e:
            print(f"模型训练失败: {e}")
    else:
        print("未注册任何人脸，跳过模型训练。")







# 主入口
def main():
    # 直接用脚本内变量
    register_faces_from_folder(INPUT_DIR, OUTPUT_DIR)


if __name__ == "__main__":
    main()

