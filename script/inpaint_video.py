import queue
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, List, Tuple

import cv2
import inpaint_mask as maskutils
import numpy as np
from inpaint_text import Inpainter


class VideoInpainter:
    QUEUE_SIZE = 15
    AUTOSUB_INTERVAL_FRAME = 10

    def __init__(
        self,
        path: str,
        regions: List[Tuple[int, int, int, int]],
        time_table: List[List[str]],
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
        self.cache = [None for _ in self.regions]
        self.last_frame = [deque([None] * 5, maxlen=5) for _ in self.regions]

        # autosub
        self.AUTO_last_sentence_id = 0
        self.AUTO_last_sentence_time = int(self.AUTOSUB_INTERVAL_FRAME)
        self.AUTO_subtitle_active = False
        self.AUTO_timeline = []
        self.AUTO_last_region_start = 0
        self.AUTO_last_frame_start = 0

    def run(self) -> bool:
        if self.inpainter.method == "AUTOSUB" and len(self.regions) != 1:
            print(f"Autosub only accepts ONE region!")
            return {"status": "Error", "message": "自动打轴只接受单个选区!"}
        try:
            self._is_cancel = False
            self.read_queue: queue.Queue = queue.Queue(maxsize=self.QUEUE_SIZE)
            self.process_queue: queue.Queue = queue.Queue(maxsize=self.QUEUE_SIZE)
            self.cache = [None for _ in self.regions]
            self.last_frame = [deque([None] * 5, maxlen=5) for _ in self.regions]
            self.AUTO_last_sentence_id = 0
            self.AUTO_last_sentence_time = int(self.AUTOSUB_INTERVAL_FRAME)
            self.AUTO_subtitle_active = False
            self.AUTO_timeline = []
            self.AUTO_last_region_start = 0
            self.AUTO_last_frame_start = 0

            self.cap = cv2.VideoCapture(str(self.path))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

            # path/file.mp4 - > path/file_temp.mp4
            output_path = self.path.with_name(self.path.stem + "_temp.mp4")
            self.out = cv2.VideoWriter(
                str(output_path), fourcc, self.fps, (width, height)
            )
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
            return {"status": "Warn", "message": ""}

        finally:
            # Release resources
            if self.cap:
                self.cap.release()
            if self.out:
                self.out.release()

            if not self._is_cancel:
                if self.inpainter.method == "AUTOSUB":
                    self.export_subtitle()
                else:
                    self.combine_audio()
                output_path.unlink()
                return {"status": "Success", "message": ""}
            else:
                output_path.unlink()
                return {"status": "Warn", "message": ""}

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
            if self.time_table[region_id][frame_idx]:
                x1, x2, y1, y2 = region["region"]
                frame_area = frame_after[y1:y2, x1:x2]

                if frame_area.size == 0:  # 空选区跳过
                    continue

                flag = False
                frame_area_inpainted, _ = self.inpainter.inpaint_text(
                    frame_area, region["binary"]
                )
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
            if self.time_table[region_id][frame_idx]:
                x1, x2, y1, y2 = region["region"]
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
                    frame_area_inpainted, _ = self.inpainter.inpaint_text(
                        frame_copy, region["binary"]
                    )
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

    def check_cache_item(self, region_id, frame_copy):
        # 检查缓存
        best_cache_item = None
        sim = -1

        cache_item = self.cache[region_id]
        if cache_item is None:
            return best_cache_item, sim
        similarity = self.calculate_frame_similarity(
            frame_copy, cache_item["inpainted"], self.regions[region_id]["binary"]
        )
        # 找到 similarity > 0.995 的项
        if similarity > 0.7:
            best_cache_item = cache_item["inpainted"]
            sim = similarity

        return best_cache_item, sim

    def calculate_frame_similarity(
        self, frame1: np.ndarray, frame2: np.ndarray, binary: bool
    ) -> float:
        mask = self.inpainter.create_mask(frame1, binary)

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

    """
    自动打轴相关
    """

    def frame_processor_autosubtitle(
        self, frame_idx: int, frame: np.ndarray
    ) -> np.ndarray:
        frame_before = frame.copy()
        frame_after = frame.copy()

        flag = True
        for region_id, region in enumerate(self.regions):
            x1, x2, y1, y2 = region["region"]
            frame_area = frame_after[y1:y2, x1:x2]
            if frame_area.size == 0:  # 空选区跳过
                continue

            # 处理第一帧
            if self.cache[region_id] is None:
                self.cache[region_id] = self.inpainter.create_mask(
                    frame_area, region["binary"]
                )
                self.update_table_callback(
                    self.AUTO_last_sentence_id,
                    frame_idx,
                    "-0 +0",
                )
                continue

            flag = False
            ret = self.check_same_sentence_with_last(
                region_id, frame_area, self.inpainter.autosub
            )
            same_frame, area_increase, area_decrease = ret

            # 判断新的一行
            if (
                not same_frame
                and self.AUTO_last_sentence_time >= self.AUTOSUB_INTERVAL_FRAME
            ):
                self.AUTO_timeline.append(
                    {
                        "id": self.AUTO_last_sentence_id,
                        "start": self.AUTO_last_region_start,
                        "end": frame_idx - 1,
                    }
                )
                self.AUTO_last_sentence_id += 1
                self.AUTO_last_sentence_time = 0
                self.AUTO_last_region_start = frame_idx
                self.AUTO_last_frame_start = area_increase

            # 更新当前帧
            self.update_table_callback(
                self.AUTO_last_sentence_id,
                frame_idx,
                f"-{area_decrease} +{area_increase}",
            )
            self.AUTO_last_sentence_time += 1

            # 处理最后一帧
            if frame_idx == self.total_frame_count - 1:
                self.AUTO_timeline.append(
                    {
                        "id": self.AUTO_last_sentence_id,
                        "start": self.AUTO_last_region_start,
                        "end": frame_idx,
                    }
                )

        if flag:
            self.update_table_callback(-1, frame_idx, "")
        # Callbacks handling
        if frame_idx % 10 == 0:
            self.input_frame_callback(frame_before)
            self.output_frame_callback(frame_after)
        print(frame_idx)
        return frame_after

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
        - (bool, int, int): 返回一个布尔值，表示掩码是否被认为是相同的；
                        以及增加的区域像素计数，减少的区域像素计数。
        """
        mask_cur = self.inpainter.create_mask(
            frame_copy, self.regions[region_id]["binary"]
        )

        mask_last = self.cache[region_id]
        self.cache[region_id] = mask_cur

        mask_cur_binary = mask_cur > 0
        mask_last_binary = mask_last > 0

        if np.sum(mask_cur) == 0 and np.sum(mask_last) > 0:
            return False, 0, np.sum(mask_last)

        # 判断是否第二张掩码包含了第一张掩码
        if np.all(mask_last_binary[mask_cur_binary]):
            if np.sum(mask_last) == 0 and np.sum(mask_cur) > 0:
                return False, np.sum(mask_cur), 0
            return True, 0, 0

        added_region = ~mask_last_binary & mask_cur_binary
        added_region_count = np.sum(added_region)
        minused_region = ~mask_cur_binary & mask_last_binary
        minused_region_count = np.sum(minused_region)

        # 如果变化部分超过阈值，则认为是新的句子
        if (added_region_count >= noise_threshold) or (
            minused_region_count >= noise_threshold
        ):
            return False, added_region_count, minused_region_count

        return True, added_region_count, minused_region_count

    def format_time(self, second):
        """
        s -> h:mm:ss.ss
        """
        H = second // 3600
        M = (second - H * 3600) // 60
        S = second - H * 3600 - M * 60 + 0.01
        format_time = "%d:%02d:%05.2f" % (H, M, S)
        return format_time

    def export_subtitle(self):
        TEMPLATE = """\
[Script Info]
; Script generated by Aegisub 3.2.2
; http://www.aegisub.org/
Title: GAKUEN IDOLMASTER
ScriptType: v4.00+
WrapStyle: 0
YCbCr Matrix: 
PlayResX: 
PlayResY: 

[Aegisub Project Garbage]
Last Style Storage: Default
Audio File: 
Video File: 
Video AR Mode: 
Video AR Value: 
Video Zoom Percent: 
Scroll Position: 
Active Line: 
Video Position: 

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Deault,思源黑体 Medium,59,&H00212121,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,3,0,1,0,0,7,295,8,1420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        # 导出时轴
        last_end = None
        for timeline in self.AUTO_timeline:
            start_frame, end_frame = timeline["start"], timeline["end"]
            if last_end and start_frame - 1 == last_end:
                start_time = self.format_time(last_end / self.fps)
            else:
                start_time = self.format_time(start_frame / self.fps)
            end_time = self.format_time(end_frame / self.fps)
            TEMPLATE += f"Dialogue: 0,{start_time},{end_time},Deault,,0,0,0,,\n"
            last_end = end_frame

        with open(f"{self.path}.ass", "w", encoding="utf-8") as f:
            f.write(TEMPLATE)
