# _*_ coding:utf-8 _*_
from cv2 import VideoCapture, threshold, COLOR_BGR2HSV, cvtColor
from cv2 import CAP_PROP_FPS, CAP_PROP_FRAME_COUNT, THRESH_BINARY, THRESH_BINARY_INV,COLOR_BGR2RGB
from pysubs2 import load, time, SSAEvent
from alive_progress import alive_bar
import matplotlib.pyplot as plt 
plt.rcParams["font.sans-serif"]=["SimHei"] #设置字体

def cal_stderr(img, imgo=None):
    if imgo is None:
        return (img ** 2).sum() / img.size * 100
    return ((img - imgo) ** 2).sum() / img.size * 100

def show(img,text):
    print('insert：'+text)
    plt.title(text)
    plt.imshow(cvtColor(img,COLOR_BGR2RGB))
    plt.pause(0.01)

file = input("把视频拖到这里 : ")
filename = file.split('.')[0]
if file.split('.')[1] != "mp4" and file.split('.')[1] != "MP4":
    print("WARNING : 建议用 MP4 格式，否则可能出现偏移")

content = []
content_file = input("把文本文档拖到这里 : ")
with open(content_file, 'r', encoding='UTF-8') as file_to_read:
    while True:
        lines = file_to_read.readline()
        if not lines:
            break
        if lines == '\n':
            continue
        content.append(lines.strip())

STYLE_FILE = """\
[Script Info]
; Script generated by Aegisub r8942
; http://www.aegisub.org/
Title: Default Aegisub file
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1920
PlayResY: 1080

[Aegisub Project Garbage]
Last Style Storage: 111
Audio File: {filename}
Video File: {filename}
Video AR Mode: 4
Video AR Value: 1.777778
Video Zoom Percent: 0.500000
Video Position: 101

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,方正粗圆_GBK,70,&H00FFFFFF,&H000000FF,&H00C8952A,&H00FFFFFF,0,0,0,0,100,100,0,0,1,7,0.3,2,10,10,150,1
Style: 选项1,华康圆体W7(P),40,&H00513B30,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,8,16,16,460,1
Style: 选项2,华康圆体W7(P),40,&H00513B30,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,8,16,16,580,1
Style: 块,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,10,10,460,1
Style: 块 - 复制,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,10,10,570,1
Style: 单选项,华康圆体W7(P),40,&H00513B30,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,8,16,16,515,1
Style: 单选块,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,10,10,510,1
Style: 日文,Gen Jyuu Gothic Bold,110,&H00FFFFFF,&H000000FF,&H00C8952A,&H00FFFFFF,0,0,0,0,100,100,0,0,1,7,0.3,2,10,10,30,1
Style: 说话,Resource Han Rounded SC,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0.2,1,220,16,30,1
Style: 说话 - 复制,Resource Han Rounded SC,70,&H00110001,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0.2,1,200,16,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(filename=file)
with open(filename+".ass", "w", encoding='utf-8') as fp:
    fp.write(STYLE_FILE)

subs = load(filename+".ass")

videoCap = VideoCapture(file)
fps = videoCap.get(CAP_PROP_FPS)
length = int(videoCap.get(CAP_PROP_FRAME_COUNT))
skip_frame = 70
for i in range(skip_frame):
    ret, last_img = videoCap.read()
curr_frame = skip_frame
start_choice = start_talk = 0
end_choice = end_talk = 0
TH = 5
TH2 = 0.5
last_end_choice = 0
ret, frame = videoCap.read()
_, last_img_talk = threshold(cvtColor(frame ,COLOR_BGR2HSV)[920:1000, 830:1080,1], 155, 255, THRESH_BINARY)
_, last_img_choice_single = threshold(frame[500:570,900:1000,0], 100, 255, THRESH_BINARY_INV)
_, last_img_choice = threshold(frame[474:600,900:1000,0], 100, 255, THRESH_BINARY_INV)

content_index = 0

with alive_bar(length-skip_frame-1, title="progress", manual=True) as bar:
    while True:
        if content_index == len(content):
            bar(1.0)
            break
        ret, frame = videoCap.read()
        if frame is None:
            break
        curr_frame = curr_frame + 1
        _, img_talk = threshold(cvtColor(frame ,COLOR_BGR2HSV)[920:1000, 830:1080,1], 155, 255, THRESH_BINARY)
        _, img_choice_single = threshold(frame[500:570,900:1000,0], 100, 255, THRESH_BINARY_INV)
        _, img_choice = threshold(frame[474:600,900:1000,0], 100, 255, THRESH_BINARY_INV)

        if cal_stderr(last_img_choice) < TH2 and cal_stderr(img_choice) >=TH2 :
            start_choice = curr_frame
        elif cal_stderr(last_img_choice_single,img_choice_single) > TH2:
            end_choice = curr_frame
            if end_choice - start_choice < 30:
                subs[0].end = time.frames_to_ms(end_choice+1, fps)
            else:
                end_choice = end_choice + 14 #点击效果会让识别失效
                t = content[content_index]
                content_index = content_index + 1
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_choice, fps),end=time.frames_to_ms(end_choice, fps),layer=1,style='单选项',text=t))
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_choice, fps),end=time.frames_to_ms(end_choice, fps),style='单选块',text="{\p1} m 0 0 l 650 0 650 50 0 50 {\p0}"))
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_choice, fps),end=time.frames_to_ms(end_choice, fps),type='comment'))#最后一个end会延后
                last_end_choice = end_choice
                start_choice = end_choice
                show(lastframe[480:600,:,:],t)
        elif cal_stderr(last_img_choice,img_choice) > TH2:
            end_choice = curr_frame
            if end_choice - start_choice < 30:
                subs[0].end = time.frames_to_ms(end_choice+1, fps)
            else:
                end_choice = end_choice + 14
                t = content[content_index]
                content_index = content_index + 1
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_choice, fps),end=time.frames_to_ms(end_choice, fps),layer=1,style='选项1',text=t))
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_choice, fps),end=time.frames_to_ms(end_choice, fps),style='块',text="{\p1} m 0 0 l 650 0 650 50 0 50 {\p0}"))
                t = content[content_index]
                content_index = content_index + 1
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_choice, fps),end=time.frames_to_ms(end_choice, fps),layer=1,style='选项2',text=t))
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_choice, fps),end=time.frames_to_ms(end_choice, fps),style='块 - 复制',text="{\p1} m 0 0 l 650 0 650 50 0 50 {\p0}"))
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_choice, fps),end=time.frames_to_ms(end_choice, fps),type='comment'))
                last_end_choice = end_choice
                start_choice = end_choice
                show(lastframe[450:650,:,:],content[content_index-2]+'\n'+t)

        if cal_stderr(last_img_talk) < TH and cal_stderr(img_talk) >=TH :
            start_talk = curr_frame
        elif cal_stderr(img_talk,last_img_talk)>TH:
            if curr_frame - start_talk > 6:
                end_talk = curr_frame
                t = content[content_index]
                content_index = content_index + 1
                subs.insert(0, SSAEvent(start=time.frames_to_ms(start_talk, fps),end=time.frames_to_ms(end_talk, fps),text=t))
                start_talk = end_talk
                show(lastframe[920:1100, :, :],t)
    
        last_img_talk = img_talk
        last_img_choice_single = img_choice_single
        last_img_choice = img_choice
        lastframe = frame
        bar((curr_frame-skip_frame)/(length-skip_frame-1))
videoCap.release()
subs.sort()
subs.save(filename+".ass")
input("Press ENTER to exit")