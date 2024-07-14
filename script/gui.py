import sys
import time
import json
import os

import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen
from PyQt5.QtCore import Qt, QRect, QPoint, QThread, pyqtSignal

from layout import VideoPlayerLayout
from inpaint_text import Inpainter
import inpaint_video


class VideoPlayer(VideoPlayerLayout):
    def __init__(self):
        super().__init__()

        # Signals
        self.select_file_button.clicked.connect(self.open_file_dialog)
        self.confirm_button.clicked.connect(self.start_confirmation)
        self.progress_slider.sliderMoved.connect(self.update_input_frame)
        self.video_label.mousePressEvent = self.start_drawing
        self.video_label.mouseMoveEvent = self.update_drawing
        self.video_label.mouseReleaseEvent = self.end_drawing

        # read config file
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                try:
                    config = json.loads(f.read())
                    print(config)
                    self.selected_region = QRect(
                        config["region"]["x"],
                        config["region"]["y"],
                        config["region"]["width"],
                        config["region"]["height"],
                    )
                    if config["is_expanded"]:
                        self.toggle_expand_window(800 + 13 * 2)
                        self.contour_area_input.setValue(config["contour_area"])
                        self.dilate_kernal_size_input.setValue(config["dilate_size"])
                    self.inpainter = Inpainter(
                        method=config["inpaint"],
                        contour_area=config["contour_area"],
                        dilate_kernal_size=config["dilate_size"] * 2 + 1,
                    )
                except:
                    self.show_erro_message(
                        text="配置文件错误", informativeText="请删除 config.json"
                    )
                    raise ValueError(
                        f"Invalid configuration. 配置文件错误, 请删除 config.json"
                    )
        else:
            self.inpainter = Inpainter()

    def open_file_dialog(self):
        """打开文件对话框，选择视频文件"""
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov)",
            options=options,
        )
        if file_name:
            self.selected_video_path = file_name
            self.load_video()

    def load_video(self):
        """加载并初始化视频"""
        self.video_capture = cv2.VideoCapture(self.selected_video_path)
        self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))

        # Get video frame size
        self.video_frame_size = (
            int(self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

        self.end_label.setText(
            f"End: {int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))}"
        )

        label_width = self.video_label.width()
        label_height = self.video_label.height()
        video_width, video_height = self.video_frame_size

        # Center the video within the label
        scaled_video_width = video_width * label_height / video_height
        scaled_video_height = video_height * label_width / video_width
        if scaled_video_width <= label_width:
            self.x_offset = (label_width - scaled_video_width) / 2
            self.y_offset = 0
        else:
            self.x_offset = 0
            self.y_offset = (label_height - scaled_video_height) / 2

        # Set slider range and enable controls
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(self.total_frames - 1)
        self.progress_slider.setEnabled(True)
        self.confirm_button.setEnabled(True)

        # Show first frame
        self.update_input_frame(0)

    def update_input_frame(self, frame_number):
        """更新输入帧显示"""
        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.video_capture.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channels = frame.shape
            bytes_per_line = channels * width
            q_img = QImage(
                frame.data, width, height, bytes_per_line, QImage.Format_RGB888
            )
            self.pixmap = QPixmap.fromImage(q_img)
            self.video_label.setPixmap(
                self.pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio)
            )
            if self.is_expanded:
                self.video_label_2.setPixmap(
                    self.pixmap.scaled(self.video_label_2.size(), Qt.KeepAspectRatio)
                )
            self.current_frame = frame_number

    def update_output_frame(self, frame):
        """更新输出帧显示"""
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = frame.shape
        bytes_per_line = channels * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        self.pixmap = QPixmap.fromImage(q_img)

        if self.is_expanded:
            self.video_label_2.setPixmap(
                self.pixmap.scaled(self.video_label_2.size(), Qt.KeepAspectRatio)
            )

    def _region_offset(self, point):
        """计算区域偏移量（竖屏视频x有偏移）"""
        label_width = self.video_label.width()
        label_height = self.video_label.height()

        # Map the point
        video_x = point.x() - self.x_offset
        video_y = point.y() - self.y_offset

        # area bound
        video_x = min(max(video_x, 0), (label_width - self.x_offset * 2))
        video_y = min(max(video_y, 0), (label_height - self.y_offset * 2))

        return QPoint(video_x, video_y)

    def _region_to_video(self, point):
        """将label坐标转换为frame坐标"""
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        video_width, video_height = self.video_frame_size

        # Calculate the scale ratio
        scale_width = video_width / (label_width - self.x_offset * 2)
        scale_height = video_height / (label_height - self.y_offset * 2)

        # Convert the coordinates to original video coordinates
        x1 = int((point.x()) * scale_width)
        y1 = int((point.y()) * scale_height)

        return x1, y1

    def start_confirmation(self):
        """开始运行"""
        x1, x2, y1, y2 = self.confirm_region()
        start, end = (
            int(self.start_label.text().split(": ")[1]),
            int(self.end_label.text().split(": ")[1]),
        )
        if not self.my_thread or not self.my_thread.isRunning():

            # storage config
            with open("config.json", "w", encoding="utf-8") as f:
                config = {
                    "is_expanded": self.is_expanded,
                    "region": {
                        "x": self.selected_region.x(),
                        "y": self.selected_region.y(),
                        "width": self.selected_region.width(),
                        "height": self.selected_region.height(),
                    },
                    "inpaint": self.inpainter.method,
                    "contour_area": self.inpainter.contour_area,
                    "dilate_size": (self.inpainter.dilate_kernal_size - 1) // 2,
                }
                f.write(json.dumps(config, indent=4))

            # start task in a thread
            self.my_thread = Worker(
                self.selected_video_path, (x1, x2, y1, y2), (start, end), self.inpainter
            )
            self.my_thread.updateProgressBar.connect(self.progress_bar.setValue)
            self.my_thread.updateButtonText.connect(self.confirm_button.setText)
            self.my_thread.enableProgress.connect(self.progress_slider.setEnabled)
            self.my_thread.enableButton.connect(self.confirm_button.setEnabled)
            self.my_thread.enableSelection.connect(self.select_file_button.setEnabled)
            self.my_thread.updateInputFrame.connect(self.update_input_frame)
            self.my_thread.updateOutputFrame.connect(self.update_output_frame)
            self.my_thread.showCompletionMessage.connect(self.show_completion_message)
            self.my_thread.start()

    def confirm_region(self):
        """获取区域坐标"""
        if not self.selected_region.isNull():
            x1, y1 = self._region_to_video(self.selected_region.topLeft())
            x2, y2 = self._region_to_video(self.selected_region.bottomRight())
            print(self, "Selected Region", f"Coordinates: ({x1}, {y1}, {x2}, {y2})")
            return (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2))
        else:
            video_width, video_height = self.video_frame_size
            return 0, video_width - 1, 0, video_height - 1

    def test(self, model):
        """测试Inpainter"""
        inpainter = Inpainter(
            model,
            int(self.contour_area_input.text()),
            int(self.dilate_kernal_size_input.text()) * 2 + 1,
        )

        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        ret, frame = self.video_capture.read()
        if ret:
            x1, x2, y1, y2 = self.confirm_region()
            frame_area = frame[y1:y2, x1:x2]
            frame_area = inpainter.inpaint_text(frame_area)
            frame[y1:y2, x1:x2] = frame_area
            self.update_output_frame(frame)

        return inpainter

    def test_mask(self):
        self.test("test")

    def test_inpaint(self):
        inpainter = self.test("opencv")
        self.inpainter = inpainter

    def test_inpaint2(self):
        inpainter = self.test("lama")
        self.inpainter = inpainter

    def show_completion_message(self, elapsed_time):
        """运行结束提示"""
        self.show_info_message("提示", "已完成", f"耗时: {elapsed_time:.2f} 秒")

    def start_drawing(self, event):
        """开始绘制选区"""
        if event.button() == Qt.LeftButton and self.video_capture is not None:
            self.start_point = self._region_offset(event.pos())
            self.is_drawing = True
            self.selected_region = QRect()  # 清空以前的选区

    def update_drawing(self, event):
        """更新绘制选区"""
        if self.is_drawing and self.video_capture is not None:
            self.end_point = self._region_offset(event.pos())
            self.selected_region = QRect(self.start_point, self.end_point)
            self.update()

    def end_drawing(self, event):
        """结束绘制选区"""
        if event.button() == Qt.LeftButton and self.video_capture is not None:
            self.end_point = self._region_offset(event.pos())
            self.selected_region = QRect(self.start_point, self.end_point)
            self.update()

    def paintEvent(self, event):
        """绘制事件（更新视频帧&红框显示）"""
        if self.video_capture != None and not self.selected_region.isNull():
            pixmap = self.pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio)
            painter = QPainter(pixmap)
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.selected_region)
            painter.end()
            self.video_label.setPixmap(pixmap)
            self.video_label.update()

    def closeEvent(self, event):
        """关闭事件"""
        if self.video_capture:
            self.video_capture.release()
        event.accept()

    def keyPressEvent(self, event):
        """按键事件（方向键控制滑动条）"""
        step = 5 if event.modifiers() & Qt.ShiftModifier else 1

        if event.key() == Qt.Key_Right:
            self.current_frame += step
            if self.current_frame >= self.total_frames:
                self.current_frame = self.total_frames - 1
            self.progress_slider.setValue(self.current_frame)
            self.update_input_frame(self.current_frame)

        elif event.key() == Qt.Key_Left:
            self.current_frame -= step
            if self.current_frame < 0:
                self.current_frame = 0
            self.progress_slider.setValue(self.current_frame)
            self.update_input_frame(self.current_frame)


