'''
主程序
流程：
广播GAME_START->调用vision.py,返回json数据->处理...


vision返回JSON格式:
{
    "num":人数,
    "box":{
        id:[[(head_x1, head_y1), (head_x2, head_y2)],
            [(body_x1, body_y1), (body_x2, body_y2),(body_x3, body_y3),(body_x4, body_y4)]]
    }
    "aim":{
        "head":[瞄到头部的id],
        "body":[瞄到身体的id]
    }
}

main调用vision方法:
from vision import HumanTracker, get_camera_size

tracker = HumanTracker()
cam_w, cam_h = get_camera_size()
aim = (cam_w // 2, cam_h // 2)

while True:
    data = tracker.get_analysis(aim)
    # 处理 data... 使用 data["box"], data["aim"] 等
'''