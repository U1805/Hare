import sys,os,re
import pysubs2
import cv2
import threading
from alive_progress import alive_bar

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

# 多线程-任务
def work(start):
    video_path = os.path.join("./temp/", "part_"+str(start)+".mp4")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    width = int(cap.get(3))
    height = int(cap.get(4))
    out = cv2.VideoWriter("./temp/part_"+str(start)+"_out.mp4",fourcc,fps,(width,height))
    print("start threading "+str(start))

    for i in range(start*num,(start+1)*num):
        ret, img = cap.read()
        if ret:
            for style in frame[i]:
                y1 ,x1 ,y2 ,x2= axis[style][0], axis[style][1], axis[style][2], axis[style][3]
                Inpainting(img,x1,y1,x2,y2,style,kernelSize=9,iter=1,r=4)
            out.write(img)
        else:
            break
        if cv2.waitKey(1) & 0xFF==27:
            break
    cap.release()
    out.release()
    print("finish threading "+str(start))
    bar()

# 坐标
axis = {}
with open("config.txt", "r",encoding='utf-8') as f:
    for line in f.readlines():
        line = line.strip('\n')
        line = line.split(':')
        style = line[0]
        axis[style] = list(map(int,list(line[1].split(','))))

filename = input("input filename: ")
path = sys.path[0]+"\\temp\\"
cap = cv2.VideoCapture(filename+".mp4")
length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
width = int(cap.get(3))
height = int(cap.get(4))
frame = [] 
for i in range(length):
    frame.append([])
if not os.path.exists(path):
    os.makedirs(path)

# 时间轴标记
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
            text = "\\N".join(re.findall(".{35}",text)) +"\\N"+ text[-(len(text)%35):]
        sub.text = text

        for i in range(start,end):
            frame[i].append("学生")
            frame[i].append("文本")

    else:
        for i in range(start,end):
            frame[i].append(sub.style)
subs.save(filename + "_out.ass")

# 多线程-预处理切分
num = 1000
i = -1
with alive_bar(length, title="preprocess") as bar:
    while 1:
        i += 1
        ret, img = cap.read()
        if ret:
            if i % num == 0:
                out = cv2.VideoWriter(path + "part_" + str(int(i/num)) + ".mp4",fourcc,fps,(width,height))
            out.write(img)
        else:
            break
        bar()
cap.release()
out.release()

cnt = -1 * (-i // num)

with open(path + "list.txt","a") as f:
    for i in range(0,cnt):
        f.write("file ./temp/part_"+str(i)+"_out.mp4\n")

thread_list = []
with alive_bar(cnt, title="thread") as bar:
    for i in range(0,cnt):
        thread = threading.Thread(target=work, args=[i])
        thread.start()
        thread_list.append(thread)
    for t in thread_list:
        t.join()

os.system("ffmpeg -f concat -safe 0 -i {path}list.txt -c copy {path}concat.mp4".format(path=path))
os.system("ffmpeg -i {path}concat.mp4 -i {filename}.mp4  -c copy -map 0 -map 1:1 -y -shortest {filename}_out.mp4".format(path=path,filename=filename))
os.system("ffmpeg -i {filename}_out.mp4 -vf subtitles={filename}_out.ass {filename}_final.mp4".format(filename=filename))
os.system("rd/s/q "+path +" && del {filename}_out.ass {filename}_out.mp4".format(filename=filename))
