import cv2
import math
import numpy as np
import os

from script.RapidOCR_api import OcrAPI


class Inpainter:
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
        res = self.ocr.runBytes(self._cv2bytes(img))
        # self.ocr.printResult(res)

        for box in res["data"]:
            x0, y0 = box["box"][0]
            x1, y1 = box["box"][1]
            x2, y2 = box["box"][2]
            x3, y3 = box["box"][3]

            x_mid0, y_mid0 = self._midpoint(x1, y1, x2, y2)
            x_mid1, y_mi1 = self._midpoint(x0, y0, x3, y3)
            thickness = int(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))

            mask = np.zeros(img.shape[:2], dtype="uint8")
            cv2.line(mask, (x_mid0, y_mid0), (x_mid1, y_mi1), 255, thickness)
            img = cv2.inpaint(img, mask, 7, cv2.INPAINT_NS)

        return img
