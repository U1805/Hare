import time

import cv2
import numpy as np

import fsr_parallel
import inpaint_mask as maskutil


class Inpainter:
    def __init__(
        self,
        method="INPAINT_NS",
        area_min: int = 0,
        area_max: int = 0,
        stroke: int = 0,
        x_offset: int = -2,
        y_offset: int = -2,
        up_expand: int = 0,
        down_expand: int = 0,
        left_expand: int = 0,
        right_expand: int = 0,
        autosub: int = 2000,
    ) -> None:
        global lama
        if method not in [
            "MASK",
            "AUTOSUB",
            "INPAINT_NS",
            "INPAINT_TELEA",
            "INPAINT_FSR_PARA",
            "INPAINT_FSR_FAST",
            "INPAINT_FSR_BEST",
        ]:
            raise ValueError(
                f"Invalid method: {method}. Method must be in \
['INPAINT_NS','INPAINT_TELEA',\
'INPAINT_FSR_PARA','INPAINT_FSR_FAST','INPAINT_FSR_BEST']."
            )

        self.method = method
        self.area_min = area_min
        self.area_max = area_max
        self.stroke = stroke
        self.dilate_kernal_size = self.stroke * 2 + 1
        # 掩码偏移
        self.x_offset = x_offset  # 向右偏移的像素数
        self.y_offset = y_offset  # 向下偏移的像素数
        # 掩码扩展
        self.up_expand = up_expand
        self.down_expand = down_expand
        self.left_expand = left_expand
        self.right_expand = right_expand
        # 打轴
        self.autosub = autosub

    def create_mask(self, img, binary):
        return maskutil.create_mask(
            img,
            self.dilate_kernal_size,
            self.area_max,
            self.area_min,
            self.x_offset,
            self.y_offset,
            binary,
        )

    def inpaint_text(self, img, binary=True):
        """识别文字区域并修复

        Args:
            img: 输入图像
            binary: True白色或黑色文字 False灰色文字

        Returns:
            已修复图像
        """
        src = img.copy()

        # 扩展边缘防止绿边
        h, w = src.shape[:2]
        src = cv2.copyMakeBorder(src, 10, 10, 10, 10, cv2.BORDER_REFLECT)

        mask = self.create_mask(src, binary)
        mask = maskutil.pad_expand_mask(
            mask, right=self.right_expand, left=self.left_expand
        )

        s = time.time()

        # 图像修复
        if self.method == "MASK" or self.method == "AUTOSUB":
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
            inpaintImg = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        elif self.method == "INPAINT_NS":
            inpaintImg = cv2.inpaint(src, mask, 3, cv2.INPAINT_NS)

        elif self.method == "INPAINT_TELEA":
            inpaintImg = cv2.inpaint(src, mask, 3, cv2.INPAINT_TELEA)

        elif self.method == "INPAINT_FSR_FAST":
            mask1 = cv2.bitwise_not(mask)
            distort = cv2.bitwise_and(src, src, mask=mask1)
            inpaintImg = src.copy()
            cv2.xphoto.inpaint(distort, mask1, inpaintImg, cv2.xphoto.INPAINT_FSR_FAST)

        elif self.method == "INPAINT_FSR_BEST":
            mask1 = cv2.bitwise_not(mask)
            distort = cv2.bitwise_and(src, src, mask=mask1)
            inpaintImg = src.copy()
            cv2.xphoto.inpaint(distort, mask1, inpaintImg, cv2.xphoto.INPAINT_FSR_BEST)

        elif self.method == "INPAINT_FSR_PARA":
            inpaintImg = fsr_parallel.fsr(src, mask)

        e = time.time()
        print("inpaint time:", e - s)  # inpaint time
        return inpaintImg[10 : h + 10, 10 : w + 10], mask[10 : h + 10, 10 : w + 10]
