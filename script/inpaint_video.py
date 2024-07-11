import cv2
from inpaint_text import Inpainter, Inpainter2
from typing import Union, Callable


def run(
    path: str,
    region: tuple,
    inpainter: Union[Inpainter, Inpainter2],
    progress_callback: Callable,
    input_frame_callback: Callable,
    output_frame_callback: Callable,
):
    # Capture the video from the given path
    cap = cv2.VideoCapture(path)

    # Get video properties
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # Codec
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Define the codec and create VideoWriter object to save the output video
    output_path = path.rsplit(".", 1)[0] + "_output.mp4"
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    current_frame = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Extract the region of interest
        x1, x2, y1, y2 = region
        frame_area = frame[y1:y2, x1:x2]

        # Inpaint the text in the specified region
        frame_area = inpainter.inpaint_text(frame_area)
        frame[y1:y2, x1:x2] = frame_area

        out.write(frame)

        current_frame += 1
        progress = current_frame / frame_count
        progress_callback(progress * 100)
        if current_frame % 100 == 0:
            input_frame_callback(current_frame)
            output_frame_callback(frame)

    # Release resources
    cap.release()
    out.release()
    cv2.destroyAllWindows()
