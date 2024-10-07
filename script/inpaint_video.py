import time
import queue
import threading
import subprocess
from pathlib import Path
from typing import Callable, List, Tuple
from collections import deque

import cv2
import numpy as np

import inpaint_mask as maskutils
from inpaint_text import Inpainter


class VideoInpainter:
    QUEUE_SIZE = 15

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
        self.cache = [None for _ in regions]
        self.last_frame = [deque([None] * 5, maxlen=5) for _ in regions]
        self.last_sentence_id = -1
        self.last_sentence_time = 0

    def run(self) -> bool:
        if self.inpainter.method == "AUTOSUB" and len(self.regions) != 1:
            print(f"Autosub only accepts ONE region!")
            return False
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
                if self.inpainter.method == "AUTOSUB":
                    pass  # 导出字幕
                else:
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
        elif self.inpainter.method == "AUTOSUB":
            return self.frame_processor_autosubtitle(frame_idx, frame)
        else:
            return self.frame_processor_no_cache(frame_idx, frame)

    def frame_processor_no_cache(self, frame_idx: int, frame: np.ndarray) -> np.ndarray:
        frame_before = frame.copy()
        frame_after = frame.copy()

        flag = True
        for region_id, region in enumerate(self.regions):
            if self.time_table[region_id][frame_idx] is not None:
                x1, x2, y1, y2 = region
                frame_area = frame_after[y1:y2, x1:x2]

                if frame_area.size == 0:  # 空选区跳过
                    continue

                flag = False
                frame_area_inpainted, _ = self.inpainter.inpaint_text(frame_area)
                frame_after[y1:y2, x1:x2] = frame_area_inpainted
                self.update_table_callback(region_id, frame_idx, "")

        if flag:
            self.update_table_callback(-1, frame_idx, "")
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

        flag = True
        for region_id, region in enumerate(self.regions):
            if self.time_table[region_id][frame_idx] is not None:
                x1, x2, y1, y2 = region
                frame_copy = frame_after[y1:y2, x1:x2].copy()

                if frame_copy.size == 0:  # 空选区跳过
                    continue

                flag = False
                # 检查缓存
                frame_gray = cv2.cvtColor(frame_copy, cv2.COLOR_BGR2GRAY)
                same_with_last = self.check_same_frame_with_last(region_id, frame_gray)
                cache, similarity = self.check_cache_item(region_id, frame_copy)

                if similarity > 0.80:
                    frame_area_inpainted = cache
                elif similarity > 0.65 and not same_with_last:
                    frame_area_inpainted = cache
                else:
                    frame_area_inpainted, _ = self.inpainter.inpaint_text(frame_copy)
                    # 保存到缓存队列中
                    self.cache[region_id] = {"inpainted": frame_area_inpainted.copy()}

                frame_after[y1:y2, x1:x2] = frame_area_inpainted
                self.update_table_callback(region_id, frame_idx, "")

        if flag:
            self.update_table_callback(-1, frame_idx, "")
        # Callbacks handling
        self.input_frame_callback(frame_before)
        self.output_frame_callback(frame_after)
        print(frame_idx)

        return frame_after

    def frame_processor_autosubtitle(
        self, frame_idx: int, frame: np.ndarray
    ) -> np.ndarray:
        frame_before = frame.copy()
        frame_after = frame.copy()

        flag = True
        for region_id, region in enumerate(self.regions):
            x1, x2, y1, y2 = region
            frame_area = frame_after[y1:y2, x1:x2]

            if frame_area.size == 0:  # 空选区跳过
                continue

            if frame_idx == 17:
                print(123)
            same_sentence, count = self.check_same_sentence_with_last(
                region_id, frame_area, self.inpainter.autosub
            )
            if np.sum(self.cache[region_id]) == 0:  # 没有文字
                for row_id, row in enumerate(self.time_table):
                    if row_id > 0:
                        row.append(None)
                self.last_sentence_time = 15
                continue

            flag = False
            if not same_sentence and self.last_sentence_time >= 15:
                self.last_sentence_time = 0
                self.last_sentence_id += 1
                # update time_table
                current_frame_count = len(self.time_table[region_id])
                self.time_table.append([None] * current_frame_count)
            self.update_table_callback(self.last_sentence_id, frame_idx, str(count))
            # update time_table
            for row_id, row in enumerate(self.time_table):
                if row_id == self.last_sentence_id:
                    row.append(1)
                else:
                    row.append(None)
            self.last_sentence_time += 1

        if flag:
            self.update_table_callback(-1, frame_idx, "")
        # Callbacks handling
        if frame_idx % 10 == 0:
            self.input_frame_callback(frame_before)
            self.output_frame_callback(frame_after)
        print(frame_idx)

        return frame_after

    def check_same_frame_with_last(self, region_id, frame_gray):
        """
        通过 SSIM 检查当前帧相比上一帧内容相似度
        如果完全一样，判断是当前句子播放完的等待时间，强制刷新修复

        参数:
        - self.last_frame[region_id] (np.array): 上一帧的图像
        - frame_gray (np.array): 当前帧的图像

        返回:
        - bool: 返回一个布尔值，表示是否被认为是相同的
        """
        frame1 = self.last_frame[region_id].pop()
        frame5 = self.last_frame[region_id].popleft()
        self.last_frame[region_id].append(frame1)
        self.last_frame[region_id].append(frame_gray.copy())
        if frame1 is None or frame5 is None:
            return False
        score, _ = cv2.quality.QualitySSIM_compute(frame1, frame_gray)
        score_, _ = cv2.quality.QualitySSIM_compute(frame1, frame5)
        return score[0] > 0.99 and score_[0] < 0.99

    def check_same_sentence_with_last(
        self, region_id, frame_copy, noise_threshold=2000
    ):
        """
        通过掩码检查当前帧和上一帧属于同一句子

        参数:
        - self.cache[region_id] (np.array): 上一帧的掩码
        - frame_copy (np.array): 当前帧的图像
        - noise_threshold (int): 允许的噪声阈值，默认为2000。

        返回:
        - (bool, int): 返回一个布尔值，表示掩码是否被认为是相同的；
                        以及减少的区域像素计数。
        """
        mask1 = maskutils.create_mask_temp(
            frame_copy,
            self.inpainter.dilate_kernal_size,
            self.inpainter.area_max,
            self.inpainter.area_min,
            self.inpainter.x_offset,
            self.inpainter.y_offset,
        )

        mask2 = self.cache[region_id]
        self.cache[region_id] = mask1
        if mask2 is None:
            return False, 0

        mask1_binary = mask1 > 0
        mask2_binary = mask2 > 0

        # 判断是否第二张掩码包含了第一张掩码
        if np.all(mask1_binary[mask2_binary]):
            if np.sum(mask2) == 0:
                return False, 0
            else:
                return True, 0

        # 检查mask1比mask2少的部分
        minused_region = ~mask1_binary & mask2_binary

        # 如果减少部分超过阈值，则认为是新的句子
        minused_region_count = np.sum(minused_region)
        if minused_region_count <= noise_threshold:
            return True, minused_region_count

        return False, minused_region_count

    def check_cache_item(self, region_id, frame_copy):
        # 检查缓存
        best_cache_item = None
        sim = -1

        cache_item = self.cache[region_id]
        if cache_item is None:
            return best_cache_item, sim
        similarity = self.calculate_frame_similarity(
            frame_copy, cache_item["inpainted"]
        )
        print(f"Similarity: {similarity}")

        # 找到 similarity > 0.995 的项
        if similarity > 0.65:
            best_cache_item = cache_item["inpainted"]
            sim = similarity

        return best_cache_item, sim

    def calculate_frame_similarity(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> float:
        mask = maskutils.create_mask(
            frame1,
            self.inpainter.dilate_kernal_size,
            self.inpainter.area_max,
            self.inpainter.area_min,
            self.inpainter.x_offset,
            self.inpainter.y_offset,
        )

        # # 横向整行扩展掩码
        # extended_mask = np.zeros_like(mask, dtype=np.uint8)
        # row_mask = np.any(mask > 0, axis=1).astype(np.uint8) * 255
        # extended_mask[row_mask > 0, :] = 255

        # 横向膨胀扩展掩码
        # kernel = np.ones((1, 25), np.uint8)
        # extended_mask = cv2.dilate(mask, kernel, iterations=1)

        # 横向最右扩展掩码
        mask = maskutils.shift_expand_mask(mask, right=50)

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
