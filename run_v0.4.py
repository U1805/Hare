import sys,os,re
from pysubs2 import load, time, SSAEvent
from cv2 import cvtColor, threshold, getStructuringElement, dilate, inpaint
from cv2 import VideoCapture, VideoWriter_fourcc, VideoWriter
from cv2 import COLOR_BGR2GRAY, THRESH_BINARY, THRESH_BINARY_INV, THRESH_OTSU, MORPH_RECT, INPAINT_NS
from cv2 import CAP_PROP_FPS, CAP_PROP_FRAME_COUNT
from threading import Thread
from alive_progress import alive_bar

def Inpainting(srcImg,x,y,xx,yy,style="文本",kernelSize=7,iter=1,r=3):
    src = srcImg[x:xx,y:yy].copy()
    gray = cvtColor(src, COLOR_BGR2GRAY,1)
    if style == "fadeout":
        thresh = threshold(gray, gray[0,0]+5, 255, THRESH_BINARY | THRESH_OTSU)[1]
    elif style == "学生" or style == "文本" or style == "地点": #白字
        thresh = threshold(gray, 145, 255, THRESH_BINARY)[1]
    else:
        thresh = threshold(gray, gray[0,0]-5, 255, THRESH_BINARY_INV)[1]
    kernel = getStructuringElement(MORPH_RECT, (kernelSize, kernelSize))
    maskImg = dilate(thresh, kernel,iterations=iter)
    inpaintImg = inpaint(src,maskImg,r,INPAINT_NS)
    srcImg[x:xx,y:yy] = inpaintImg

# 多线程-任务
def work(start):
    video_path = os.path.join("./temp/", "part_"+str(start)+".mp4")
    cap = VideoCapture(video_path)
    fps = cap.get(CAP_PROP_FPS)
    fourcc = VideoWriter_fourcc(*'mp4v')
    width = int(cap.get(3))
    height = int(cap.get(4))
    out = VideoWriter("./temp/part_"+str(start)+"_out.mp4",fourcc,fps,(width,height))
    print("start threading "+str(start))

    for i in range(start*num,(start+1)*num):
        ret, img = cap.read()
        if ret:
            for style in frame[i]:
                if "fadeout" in style:
                    y1 ,x1 ,y2 ,x2= axis[style[:-8]][0], axis[style[:-8]][1], axis[style[:-8]][2], axis[style[:-8]][3]
                    style = "fadeout"
                elif style in axis:
                    y1 ,x1 ,y2 ,x2= axis[style][0], axis[style][1], axis[style][2], axis[style][3]
                else:
                    continue
                Inpainting(img,x1,y1,x2,y2,style,kernelSize=9)
            out.write(img)
        else:
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

filename = input("输入文件名: ")
path = os.path.dirname(os.path.realpath(sys.executable))+"\\temp\\"
# path = sys.path[0]+"\\temp\\"
cap = VideoCapture(filename+".mp4")
length = int(cap.get(CAP_PROP_FRAME_COUNT))
fps = cap.get(CAP_PROP_FPS)
fourcc = VideoWriter_fourcc(*'mp4v')
width = int(cap.get(3))
height = int(cap.get(4))
frame = []
for i in range(length):
    frame.append([])
if not os.path.exists(path):
    os.makedirs(path)

# 时间轴标记
subs = load(filename+".ass")
for sub in subs:
    start = time.ms_to_frames(sub.start, fps)
    end = time.ms_to_frames(sub.end, fps)
    if "文本" in sub.style and "：" in sub.text:
        name_school = sub.text.split("：")[0]
        text = sub.text.split("：")[-1]
        sub.text = text
        if name_school != text:
            name = name_school.split('（')[0]
            school = name_school.split('（')[-1].replace("）","")
            if name != school:
                t = ("{\\fad(0,500)}" if "fadeout" in sub.style else "")+name+" {\\fs35 \\c&H f4ca80 }"+school
            else :
                t = ("{\\fad(0,500)}" if "fadeout" in sub.style else "")+name
            subs.insert(0, SSAEvent(start=sub.start, end=sub.end, text=t, style="学生"))
for sub in subs:
    start = time.ms_to_frames(sub.start, fps)
    end = time.ms_to_frames(sub.end, fps) +1
    if "文本" in sub.style :
        text = sub.text
        cnt = 1
        s = ""
        for word in text:
            s = s+"{\\1a&HFF&\\3a&HFF&\\4a&HFF&}{\\t("+str(cnt*33)+","+str(cnt*33+1)+",\\1a&H00&\\3a&H00&\\4a&H00&)}"+word
            if cnt % 35 == 0:
                s += "\\N{\\fs 0}\\N"
            cnt+=1
        sub.text = ("{\\fad(0,500)}" if "fadeout" in sub.style else "") + s
        for i in range(start,end):
            frame[i].append("文本")
        if sub.style == "文本-fadeout":
            for i in range(end-45,end):
                frame[i].remove("文本")
                frame[i].append("文本-fadeout")
                if "学生" in frame[i]:
                    frame[i].remove("学生")
                    frame[i].append("学生-fadeout")
    elif "标题" in sub.style:
        sub.text = "{\\fad(500,500)}" + sub.text
        for i in range(start,end):
            frame[i].append(sub.style)
    elif sub.style == "地点":
        sub.text = "{\\fad(200,200)}" + sub.text
        for i in range(start,start+25):
            frame[i].append("地点-fadeout")
        for i in range(start+25,end-25):
            frame[i].append("地点")
        for i in range(end-25,end):
            frame[i].append("地点-fadeout")
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
                out = VideoWriter(path + "part_" + str(int(i/num)) + ".mp4",fourcc,fps,(width,height))
            out.write(img)
        else:
            break
        bar()
cap.release()
out.release()
cnt = -1 * (-i // num)

with open("./temp/list.txt","a") as f:
    for i in range(0,cnt):
        f.write("file part_"+str(i)+"_out.mp4\n")

thread_list = []
with alive_bar(cnt, title="thread") as bar:
    for i in range(0,cnt):
        thread = Thread(target=work, args=[i])
        thread.start()
        thread_list.append(thread)
    for t in thread_list:
        t.join()

os.system("ffmpeg -f concat -safe 0 -i ./temp/list.txt -c copy {path}concat.mp4".format(path=path))
os.system("ffmpeg -i {path}concat.mp4 -i {filename}.mp4  -c copy -map 0 -map 1:1 -y -shortest {filename}_out.mp4".format(path=path,filename=filename))
os.system("ffmpeg -i {filename}_out.mp4 -vf subtitles={filename}_out.ass {filename}_final.mp4".format(filename=filename))
os.system("rd/s/q "+path +" && del {filename}_out.ass {filename}_out.mp4".format(filename=filename))
input("Press Enter To Exit")
