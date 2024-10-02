import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class SharedNDArray:
    def __init__(self, arr):
        self.arr = arr
        self.lock = threading.Lock()


def inpaint_block(args):
    shared_src, shared_mask, shared_result, y_start, y_end, x_start, x_end, overlap = (
        args
    )

    # Define extended region with overlap
    y_start_ext = max(0, y_start - overlap)
    y_end_ext = min(shared_src.arr.shape[0], y_end + overlap)
    x_start_ext = max(0, x_start - overlap)
    x_end_ext = min(shared_src.arr.shape[1], x_end + overlap)

    # Extract extended block from source and mask
    block = shared_src.arr[y_start_ext:y_end_ext, x_start_ext:x_end_ext]
    mask_block = shared_mask.arr[y_start_ext:y_end_ext, x_start_ext:x_end_ext]

    # Perform inpainting on the extended block
    cv2.xphoto.inpaint(block, mask_block, block, cv2.xphoto.INPAINT_FSR_FAST)

    # Calculate the actual overlap for trimming, especially near the edges
    y_overlap_top = y_start - y_start_ext
    y_overlap_bottom = y_end_ext - y_end
    x_overlap_left = x_start - x_start_ext
    x_overlap_right = x_end_ext - x_end

    # Insert the inpainted result back into the result array, trimming the overlap
    with shared_result.lock:
        shared_result.arr[y_start:y_end, x_start:x_end] = block[
            y_overlap_top : block.shape[0] - y_overlap_bottom,
            x_overlap_left : block.shape[1] - x_overlap_right,
        ]


def fsr(src, mask, num_threads=16, block_size=64, overlap=16):
    height, width = src.shape[:2]

    # Create shared arrays
    shared_src = SharedNDArray(src)
    shared_mask = SharedNDArray(cv2.bitwise_not(mask))
    shared_result = SharedNDArray(np.zeros_like(src))

    # Generate block coordinates
    blocks = [
        (
            shared_src,
            shared_mask,
            shared_result,
            y,
            min(y + block_size, height),
            x,
            min(x + block_size, width),
            overlap,
        )
        for y in range(0, height, block_size)
        for x in range(0, width, block_size)
    ]

    # Process blocks using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(inpaint_block, block) for block in blocks]
        for future in as_completed(futures):
            future.result()  # Ensures that exceptions are raised if any

    return shared_result.arr
