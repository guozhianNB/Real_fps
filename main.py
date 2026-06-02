"""
RealFPS 主程序
使用 YOLO 跟踪模式追踪人体，并在 OpenCV 窗口中实时显示。
"""

import cv2
import time
from vision import HumanTracker, MODEL_PATH, CAMERA_PATH
from pathlib import Path


def main():
    # 检查模型文件是否存在
    if not Path(MODEL_PATH).exists():
        print(f"[错误] 模型文件未找到: {MODEL_PATH}")
        print("请将 yolo26n-pose.pt 放在 model/ 目录下")
        input("按 Enter 退出...")
        return

    print("正在启动 YOLO 人体跟踪器...")
    tracker = HumanTracker(camera_url=CAMERA_PATH, model_path=MODEL_PATH)

    cv2.namedWindow("RealFPS - YOLO Track", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("RealFPS - YOLO Track", 1280, 720)

    print("跟踪中... 按 'q' 或 ESC 退出")

    try:
        while True:
            frame, result, trajectories = tracker.get_latest()
            if frame is None:
                time.sleep(0.05)
                continue

            # 如果 YOLO 有结果，绘制跟踪框和 ID
            if result is not None:
                annotated = result.plot()  # ultralytics 内置绘制
            else:
                annotated = frame.copy()

            # 绘制轨迹线
            for tid, pts in trajectories.items():
                if len(pts) < 2:
                    continue
                for i in range(1, len(pts)):
                    cv2.line(
                        annotated,
                        (int(pts[i - 1][0]), int(pts[i - 1][1])),
                        (int(pts[i][0]), int(pts[i][1])),
                        (0, 255, 255),
                        2,
                    )

            # 显示人数统计
            if result and result.boxes:
                count = len(result.boxes)
                cv2.putText(
                    annotated,
                    f"Tracked: {count}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,
                    (0, 255, 0),
                    3,
                )

            cv2.imshow("RealFPS - YOLO Track", annotated)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # q 或 ESC
                break

    finally:
        tracker.release()
        cv2.destroyAllWindows()
        print("程序已退出。")


if __name__ == "__main__":
    main()