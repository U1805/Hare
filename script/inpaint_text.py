import cv2
import numpy as np


class Inpainter:
    def __init__(
        self,
        method="INPAINT_NS",
        contour_area: int = 0,
        dilate_kernal_size: int = 5,
        x_offset: int = 0,
        y_offset: int = 0,
    ) -> None:
        global lama
        if method not in [
            "MASK",
            "INPAINT_NS",
            "INPAINT_TELEA",
            "INPAINT_FSR_FAST",
            "INPAINT_FSR_BEST",
        ]:
            raise ValueError(
                f"Invalid method: {method}. Method must be in ['INPAINT_NS','INPAINT_TELEA','INPAINT_FSR_FAST','INPAINT_FSR_BEST']."
            )

        self.method = method
        self.contour_area = contour_area
        self.dilate_kernal_size = dilate_kernal_size
        self.x_offset = x_offset  # 向右偏移的像素数
        self.y_offset = y_offset  # 向下偏移的像素数

    def check_contour(self, contour):
        # _, _, w, h = cv2.boundingRect(contour)
        # aspect_ratio = w / float(h)
        # if 0.2 < aspect_ratio < 5: # 文字的长宽比
        #     return True

        area = cv2.contourArea(contour)
        if area > self.contour_area:  # 面积
            return True

        # perimeter = cv2.arcLength(contour, True)
        # circularity = 4 * np.pi * (area / (perimeter * perimeter + 1e-6))
        # if 0 < circularity < 1.2:  # 圆度
        #     return True

        return False

    def create_mask(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

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

        mask = np.zeros_like(gray)

        # 过滤和绘制符合文字特征的轮廓
        for contour in contours:
            if self.check_contour(contour):
                cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)

        kernel = np.ones((self.dilate_kernal_size, self.dilate_kernal_size), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

        # 偏移结果
        shifted_mask = np.zeros_like(mask)
        height, width = mask.shape

        if self.x_offset >= 0 and self.y_offset >= 0:  # 右下偏移
            shifted_mask[self.y_offset :, self.x_offset :] = mask[
                : height - self.y_offset, : width - self.x_offset
            ]
        elif self.x_offset >= 0 and self.y_offset < 0:  # 右上偏移
            shifted_mask[: height + self.y_offset, self.x_offset :] = mask[
                -self.y_offset :, : width - self.x_offset
            ]
        elif self.x_offset < 0 and self.y_offset >= 0:  # 左下偏移
            shifted_mask[self.y_offset :, : width + self.x_offset] = mask[
                : height - self.y_offset, -self.x_offset :
            ]
        else:  # 左上偏移
            shifted_mask[: height + self.y_offset, : width + self.x_offset] = mask[
                -self.y_offset :, -self.x_offset :
            ]

        return shifted_mask

    def inpaint_text(self, img):
        src = img.copy()
        mask = self.create_mask(src)

        # 图像修复
        if self.method == "MASK":
            image = cv2.cvtColor(src, cv2.COLOR_BGR2BGRA)
            overlay = np.zeros_like(image, dtype=np.uint8)
            overlay[mask != 0] = [0, 0, 255, 150]  # 红色 (RGBA)
            overlay[mask == 0, 3] = 0
            alpha_channel = overlay[:, :, 3] / 255.0
            alpha_inv = 1.0 - alpha_channel

            for c in range(0, 3):
                image[:, :, c] = (
                    alpha_channel * overlay[:, :, c] + alpha_inv * image[:, :, c]
                )
            masked_img = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

            return masked_img

        elif self.method == "INPAINT_FSR_FAST":
            mask1 = cv2.bitwise_not(mask)
            distort = cv2.bitwise_and(src, src, mask=mask1)
            inpaintImg = src.copy()
            cv2.xphoto.inpaint(distort, mask1, inpaintImg, cv2.xphoto.INPAINT_FSR_FAST)
            return inpaintImg

        elif self.method == "INPAINT_FSR_BEST":
            mask1 = cv2.bitwise_not(mask)
            distort = cv2.bitwise_and(src, src, mask=mask1)
            inpaintImg = src.copy()
            cv2.xphoto.inpaint(distort, mask1, inpaintImg, cv2.xphoto.INPAINT_FSR_BEST)
            return inpaintImg

        elif self.method == "INPAINT_TELEA":
            inpaintImg = cv2.inpaint(src, mask, 3, cv2.INPAINT_TELEA)
            return inpaintImg

        elif self.method == "INPAINT_NS":
            inpaintImg = cv2.inpaint(src, mask, 3, cv2.INPAINT_NS)
            return inpaintImg
