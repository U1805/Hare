import threading
import queue
import subprocess
from typing import Callable
from pathlib import Path

import cv2
from inpaint_text import Inpainter


class VideoInpainter:
    def __init__(
        self,
        path: str,
        regions: list,
        time_table: list,
        inpainter: Inpainter,
        progress_callback: Callable,
        input_frame_callback: Callable,
        output_frame_callback: Callable,
        update_table_callback: Callable,
        stop_check: Callable,
    ):
        self.inpainter = inpainter
        self.regions = regions
        self.time_table = time_table

        self.path = path
        self.cap = None  # input_video
        self.out = None  # output_video
        self.total_frame_count = 0

        self.read_queue = queue.Queue(maxsize=15)
        self.process_queue = queue.Queue(maxsize=15)

        self.progress_callback = progress_callback
        self.input_frame_callback = input_frame_callback
        self.output_frame_callback = output_frame_callback
        self.update_table_callback = update_table_callback
        self.stop_check = stop_check

        self._is_cancel = False

    def run(self):
        self._is_cancel = False
        self.cap = cv2.VideoCapture(self.path)
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        # path/file.mp4 - > path/file_temp.mp4
        output_path = Path(self.path).with_name(Path(self.path).stem + "_temp.mp4")
        self.out = cv2.VideoWriter(str((output_path)), fourcc, fps, (width, height))
        self.total_frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 生产者-消费者模式实现并发
        reader_thread = threading.Thread(target=self.video_reader)
        processor_thread = threading.Thread(target=self.video_processor)
        writer_thread = threading.Thread(target=self.video_writer)

        reader_thread.start()
        processor_thread.start()
        writer_thread.start()

        reader_thread.join()
        processor_thread.join()
        writer_thread.join()
        self.progress_callback(100)

        # Release resources
        self.cap.release()
        self.out.release()

        if not self._is_cancel:
            self.combine_audio()
            output_path.unlink()
            return True
        else:
            # remove temp video file
            output_path.unlink()
            return False

    def video_reader(self):
        frame_idx = 0
        while self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if not ret:
                    break

                frames = (frame_idx, frame)
                self.read_queue.put(frames, timeout=0.1)
                frame_idx += 1

            except queue.Full:
                # 直接在 while 开头判断 stop_check() 可能遇到 read_queue 已满
                # read_queue.put() 阻塞的问题导致无法进入下一次 while 循环，从而无法退出的情况
                # 解决方案是在队列满时检查 stop_check()
                # 当停止时 processor 线程结束，一定会出现 read_queue 队列满的是时候
                if self.stop_check():
                    self._is_cancel = True
                    print("Reader Process canceled while queue was full!")
                    break
                # Otherwise, try again in the next iteration
        try:
            # None: Signal that reading is done
            self.read_queue.put(None, timeout=0.1)
        except queue.Full:
            if self.stop_check():
                self._is_cancel = True
                print("Reader Process canceled while queue was not full")

    def video_processor(self):
        while True:
            try:
                frames = self.read_queue.get(timeout=0.1)
            except queue.Empty:
                if self.stop_check():
                    self._is_cancel = True
                    print("Processor Process canceled while queue was empty!")
                    break
                else:
                    continue

            if frames is None:
                self.process_queue.put(None)
                break

            frame_idx, frame = frames
            frame = self.frame_processor(frame_idx, frame)
            print(frame_idx)

            try:
                self.process_queue.put((frame_idx, frame), timeout=0.1)
            except queue.Full:
                if self.stop_check():
                    self._is_cancel = True
                    print("Processor Process canceled while queue was full!")
                    break

    def video_writer(self):
        written_count = 0
        while True:
            try:
                frames = self.process_queue.get(timeout=0.1)
            except queue.Empty:
                if self.stop_check():
                    self._is_cancel = True
                    print("Writer Process canceled while queue was empty!")
                    break
                else:
                    continue

            if frames is None:
                break

            _, frame = frames
            self.out.write(frame)
            written_count += 1

            progress = (written_count / self.total_frame_count) * 100 - 1e-7
            self.progress_callback(progress)

    def combine_audio(self):
        """Extract audio from the original video and combine it with the processed video"""
        # path/file.mp4 - > path/file_temp.mp4
        temp_path = Path(self.path).with_name(Path(self.path).stem + "_temp.mp4")
        # path/file.mp4 -> path/file_output.mp4
        output_path = Path(self.path).with_name(Path(self.path).stem + "_output.mp4")

        ffmpeg_path = Path(__file__).parent.parent / "ffmpeg.exe"
        # fmt: off
        command = [
            str(ffmpeg_path),
            "-y",
            "-i", str(temp_path),
            "-i", str(self.path), 
            "-map", "0:v", "-map", "1:a", "-c", "copy",
            str(output_path),
        ]
        # fmt: on
        subprocess.run(command, capture_output=True, text=True, encoding="utf-8")

    def frame_processor(self, frame_idx, frame):
        frame_before = frame.copy()
        frame_after = frame.copy()

        for region_id, region in enumerate(self.regions):
            if self.time_table[region_id][frame_idx]:
                x1, x2, y1, y2 = region

                # 扩展取一像素
                x1_ext = max(0, x1 - 1)
                x2_ext = min(frame_after.shape[1], x2 + 1)
                y1_ext = max(0, y1 - 1)
                y2_ext = min(frame_after.shape[0], y2 + 1)

                frame_area_ext = frame_after[y1_ext:y2_ext, x1_ext:x2_ext]
                frame_area_ext_inpainted = self.inpainter.inpaint_text(frame_area_ext)
                frame_area_inpainted = frame_area_ext_inpainted[
                    1 : (y2 - y1 + 1), 1 : (x2 - x1 + 1)
                ]
                frame_after[y1:y2, x1:x2] = frame_area_inpainted

                self.update_table_callback(region_id, frame_idx)

        # Callbacks handling
        if frame_idx % 10 == 0:
            self.input_frame_callback(frame_before)
            self.output_frame_callback(frame_after)

        return frame_after
