import threading
import queue
from pathlib import Path
from typing import Callable, List, Tuple
import queue
from collections import deque
import time

import cv2
import numpy as np
import subprocess
from inpaint_text import Inpainter


class VideoInpainter:
    QUEUE_SIZE = 15
    FRAME_COMPARISON_INTERVAL = 10
    SIMILARITY_THRESHOLD = 0.95
    CACHE_SIZE = 1

    def __init__(
        self,
        path: str,
        regions: List[Tuple[int, int, int, int]],
        time_table: List[List[bool]],
        inpainter: Inpainter,
        progress_callback: Callable[[float], None],
        input_frame_callback: Callable[[np.ndarray], None],
        output_frame_callback: Callable[[np.ndarray], None],
        update_table_callback: Callable[[int, int, str], None],
        stop_check: Callable[[], bool],
    ):
        self.inpainter = inpainter
        self.regions = regions
        self.time_table = time_table

        self.path = Path(path)
        self.cap: cv2.VideoCapture | None = None  # input_video
        self.out: cv2.VideoWriter | None = None  # output_video
        self.total_frame_count = 0

        self.read_queue: queue.Queue = queue.Queue(maxsize=self.QUEUE_SIZE)
        self.process_queue: queue.Queue = queue.Queue(maxsize=self.QUEUE_SIZE)

        self.progress_callback = progress_callback
        self.input_frame_callback = input_frame_callback
        self.output_frame_callback = output_frame_callback
        self.update_table_callback = update_table_callback
        self.stop_check = stop_check

        self._is_cancel = False
        self.cache = [deque(maxlen=self.CACHE_SIZE) for _ in regions]
        self.last_frame = [deque([None] * 5, maxlen=5) for _ in regions]

    def run(self) -> bool:
        try:
            self._is_cancel = False
            self.cap = cv2.VideoCapture(str(self.path))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

            # path/file.mp4 - > path/file_temp.mp4
            output_path = self.path.with_name(self.path.stem + "_temp.mp4")
            self.out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            self.total_frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 生产者-消费者模式实现并发
            threads = [
                threading.Thread(target=self.video_reader, name="ReaderThread"),
                threading.Thread(target=self.video_processor, name="ProcessorThread"),
                threading.Thread(target=self.video_writer, name="WriterThread"),
            ]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            self.progress_callback(100)

        except Exception as e:
            print(f"An error occurred during video processing: {str(e)}")
            return False

        finally:
            # Release resources
            if self.cap:
                self.cap.release()
            if self.out:
                self.out.release()

            if not self._is_cancel:
                self.combine_audio()
                output_path.unlink()
                return True
            else:
                output_path.unlink()
                return False

    def video_reader(self) -> None:
        frame_idx = 0
        while self.cap and self.cap.isOpened() and not self.stop_check():
            ret, frame = self.cap.read()
            if not ret:
                break
            frames = (frame_idx, frame)
            while True:
                if self.stop_check():
                    self._is_cancel = True
                    print("Reader thread cancelled while queue is full!")
                    return
                try:
                    self.read_queue.put(frames, timeout=0.1)
                    frame_idx += 1
                    break
                except queue.Full:
                    time.sleep(0.01)  # 短暂睡眠以避免CPU过度使用

        # 发送结束信号
        while True:
            if self.stop_check():
                self._is_cancel = True
                print("Reader thread cancelled while trying to send end signal")
                return
            try:
                self.read_queue.put(None, timeout=0.1)
                break
            except queue.Full:
                time.sleep(0.01)

    def video_processor(self) -> None:
        while not self.stop_check():
            try:
                frames = self.read_queue.get(timeout=0.1)
                if frames is None:
                    break
                frame_idx, frame = frames
                try:
                    processed_frame = self.frame_processor(frame_idx, frame)
                    while True:
                        if self.stop_check():
                            self._is_cancel = True
                            print("Processor thread cancelled while queue is full!")
                            return
                        try:
                            self.process_queue.put(
                                (frame_idx, processed_frame), timeout=0.1
                            )
                            print(f"Processed frame {frame_idx}")
                            break
                        except queue.Full:
                            time.sleep(0.01)
                except Exception as e:
                    print(f"Error processing frame {frame_idx}: {str(e)}")
                finally:
                    self.read_queue.task_done()
            except queue.Empty:
                continue

        # 发送结束信号
        while True:
            if self.stop_check():
                self._is_cancel = True
                print("Processor thread cancelled while trying to send end signal")
                return
            try:
                self.process_queue.put(None, timeout=0.1)
                break
            except queue.Full:
                time.sleep(0.01)

    def video_writer(self) -> None:
        written_count = 0
        while not self.stop_check():
            try:
                frames = self.process_queue.get(timeout=0.1)
                if frames is None:
                    break
                _, frame = frames
                self.out.write(frame)
                written_count += 1
                progress = (written_count / self.total_frame_count) * 100
                self.progress_callback(progress)
                self.process_queue.task_done()
            except queue.Empty:
                continue

    def combine_audio(self) -> None:
        """Extract audio from the original video and combine it with the processed video"""
        # path/file.mp4 - > path/file_temp.mp4
        temp_path = self.path.with_name(self.path.stem + "_temp.mp4")
        # path/file.mp4 -> path/file_output.mp4
        output_path = self.path.with_name(self.path.stem + "_output.mp4")

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
        try:
            subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        except subprocess.CalledProcessError as e:
            print(f"Error combining audio: {e.stderr}")
            raise

    def frame_processor(self, frame_idx: int, frame: np.ndarray) -> np.ndarray:
        if self.inpainter.method.startswith("INPAINT_FSR"):
            return self.frame_processor_with_cache(frame_idx, frame)
        else:
            return self.frame_processor_no_cache(frame_idx, frame)

    def frame_processor_no_cache(self, frame_idx: int, frame: np.ndarray) -> np.ndarray:
        frame_before = frame.copy()
        frame_after = frame.copy()

        for region_id, region in enumerate(self.regions):
            if self.time_table[region_id][frame_idx]:
                x1, x2, y1, y2 = region
                frame_area = frame_after[y1:y2, x1:x2]

                if frame_area.size > 0:  # 空选区跳过
                    frame_area_inpainted, _ = self.inpainter.inpaint_text(frame_area)
                    frame_after[y1:y2, x1:x2] = frame_area_inpainted
                self.update_table_callback(region_id, frame_idx, "")

        # Callbacks handling
        if frame_idx % 10 == 0:
            self.input_frame_callback(frame_before)
            self.output_frame_callback(frame_after)
        print(frame_idx)

        return frame_after

    def frame_processor_with_cache(
        self, frame_idx: int, frame: np.ndarray
    ) -> np.ndarray:
        frame_before = frame.copy()
        frame_after = frame.copy()

        for region_id, region in enumerate(self.regions):
            if self.time_table[region_id][frame_idx]:
                x1, x2, y1, y2 = region
                frame_copy = frame_after[y1:y2, x1:x2].copy()

                if frame_copy.size == 0:  # 空选区跳过
                    self.update_table_callback(region_id, frame_idx, "")
                    continue

                # 检查缓存
                frame_gray = cv2.cvtColor(frame_copy, cv2.COLOR_BGR2GRAY)
                same_with_last = self.check_same_with_last(region_id, frame_gray)
                cache, similarity = self.find_best_cache_item(region_id, frame_copy)

                if similarity > 0.80:
                    frame_area_inpainted = cache
                elif similarity > 0.65 and not same_with_last:
                    frame_area_inpainted = cache
                else:
                    frame_area_inpainted, mask_count = self.inpainter.inpaint_text(
                        frame_copy
                    )
                    # 保存到缓存队列中
                    if same_with_last:
                        self.cache[region_id].clear()
                    self.cache[region_id].append(
                        {
                            "inpainted": frame_area_inpainted.copy(),
                            "mask_count": mask_count,
                        }
                    )

                frame_after[y1:y2, x1:x2] = frame_area_inpainted
                self.update_table_callback(region_id, frame_idx, "")

        # Callbacks handling
        self.input_frame_callback(frame_before)
        self.output_frame_callback(frame_after)
        print(frame_idx)

        return frame_after

    def check_same_with_last(self, region_id, frame_gray):
        # 播放完毕开始停留的帧强制修复
        frame1 = self.last_frame[region_id].pop()
        frame5 = self.last_frame[region_id].popleft()
        self.last_frame[region_id].append(frame1)
        self.last_frame[region_id].append(frame_gray.copy())
        if frame1 is None or frame5 is None:
            return False
        score, _ = cv2.quality.QualitySSIM_compute(frame1, frame_gray)
        score_, _ = cv2.quality.QualitySSIM_compute(frame1, frame5)
        return score[0] > 0.99 and score_[0] < 0.99

    def find_best_cache_item(self, region_id, frame_copy):
        # 检查缓存
        min_mask_count = float("inf")
        best_cache_item = None
        sim = -1

        for cache_item in reversed(self.cache[region_id]):
            similarity = self.calculate_frame_similarity(
                frame_copy, cache_item["inpainted"]
            )
            print(f"Similarity: {similarity}")

            # 找到 similarity > 0.995 且 mask_count 最小的项
            if similarity > 0.80:
                best_cache_item = cache_item["inpainted"]
                sim = similarity
                break
            if similarity > 0.65 and cache_item["mask_count"] < min_mask_count:
                min_mask_count = cache_item["mask_count"]
                best_cache_item = cache_item["inpainted"]
                sim = similarity

        return best_cache_item, sim

    def calculate_frame_similarity(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> float:
        mask = self.inpainter.create_mask(frame1)

        # # 横向整行扩展掩码
        # extended_mask = np.zeros_like(mask, dtype=np.uint8)
        # row_mask = np.any(mask > 0, axis=1).astype(np.uint8) * 255
        # extended_mask[row_mask > 0, :] = 255

        # 横向膨胀扩展掩码
        # kernel = np.ones((1, 25), np.uint8)
        # extended_mask = cv2.dilate(mask, kernel, iterations=1)

        # 横向最右扩展掩码
        mask = self.inpainter.shift_expand_mask(mask, right=50)

        # 掩码反向
        mask1 = cv2.bitwise_not(mask)

        # SSIM 相似度
        frame1_minus_mask = cv2.bitwise_and(frame1, frame1, mask=mask1)
        frame2_minus_mask = cv2.bitwise_and(frame2, frame2, mask=mask1)

        gray1 = cv2.cvtColor(frame1_minus_mask, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2_minus_mask, cv2.COLOR_BGR2GRAY)
        score, _ = cv2.quality.QualitySSIM_compute(gray1, gray2)

        # 亮度权重
        gray_diff = abs(np.mean(gray1) - np.mean(gray2))
        gray_weight = (gray_diff / 255) ** 0.15

        return score[0] * (1 - gray_weight)
