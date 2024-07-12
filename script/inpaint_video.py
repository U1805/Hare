import cv2
import asyncio
from inpaint_text import Inpainter
from typing import Callable


async def video_reader(cap, read_queue, batch_size=10):
    frame_idx = 0
    while cap.isOpened():
        frames = []
        for _ in range(batch_size):
            ret, frame = cap.read()
            if not ret:
                break
            frames.append((frame_idx, frame))
            frame_idx += 1
        if frames:
            await read_queue.put(frames)
        else:
            break
    await read_queue.put(None)  # Signal that reading is done


async def frame_processor(
    read_queue,
    process_queue,
    start_frame,
    end_frame,
    region: tuple,
    inpainter: Inpainter,
    input_frame_callback: Callable,
    output_frame_callback: Callable,
):
    while True:
        frames = await read_queue.get()
        if frames is None:
            await process_queue.put(None)
            break

        processed_frames = []
        for frame_idx, frame in frames:
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

            processed_frames.append((frame_idx, frame))

        await process_queue.put(processed_frames)


async def video_writer(out, process_queue, total_frame_count, progress_callback):
    written_count = 0
    while True:
        frames = await process_queue.get()
        if frames is None:
            break
        for _, frame in frames:
            out.write(frame)
            written_count += 1

            # Update progress and call frame callbacks
            progress = (written_count / total_frame_count) * 100
            progress_callback(progress)


async def run(
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
    output_path = path.rsplit(".", 1)[0] + "_output.mp4"
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    read_queue = asyncio.Queue(maxsize=10)
    process_queue = asyncio.Queue(maxsize=10)

    # Create and start the tasks
    reader_task = asyncio.create_task(
        video_reader(cap, read_queue)
    )
    processor_task = asyncio.create_task(
        frame_processor(
            read_queue,
            process_queue,
            start_frame,
            end_frame,
            region,
            inpainter,
            input_frame_callback,
            output_frame_callback,
        )
    )
    writer_task = asyncio.create_task(
        video_writer(out, process_queue, total_frame_count, progress_callback)
    )

    # Wait for all tasks to complete
    await asyncio.gather(reader_task, processor_task, writer_task)

    # Release resources
    cap.release()
    out.release()
