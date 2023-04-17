import json
import os
from threading import Thread

from alive_progress import alive_bar
from cv2 import (CAP_PROP_FPS, CAP_PROP_FRAME_COUNT, CAP_PROP_FRAME_HEIGHT,
                 CAP_PROP_FRAME_WIDTH, THRESH_BINARY, VideoCapture, imwrite,
                 threshold)

from modules.CallingOCR import CallingOCR  # OCR调用接口
from modules.subUtils import insertSub

filename = ""
path = ""
fps = 0
start, end = 0, 0
ocr = None
frame, last_frame = None, None
text, name, text_area = None, None, None

def check(img1, img2=None):
    if(img2 is None):  # 有字幕
        if (img1 ** 2).sum() / img1.size * 100 > 1:
            return True
    else:  # 字幕变化
        if ((img2 - img1) ** 2).sum() / img1.size * 100 > 1:
            return True
    return False


# 名字出现
def check_name_appear(last_frame, frame):
    return check(nameImg(last_frame), nameImg(frame)) and not check(nameImg(last_frame)) and check(nameImg(frame))
# 文本消失
def check_text_disappear(last_frame, frame):
    return check(textImg(last_frame), textImg(frame)) and check(textImg(last_frame)) and not check(textImg(frame))
# 名字改变
def check_name_change(last_frame, frame):
    return check(nameImg(last_frame), nameImg(frame)) and check(nameImg(last_frame)) and check(nameImg(frame))
# 文本出现
def check_text_appear(last_frame, frame):
    return check(textImg(last_frame), textImg(frame)) and not check(textImg(last_frame)) and check(textImg(frame))

# 截取文本区域
def textImg(frame):
    _, img = threshold(frame[:, :, 0][text[1]:text[3],text[0]:text[2]], 145, 255, THRESH_BINARY)
    return img
# 截取名字区域
def nameImg(frame):
    _, img = threshold(frame[:, :, 0][name[0]:name[1],:], 145, 255, THRESH_BINARY)
    return img

def func(last_frame, start, end, id):
    global filename, path, ocr, fps
    
    img_path = f".\\tmp\\{id}.jpg"
    imwrite(img_path, last_frame[text_area[0]:text_area[1]])
    oget = ocr.run(os.path.abspath(img_path))  # 调用图片识别
    if oget['code'] == 100:  # 成功
        dataStr = ""
        for i in oget['data']:
            dataStr += i["text"]
        print("%d - %d: %s" % (start, end-1, dataStr))
        insertSub(os.path.join(path, filename+".ass"), fps, start, end, dataStr)
    os.remove(img_path)
    

def run(file=None):
    global filename, fps, text, name, text_area, last_frame, frame, ocr, start, end, path
    if not file:
        file = input("请拖入视频文件：")
    path, filename = os.path.split(os.path.normpath(file))
    filename, ext = os.path.splitext(os.path.normpath(filename))
    if ext != '.mp4':
        raise TypeError("推荐使用 mp4 格式")
    # filename = "白子Momotalk-1"

    print("--------初始化开始--------")
    videoCap = VideoCapture(file)
    fps = videoCap.get(CAP_PROP_FPS)  # 帧频
    total_frames = int(videoCap.get(CAP_PROP_FRAME_COUNT))  # 视频总帧数
    width = int(videoCap.get(CAP_PROP_FRAME_WIDTH))
    height = int(videoCap.get(CAP_PROP_FRAME_HEIGHT))  # 图像尺寸
    print("""\
filename: {filename}.mp4
fps:      {fps}
frames:   {frames}
frame size: {width}*{height}
""".format(filename=filename, fps=fps, frames=total_frames, width=width, height=height))

    print("import 样式.ass")
    if os.path.isfile(".\\modules\\样式.ass"):
        STYLE_FILE = open(".\\modules\\样式.ass", 
            encoding='utf-8').read().format(filename=file, width=width, height=height)
    else:
        print("样式.ass does not exist")
        STYLE_FILE = open(input("请拖入样式"), encoding='utf-8').read()
        try:
            STYLE_FILE = STYLE_FILE.format(
                filename=file, width=width, height=height)
        except Exception:
            print("Does not seem to be a standard template style file.")

    print("import config:")
    if not os.path.isfile(".\\modules\\config.json"):
        raise IOError("config.json does not exist.")
    with open(".\\modules\\config.json", "r", encoding='utf-8') as fp:
        data = fp.read()
        data = json.loads(data)
        text = data["data"][1]["text"]
        name = data["data"][1]["name"]
        text_area = data["data"][1]["text_area"]
        print(data["data"][1])

    print("\ncreate ass file:"+os.path.join(path, filename+".ass"))
    with open(os.path.join(path, filename+".ass"), "w", encoding='utf-8') as fp:
        fp.write(STYLE_FILE)

    ocrToolPath = ".\\modules\\PaddleOCR-json\\PaddleOCR_json.exe"  # 识别器路径
    configPath = "PaddleOCR_json_config_日文.txt"  # 配置文件路径
    ocr = CallingOCR(ocrToolPath, configPath)
    print("load ocr tool success")
    cnt = 0  # 当前帧数
    ret, last_frame = videoCap.read()
    start, end = 0, 0
    print("--------初始化结束--------")

    with alive_bar(total_frames-1, title="progress") as bar:
        while True:
            ret, frame = videoCap.read()
            cnt += 1
            if not ret:
                break
            if(
                check_name_appear(last_frame, frame) or
                check_text_disappear(last_frame, frame) or
                check_name_change(last_frame, frame)
            ):
                end = cnt
                if end-start > 15 and start != 0:
                    t1 = Thread(target=func, args=(last_frame, start, end, cnt-1))
                    t1.start()
                    t1.join()
                start = cnt
            if check_text_appear(last_frame, frame) and cnt - start >= 10:
                start = cnt
            last_frame = frame
            bar()
    videoCap.release()
    print('\n˙◡˙ video: %s finished at %dth frame.\n' % (filename, cnt))

if __name__ == "__main__":
    run()
