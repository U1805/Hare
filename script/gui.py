import sys
import cv2
import time
import numpy as np
from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen
from PyQt5.QtCore import Qt, QRect, QPoint, QThread, pyqtSignal
import inpaint_video
import asyncio
from layout import VideoPlayerLayout
from inpaint_text import Inpainter
from PyQt5.QtWidgets import QMessageBox


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

        self.inpainter = Inpainter()

    def open_file_dialog(self):
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
        self.video_capture = cv2.VideoCapture(self.selected_video_path)
        self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))

        # Get video frame size
        self.video_frame_size = (
            int(self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
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

    def start_drawing(self, event):
        if event.button() == Qt.LeftButton and self.video_capture != None:
            self.video_label.setPixmap(
                self.pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio)
            )
            self.start_point = self._region_offset(event.pos())
            self.is_drawing = True
            self.selected_region = QRect()  # Clear the previous selection

    def update_drawing(self, event):
        if self.is_drawing and self.video_capture != None:
            self.video_label.setPixmap(
                self.pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio)
            )
            self.end_point = self._region_offset(event.pos())
            self.selected_region = QRect(self.start_point, self.end_point)
            self.update()

    def end_drawing(self, event):
        if event.button() == Qt.LeftButton and self.video_capture != None:
            self.video_label.setPixmap(
                self.pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio)
            )
            self.end_point = self._region_offset(event.pos())
            self.selected_region = QRect(self.start_point, self.end_point)
            self.update()

    def paintEvent(self, event):
        if not self.selected_region.isNull():
            painter = QPainter(self.video_label.pixmap())
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.selected_region)
            self.video_label.update()

    def start_confirmation(self):
        x1, x2, y1, y2 = self.confirm_region()
        if not self.my_thread or not self.my_thread.isRunning():
            self.my_thread = Worker(
                self.selected_video_path, (x1, x2, y1, y2), self.inpainter
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
        if not self.selected_region.isNull():
            x1, y1 = self._region_to_video(self.selected_region.topLeft())
            x2, y2 = self._region_to_video(self.selected_region.bottomRight())
            print(self, "Selected Region", f"Coordinates: ({x1}, {y1}, {x2}, {y2})")
            return (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2))
        else:
            video_width, video_height = self.video_frame_size
            return 0, video_width - 1, 0, video_height - 1

    def closeEvent(self, event):
        if self.video_capture:
            self.video_capture.release()
        event.accept()

    def test(self, model):
        # if self.checkbox.checkState() == 2:
        #     inpainter = Inpainter(
        #         model,
        #         int(self.contour_area_input.text()),
        #         int(self.dilate_kernal_size_input.text()) * 2 + 1,
        #         self.color_display_input.text(),
        #         int(self.color_tolerance.text()),
        #     )
        # elif self.checkbox.checkState() == 0:
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
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("已完成")
        msg.setInformativeText(f"耗时: {elapsed_time:.2f} 秒")
        msg.setWindowTitle("提示")
        msg.exec_()


class Worker(QThread):
    updateProgressBar = pyqtSignal(int)
    updateButtonText = pyqtSignal(str)
    updateInputFrame = pyqtSignal(int)
    updateOutputFrame = pyqtSignal(np.ndarray)  # image(np.ndarray)
    enableProgress = pyqtSignal(bool)
    enableButton = pyqtSignal(bool)
    enableSelection = pyqtSignal(bool)
    showCompletionMessage = pyqtSignal(float)

    def __init__(self, selected_video_path, selected_region, inpainter):
        super().__init__()
        self.selected_video_path = selected_video_path
        self.selected_region = selected_region
        self.inpainter = inpainter

    def run(self):
        self.enableProgress.emit(False)
        self.enableButton.emit(False)
        self.enableSelection.emit(False)
        self.updateButtonText.emit("Running...")
        self.updateProgressBar.emit(0)

        start_time = time.time()  # Start timing

        asyncio.run(
            inpaint_video.run(
                self.selected_video_path,
                self.selected_region,
                self.inpainter,
                self.updateProgressBar.emit,
                self.updateInputFrame.emit,
                self.updateOutputFrame.emit,
            )
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
