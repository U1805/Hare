import json
import os
import re
from threading import Thread

from alive_progress import alive_bar
from cv2 import (CAP_PROP_FPS, CAP_PROP_FRAME_COUNT, COLOR_BGR2GRAY,
                 INPAINT_NS, MORPH_RECT, THRESH_BINARY, THRESH_BINARY_INV,
                 THRESH_OTSU, VideoCapture, VideoWriter, VideoWriter_fourcc,
                 cvtColor, dilate, getStructuringElement, inpaint, threshold)

axis = {}
frame = []
filename = ""
num = 0
length = 0
path = ""
fps = 0
temp_path = ""
bar = None


def Inpainting(srcImg, x, y, xx, yy, style="文本", kernelSize=7, iter=1, r=3):
    src = srcImg[x:xx, y:yy].copy()
    gray = cvtColor(src, COLOR_BGR2GRAY, 1)
    if style == "fadeout":
        thresh = threshold(gray, gray[0, 0]+5, 255, THRESH_BINARY | THRESH_OTSU)[1]
    elif "学生" in style or "文本" in style or "地点" in style:  # 白字
        thresh = threshold(gray, 145, 255, THRESH_BINARY)[1]
    else:
        thresh = threshold(gray, gray[0, 0]-5, 255, THRESH_BINARY_INV)[1]
    kernel = getStructuringElement(MORPH_RECT, (kernelSize, kernelSize))
    maskImg = dilate(thresh, kernel, iterations=iter)
    inpaintImg = inpaint(src, maskImg, r, INPAINT_NS)
    srcImg[x:xx, y:yy] = inpaintImg


def readAxis():
    # 坐标
    global axis
    print("import config")
    with open("config.json", "r", encoding='utf-8') as fp:
        data = fp.read()
        data = json.loads(data)
        axis = data["data"][0]
    print(axis)

# time convert utils

def ms_to_frames(ms , fps) -> int:
    return int((ms / 1000) * fps)

def times_to_ms(time:str) -> int:
    ms = 0
    (h, m, s) = re.match(r'(.*):(.*):(.*)',time).groups()
    ms += float(s) * 1000
    ms += int(m) * 60000
    ms += int(h) * 3600000
    return int(ms)

def ms_to_str(ms) -> str:
    ms = int(ms)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    sgn = "-" if ms < 0 else ""
    return f"{sgn}{h:01d}:{m:02d}:{s:02d}.{ms:03d}"

# subtitile utils

def insertSub(path, start, end, style="Default", text=""):
    with open(path, 'a', encoding='utf-8') as fp:
        fp.write(f"Dialogue: 0,{start},{end},{style},,0,0,0,, {text}\n")

def readSub(path):
    with open(path, 'r', encoding='utf-8') as fp:
        lines = fp.readlines()
        ans = []
        for line in lines:
            if line.startswith("Dialogue"):
                sub = re.match( r'Dialogue: 0,(.*),(.*),(.*),,0,0,0,,(.*)\n', line, re.M|re.I).groups()
                ans.append({'start':times_to_ms(sub[0]),'end':times_to_ms(sub[1]),'style':sub[2],'text':sub[3]}) 
    return ans

def saveSub(save_path, orig_path, subs):
    global fps
    with open(save_path, 'w', encoding='utf-8') as wf:
        with open(orig_path,'r', encoding='utf-8') as rf:
            lines = rf.readlines()
            for line in lines:
                if not line.startswith("Dialogue"):
                    wf.write(line)
        for sub in subs:
            line = f'Dialogue: 0,{ms_to_frames(sub["start"], fps)},{ms_to_frames(sub["end"], fps)},{sub["style"]},,0,0,0,, {sub["text"]}\n'
            wf.write(line)

def readAss():
    # 时间轴标记
    global frame, filename, length, path, fps
    print("process ass file: "+os.path.join(path, filename+"_out.ass"))
    for i in range(length):
        frame.append([])
    if not os.path.exists(path):
        os.makedirs(path)

    # 分离出学生
    ass_path = os.path.join(path, filename+".ass")
    subs = readSub(ass_path)
    for sub in subs:
        start = ms_to_frames(sub["start"], fps)
        end = ms_to_frames(sub["end"], fps)
        if "文本" in sub["style"] and "：" in sub["text"]:
            # 可能没有社团 ① 白子（对策） ② 初音未来
            try:
                match = re.match(r'(.*)（(.*)）：(.*)', sub["text"], re.M).groups()
            except Exception:
                match = re.match(r'(.*)：(.*)', sub["text"], re.M).groups()
            sub["text"] = match[-1]
            if len(match) == 3:
                t = ("{\\fad(0,500)}" if "fadeout" in sub["style"] else "") + \
                    match[0]+f' {axis["student_style"]}'+match[1]
            else:
                t = (
                    "{\\fad(0,500)}" if "fadeout" in sub["style"] else "")+match[0]
            insertSub(ass_path, ms_to_times(sub["start"]), ms_to_times(sub["end"]), "学生", t)
    # frame[] 标记
    subs = readSub(ass_path)
    for sub in subs:
        start = ms_to_frames(sub["start"], fps)
        end = ms_to_frames(sub["end"], fps) + 1
        if "文本" in sub["style"]:
            text = sub["text"]
            cnt = 1
            s = ""
            # 打字机效果
            for word in text:
                s = s+"{\\1a&HFF&\\3a&HFF&\\4a&HFF&}{\\t("+str(cnt*33)+"," \
                    + str(cnt*33+1)+",\\1a&H00&\\3a&H00&\\4a&H00&)}"+word
                if cnt % axis["line_num"] == 0:  # 每行 35 字换行
                    s += "\\N{\\fs 0}\\N"
                cnt += 1
            sub["text"] = ("{\\fad(0,500)}" if "fadeout" in sub["style"] else "") + s
            for i in range(start, end):
                frame[i].append("文本")
            if "fadeout" in sub["style"]:
                for i in range(end-45, end):
                    frame[i].remove("文本")
                    frame[i].append("文本-fadeout")
                    if "学生" in frame[i]:
                        frame[i].remove("学生")
                        frame[i].append("学生-fadeout")
        elif "标题" in sub["style"]:
            sub["text"] = "{\\fad(500,500)}" + sub["text"]
            for i in range(start, end):
                frame[i].append(sub["style"])
        elif sub["style"] == "地点":
            sub["text"] = "{\\fad(200,200)}" + sub["text"]
            for i in range(start, start+25):
                frame[i].append("地点-fadeout")
            for i in range(start+25, end-25):
                frame[i].append("地点")
            for i in range(end-25, end):
                frame[i].append("地点-fadeout")
        else:
            for i in range(start, end):
                frame[i].append(sub["style"])
    out_ass_path = os.path.join(path, filename+"_out.ass")
    saveSub(out_ass_path, ass_path, subs)