class Worker(QThread):
    updateProgressBar = pyqtSignal(int)
    updateButtonText = pyqtSignal(str)
    updateInputFrame = pyqtSignal(int)
    updateOutputFrame = pyqtSignal(np.ndarray)  # image(np.ndarray)
    enableProgress = pyqtSignal(bool)
    enableButton = pyqtSignal(bool)
    enableSelection = pyqtSignal(bool)
    showCompletionMessage = pyqtSignal(float)

    def __init__(self, selected_video_path, selected_region, during, inpainter):
        super().__init__()
        self.selected_video_path = selected_video_path
        self.selected_region = selected_region
        self.start_frame, self.end_frame = during
        self.inpainter = inpainter

    def run(self):
        self.enableProgress.emit(False)
        self.enableButton.emit(False)
        self.enableSelection.emit(False)
        self.updateButtonText.emit("Running...")
        self.updateProgressBar.emit(0)

        start_time = time.time()  # Start timing

        inpaint_video.run(
            self.selected_video_path,
            self.selected_region,
            self.inpainter,
            self.start_frame,
            self.end_frame,
            self.updateProgressBar.emit,
            self.updateInputFrame.emit,
            self.updateOutputFrame.emit,
        )

        end_time = time.time()  # End timing
        elapsed_time = end_time - start_time
        self.showCompletionMessage.emit(elapsed_time)

        self.enableProgress.emit(True)
        self.enableButton.emit(True)
        self.enableSelection.emit(True)
        self.updateButtonText.emit("🚀 Run!")


def main():
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec_())
