import json
import os
import difflib
from collections.abc import Iterable
from threading import Thread
from threading import BoundedSemaphore

from cv2 import (
    CAP_PROP_FPS,
    CAP_PROP_FRAME_COUNT,
    CAP_PROP_FRAME_HEIGHT,
    CAP_PROP_FRAME_WIDTH,
    VideoCapture,
    imwrite,
)

from RapidOCR_api import OcrAPI  # OCR调用接口
from subUtils import insertSub_2 as insertSub
from subUtils import modifyLastEnd


frame, last_frame = None, None
start, end = 0, 0
text = None
sentence = ""
result_text = ""


from numpy import (
    asarray,
    complex64,
    complex128,
    dtype,
    float16,
    float32,
    float64,
    mean,
    result_type,
)

new_float_type = {
    float32().dtype.char: float32,
    float64().dtype.char: float64,
    complex64().dtype.char: complex64,
    complex128().dtype.char: complex128,
    float16().dtype.char: float32,
    "g": float64,  # np.float128 ; doesn't exist on windows
    "G": complex128,  # np.complex256 ; doesn't exist on windows
}


def _supported_float_type(input_dtype, allow_complex=False):
    if isinstance(input_dtype, Iterable) and not isinstance(input_dtype, str):
        return result_type(*(_supported_float_type(d) for d in input_dtype))
    input_dtype = dtype(input_dtype)
    if not allow_complex and input_dtype.kind == "c":
        raise ValueError("complex valued input is not supported")
    return new_float_type.get(input_dtype.char, float64)


def check_shape_equality(*images):
    image0 = images[0]
    if not all(image0.shape == image.shape for image in images[1:]):
        raise ValueError("Input images must have the same dimensions.")
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
    return frame[text[1] : text[3], text[0] : text[2]]


def run(file, output_file, video_type, config, progress_callback):
    global text, last_frame, frame, start, end, result_text

    def func(last_frame, start, end, id):
        global sentence, result_text
        img_path = f".\\tmp\\{id}.jpg"
        imwrite(img_path, last_frame[text_area[0] : text_area[1]])
        oget = ocr.run(os.path.abspath(img_path))  # 调用图片识别
        if oget["code"] == 100:  # 成功
            dataStr = ""
            for i in oget["data"]:
                dataStr += i["text"]
            print("%d - %d: %s" % (start, end - 1, dataStr))
            result_text += dataStr + "\n"
            if difflib.SequenceMatcher(None, sentence, dataStr).ratio() > 0.75:
                modifyLastEnd(output_file, fps, end)
            else:
                insertSub(output_file, fps, start, end, dataStr)
            sentence = dataStr
        os.remove(img_path)
        progress_callback(id / total_frames * 100)

    _, filename = os.path.split(os.path.normpath(file))

    # 初始化
    print("--------初始化开始--------")
    videoCap = VideoCapture(file)
    fps = videoCap.get(CAP_PROP_FPS)  # 帧频
    total_frames = int(videoCap.get(CAP_PROP_FRAME_COUNT))  # 视频总帧数
    width = int(videoCap.get(CAP_PROP_FRAME_WIDTH))
    height = int(videoCap.get(CAP_PROP_FRAME_HEIGHT))  # 图像尺寸
    print(
        """\
filename: {filename}
fps:      {fps}
frames:   {frames}
frame size: {width}*{height}
""".format(
            filename=filename, fps=fps, frames=total_frames, width=width, height=height
        )
    )

    print("import style.ass")
    STYLE_FILE = (
        open("./site-packages/style.ass", encoding="utf-8")
        .read()
        .format(filename=filename, width=width, height=height)
    )
    text = config["text"]
    text_area = config["text_area"]
    print(f"import config: {text} {text_area}")

    # 如果没有文件夹，创建
    temp_path = "./tmp"
    if not os.path.exists(temp_path):
        os.makedirs(temp_path)
        print("create temp filefolder", temp_path)

    print("\ncreate output ass file")
    with open(output_file, "w", encoding="utf-8") as fp:
        fp.write(STYLE_FILE)

    ocrToolPath = "./site-packages/RapidOCR-json/RapidOCR-json.exe"  # 识别器路径
    configstr = "--cls=ch_ppocr_mobile_v2.0_cls_infer.onnx --det=ch_PP-OCRv3_det_infer.onnx --rec=rec_japan_PP-OCRv3_infer.onnx --keys=dict_japan.txt"
    ocr = OcrAPI(ocrToolPath, configstr)
    print("load ocr tool success")
    print("--------初始化结束--------")

    cnt = 0  # 当前帧数
    ret, last_frame = videoCap.read()
    start, end = 0, 0
    # 主体循环
    thread_list = []
    while True:
        ret, frame = videoCap.read()
        cnt += 1
        if not ret:
            break
        if check(textImg(last_frame), textImg(frame)):
            end = cnt
            if end - start > 15 and start != 0:
                t1 = Thread(target=func, args=(last_frame, start, end, cnt - 1))
                t1.start()
                thread_list.append(t1)
            start = cnt
        last_frame = frame
    for t in thread_list:
        t.join()

    progress_callback(100)
    os.rmdir(temp_path)
    videoCap.release()
    print("\n˙◡˙ video: %s finished at %dth frame.\n" % (filename, cnt))
