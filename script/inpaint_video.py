import cv2
import asyncio
from inpaint_text import Inpainter
from typing import Callable


async def video_reader(cap, process_queue, batch_size=10):
    while cap.isOpened():
        frames = []
        for _ in range(batch_size):
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        if frames:
            await process_queue.put(frames)
        else:
            break
    await process_queue.put(None)  # Signal that reading is done


async def frame_processor(
    process_queue,
    write_queue,
    region: tuple,
    inpainter: Inpainter,
    progress_callback: Callable,
    input_frame_callback: Callable,
    output_frame_callback: Callable,
    total_frame_count,
):
    processed_count = 0
    while True:
        frames = await process_queue.get()
        if frames is None:
            break
        processed_frames = []
        for idx, frame in enumerate(frames):
            # Process each frame
            x1, x2, y1, y2 = region
            frame_area = frame[y1:y2, x1:x2]
            frame_area = inpainter.inpaint_text(frame_area)
            frame[y1:y2, x1:x2] = frame_area
            processed_frames.append(frame)

            # Callbacks handling
            if (processed_count + idx) % 100 == 0:
                input_frame_callback(processed_count + idx)
                output_frame_callback(frame)

        await write_queue.put(processed_frames)
        processed_count += len(frames)
        print(processed_count)

        # Update progress
        progress = (processed_count / total_frame_count) * 100
        progress_callback(progress)

    await write_queue.put(None)


async def video_writer(out, write_queue):
    while True:
        processed_frames = await write_queue.get()
        if processed_frames is None:
            break
        for frame in processed_frames:
            out.write(frame)


async def run(
    path: str,
    region: tuple,
    inpainter: Inpainter,
    progress_callback: Callable,
    input_frame_callback: Callable,
    output_frame_callback: Callable,
):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    output_path = path.rsplit(".", 1)[0] + "_output.mp4"
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    process_queue = asyncio.Queue(maxsize=100)
    write_queue = asyncio.Queue(maxsize=100)

    reader_task = asyncio.create_task(video_reader(cap, process_queue))
    processor_task = asyncio.create_task(
        frame_processor(
            process_queue,
            write_queue,
            region,
            inpainter,
            progress_callback,
            input_frame_callback,
            output_frame_callback,
            total_frame_count,
        )
    )
    writer_task = asyncio.create_task(video_writer(out, write_queue))

    await asyncio.gather(reader_task, processor_task, writer_task)

    cap.release()
    out.release()