def run():
    global axis, frame, filename, num, length, path, fps, temp_path, bar
    file = input("请拖入视频文件：")
    path, filename = os.path.split(os.path.normpath(file))
    filename, ext = os.path.splitext(os.path.normpath(filename))
    if ext != '.mp4':
        raise TypeError("推荐使用 mp4 格式")
    print("--------初始化开始--------")
    cap = VideoCapture(file)
    length = int(cap.get(CAP_PROP_FRAME_COUNT))
    fps = cap.get(CAP_PROP_FPS)
    fourcc = VideoWriter_fourcc(*'mp4v')
    width = int(cap.get(3))
    height = int(cap.get(4))
    print("""\
filename: {filename}.mp4
fps:      {fps}
frames:   {frames}
frame size: {width}*{height}
""".format(filename=filename, fps=fps, frames=length, width=width, height=height))

    temp_path = os.path.join(path, "temp")
    if not os.path.exists(temp_path):
        os.makedirs(temp_path)
        print('create filefolder：', temp_path)

    readAxis()
    readAss()
    print("--------初始化结束--------")

    # 多线程-预处理切分
    num = axis["part_frame_num"]  # 每num帧切片
    i = -1
    with alive_bar(length, title="preprocess") as bar:
        while True:
            i += 1
            ret, img = cap.read()
            if not ret:
                break
            if i % num == 0:
                p = os.path.join(temp_path, f"part_{int(i/num)}.mp4")
                out = VideoWriter(p, fourcc, fps, (width, height))
            out.write(img)
            bar()
    cap.release()
    out.release()

    cnt = -1 * (-i // num)  # i/num向上取整
    with open("./temp/list.txt", "a") as f:
        for i in range(0, cnt):
            f.write(f"file part_{i}_out.mp4\n")

    thread_list = []
    with alive_bar(cnt, title="thread") as bar:
        for i in range(0, cnt):
            thread = Thread(target=work, args=[i])
            thread.start()
            thread_list.append(thread)
        for t in thread_list:
            t.join()

    # 按list合并 -> concat.mp4 
    # concat.mp4 + filename.mp4 -> output.mp4
    # output.mp4 + filename_out.ass -> final.mp4
    list_path = os.path.join(temp_path, "list.txt")
    concat_path = os.path.join(temp_path, "concat.mp4")
    output_path = os.path.join(path, filename+"_out.mp4")
    output_ass = os.path.join(path, filename+"_out.ass")
    finall_path = os.path.join(path, filename+"_final.mp4")
    os.system(f"ffmpeg -f concat -safe 0 -i {list_path} -c copy {concat_path}")
    os.system(f"ffmpeg -i {concat_path} -i {file}  -c copy -map 0 -map 1:1 -y -shortest {output_path}")
    os.system(f"ffmpeg -i {output_path} -vf subtitles={output_ass} {finall_path}")
    # os.system(f"rd/s/q {temp_path} && del {output_ass} {output_path}")
    input("Press Enter To Exit")


def work(start):
    # 多线程-任务
    global num, axis, temp_path, bar
    video_path = os.path.join(temp_path, f"part_{start}.mp4")
    cap = VideoCapture(video_path)
    fps = cap.get(CAP_PROP_FPS)
    fourcc = VideoWriter_fourcc(*'mp4v')
    width = int(cap.get(3))
    height = int(cap.get(4))
    out = VideoWriter("./temp/part_"+str(start)+"_out.mp4",
                      fourcc, fps, (width, height))
    print("start threading "+str(start))

    for i in range(start*num, (start+1)*num):
        ret, img = cap.read()
        if ret:
            for style in frame[i]:
                if "fadeout" in style:
                    style = style[:-8]
                    y1, x1, y2, x2 = axis[style][0], axis[style][1], axis[style][2], axis[style][3]
                    Inpainting(img, x1, y1, x2, y2, "fadeout", kernelSize=9)
                elif style in axis:
                    y1, x1, y2, x2 = axis[style][0], axis[style][1], axis[style][2], axis[style][3]
                    Inpainting(img, x1, y1, x2, y2, style, kernelSize=9)
                
            out.write(img)
        else:
            break
    cap.release()
    out.release()
    print("finish threading "+str(start))
    bar()


if __name__ == "__main__":
    run()