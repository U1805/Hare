from typing import Tuple

import cv2
import numpy as np


def create_mask(
    img: np.ndarray,
    dilate_kernal_size: int,
    x_offset: int = -2,
    y_offset: int = -2,
    binary: bool = True,
) -> np.ndarray:
    _, width = img.shape[:2]

    # Guardian Line
    src_mirrored = cv2.flip(img, 1)
    combined = np.hstack((img, src_mirrored))
    colors = [[250, 250, 250], [5, 5, 5]] if binary else []
    add_text_to_image(combined, width, colors)

    # 形态学掩码
    mask_morph, black_font = create_mask_morph(
        combined, dilate_kernal_size, x_offset, y_offset
    )
    if black_font:
        combined = cv2.bitwise_not(combined)
    img_masked = cv2.bitwise_and(combined, combined, mask=mask_morph)

    # 色彩空间掩码
    mask_color = create_mask_color(img_masked, dilate_kernal_size, x_offset, y_offset)
    result_mask = cv2.bitwise_and(mask_morph, mask_morph, mask=mask_color)
    result_mask = result_mask[:, :width]

    return result_mask


def create_mask_morph(
    img: np.ndarray,
    dilate_kernal_size: int,
    x_offset: int = -2,
    y_offset: int = -2,
) -> Tuple[np.ndarray, bool]:
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
    contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(binary)
    cv2.drawContours(mask, contours, -1, 255, thickness=cv2.FILLED)

    kernel = np.ones((dilate_kernal_size, dilate_kernal_size), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    mask = move_mask(mask, x_offset=x_offset, y_offset=y_offset)

    # 判断文字黑白
    if mask.any():
        pixel_mean = np.sum(gray * (mask > 0)) / np.count_nonzero(mask)
        gray_mean = np.mean(gray)
        black_font = pixel_mean < gray_mean
    else:
        black_font = False
    return mask, black_font


def create_mask_color(
    img: np.ndarray,
    dilate_kernal_size: int,
    x_offset: int = -2,
    y_offset: int = -2,
) -> np.ndarray:
    # 转换到 HSV 颜色空间
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    _, _, v = cv2.split(hsv)

    # 使用亮度通道进行阈值分割
    _, binary_v = cv2.threshold(v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 使用形态学操作去除线条和噪声
    kernel = np.ones((2, 2), np.uint8)
    morph = cv2.morphologyEx(binary_v, cv2.MORPH_CLOSE, kernel)
    morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel)

    # 查找轮廓
    contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(v)
    cv2.drawContours(mask, contours, -1, 255, thickness=cv2.FILLED)

    kernel = np.ones((dilate_kernal_size + 10, dilate_kernal_size + 10), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    mask = move_mask(mask, x_offset=x_offset, y_offset=y_offset)
    return mask


def move_mask(
    mask: np.ndarray,
    x_offset: int = -2,
    y_offset: int = -2,
) -> np.ndarray:
    # 偏移结果
    shifted_mask = np.zeros_like(mask)
    height, width = mask.shape

    if x_offset >= 0 and y_offset >= 0:  # 右下偏移
        shifted_mask[y_offset:, x_offset:] = mask[
            : height - y_offset, : width - x_offset
        ]
    elif x_offset >= 0 and y_offset < 0:  # 右上偏移
        shifted_mask[: height + y_offset, x_offset:] = mask[
            -y_offset:, : width - x_offset
        ]
    elif x_offset < 0 and y_offset >= 0:  # 左下偏移
        shifted_mask[y_offset:, : width + x_offset] = mask[
            : height - y_offset, -x_offset:
        ]
    else:  # 左上偏移
        shifted_mask[: height + y_offset, : width + x_offset] = mask[
            -y_offset:, -x_offset:
        ]
    return shifted_mask


def shift_expand_mask(
    mask: np.ndarray, up: int = 0, down: int = 0, right: int = 0, left: int = 0
) -> np.ndarray:
    if up + down + right + left == 0:
        return mask

    height, width = mask.shape[:2]
    expanded_mask = np.zeros_like(mask)
    mask_indices = np.argwhere(mask > 0)
    for row, col in mask_indices:
        start_row = max(row - up, 0)
        end_row = min(row + down + 1, height)
        start_col = max(col - left, 0)
        end_col = min(col + right + 1, width)
        expanded_mask[start_row:end_row, start_col:end_col] = 255

    return expanded_mask


def add_text_to_image(image: np.ndarray, width: int, colors) -> None:
    # fmt: off
    text = "ABCDEFGHIJKLM" 
    char_width = 30
    for i, char in enumerate(text, 1):
        for ii, color in enumerate(colors, 1):
            position = (width + i * char_width, char_width * ii) 
            cv2.putText(image, char, position, cv2.FONT_HERSHEY_SIMPLEX, \
                1, color, 10, cv2.LINE_AA)
    # fmt: on
