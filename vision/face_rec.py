from __future__ import annotations

import json
from pathlib import Path


import cv2
import numpy as np
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None
    print("未安装 ultralytics，YOLOv11n-face.pt 检测不可用！请 pip install ultralytics")


# ====== 直接在这里设置输入路径和参数 ======
# 输入路径，可以是图片路径、视频路径或摄像头编号（如0）
INPUT_PATH = r"D:\_project\ultralytics-8.4.41\image_video_test\PV.mp4"  # TODO: 修改为你的图片/视频路径，或摄像头编号（如0）
# 识别方法：LBPH、EigenFace、FisherFace
RECOGNIZE_METHOD = "LBPH"
# 数据集目录
DATA_DIR = Path(__file__).resolve().parent  / "dataset"
# 模型保存目录
MODEL_DIR = Path(__file__).resolve().parent  / "model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
# yolov11n-face.pt 路径
YOLO_MODEL_PATH = Path(__file__).resolve().parent / "model" / "yolov11n-face.pt"  # TODO: 修改为你的YOLO模型路径
# 识别阈值（None为默认）
THRESHOLD = None
# 数据集变化时是否自动重训模型
AUTO_RETRAIN_IF_DATA_CHANGED = True
# 每个人建议最少样本数（低于该值会提示）
MIN_SAMPLES_PER_PERSON = 3
# =====================================

# 人脸图像统一缩放尺寸
FACE_SIZE = (200, 200)


# 用YOLOv11n-face.pt检测图片中的所有人脸，返回[x1, y1, x2, y2]列表
def detect_faces_yolo(img, yolo_model):
    results = yolo_model(img, verbose=False)
    faces = []
    h, w = img.shape[:2]
    for result in results:
        if hasattr(result, "boxes"):
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                x1 = max(0, min(x1, w - 1))
                y1 = max(0, min(y1, h - 1))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))
                if x2 <= x1 or y2 <= y1:
                    continue
                faces.append((x1, y1, x2, y2))
    return faces

# 创建人脸识别器，支持LBPH/EigenFace/FisherFace三种方法
def create_recognizer(method: str):
    if not hasattr(cv2, "face"):
        raise RuntimeError(
            "本脚本需要安装 opencv-contrib-python，否则没有cv2.face模块。"
        )

    method = method.upper()
    if method == "LBPH":
        # LBPH方法，适合小样本，鲁棒性好
        return cv2.face.LBPHFaceRecognizer_create(), 90.0  # 阈值可调
    if method == "EIGENFACE":
        # EigenFace方法，PCA主成分分析
        return cv2.face.EigenFaceRecognizer_create(), 4500.0
    if method == "FISHERFACE":
        # FisherFace方法，LDA判别分析
        return cv2.face.FisherFaceRecognizer_create(), 400.0
    raise ValueError("method 必须是: LBPH, EigenFace, FisherFace 之一")

# 加载数据集，返回图片、标签、映射表
def load_dataset(data_dir: Path):
    images = []  # 所有人脸图片
    labels = []  # 对应标签id
    label_to_id = {}  # 姓名->id
    id_to_label = {}  # id->姓名
    person_image_count = {}  # 姓名->有效样本数
    latest_data_mtime = 0.0  # 数据集内最新文件修改时间
    next_id = 0

    if not data_dir.exists():
        return images, labels, label_to_id, id_to_label, person_image_count, latest_data_mtime

    # 遍历每个人的文件夹
    for person_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        person_name = person_dir.name
        if person_name not in label_to_id:
            label_to_id[person_name] = next_id
            id_to_label[next_id] = person_name
            next_id += 1

        person_id = label_to_id[person_name]
        valid_count = 0
        for image_path in sorted(person_dir.glob("*")):
            if image_path.is_file():
                latest_data_mtime = max(latest_data_mtime, image_path.stat().st_mtime)
            image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            image = cv2.resize(image, FACE_SIZE)
            images.append(image)
            labels.append(person_id)
            valid_count += 1

        if valid_count > 0:
            person_image_count[person_name] = valid_count

    return images, labels, label_to_id, id_to_label, person_image_count, latest_data_mtime

