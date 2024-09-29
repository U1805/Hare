import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QGridLayout,
    QSpinBox,
    QTableWidget,
    QSplashScreen,
    QAction,
    QPushButton,
    QSlider,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QProgressDialog,
    QVBoxLayout,
    QDialogButtonBox,
    QMessageBox,
    QSizePolicy,
    QTableWidgetItem,
    QSpacerItem,
    QFileDialog,
    QDialog,
)
from PyQt5.QtCore import Qt, QPoint, QRect, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QIcon, QImage, QColor, QPainter, QPen
from inpaint_text import Inpainter
import inpaint_video
import cv2
import numpy as np
import time


class InfoWindow(QMessageBox):
    def __init__(self, msg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Information")
        self.setIcon(QMessageBox.Information)
        self.setText(msg)
        self.setStandardButtons(QMessageBox.Ok)
        self.exec_()


class WarnWindow(QMessageBox):
    def __init__(self, msg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Warning")
        self.setIcon(QMessageBox.Warning)
        self.setText(msg)
        self.setStandardButtons(QMessageBox.Ok)
        self.exec_()


class ErrorWindow(QMessageBox):
    def __init__(self, msg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Error")
        self.setIcon(QMessageBox.Critical)
        self.setText(msg)
        self.setStandardButtons(QMessageBox.Ok)
        self.exec_()


class ParameterWindow(QDialog):
    def __init__(
        self, noise_input, stroke_input, x_offset_input, y_offset_input, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("参数设置")
        layout = QVBoxLayout(self)

        # 噪声参数
        self.noise_label = QLabel("噪声:")
        self.noise_input = QSpinBox(self)
        self.noise_input.setRange(0, 100)
        self.noise_input.setValue(noise_input)
        self.noise_input.setAlignment(Qt.AlignCenter)
        noise_layout = QHBoxLayout()
        noise_layout.addWidget(self.noise_label)
        noise_layout.addWidget(self.noise_input)

        # 描边参数
        self.stroke_label = QLabel("描边:")
        self.stroke_input = QSpinBox(self)
        self.stroke_input.setRange(0, 100)
        self.stroke_input.setValue(stroke_input)
        self.stroke_input.setAlignment(Qt.AlignCenter)
        stroke_layout = QHBoxLayout()
        stroke_layout.addWidget(self.stroke_label)
        stroke_layout.addWidget(self.stroke_input)

        # 水平偏移参数
        self.x_offset_label = QLabel("水平偏移:")
        self.x_offset_input = QSpinBox(self)
        self.x_offset_input.setRange(-10, 10)
        self.x_offset_input.setValue(x_offset_input)
        self.x_offset_input.setAlignment(Qt.AlignCenter)
        x_offset_layout = QHBoxLayout()
        x_offset_layout.addWidget(self.x_offset_label)
        x_offset_layout.addWidget(self.x_offset_input)

        # 垂直偏移参数
        self.y_offset_label = QLabel("垂直偏移:")
        self.y_offset_input = QSpinBox(self)
        self.y_offset_input.setRange(-10, 10)
        self.y_offset_input.setValue(y_offset_input)
        self.y_offset_input.setAlignment(Qt.AlignCenter)
        y_offset_layout = QHBoxLayout()
        y_offset_layout.addWidget(self.y_offset_label)
        y_offset_layout.addWidget(self.y_offset_input)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # 添加到布局
        layout.addLayout(noise_layout)
        layout.addLayout(stroke_layout)
        layout.addLayout(x_offset_layout)
        layout.addLayout(y_offset_layout)
        layout.addWidget(button_box)

    # 返回四个参数值
    def get_values(self):
        return (
            self.noise_input.value(),
            self.stroke_input.value(),
            self.x_offset_input.value(),
            self.y_offset_input.value(),
        )


class ProgressWindow(QProgressDialog):
    cancel_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Processing...", "Cancel", 0, 100, parent)
        self.setWindowTitle("Running")
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumDuration(0)
        self.setValue(0)
        self.setAutoClose(True)

        self.start_time = time.time()  # Start timing
        self._is_canceled = False
        self.canceled.connect(self.on_cancel)

        self.show()

    def on_cancel(self):
        self._is_canceled = True
        self.cancel_signal.emit()
        self.close()

    def update_progress(self, value):
        if self._is_canceled:
            return
        self.setValue(value)
        if value >= 100:
            self.close()
            self.end_time = time.time()  # End timing
            msg = f"已完成！耗时: {(self.end_time - self.start_time):.2f} 秒"
            QMessageBox.information(self, "Complete", msg)


class Worker(QThread):
    test_button = pyqtSignal(bool)
    time_slider = pyqtSignal(bool)
    start_button = pyqtSignal(bool)
    update_input_frame = pyqtSignal(int)
    update_output_frame = pyqtSignal(np.ndarray)  # image(np.ndarray)
    update_progress = pyqtSignal(float)
    update_table = pyqtSignal(int)

    def __init__(self, selected_video_path, selected_region, inpainter):
        super().__init__()
        self.selected_video_path = selected_video_path
        self.selected_region = selected_region
        self.inpainter = inpainter
        self._is_running = True

    def run(self):
        self._is_running = True
        self.test_button.emit(False)
        self.time_slider.emit(False)
        self.start_button.emit(False)
        
        ret = inpaint_video.run(
            self.selected_video_path,
            self.selected_region,
            self.inpainter,
            self.update_progress.emit,
            self.update_input_frame.emit,
            self.update_output_frame.emit,
            self.update_table.emit,
            stop_check=self.stop_check,
        )

        self.test_button.emit(True)
        self.time_slider.emit(True)
        self.start_button.emit(True)

    def stop_check(self):
        return not self._is_running

    def stop(self):
        self._is_running = False


class MainWindowLayout(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hare")
        self.setAcceptDrops(True)

        # Setup central widget and layout
        self.central_widget = QWidget()
        self.main_layout = QGridLayout()
        self.main_layout.setSpacing(10)
        self.central_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.central_widget)

        # 加载组件
        self.setup_control_toolbar()
        self.setup_video_players()
        self.setup_subtitle_table()
        self.setup_menu_bar()

        # Ensure focus policy
        self.setFocusPolicy(Qt.StrongFocus)

    def setup_video_players(self):
        """上侧预览视频"""
        # 输入视频
        self.video_label_input = QLabel(self)
        self.video_label_input.setAlignment(Qt.AlignCenter)
        self.video_label_input.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.video_label_input.setStyleSheet(
            """
            background-color: transparent;
            border: 1px solid #76797C;
            border-radius: 5px;
        """
        )
        self.main_layout.addWidget(self.video_label_input, 1, 0, 3, 10)

        # 输出视频
        self.video_label_output = QLabel(self)
        self.video_label_output.setAlignment(Qt.AlignCenter)
        self.video_label_output.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.video_label_output.setStyleSheet(
            """
            background-color: transparent;
            border: 1px solid #76797C;
            border-radius: 5px;
        """
        )
        self.main_layout.addWidget(self.video_label_output, 1, 10, 3, 10)

    def setup_subtitle_table(self):
        """下侧时轴表"""
        self.subtitle_table = QTableWidget()
        self.subtitle_table.setColumnCount(101)
        self.subtitle_table.setRowCount(5)

        for i in range(101):
            time_label = QTableWidgetItem(f"{i+1}\n{i//60:02d}:{i%60:02d}.000")
            self.subtitle_table.setHorizontalHeaderItem(i, time_label)

        self.main_layout.addWidget(self.subtitle_table, 4, 0, 3, 20)

    def setup_control_toolbar(self):
        """上方控制按钮工具栏"""
        control_widget = QWidget()
        control_widget.setFixedHeight(40)
        control_layout = QHBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(5)

        # 开始按钮
        self.start_button = QPushButton("开始运行")
        self.start_button.setEnabled(False)
        control_layout.addWidget(self.start_button)

        control_layout.addItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Minimum)
        )

        # 时间轴
        self.time_label = QLabel("00:00 / 00:00")
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setEnabled(False)
        control_layout.addWidget(self.time_label)
        control_layout.addWidget(self.time_slider)

        control_layout.addItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Minimum)
        )

        # 当前帧测试 相关参数
        self.test_button = QPushButton("测试当前帧")
        self.test_button.setEnabled(False)
        control_layout.addWidget(self.test_button)

        self.algorithm_param_button = QPushButton("参数设置")
        control_layout.addWidget(self.algorithm_param_button)

        self.algorithm_label = QLabel("修复算法选择:")
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(
            [
                "MASK",
                "INPAINT_NS",
                "INPAINT_TELEA",
                "INPAINT_FSR_FAST",
                "INPAINT_FSR_BEST",
            ]
        )
        control_layout.addWidget(self.algorithm_label)
        control_layout.addWidget(self.algorithm_combo)

        self.main_layout.addWidget(control_widget, 0, 0, 1, 20)

    def setup_menu_bar(self):
        """顶部菜单栏"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("文件")
        self.open_video = QAction("选择视频", self)
        self.open_subtitle = QAction("选择字幕", self)
        file_menu.addAction(self.open_video)
        file_menu.addAction(self.open_subtitle)

        # Edit menu
        edit_menu = menu_bar.addMenu("编辑")
        test_action = QAction("测试用选项卡", self)
        edit_menu.addAction(test_action)

        # Help menu
        help_menu = menu_bar.addMenu("帮助")
        about_action = QAction("关于", self)
        help_menu.addAction(about_action)


class MainWindow(MainWindowLayout):
    def __init__(self):
        super().__init__()
        self.open_video.triggered.connect(self.select_video_file)
        self.time_slider.sliderMoved.connect(self.update_frame_input)
        self.time_slider.sliderMoved.connect(self.roll_table)
        self.video_label_input.mousePressEvent = self.start_drawing
        self.video_label_input.mouseMoveEvent = self.update_drawing
        self.video_label_input.mouseReleaseEvent = self.end_drawing
        self.algorithm_param_button.clicked.connect(self.update_param)
        self.test_button.clicked.connect(self.test)
        self.start_button.clicked.connect(self.run)

        self.cap = None
        self.total_frames = 0
        self.fps = 0
        self.video_frame_size = (0, 0)
        self.table = {
            "default1": [],
            "default2": [],
            "default3": [],
            "default4": [],
            "default5": [],
        }

        # 选区参数
        self.x_offset, self.y_offset = 0, 0
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selected_region = QRect()
        self.is_drawing = False
        self.pixmap = None

        # 算法参数
        self.noise_input = 20
        self.stroke_input = 0
        self.x_offset_input = -2
        self.y_offset_input = -2
        self.inpainter = Inpainter(
            "INPAINT_NS",
            self.noise_input,
            self.stroke_input,
            self.x_offset_input,
            self.y_offset_input,
        )
        self.my_thread = None

    def select_video_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4);;所有文件 (*)",
            options=options,
        )
        if not file_name:
            return
        self.cap = cv2.VideoCapture(file_name)
        self.file_path = file_name
        if not self.cap.isOpened():
            print("无法打开视频文件")
            return

        # 加载视频
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.video_frame_size = (
            int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        self.time_slider.setRange(0, self.total_frames - 1)

        # 计算偏移
        label_width = self.video_label_input.width()
        label_height = self.video_label_input.height()
        video_width, video_height = self.video_frame_size

        scaled_video_width = video_width * label_height / video_height
        scaled_video_height = video_height * label_width / video_width
        if scaled_video_width <= label_width:
            self.x_offset = (label_width - scaled_video_width) / 2
            self.y_offset = 0
        else:
            self.x_offset = 0
            self.y_offset = (label_height - scaled_video_height) / 2

        # 初始化视频
        self.update_frame_input(0)
        self.update_time_label(0)
        self.update_table_video()
        self.start_button.setEnabled(True)
        self.time_slider.setEnabled(True)
        self.test_button.setEnabled(True)

    def update_frame_input(self, frame_number=None):
        if not self.cap or not self.cap.isOpened():
            print("视频未打开")
            return

        if frame_number is not None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, self.current_frame = self.cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
            height, weight, channel = frame_rgb.shape
            bytes_per_line = channel * weight
            q_image = QImage(
                frame_rgb.data, weight, height, bytes_per_line, QImage.Format_RGB888
            )
            self.pixmap = QPixmap.fromImage(q_image)

            # 在 QLabel 中居中显示图像
            self.video_label_input.setPixmap(
                self.pixmap.scaled(self.video_label_input.size(), Qt.KeepAspectRatio)
            )
            self.video_label_input.setAlignment(Qt.AlignCenter)

            if frame_number is not None:
                self.update_time_label(frame_number)
        else:
            print("无法读取视频帧")

    def update_frame_output(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, weight, channel = frame_rgb.shape
        bytes_per_line = channel * weight
        q_image = QImage(
            frame_rgb.data, weight, height, bytes_per_line, QImage.Format_RGB888
        )
        pixmap = QPixmap.fromImage(q_image)

        # 在 QLabel 中居中显示图像
        self.video_label_output.setPixmap(
            pixmap.scaled(self.video_label_output.size(), Qt.KeepAspectRatio)
        )
        self.video_label_output.setAlignment(Qt.AlignCenter)

    def update_time_label(self, frame_number):
        if self.cap:
            current_time = frame_number / self.fps
            total_time = self.total_frames / self.fps
            self.time_label.setText(
                f"{self.format_time(current_time)} / {self.format_time(total_time)}"
            )

    def update_table_video(self):
        self.subtitle_table.setColumnCount(self.total_frames)
        for i in range(self.total_frames):
            current_time = i / self.fps
            time_label = QTableWidgetItem(f"{i+1}\n{self.format_time2(current_time)}")
            self.subtitle_table.setHorizontalHeaderItem(i, time_label)
            self.set_background_color(0, i, QColor("#FA8072"))
            self.table["default1"].append(True)

    def roll_table(self, value):
        self.subtitle_table.horizontalScrollBar().setValue(value)

    def update_param(self):
        window = ParameterWindow(
            self.noise_input,
            self.stroke_input,
            self.x_offset_input,
            self.y_offset_input,
        )
        if window.exec_() == QDialog.Accepted:
            noise, stroke, x_offset, y_offset = window.get_values()
            self.noise_input = noise
            self.stroke_input = stroke
            self.x_offset_input = x_offset
            self.y_offset_input = y_offset

    def test(self):
        inpainter = Inpainter(
            self.algorithm_combo.currentText(),
            self.noise_input,
            self.stroke_input * 2 + 1,
            self.x_offset_input,
            self.y_offset_input,
        )

        frame = self.current_frame.copy()
        x1, x2, y1, y2 = self.confirm_region()

        # 扩展取一像素
        x1_ext = max(0, x1 - 1)
        x2_ext = min(frame.shape[1], x2 + 1)
        y1_ext = max(0, y1 - 1)
        y2_ext = min(frame.shape[0], y2 + 1)

        frame_area_ext = frame[y1_ext:y2_ext, x1_ext:x2_ext]
        frame_area_ext_inpainted = inpainter.inpaint_text(frame_area_ext)
        frame_area_inpainted = frame_area_ext_inpainted[
            1 : (y2 - y1 + 1), 1 : (x2 - x1 + 1)
        ]
        frame[y1:y2, x1:x2] = frame_area_inpainted
        self.update_frame_output(frame)
        self.inpainter = inpainter

        return inpainter

    def run(self):
        x1, x2, y1, y2 = self.confirm_region()
        if not self.my_thread or not self.my_thread.isRunning():
            self.progress = ProgressWindow()
            self.my_thread = Worker(self.file_path, (x1, x2, y1, y2), self.inpainter)
            self.my_thread.start_button.connect(self.start_button.setEnabled)
            self.my_thread.time_slider.connect(self.time_slider.setEnabled)
            self.my_thread.test_button.connect(self.test_button.setEnabled)
            self.my_thread.update_input_frame.connect(self.update_frame_input)
            self.my_thread.update_output_frame.connect(self.update_frame_output)
            self.my_thread.update_progress.connect(self.progress.update_progress)
            self.my_thread.update_table.connect(self.roll_table)
            self.progress.cancel_signal.connect(self.my_thread.stop)
            self.my_thread.start()

    # utils
    def set_background_color(self, row, col, color):
        """设置表格单元格背景色"""
        item = self.subtitle_table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            self.subtitle_table.setItem(row, col, item)
        item.setBackground(color)

    def region_offset(self, point):
        """计算区域偏移量（竖屏视频x有偏移）"""
        label_width = self.video_label_input.width()
        label_height = self.video_label_input.height()

        # Map the point
        video_x = point.x() - self.x_offset
        video_y = point.y() - self.y_offset

        # area bound
        video_x = min(max(video_x, 0), (label_width - self.x_offset * 2))
        video_y = min(max(video_y, 0), (label_height - self.y_offset * 2))

        return QPoint(video_x, video_y)

    def region_to_video(self, point):
        """将label坐标转换为frame坐标"""
        label_width = self.video_label_input.width()
        label_height = self.video_label_input.height()
        video_width, video_height = self.video_frame_size

        # Calculate the scale ratio
        scale_width = video_width / (label_width - self.x_offset * 2)
        scale_height = video_height / (label_height - self.y_offset * 2)

        # Convert the coordinates to original video coordinates
        x1 = int((point.x()) * scale_width)
        y1 = int((point.y()) * scale_height)

        return x1, y1

    def confirm_region(self):
        """获取区域坐标"""
        if not self.selected_region.isNull():
            x1, y1 = self.region_to_video(self.selected_region.topLeft())
            x2, y2 = self.region_to_video(self.selected_region.bottomRight())
            return (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2))
        else:
            video_width, video_height = self.video_frame_size
            return 0, video_width - 1, 0, video_height - 1

    @staticmethod
    def format_time(seconds):
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def format_time2(seconds):
        milliseconds = int((seconds - int(seconds)) * 1000)
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes:02d}:{int(seconds):02d}.{milliseconds:03d}"

    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "current_frame"):
            self.update_frame_input()

    def start_drawing(self, event):
        """开始绘制选区"""
        if event.button() == Qt.LeftButton and self.cap is not None:
            self.start_point = self.region_offset(event.pos())
            self.is_drawing = True
            self.selected_region = QRect()  # 清空以前的选区

    def update_drawing(self, event):
        """更新绘制选区"""
        if self.is_drawing and self.cap is not None:
            self.end_point = self.region_offset(event.pos())
            self.selected_region = QRect(self.start_point, self.end_point)
            self.update()

    def end_drawing(self, event):
        """结束绘制选区"""
        if event.button() == Qt.LeftButton and self.cap is not None:
            self.end_point = self.region_offset(event.pos())
            self.selected_region = QRect(self.start_point, self.end_point)
            self.update()

    def paintEvent(self, event):
        """绘制事件（更新视频帧&红框显示）"""
        if self.cap != None and not self.selected_region.isNull():
            pixmap = self.pixmap.scaled(
                self.video_label_input.size(), Qt.KeepAspectRatio
            )
            painter = QPainter(pixmap)
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.selected_region)
            painter.end()
            self.video_label_input.setPixmap(pixmap)
            self.video_label_input.update()


def main():
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    resources_path = Path("resources")

    # Splash screen
    splash_path = resources_path / "splash.png"
    splash_img = QPixmap(str(splash_path)).scaled(
        300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    splash = QSplashScreen(splash_img)
    splash.show()

    # Apply QSS styling
    qss_path = resources_path / "qdark.qss"
    with open(qss_path, "r") as qss_file:
        app.setStyleSheet(qss_file.read())

    app.setFont(QFont("Microsoft YaHei", 9))

    # Create and setup main window
    main_window = MainWindow()
    favicon_path = resources_path / "favicon.ico"
    main_window.setWindowIcon(QIcon(str(favicon_path)))

    # Set window size and position
    screen_geometry = app.primaryScreen().geometry()
    main_window.resize(
        int(screen_geometry.width() * 0.75), int(screen_geometry.height() * 0.75)
    )
    main_window.move(
        (screen_geometry.width() - main_window.width()) // 2,
        (screen_geometry.height() - main_window.height()) // 2,
    )

    main_window.showMaximized()
    splash.finish(main_window)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
