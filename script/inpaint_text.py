import cv2
import math
import numpy as np
import os

from script.RapidOCR_api import OcrAPI
from simple_lama_inpainting import SimpleLama

os.environ["LAMA_MODEL"] = "./big-lama.pt"


class Inpainter:
    def __init__(
        self, contour_area=50, erode_kernal_size=7, dilate_kernal_size=25
    ) -> None:
        self.contour_area = contour_area
        self.erode_kernal_size = erode_kernal_size
        self.dilate_kernal_size = dilate_kernal_size
        self.simple_lama = SimpleLama()

    def inpaint_text(self, img):
        src = img.copy()

        gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )

        edges = cv2.Canny(thresh, 50, 150)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        mask = np.zeros_like(gray)

        for contour in contours:
            # 近似轮廓
            epsilon = 0.001 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # 根据轮廓面积过滤
            if cv2.contourArea(contour) > self.contour_area:
                cv2.drawContours(mask, [approx], -1, (255), thickness=cv2.FILLED)

        kernel = np.ones((self.erode_kernal_size, self.erode_kernal_size), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        kernel = np.ones((self.dilate_kernal_size, self.dilate_kernal_size), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)
        inpaintImg = self.simple_lama(src, mask)
        # ValueError: could not broadcast input array from shape (200,472,3) into shape (196,470,3)
        inpaintImg = inpaintImg[: src.shape[0], : src.shape[1]]
        return inpaintImg


class Inpainter2:
    def __init__(self, models="jp") -> None:
        self.model_args = {
            "chs_v3": {
                "name": "简体中文(V3)",
                "rec": "ch_PP-OCRv3_rec_infer.onnx",
                "keys": "dict_chinese.txt",
            },
            "chs_v4": {
                "name": "简体中文(V4)",
                "rec": "rec_ch_PP-OCRv4_infer.onnx",
                "keys": "dict_chinese.txt",
            },
            "en": {
                "name": "English",
                "rec": "rec_en_PP-OCRv3_infer.onnx",
                "keys": "dict_chinese.txt",
            },
            "cht": {
                "name": "繁體中文",
                "rec": "rec_chinese_cht_PP-OCRv3_infer.onnx",
                "keys": "dict_chinese_cht.txt",
            },
            "jp": {
                "name": "日本語",
                "rec": "rec_japan_PP-OCRv3_infer.onnx",
                "keys": "dict_japan.txt",
            },
            "kr": {
                "name": "한국어",
                "rec": "rec_korean_PP-OCRv3_infer.onnx",
                "keys": "dict_korean.txt",
            },
            "rs": {
                "name": "Русский",
                "rec": "rec_cyrillic_PP-OCRv3_infer.onnx",
                "keys": "dict_cyrillic.txt",
            },
        }

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.ocrPath = os.path.join(script_dir, "RapidOCR/RapidOCR-json.exe")
        self.ocr = OcrAPI(
            self.ocrPath,
            f"--rec={self.model_args[models]['rec']} \
              --keys={self.model_args[models]['keys']}",
        )

    def _cv2bytes(self, im):
        """cv2转二进制图片

        :param im: cv2图像，numpy.ndarray
        :return: 二进制图片数据，bytes
        """
        return np.array(cv2.imencode(".png", im)[1]).tobytes()

    def _midpoint(self, x1, y1, x2, y2):
        x_mid = int((x1 + x2) / 2)
        y_mid = int((y1 + y2) / 2)
        return (x_mid, y_mid)

    def inpaint_text(self, img):
        src = img.copy()
        res = self.ocr.runBytes(self._cv2bytes(src))
        # self.ocr.printResult(res)

        if res["code"] != 100:
            return src

        for box in res["data"]:
            x0, y0 = box["box"][0]
            x1, y1 = box["box"][1]
            x2, y2 = box["box"][2]
            x3, y3 = box["box"][3]

            x_mid0, y_mid0 = self._midpoint(x1, y1, x2, y2)
            x_mid1, y_mi1 = self._midpoint(x0, y0, x3, y3)
            thickness = int(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))

            mask = np.zeros(src.shape[:2], dtype="uint8")
            cv2.line(mask, (x_mid0, y_mid0), (x_mid1, y_mi1), 255, thickness)
            src = cv2.inpaint(src, mask, 7, cv2.INPAINT_NS)

        return src
