import sys
import cv2
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QWidget,
    QSlider,
    QMessageBox,
    QProgressBar,
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen
from PyQt5.QtCore import Qt, QRect, QPoint, QThread, pyqtSignal
import inpaint_video

class Worker(QThread):
    updateProgressBar = pyqtSignal(int)
    updateButtonText = pyqtSignal(str)
    updateFrame = pyqtSignal(int)

    def __init__(self, selected_video_path, selected_region):
        super().__init__()
        self.selected_video_path = selected_video_path
        self.selected_region = selected_region

    def run(self):
        inpaint_video.run(
            self.selected_video_path,
            self.selected_region,
            self.updateProgressBar.emit,
            self.updateButtonText.emit,
            self.updateFrame.emit,
        )

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Player")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # Widgets
        # Video Frame Image
        self.video_label = QLabel(self)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.video_label)
        # Video Progress Slider
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setEnabled(False)
        self.layout.addWidget(self.progress_slider)
        # Video File Selection
        self.select_file_button = QPushButton("Select Video File", self)
        self.select_file_button.clicked.connect(self.open_file_dialog)
        self.layout.addWidget(self.select_file_button)
        # Confirm Button
        self.confirm_button = QPushButton("🚀 Run!", self)
        self.confirm_button.setEnabled(False)
        self.layout.addWidget(self.confirm_button)
        # Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        # Signals
        self.confirm_button.clicked.connect(self.start_confirmation)
        self.progress_slider.sliderMoved.connect(self.update_frame)

        self.selected_video_path = None
        self.video_capture = None
        self.total_frames = 0
        self.current_frame = 0
        self.video_fps = 30  # Assume default 30 FPS for simplicity

        # Region selection variables
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_drawing = False
        self.selected_region = QRect()

        self.video_label.mousePressEvent = self.start_drawing
        self.video_label.mouseMoveEvent = self.update_drawing
        self.video_label.mouseReleaseEvent = self.end_drawing

        self.video_frame_size = None
        self.pixmap = None
        self.my_thread = None

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

        # Set slider range and enable controls
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(self.total_frames - 1)
        self.progress_slider.setEnabled(True)
        self.confirm_button.setEnabled(True)

        # Show first frame
        self.update_frame(0)

    def update_frame(self, frame_number):
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
            self.current_frame = frame_number

    def start_drawing(self, event):
        if event.button() == Qt.LeftButton:
            self.video_label.setPixmap(
                self.pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio)
            )
            self.start_point = event.pos()
            self.is_drawing = True
            self.selected_region = QRect()  # Clear the previous selection

    def update_drawing(self, event):
        if self.is_drawing:
            self.video_label.setPixmap(
                self.pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio)
            )
            self.end_point = event.pos()
            # area bound
            x1 = min(max(self.start_point.x(), 0), self.video_label.width()-1)
            y1 = min(max(self.start_point.y(), 0), self.video_label.height()-1)
            x2 = min(max(self.end_point.x(), 0), self.video_label.width()-1)
            y2 = min(max(self.end_point.y(), 0), self.video_label.height()-1)
            self.selected_region = QRect(QPoint(x1, y1), QPoint(x2, y2))
            self.update()

    def end_drawing(self, event):
        if event.button() == Qt.LeftButton:
            self.video_label.setPixmap(
                self.pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio)
            )
            self.is_drawing = False
            self.end_point = event.pos()
            # area bound
            x1 = min(max(self.start_point.x(), 0), self.video_label.width()-1)
            y1 = min(max(self.start_point.y(), 0), self.video_label.height()-1)
            x2 = min(max(self.end_point.x(), 0), self.video_label.width()-1)
            y2 = min(max(self.end_point.y(), 0), self.video_label.height()-1)
            self.selected_region = QRect(QPoint(x1, y1), QPoint(x2, y2))
            self.update()

    def paintEvent(self, event):
        if not self.selected_region.isNull():
            painter = QPainter(self.video_label.pixmap())
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.selected_region)
            self.video_label.update()

    def start_confirmation(self):
        res, x1, x2, y1, y2 = self.confirm_region()
        if not self.my_thread or not self.my_thread.isRunning():
            if res:           
                self.my_thread = Worker(
                    self.selected_video_path,
                    (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)),
                )
            else:
                video_width, video_height = self.video_frame_size
                self.my_thread = Worker(
                    self.selected_video_path,
                    (0, video_width-1, 0, video_height-1),
                )
            self.my_thread.updateProgressBar.connect(self.update_progressBar)
            self.my_thread.updateButtonText.connect(self.update_buttonText)
            self.my_thread.updateFrame.connect(self.update_frame)
            self.progress_bar.setValue(0)
            self.confirm_button.setText("Running...")
            self.my_thread.start()
            self.progress_bar.setValue(100)
            self.confirm_button.setText("🚀 Run!")
            # print((x1, x2, y1, y2))
                    
    
    def update_progressBar(self, cnt):
        self.progress_bar.setValue(cnt)

    def update_buttonText(self, msg):
        self.confirm_button.setText(msg)

    def confirm_region(self):
        if not self.selected_region.isNull():
            label_width = self.video_label.width()
            label_height = self.video_label.height()
            video_width, video_height = self.video_frame_size

            # Calculate the scale ratio
            scale_width = video_width / label_width
            scale_height = video_height / label_height

            # Convert the coordinates to original video coordinates
            x1 = int(self.selected_region.topLeft().x() * scale_width)
            y1 = int(self.selected_region.topLeft().y() * scale_height)
            x2 = int(self.selected_region.bottomRight().x() * scale_width)
            y2 = int(self.selected_region.bottomRight().y() * scale_height)

            print(self, "Selected Region", f"Coordinates: ({x1}, {y1}, {x2}, {y2})")
            return True, x1, x2, y1, y2
        else:
            # QMessageBox.information(
            #     self, "No Region Selected", "Please select a region first."
            # )
            return False, None, None, None, None

    def closeEvent(self, event):
        if self.video_capture:
            self.video_capture.release()
        event.accept()


def main():
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec_())
