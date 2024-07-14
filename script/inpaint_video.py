import threading
import queue
import subprocess
from typing import Callable
from pathlib import Path

import cv2
from inpaint_text import Inpainter


def video_reader(cap, read_queue):
    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frames = (frame_idx, frame)
        frame_idx += 1
        read_queue.put(frames)
    read_queue.put(None)  # Signal that reading is done


def frame_processor(
    read_queue: queue.Queue,
    process_queue: queue.Queue,
    start_frame: int,
    end_frame: int,
    region: tuple,
    inpainter: Inpainter,
    input_frame_callback: Callable,
    output_frame_callback: Callable,
):
    while True:
        frames = read_queue.get()
        if frames is None:
            process_queue.put(None)
            break

        frame_idx, frame = frames
        if start_frame <= frame_idx < end_frame:
            # Process each frame
            x1, x2, y1, y2 = region
            frame_area = frame[y1:y2, x1:x2]
            frame_area = inpainter.inpaint_text(frame_area)
            frame[y1:y2, x1:x2] = frame_area

            # Callbacks handling
            if frame_idx % 100 == 0:
                input_frame_callback(frame_idx)
                output_frame_callback(frame)

        print(frame_idx)

        process_queue.put((frame_idx, frame))


def video_writer(out, process_queue, total_frame_count, progress_callback):
    written_count = 0
    while True:
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
    start_frame: int,
    end_frame: int,
    progress_callback: Callable,
    input_frame_callback: Callable,
    output_frame_callback: Callable,
):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    output_path = Path(path).with_name(Path(path).stem + "_temp.mp4")
    out = cv2.VideoWriter(str((output_path)), fourcc, fps, (width, height))
    total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    read_queue = queue.Queue(maxsize=15)
    process_queue = queue.Queue(maxsize=15)

    # Create and start the threads
    reader_thread = threading.Thread(target=video_reader, args=(cap, read_queue))
    processor_thread = threading.Thread(
        target=frame_processor,
        args=(
            read_queue,
            process_queue,
            start_frame,
            end_frame,
            region,
            inpainter,
            input_frame_callback,
            output_frame_callback,
        ),
    )
    writer_thread = threading.Thread(
        target=video_writer,
        args=(out, process_queue, total_frame_count, progress_callback),
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

    # Extract audio from the original video and combine it with the processed video
    final_output_path = Path(path).with_name(Path(path).stem + "_output.mp4")
    ffmpeg_path = Path(__file__).parent.parent / "ffmpeg.exe"
    command = [
        str(ffmpeg_path),
        "-y",
        "-i", str(output_path),
        "-i", str(path),
        "-map", "0:v",
        "-map", "1:a",
        "-c", "copy",
        str(final_output_path),
    ]
    subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    output_path.unlink()
