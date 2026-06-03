
from __future__ import annotations
from pathlib import Path
import cv2
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

        img = cv2.imread(str(img_path))
        if img is None:
            print(f"无法读取图片: {img_path}")
            continue
        # 用YOLO检测人脸
        faces = detect_faces_yolo(img, yolo_model)
        if len(faces) == 0:
            print(f"未检测到人脸: {img_path}")
            continue
        
        for  idx,(x1, y1, x2, y2) in enumerate(faces):
            face_roi = img[y1:y2, x1:x2]
            if face_roi.size == 0:
                continue
            face_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            face_roi = cv2.resize(face_roi, FACE_SIZE)
            # 保存为 person_name_001.png 这种格式
            file_path = person_dir / f"{person_name}_{image_count+1:03d}.png"
            cv2.imwrite(str(file_path), face_roi)
            print(f"已保存: {file_path}")
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

