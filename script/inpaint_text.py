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
        dilate_kernal_size: int = 5,
    ) -> None:
        if method not in ["lama", "opencv", "test"]:
            raise ValueError(
                f"Invalid method: {method}. Method must be 'lama' or 'opencv'."
            )

        self.method = method
        self.contour_area = contour_area
        self.dilate_kernal_size = dilate_kernal_size
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

        # 将图像转换为灰度图
        gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)

        # 使用高斯模糊减少噪声
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # 使用Sobel算子进行梯度检测
        grad_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        gradient = cv2.addWeighted(
            cv2.convertScaleAbs(grad_x), 0.5, cv2.convertScaleAbs(grad_y), 0.5, 0
        )

        # 使用Otsu阈值进行二值化
        _, binary = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 使用闭操作去除噪声, 使用开操作去除细小噪声
        kernel = np.ones((2, 2), np.uint8)
        morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel)

        # 查找轮廓
        contours, _ = cv2.findContours(
            morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # 创建一个空白图像用于绘制掩码
        mask = np.zeros_like(gray)

        # 过滤和绘制符合文字特征的轮廓
        for contour in contours:
            _, _, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h)
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * np.pi * (area / (perimeter * perimeter + 1e-6))
            if (
                0.2 < aspect_ratio < 5  # 文字的长宽比
                and area > self.contour_area  # 面积
                and 0 < circularity < 1.2  # 圆度
            ):
                cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)

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
            inpaintImg = cv2.inpaint(src, mask, 3, cv2.INPAINT_NS)
            return inpaintImg
