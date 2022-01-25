import cv2
import pysubs2
import re
import os

def Inpainting(srcImg,x,y,xx,yy,style="文本",kernelSize=7,iter=1,r=3):
    src = srcImg[x:xx,y:yy].copy()
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY,1)
    if style == "学生" or style == "文本": #白字
        thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)[1]
    else:
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernelSize, kernelSize))
    maskImg = cv2.dilate(thresh, kernel,iterations=iter)
    inpaintImg = cv2.inpaint(src,maskImg,r,cv2.INPAINT_NS)
    srcImg[x:xx,y:yy] = inpaintImg

filename = input("input filename:")
axis = {}
with open("config.txt", "r",encoding='utf-8') as f:
    for line in f.readlines():
        line = line.strip('\n')
        line = line.split(':')
        style = line[0]
        axis[style] = list(map(int,list(line[1].split(','))))

#filename_temp.mp4
cap = cv2.VideoCapture(filename+".mp4")
length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
width = int(cap.get(3))
height = int(cap.get(4))
out = cv2.VideoWriter(filename+'_temp.mp4',fourcc,fps,(width,height))
frame = []
for i in range(length):
    frame.append([])

#filename_out.ass
subs = pysubs2.load(filename+".ass")
for sub in subs:
    start = pysubs2.time.ms_to_frames(sub.start, fps)
    end = pysubs2.time.ms_to_frames(sub.end, fps)

    if sub.style == "文本":
        name_school = sub.text.split("：")[0]
        text = sub.text.split("：")[-1]

        if name_school != text:
            name = name_school.split('（')[0]
            school = name_school.split('（')[-1].replace("）","")
            subs.insert(0, pysubs2.SSAEvent(start=sub.start, end=sub.end, text=name+" {\\fs35 \c&H f4ca80 }"+school, style="学生"))

        if len(text) > 35: # 换行
            text = "\\N".join(re.findall(".{35}",text)) 
        sub.text = text

        for i in range(start,end):
            frame[i].append("学生")
            frame[i].append("文本")

    else:
        for i in range(start,end):
            frame[i].append(sub.style)
subs.save(filename+"_out.ass")


for i in range(length):
    ret, img = cap.read()
    print(str(i)+"/"+str(length))
    if ret:
        for style in frame[i]:
            y1 ,x1 ,y2 ,x2= axis[style][0], axis[style][1], axis[style][2], axis[style][3]
            Inpainting(img,x1,y1,x2,y2,style,kernelSize=9,iter=1,r=4)
        out.write(img)
        img = cv2.resize(img, (0, 0),fx = 0.5,fy = 0.5)
        cv2.imshow('img',img)
    else:
        print("Error")
        break
    if cv2.waitKey(1) & 0xFF==27:
        break
cap.release()
out.release()
cv2.destroyAllWindows()
