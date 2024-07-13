import os
import cv2
import numpy as np
import onnxruntime


def get_image(image):
    if isinstance(image, np.ndarray):
        img = image.copy()
    else:
        raise Exception("Input image should be numpy array!")

    if img.ndim == 3:
        img = np.transpose(img, (2, 0, 1))  # chw
    elif img.ndim == 2:
        img = img[np.newaxis, ...]

    assert img.ndim == 3

    img = img.astype(np.float32) / 255
    return img


def ceil_modulo(x, mod):
    if x % mod == 0:
        return x
    return (x // mod + 1) * mod


def scale_image(img, factor, interpolation=cv2.INTER_AREA):
    if img.shape[0] == 1:
        img = img[0]
    else:
        img = np.transpose(img, (1, 2, 0))

    img = cv2.resize(img, dsize=None, fx=factor, fy=factor, interpolation=interpolation)

    if img.ndim == 2:
        img = img[None, ...]
    else:
        img = np.transpose(img, (2, 0, 1))
    return img


def pad_img_to_modulo(img, mod):
    channels, height, width = img.shape
    out_height = ceil_modulo(height, mod)
    out_width = ceil_modulo(width, mod)
    return np.pad(
        img,
        ((0, 0), (0, out_height - height), (0, out_width - width)),
        mode="symmetric",
    )


def prepare_img_and_mask(image, mask, pad_out_to_modulo=8, scale_factor=None):
    out_image = get_image(image)
    out_mask = get_image(mask)

    if scale_factor is not None:
        out_image = scale_image(out_image, scale_factor)
        out_mask = scale_image(out_mask, scale_factor, interpolation=cv2.INTER_NEAREST)

    if pad_out_to_modulo is not None and pad_out_to_modulo > 1:
        out_image = pad_img_to_modulo(out_image, pad_out_to_modulo)
        out_mask = pad_img_to_modulo(out_mask, pad_out_to_modulo)

    out_mask = (out_mask > 0).astype(np.float32) * 1

    return out_image, out_mask


class SimpleLama:
    def __init__(self, model_path="lama_fp32.onnx") -> None:

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"lama model not found: {model_path}\nplease download from https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx?download=true"
            )

        # 使用 ONNX Runtime 加载模型
        sess_options = onnxruntime.SessionOptions()
        self.model = onnxruntime.InferenceSession(model_path, sess_options=sess_options)

    def __call__(self, image, mask):
        # 检查输入
        if not isinstance(image, np.ndarray) or not isinstance(mask, np.ndarray):
            raise ValueError("Input image and mask should be numpy arrays")

        if image.shape[:2] != mask.shape[:2]:
            raise ValueError("Input image and mask should have the same dimensions")

        original_size = (image.shape[1], image.shape[0])  # (width, height)
        resized_image = cv2.resize(image, (512, 512))
        resized_mask = cv2.resize(mask, (512, 512))
        image, mask = prepare_img_and_mask(resized_image, resized_mask)

        outputs = self.model.run(
            None,
            {
                "image": image[np.newaxis, ...].astype(np.float32),
                "mask": mask[np.newaxis, ...].astype(np.float32),
            },
        )
        output = outputs[0][0]

        output = output.transpose(1, 2, 0)
        output = output.astype(np.uint8)

        # 将输出图像调整为原图尺寸
        cur_res = cv2.resize(output, original_size)
        return cur_res
