import cv2
import numpy as np
import os

from simple_lama_inpainting import SimpleLama

os.environ["LAMA_MODEL"] = "./big-lama.pt"


class Inpainter:
    def __init__(
        self,
        method="opencv",
        contour_area: int = 0,
        dilate_kernal_size: int = 35,
        text_color: str = None,
        color_tolerance: int = None,
    ) -> None:
        if method not in ["lama", "opencv", "test"]:
            raise ValueError(
                f"Invalid method: {method}. Method must be 'lama' or 'opencv'."
            )

        self.method = method
        self.contour_area = contour_area
        self.dilate_kernal_size = dilate_kernal_size
        self.text_color = text_color
        self.color_tolerance = color_tolerance
        self.simple_lama = SimpleLama()

    def _hex_to_rgb(self, hex_string):
        # 去掉开头的 '#'
        hex_string = hex_string.lstrip("#")

        # 拆分成三个部分：每两个字符表示一个颜色通道
        r = int(hex_string[0:2], 16)
        g = int(hex_string[2:4], 16)
        b = int(hex_string[4:6], 16)

        # 返回 NumPy 数组
        return np.array([r, g, b])

    def inpaint_text(self, img):
        src = img.copy()

        gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
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

        # Color filtering to detect white text 根据字体颜色过滤代替侵蚀
        if self.text_color:
            text_color_hex = self._hex_to_rgb("#6E6C6D")
            color_tolerance = np.array(
                [self.color_tolerance, self.color_tolerance, self.color_tolerance]
            )
            lower_bound = text_color_hex - color_tolerance
            upper_bound = text_color_hex + color_tolerance
            mask_color = cv2.inRange(src, lower_bound, upper_bound)
            mask = cv2.bitwise_and(mask, mask, mask=mask_color)

        kernel = np.ones((self.dilate_kernal_size, self.dilate_kernal_size), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

        if self.method == "test":  # 测试代码
            masked_img = cv2.bitwise_and(src, src, mask=mask)
            return masked_img
        if self.method == "lama":
            inpaintImg = self.simple_lama(src, mask)
            # ValueError: could not broadcast input array from shape (200,472,3) into shape (196,470,3)
            inpaintImg = inpaintImg[: src.shape[0], : src.shape[1]]
            return inpaintImg
        elif self.method == "opencv":
            inpaintImg = cv2.inpaint(src, mask, 7, cv2.INPAINT_NS)
            return inpaintImg
