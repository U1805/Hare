import json
import os
from collections.abc import Iterable
from threading import Thread

import gradio as gr
from alive_progress import alive_bar
from cv2 import (CAP_PROP_FPS, CAP_PROP_FRAME_COUNT, CAP_PROP_FRAME_HEIGHT,
                 CAP_PROP_FRAME_WIDTH, VideoCapture, imwrite)

from modules.CallingOCR import CallingOCR  # OCR调用接口
from modules.subUtils import insertSub_2 as insertSub
from modules.subUtils import modifyLastEnd

# from skimage.metrics import mean_squared_error


filename = ""
frame, last_frame = None, None
start, end = 0, 0
text, name, text_area = None, None, None
fps = 0
path = ""
ocr = None
result_text = ""
fill = ""
sentence = ""

from numpy import (asarray, complex64, complex128, dtype, float16, float32,
                   float64, mean, result_type)

new_float_type = {
    float32().dtype.char: float32,
    float64().dtype.char: float64,
    complex64().dtype.char: complex64,
    complex128().dtype.char: complex128,
    float16().dtype.char: float32,
    'g': float64,      # np.float128 ; doesn't exist on windows
    'G': complex128,   # np.complex256 ; doesn't exist on windows
}

def _supported_float_type(input_dtype, allow_complex=False):
    if isinstance(input_dtype, Iterable) and not isinstance(input_dtype, str):
        return result_type(*(_supported_float_type(d) for d in input_dtype))
    input_dtype = dtype(input_dtype)
    if not allow_complex and input_dtype.kind == 'c':
        raise ValueError("complex valued input is not supported")
    return new_float_type.get(input_dtype.char, float64)

def check_shape_equality(*images):
    image0 = images[0]
    if not all(image0.shape == image.shape for image in images[1:]):
        raise ValueError('Input images must have the same dimensions.')
    return

def _as_floats(image0, image1):
    float_type = _supported_float_type([image0.dtype, image1.dtype])
    image0 = asarray(image0, dtype=float_type)
    image1 = asarray(image1, dtype=float_type)
    return image0, image1

def mean_squared_error(image0, image1):
    check_shape_equality(image0, image1)
    image0, image1 = _as_floats(image0, image1)
    return mean((image0 - image1) ** 2, dtype=float64)

# 字幕变化
def check(img1, img2=None):     
    return mean_squared_error(img2, img1) > 1000

# 截取文本区域
def textImg(frame):
    return frame[text[1]:text[3],text[0]:text[2]]

import difflib


def func(last_frame, start, end, id):
    global filename, path, ocr, text_area, fps, sentence, result_text
    img_path = f".\\tmp\\{id}.jpg"
    imwrite(img_path, last_frame[text_area[0]:text_area[1]])
    oget = ocr.run(os.path.abspath(img_path))  # 调用图片识别
    if oget['code'] == 100:  # 成功
        dataStr = ""
        for i in oget['data']:
            dataStr += i["text"]
        print("%d - %d: %s" % (start, end-1, dataStr))
        result_text += dataStr+"\n"
        if difflib.SequenceMatcher(None, sentence,dataStr).ratio() > 0.75:
            modifyLastEnd(os.path.join(path, filename+".ass"), fps, end)
        else:
            if fill:
                insertSub(os.path.join(".\\output", filename+".ass"), fps, start, end, dataStr)
            else:
                insertSub(os.path.join(".\\output", filename+".ass"), fps, start, end, "")
        sentence = dataStr
    os.remove(img_path)


def run(file, video_size, video_type, fill_):
    global filename, fps, text, name, text_area, last_frame, frame, ocr, start, end, path, fill, result_text
    result_text = ""
    fill = fill_
    path, filename = os.path.split(os.path.normpath(file))
    filename, ext = os.path.splitext(os.path.normpath(filename))
    if file == "":
        raise gr.Error("没有选择文件")
    if ext != '.mp4':
        raise gr.Error("请使用 mp4 格式")

    # 初始化
    print("--------初始化开始--------")
    videoCap = VideoCapture(file)
    fps = videoCap.get(CAP_PROP_FPS)  # 帧频
    total_frames = int(videoCap.get(CAP_PROP_FRAME_COUNT))  # 视频总帧数
    width = int(videoCap.get(CAP_PROP_FRAME_WIDTH))
    height = int(videoCap.get(CAP_PROP_FRAME_HEIGHT))  # 图像尺寸
    if height!=int(video_size.split("*")[-1]) or width!=int(video_size.split("*")[0]):
        raise gr.Error("请正确选择视频分辨率")
    style = str(min(int(video_size.split("*")[-1]), int(video_size.split("*")[0])))+"P"
    print("""\
filename: {filename}.mp4
fps:      {fps}
frames:   {frames}
frame size: {width}*{height}
""".format(filename=filename, fps=fps, frames=total_frames, width=width, height=height))

    print("import style.ass")
    if os.path.isfile(f".\\modules\\频道{style}.ass"):
        STYLE_FILE = open(
            f".\\modules\\频道{style}.ass", encoding='utf-8').read().format(filename=filename+".mp4", width=width, height=height)
    else:
        STYLE_FILE = open(
            f".\\modules\\默认样式.ass", encoding='utf-8').read()

    print("import config:")
    if not os.path.isfile(".\\modules\\config.json"):
        raise IOError("config.json does not exist.")
    with open(".\\modules\\config.json", "r", encoding='utf-8') as fp:
        data = fp.read()
        data = json.loads(data)
        for item in data["频道打轴"][video_type]:
            if item["size"]==video_size:
                text = item["text"]
                text_area = item["text_area"]
                print(item)
        if not text:
            raise gr.Error("没有符合的分辨率")

    # 如果没有文件夹，创建
    temp_path = os.path.abspath(os.path.join(".\\", "tmp"))
    if not os.path.exists(temp_path):
        os.makedirs(temp_path)
        print('create filefolder：', temp_path)
    output_path_ = os.path.abspath(os.path.join(".\\", "output"))
    if not os.path.exists(output_path_):
        os.makedirs(output_path_)
        print('create filefolder：', output_path_)
        
    print("\ncreate ass file:"+os.path.join(".\\output", filename+".ass"))
    with open(os.path.join(".\\output", filename+".ass"), "w", encoding='utf-8') as fp:
        fp.write(STYLE_FILE)

    ocrToolPath = ".\\modules\\PaddleOCR-json\\PaddleOCR_json.exe"  # 识别器路径
    configPath = "PaddleOCR_json_config_日文.txt"  # 配置文件路径
    ocr = CallingOCR(ocrToolPath, configPath)
    print("load ocr tool success")
    cnt = 0  # 当前帧数
    ret, last_frame = videoCap.read()
    start, end = 0, 0
    print("--------初始化结束--------")

    # 主体循环
    with alive_bar(total_frames-1, title="progress") as bar:
        while True:
            ret, frame = videoCap.read()
            cnt += 1
            if not ret:
                break
            if (check(textImg(last_frame), textImg(frame))):
                end = cnt
                if end-start > 15 and start != 0:
                    t1 = Thread(target=func, args=(last_frame, start, end, cnt-1))
                    t1.start()
                    # t1.join()
                start = cnt
            last_frame = frame
            bar()
    videoCap.release()
    print('\n˙◡˙ video: %s finished at %dth frame.\n' % (filename, cnt))
    return os.path.join(".\\output", filename+".ass"), result_text