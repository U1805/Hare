import os
import subprocess

import cv2
import numpy as np
import torch


def get_image(image):
    img = image.copy()

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


def prepare_img_and_mask(image, mask, device, pad_out_to_modulo=8, scale_factor=None):
    out_image = get_image(image)
    out_mask = get_image(mask)

    if scale_factor is not None:
        out_image = scale_image(out_image, scale_factor)
        out_mask = scale_image(out_mask, scale_factor, interpolation=cv2.INTER_NEAREST)

    if pad_out_to_modulo is not None and pad_out_to_modulo > 1:
        out_image = pad_img_to_modulo(out_image, pad_out_to_modulo)
        out_mask = pad_img_to_modulo(out_mask, pad_out_to_modulo)

    out_image = torch.from_numpy(out_image).unsqueeze(0).to(device)
    out_mask = torch.from_numpy(out_mask).unsqueeze(0).to(device)

    out_mask = (out_mask > 0) * 1

    return out_image, out_mask


def run_command(command, status_message):
    """Runs a command and shows terminal window"""
    print(status_message)
    # Show terminal window when running pip commands
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags &= ~subprocess.STARTF_USESHOWWINDOW
    process = subprocess.Popen(
        command,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    process.wait()


def download_model():
    model_url = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
    accelerated_urls = ["https://gh.llkk.cc/", "https://github.moeyy.xyz/"]
    get_model_path = "big-lama.pt"

    # 尝试加速 URL
    for url in accelerated_urls:
        try:
            command = ["curl", "-L", "-o", get_model_path, url + model_url]
            run_command(command, f"尝试从 {url} 下载模型...")
            print("下载成功!")
            return
        except Exception as e:
            print(f"从 {url} 下载失败: {e}")
    # 如果所有加速链接都失败，使用原始链接
    try:
        command = ["curl", "-L", "-o", get_model_path, model_url]
        run_command(command, f"尝试从原始 URL 下载模型...")
        print("下载成功!")
    except Exception as e:
        print(f"从原始 URL 下载失败: {e}")


class SimpleLama:
    def __init__(self, model_path="big-lama.pt") -> None:

        if not os.path.exists(model_path):
            try:
                download_model()
            except:
                raise FileNotFoundError(
                    f"lama model not found: {model_path}\nplease download from https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
                )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = torch.jit.load(model_path, map_location=device)
        self.model.eval()
        self.model.to(device)
        self.device = device

    def __call__(self, image, mask):
        image, mask = prepare_img_and_mask(image, mask, self.device)

        with torch.inference_mode():
            inpainted = self.model(image, mask)

            cur_res = inpainted[0].permute(1, 2, 0).detach().cpu().numpy()
            cur_res = np.clip(cur_res * 255, 0, 255).astype(np.uint8)
            return cur_res
