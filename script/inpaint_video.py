import threading
import queue
import subprocess
from typing import Callable
from pathlib import Path

import cv2
from inpaint_text import Inpainter


is_cancel = False


def video_reader(cap, read_queue, stop_check):
    global is_cancel
    frame_idx = 0
    while cap.isOpened():
        try:
            ret, frame = cap.read()
            if not ret:
                break

            frames = (frame_idx, frame)
            read_queue.put(frames, timeout=0.1)
            frame_idx += 1

        except queue.Full:
            # 直接在 while 开头判断 stop_check() 可能遇到 read_queue 已满
            # read_queue.put() 阻塞的问题导致无法进入下一次 while 循环，从而无法退出的情况
            # 解决方案是在队列满时检查 stop_check()
            # 当停止时 processor 线程结束，一定会出现 read_queue 队列满的是时候
            if stop_check():
                is_cancel = True
                print("Reader Process canceled while queue was full!")
                break
            # Otherwise, try again in the next iteration
    try:
        # Signal that reading is done
        read_queue.put(None, timeout=0.1)
    except queue.Full:
        if stop_check():
            is_cancel = True
            print("Reader Process canceled while queue was not full")


def frame_processor(
    read_queue: queue.Queue,
    process_queue: queue.Queue,
    region: tuple,
    inpainter: Inpainter,
    input_frame_callback: Callable,
    output_frame_callback: Callable,
    update_table_callback: Callable,
    stop_check: Callable,
):
    global is_cancel
    while True:
        if stop_check():
            is_cancel = True
            print("Processor Process canceled!")
            break

        frames = read_queue.get()
        if frames is None:
            process_queue.put(None)
            break

        frame_idx, frame = frames
        # Process each frame
        x1, x2, y1, y2 = region

        # 扩展取一像素
        x1_ext = max(0, x1 - 1)
        x2_ext = min(frame.shape[1], x2 + 1)
        y1_ext = max(0, y1 - 1)
        y2_ext = min(frame.shape[0], y2 + 1)

        frame_area_ext = frame[y1_ext:y2_ext, x1_ext:x2_ext]
        frame_area_ext_inpainted = inpainter.inpaint_text(frame_area_ext)
        frame_area_inpainted = frame_area_ext_inpainted[
            1 : (y2 - y1 + 1), 1 : (x2 - x1 + 1)
        ]
        frame[y1:y2, x1:x2] = frame_area_inpainted

        # Callbacks handling
        if frame_idx % 30 == 0:
            input_frame_callback(frame_idx)
            output_frame_callback(frame)

        print(frame_idx)
        update_table_callback(frame_idx)

        process_queue.put((frame_idx, frame))


def video_writer(out, process_queue, total_frame_count, progress_callback, stop_check):
    global is_cancel
    written_count = 0
    while True:
        if stop_check():
            is_cancel = True
            print("Writer Process canceled!")
            break

        frames = process_queue.get()
        if frames is None:
            break

        _, frame = frames
        out.write(frame)
        written_count += 1

        # Update progress and call frame callbacks
        progress = (written_count / total_frame_count) * 100
        progress_callback(progress)


def run(
    path: str,
    region: tuple,
    inpainter: Inpainter,
    progress_callback: Callable,
    input_frame_callback: Callable,
    output_frame_callback: Callable,
    update_table_callback: Callable,
    stop_check: Callable,
):
    global is_cancel
    is_cancel = False
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    output_path = Path(path).with_name(Path(path).stem + "_temp.mp4")
    out = cv2.VideoWriter(str((output_path)), fourcc, fps, (width, height))
    total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    read_queue = queue.Queue(maxsize=50)
    process_queue = queue.Queue(maxsize=50)

    # Create and start the threads
    reader_thread = threading.Thread(
        target=video_reader, args=(cap, read_queue, stop_check)
    )
    processor_thread = threading.Thread(
        target=frame_processor,
        args=(
            read_queue,
            process_queue,
            region,
            inpainter,
            input_frame_callback,
            output_frame_callback,
            update_table_callback,
            stop_check,
        ),
    )
    writer_thread = threading.Thread(
        target=video_writer,
        args=(out, process_queue, total_frame_count, progress_callback, stop_check),
    )

    reader_thread.start()
    processor_thread.start()
    writer_thread.start()

    # Wait for all threads to complete
    reader_thread.join()
    processor_thread.join()
    writer_thread.join()

    # Release resources
    cap.release()
    out.release()

    if not is_cancel:
        # Extract audio from the original video and combine it with the processed video
        final_output_path = Path(path).with_name(Path(path).stem + "_output.mp4")
        ffmpeg_path = Path(__file__).parent.parent / "ffmpeg.exe"
        command = [
            str(ffmpeg_path),
            "-y",
            "-i",
            str(output_path),
            "-i",
            str(path),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c",
            "copy",
            str(final_output_path),
        ]
        subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        output_path.unlink()
        return True
    else:
        # remove temp video file
        output_path.unlink()
        return False