# 训练识别器并保存模型和标签映射
def train_and_save_recognizer(method: str, data_dir: Path, model_dir: Path):
    images, labels, _, id_to_label, person_image_count, _ = load_dataset(data_dir)
    if not images:
        raise RuntimeError(f"数据集 {data_dir} 里没有图片，无法训练")

    for person_name, count in sorted(person_image_count.items()):
        if count < MIN_SAMPLES_PER_PERSON:
            print(f"警告: {person_name} 只有 {count} 张样本，建议至少 {MIN_SAMPLES_PER_PERSON} 张")

    # EigenFace/FisherFace 需要至少两个人
    if len(id_to_label) < 2 and method.upper() in {"EIGENFACE", "FISHERFACE"}:
        raise RuntimeError(f"{method} 需要至少两个人的数据集")

    recognizer, threshold = create_recognizer(method)
    recognizer.train(images, np.array(labels))

    model_path = model_dir / f"{method.lower()}_face_model.yml"
    labels_path = model_dir / f"{method.lower()}_labels.json"
    recognizer.save(str(model_path))
    with labels_path.open("w", encoding="utf-8") as fp:
        json.dump({str(k): v for k, v in id_to_label.items()}, fp, ensure_ascii=True, indent=2)

    return recognizer, id_to_label, threshold

# 加载已训练好的模型（训练由 face_register.py 完成）
def load_model(method: str, model_dir: Path):
    """加载训练好的识别模型和标签映射。"""
    model_path = model_dir / f"{method.lower()}_face_model.yml"
    labels_path = model_dir / f"{method.lower()}_labels.json"

    if not model_path.exists() or not labels_path.exists():
        raise RuntimeError(
            f"模型文件不存在: {model_path}\n"
            "请先运行 python vision/face_register.py 注册人脸并训练模型"
        )

    recognizer, threshold = create_recognizer(method)
    recognizer.read(str(model_path))

    with labels_path.open("r", encoding="utf-8") as fp:
        id_to_label = {int(k): v for k, v in json.load(fp).items()}

    return recognizer, id_to_label, threshold

# 实时检测摄像头画面中的人脸并识别身份

# 通用识别入口，支持图片、视频、摄像头

def detect_and_recognize_auto(input_path, method: str, data_dir: Path, model_dir: Path, threshold: float | None):
    if YOLO is None:
        print("未安装 ultralytics，无法使用YOLOv11n-face.pt 检测人脸！")
        return
    yolo_model = YOLO(str(YOLO_MODEL_PATH))
    recognizer, id_to_label, default_confidence = load_model(method, model_dir)
    if threshold is None:
        threshold = default_confidence  # 使用默认阈值

    # 判断输入类型
    if isinstance(input_path, int) or (isinstance(input_path, str) and input_path.isdigit()):
        # 摄像头
        cap = cv2.VideoCapture(int(input_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera {input_path}")
        print("按q退出。")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            _draw_and_show_yolo(frame, yolo_model, recognizer, id_to_label, threshold)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        cap.release()
        cv2.destroyAllWindows()
        return

    input_path = str(input_path)
    # 判断是否为图片
    img_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    if any(input_path.lower().endswith(ext) for ext in img_exts):
        img = cv2.imread(input_path)
        if img is None:
            print(f"无法读取图片: {input_path}")
            return
        _draw_and_show_yolo(img, yolo_model, recognizer, id_to_label, threshold, window_name="OpenCV人脸识别-图片")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return

    # 其他情况按视频处理
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"无法打开视频或摄像头: {input_path}")
        return
    print("按q退出。")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        _draw_and_show_yolo(frame, yolo_model, recognizer, id_to_label, threshold)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


# 用YOLO检测并识别单帧，画框显示
def _draw_and_show_yolo(frame, yolo_model, recognizer, id_to_label, threshold, window_name="OpenCV人脸识别"):
    faces = detect_faces_yolo(frame, yolo_model)
    for (x1, y1, x2, y2) in faces:
        face_roi = frame[y1:y2, x1:x2]
        if face_roi.size == 0:
            continue
        face_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        face_roi = cv2.resize(face_roi, FACE_SIZE)
        label_id, confidence = recognizer.predict(face_roi)
        person_name = id_to_label.get(label_id, "Unknown")
        if confidence <= threshold:
            text = f"{person_name} ({confidence:.1f})"
            color = (0, 255, 0)
        else:
            text = f"Unknown ({confidence:.1f})"
            color = (0, 0, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            text,
            (x1, max(20, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )
    cv2.imshow(window_name, frame)


# 主入口
def main():
    detect_and_recognize_auto(INPUT_PATH, RECOGNIZE_METHOD, DATA_DIR, MODEL_DIR, THRESHOLD)


if __name__ == "__main__":
    main()