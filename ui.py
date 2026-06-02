import cv2
import numpy as np
import random
W,H=800,600
score=0
enemy_list=[]
def create_enemy():
    x=random.randint(50,W-50)
    y=random.randint(50,H-50)
    dx=random.choice([-2,2])
    dy=random.choice([-2,2])
    return [x,y,dx,dy]
for _ in range(8):
    enemy_list.append(create_enemy())
def click_shoot(event,x,y,flags,param):
    global score
    if event==cv2.EVENT_LBUTTONDOWN:
        for idx,(ex,ey,_,_) in enumerate(enemy_list):
            if abs(x-ex)<25 and abs(y-ey)<25:
                del enemy_list[idx]
                score+=15
                enemy_list.append(create_enemy())
                break
win_name="小人射击 | ESC退出 | 左键点击打人"
cv2.namedWindow(win_name)
cv2.setMouseCallback(win_name,click_shoot)
while True:
    screen=np.zeros((H,W,3),dtype=np.uint8)
    for i in range(len(enemy_list)):
        x,y,dx,dy=enemy_list[i]
        x+=dx
        y+=dy
        if x<30 or x>W-30:
            dx=-dx
        if y<30 or y>H-30:
            dy=-dy
        enemy_list[i]=[x,y,dx,dy]
        cv2.circle(screen,(x,y),22,(0,180,255),-1)
        cv2.rectangle(screen,(x-12,y+22),(x+12,y+55),(255,255,255),-1)
    cv2.putText(screen,f"Score:{score}",(20,40),cv2.FONT_HERSHEY_SIMPLEX,1.3,(0,255,0),2)
    cv2.imshow(win_name,screen)
    key=cv2.waitKey(1)&0xFF
    if key==27:
        break
cv2.destroyAllWindows()