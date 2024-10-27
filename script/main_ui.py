import re
import time
import json
import sys
from pathlib import Path

import cv2
import numpy as np
# fmt: off
from PyQt5.QtWidgets import (
    QGridLayout, QHBoxLayout, QVBoxLayout, QSpacerItem, 
    QApplication, QMainWindow, QWidget, QSplashScreen,
    QLabel, QComboBox, QSpinBox, QMessageBox, QPushButton, QSlider, 
    QFileDialog, QDialog, QProgressDialog, QDialogButtonBox, 
    QTableWidget, QTableWidgetItem,
    QSizePolicy, QAction
)
# fmt: on
from PyQt5.QtCore import Qt, QPoint, QRect, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QIcon, QImage, QColor, QPainter, QPen

from inpaint_text import Inpainter
from inpaint_video import VideoInpainter

# fmt: off
try:
    import importlib.metadata
    importlib.metadata.version("torch")
    lama_flag = True
except ImportError as e:
    lama_flag = False
# fmt: on


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
        self,
        stroke_input,
        x_offset_input=-2,
        y_offset_input=-2,
        autosub=3000,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("参数设置")

        # 创建一个网格布局
        layout = QVBoxLayout(self)
        grid_layout = QGridLayout()

        # 描边
        self.stroke_label = QLabel("描边:")
        self.stroke_input = QSpinBox(self)
        self.stroke_input.setRange(0, 100)
        self.stroke_input.setValue(stroke_input)
        self.stroke_input.setAlignment(Qt.AlignCenter)
        grid_layout.addWidget(self.stroke_label, 0, 0)
        grid_layout.addWidget(self.stroke_input, 0, 1, 1, 3)

        # 水平偏移
        self.x_offset_label = QLabel("水平偏移:")
        self.x_offset_input = QSpinBox(self)
        self.x_offset_input.setRange(-10, 100)
        self.x_offset_input.setValue(x_offset_input)
        self.x_offset_input.setAlignment(Qt.AlignCenter)
        grid_layout.addWidget(self.x_offset_label, 1, 0)
        grid_layout.addWidget(self.x_offset_input, 1, 1)

        # 垂直偏移
        self.y_offset_label = QLabel("垂直偏移:")
        self.y_offset_input = QSpinBox(self)
        self.y_offset_input.setRange(-10, 100)
        self.y_offset_input.setValue(y_offset_input)
        self.y_offset_input.setAlignment(Qt.AlignCenter)
        grid_layout.addWidget(self.y_offset_label, 1, 2)
        grid_layout.addWidget(self.y_offset_input, 1, 3)

        # 打轴机阈值
        self.autosub_label = QLabel("打轴阈值:")
        self.autosub_input = QSpinBox(self)
        self.autosub_input.setRange(0, 999999)
        self.autosub_input.setValue(autosub)
        self.autosub_input.setAlignment(Qt.AlignCenter)
        grid_layout.addWidget(self.autosub_label, 2, 0)
        grid_layout.addWidget(self.autosub_input, 2, 1, 1, 3)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # 将网格布局添加到垂直布局中
        layout.addLayout(grid_layout)
        layout.addWidget(button_box)

    # 返回参数值
    def get_values(self):
        return (
            self.stroke_input.value(),
            self.x_offset_input.value(),
            self.y_offset_input.value(),
            self.autosub_input.value(),
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
        if value >= 100 and not self._is_canceled:
            self.close()
            self.end_time = time.time()  # End timing
            msg = f"已完成！耗时: {(self.end_time - self.start_time):.2f} 秒"
            QMessageBox.information(self, "Complete", msg)
            self._is_canceled = True


class Worker(QThread):
    test_button = pyqtSignal(bool)
    time_slider = pyqtSignal(bool)
    start_button = pyqtSignal(bool)
    update_input_frame = pyqtSignal(np.ndarray)
    update_output_frame = pyqtSignal(np.ndarray)
    update_progress = pyqtSignal(float)
    update_table = pyqtSignal((int, int, str))
    result_signal = pyqtSignal(object)

    def __init__(self, selected_video_path, selected_regions, inpainter, time_table):
        super().__init__()
        self.selected_video_path = selected_video_path
        self.selected_regions = selected_regions
        self.inpainter = inpainter
        self.time_table = time_table
        self._is_running = True

        self.inpaint_video = VideoInpainter(
            self.selected_video_path,
            self.selected_regions,
            self.time_table,
            self.inpainter,
            self.update_progress.emit,
            self.update_input_frame.emit,
            self.update_output_frame.emit,
            self.update_table.emit,
            stop_check=self.stop_check,
        )

    def run(self):
        self._is_running = True
        self.test_button.emit(False)
        self.time_slider.emit(False)
        self.start_button.emit(False)

        ret = self.inpaint_video.run()
        self.result_signal.emit(ret)

        self.test_button.emit(True)
        self.time_slider.emit(True)
        self.start_button.emit(True)

    def stop_check(self):
        return not self._is_running

    def stop(self):
        self._is_running = False


class MainWindowLayout(QMainWindow):
    """
    主窗口类，实现组件布局
    """

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
        self.subtitle_table.setEditTriggers(QTableWidget.NoEditTriggers)

        for i in range(101):
            time_label = QTableWidgetItem(f"{i}\n{i//60:02d}:{i%60:02d}.000")
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

        self.algorithm_label = QLabel("算法选择:")
        self.algorithm_combo = QComboBox()
        algo_list = [
            "MASK",
            "AUTOSUB",
            "INPAINT_NS",
            # "INPAINT_TELEA",
            "INPAINT_FSR_PARA",
            # "INPAINT_FSR_FAST",
            # "INPAINT_FSR_BEST",
        ]
        if lama_flag:
            algo_list.append("INPAINT_LAMA")
        self.algorithm_combo.addItems(algo_list)
        control_layout.addWidget(self.algorithm_label)
        control_layout.addWidget(self.algorithm_combo)

        self.main_layout.addWidget(control_widget, 0, 0, 1, 20)

    def setup_menu_bar(self):
        """顶部菜单栏"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("文件")
        self.open_video_button = QAction("选择视频", self)
        self.open_sub_button = QAction("选择字幕", self)
        file_menu.addAction(self.open_video_button)
        file_menu.addAction(self.open_sub_button)

        # Edit menu
        edit_menu = menu_bar.addMenu("编辑")
        self.load_config_button = QAction("加载配置", self)
        self.save_config_button = QAction("保存配置", self)
        edit_menu.addAction(self.load_config_button)
        edit_menu.addAction(self.save_config_button)

        # Help menu
        help_menu = menu_bar.addMenu("帮助")
        about_action = QAction("关于", self)
        test_action = QAction("测试用选项卡", self)
        help_menu.addAction(about_action)
        help_menu.addAction(test_action)


class MainWindow(MainWindowLayout):
    """
    主窗口类，实现信号槽绑定和具体功能
    """

    def __init__(self):
        """
        初始化主窗口，设置界面各控件的信号槽连接，初始化相关参数
        """
        # 初始化布局
        super().__init__()
        # 连接信号槽
        load_video = lambda: self.load_video_file(None)
        self.open_video_button.triggered.connect(load_video)  # 打开视频文件
        load_subtitle = lambda: self.load_subtitle_file(None)
        self.open_sub_button.triggered.connect(load_subtitle)  # 打开字幕文件
        load_config = lambda: self.load_config(None)
        self.load_config_button.triggered.connect(load_config)  # 打开配置
        self.save_config_button.triggered.connect(self.save_config)  # 保存配置
        self.time_slider.sliderMoved.connect(self.update_frame)  # 更新视频帧
        self.time_slider.sliderMoved.connect(self.roll_table)  # 滚动字幕表格
        self.video_label_input.mousePressEvent = self.start_drawing  # 开始绘制选区
        self.video_label_input.mouseMoveEvent = self.update_drawing  # 更新绘制
        self.video_label_input.mouseReleaseEvent = self.end_drawing  # 结束绘制
        self.algorithm_param_button.clicked.connect(self.update_param)  # 更新算法参数
        self.test_button.clicked.connect(self.test)  # 测试图像修复算法
        self.start_button.clicked.connect(self.run)  # 运行修复任务
        self.subtitle_table.itemSelectionChanged.connect(self.selected_cell)
        self.subtitle_table.cellDoubleClicked.connect(self.change_state_cell)
        self.subtitle_table.verticalHeader().sectionClicked.connect(self.select_region)
        self.subtitle_table.verticalHeader().sectionDoubleClicked.connect(
            self.change_region_color
        )

        # 初始化视频相关参数
        self.cap = None
        self.total_frames = 0
        self.fps = 0
        self.video_frame_size = (0, 0)
        self.table = {}  # 存储时轴表格信息
        self.video_path = ""
        self.subtitle_path = ""

        # 初始化选区参数
        self.x_offset, self.y_offset = -2, -2
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selected_regions = [{"region": QRect(0, 0, 0, 0), "binary": True}]
        self.is_drawing = False
        self.pixmap = None
        self.draw_id = 0

        # 初始化算法参数
        self.worker_thread = None
        self.stroke_input = 0
        self.x_offset_input = 0
        self.y_offset_input = 0
        self.autosub_input = 0
        self.inpainter = Inpainter()
        if Path("config.json").exists():
            self.load_config(Path("config.json"))
        else:
            self.load_default_config()

    # 配置参数持久化
    def load_config(self, path=None):
        if path is None:
            options = QFileDialog.Options()
            options |= QFileDialog.ReadOnly
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择配置文件",
                "",
                "配置文件 (*.json);;所有文件 (*)",
                options=options,
            )

        with open(path, "r", encoding="utf-8") as f:
            try:
                config = json.loads(f.read())
                print(config)
                self.stroke_input = config["stroke"]
                self.x_offset_input = config["x_offset"]
                self.y_offset_input = config["y_offset"]
                self.autosub_input = config["autosub"]
                self.algorithm_combo.setCurrentText(config["inpaint"])
                self.inpainter = Inpainter(
                    method=config["inpaint"],
                    stroke=self.stroke_input,
                    x_offset=self.x_offset_input,
                    y_offset=self.y_offset_input,
                    autosub=self.autosub_input,
                )
            except:
                WarnWindow("配置文件错误，请删除 config.json")
                self.load_default_config()

    def load_default_config(self):
        self.stroke_input = 0
        self.x_offset_input = -2
        self.y_offset_input = -2
        self.autosub_input = 3000
        self.inpainter = Inpainter(
            "MASK",
        )

    def save_config(self):
        with open("config.json", "w", encoding="utf-8") as f:
            config = {
                "inpaint": self.inpainter.method,
                "stroke": self.inpainter.stroke,
                "x_offset": self.inpainter.x_offset,
                "y_offset": self.inpainter.y_offset,
                "autosub": self.autosub_input,
            }
            f.write(json.dumps(config, indent=4, ensure_ascii=False))

    def update_param(self):
        """
        更新图像修复算法的参数，通过弹窗获取用户输入的参数
        """
        window = ParameterWindow(
            self.stroke_input,
            self.x_offset_input,
            self.y_offset_input,
            self.autosub_input,
        )
        if window.exec_() == QDialog.Accepted:
            (
                self.stroke_input,
                self.x_offset_input,
                self.y_offset_input,
                self.autosub_input,
            ) = window.get_values()

    # 载入视频文件和时轴文件
    def load_video_file(self, file_name=None):
        """
        打开并加载视频文件，初始化相关视频参数并更新界面
        """
        if file_name is None:
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

        if self.cap is not None and self.cap.isOpened():
            if file_name == self.video_path:
                self.init_table()
                return
            else:
                self.cap.release()

        self.cap = cv2.VideoCapture(file_name)
        self.video_path = file_name
        self.subtitle_path = ""
        if not self.cap.isOpened():
            ErrorWindow("无法打开视频文件")
            return

        # 初始化视频相关参数
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.video_frame_size = (
            int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        self.time_slider.setRange(0, self.total_frames - 1)
        self.draw_id = 0

        # 更新界面
        self.init_offset()
        self.init_table()
        self.update_frame(0)
        self.update_time_label(0)
        self.start_button.setEnabled(True)
        self.time_slider.setEnabled(True)
        self.test_button.setEnabled(True)

    def load_subtitle_file(self, file_name=None):
        """
        打开并加载字幕文件，解析字幕并更新时轴表格
        """
        if file_name is None:
            if not self.cap or not self.fps:
                WarnWindow("请先选择视频文件")
                return
            options = QFileDialog.Options()
            options |= QFileDialog.ReadOnly
            file_name, _ = QFileDialog.getOpenFileName(
                self,
                "选择时轴文件",
                "",
                "时轴文件 (*.ass);;所有文件 (*)",
                options=options,
            )
            if not file_name:
                return

        with open(file_name, "r", encoding="utf-8") as f:
            content = f.read()
        self.subtitle_path = file_name

        # 分析字幕文件数据
        dialogue_list = []
        for line in content.split("\n"):
            temp = self.parse_ass_line(line)
            if temp and temp["Type"] == "Dialogue":
                temp["Start"] = int(temp["Start"] * self.fps) + 1
                temp["End"] = int(temp["End"] * self.fps) + 1
                dialogue_list.append(temp)

        # 整理成时轴表格
        self.table = {}
        flag = True
        for idx, dialogue in enumerate(dialogue_list):
            title = dialogue["Style"]
            if title not in self.table:
                self.table[title] = [None] * self.total_frames
            for i in range(dialogue["Start"], dialogue["End"]):
                try:
                    if self.table[title][i] is None and flag:
                        self.table[title][i] = (
                            f"{idx + 1} - {dialogue['Name']}"
                            if dialogue["Name"]
                            else f"{idx + 1}"
                        )
                except:
                    ErrorWindow("时轴超过视频范围，请检查时轴")
                    flag = False
        self.update_table(self.table)

    # 图像修复算法相关函数
    def set_inpainter(self):
        return Inpainter(
            self.algorithm_combo.currentText(),
            self.stroke_input,
            self.x_offset_input,
            self.y_offset_input,
            self.autosub_input,
        )

    def test(self):
        """
        测试图像修复算法，在当前选区内执行图像修复操作
        """
        self.subtitle_table.clearSelection()
        self.inpainter = self.set_inpainter()

        frame = self.current_frame.copy()

        # 单选区直接修复
        if self.subtitle_path == "":
            region = self.selected_regions[0]
            x1, x2, y1, y2 = self.confirm_region(region["region"])
            frame_area = frame[y1:y2, x1:x2]
            if frame_area.size > 0:
                frame_area_inpainted, _ = self.inpainter.inpaint_text(
                    frame_area, region["binary"]
                )
                frame[y1:y2, x1:x2] = frame_area_inpainted
            self.update_frame_output(frame)
            return

        # 多选区根据 self.table
        time_table = list(self.table.values())
        for region_id, region in enumerate(self.selected_regions):
            if time_table[region_id][self.time_slider.value()] is not None:
                x1, x2, y1, y2 = self.confirm_region(region["region"])
                frame_area = frame[y1:y2, x1:x2]
                if frame_area.size > 0:
                    frame_area_inpainted, _ = self.inpainter.inpaint_text(
                        frame_area, region["binary"]
                    )
                    frame[y1:y2, x1:x2] = frame_area_inpainted
        self.update_frame_output(frame)

    def run(self):
        """
        运行图像修复任务，根据选区和字幕表信息批量进行修复
        """
        self.subtitle_table.clearSelection()
        self.inpainter = self.set_inpainter()
        self.save_config()

        # 启动工作线程
        if not self.worker_thread or not self.worker_thread.isRunning():
            regions = [
                {
                    "region": self.confirm_region(region["region"]),
                    "binary": region["binary"],
                }
                for region in self.selected_regions
            ]
            time_table = list(self.table.values())
            self.progress = ProgressWindow()
            self.worker_thread = Worker(
                self.video_path, regions, self.inpainter, time_table
            )
            self.worker_thread.start_button.connect(self.start_button.setEnabled)
            self.worker_thread.time_slider.connect(self.time_slider.setEnabled)
            self.worker_thread.test_button.connect(self.test_button.setEnabled)
            self.worker_thread.update_input_frame.connect(self.update_frame_input)
            self.worker_thread.update_output_frame.connect(self.update_frame_output)
            self.worker_thread.update_progress.connect(self.progress.update_progress)
            self.worker_thread.update_table.connect(self.complete_cell)
            self.progress.cancel_signal.connect(self.worker_thread.stop)
            self.worker_thread.result_signal.connect(self.handle_result)
            self.worker_thread.start()

    def handle_result(self, result):
        """
        处理工作线程返回的结果
        """
        if result["status"] != "Success":
            regions = self.selected_regions.copy()
            if self.video_path:
                self.load_video_file(self.video_path)
            if self.subtitle_path:
                self.load_subtitle_file(self.subtitle_path)
            self.selected_regions = regions
        if result["status"] == "Error":
            ErrorWindow(result["message"])
            return

    # 更新帧画面显示
    def update_frame(self, frame_number=None):
        """
        根据给定帧号更新当前显示的视频帧
        """
        if not self.cap or not self.cap.isOpened():
            ErrorWindow("视频未打开")
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
            pixmap = QPixmap.fromImage(q_image)
            self.pixmap = pixmap

            # 在 QLabel 中居中显示图像
            self.video_label_input.setPixmap(
                self.pixmap.scaled(self.video_label_input.size(), Qt.KeepAspectRatio)
            )
            self.video_label_output.setPixmap(
                pixmap.scaled(self.video_label_output.size(), Qt.KeepAspectRatio)
            )
            self.video_label_input.setAlignment(Qt.AlignCenter)
            self.video_label_output.setAlignment(Qt.AlignCenter)

            if frame_number is not None:
                self.update_time_label(frame_number)
        else:
            ErrorWindow("无法读取视频帧")
            return

    def update_frame_input(self, frame):
        """
        更新输入窗口的视频帧显示
        """
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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

    def update_frame_output(self, frame):
        """
        更新输出窗口的视频帧显示
        """
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

    # 表格处理相关
    def update_table(self, table):
        """
        根据 self.table 更新时轴表格
        """
        self.subtitle_table.setRowCount(len(table))
        for i, title in enumerate(table):
            title_label = QTableWidgetItem(title)
            self.subtitle_table.setVerticalHeaderItem(i, title_label)
            for j, text in enumerate(table[title]):
                if text is not None:
                    self.set_cell(i, j, QColor("#C5E4FD"), text, QColor("#000000"))
                else:
                    self.set_cell(i, j, QColor("#232629"))
        self.selected_regions = [
            {"region": QRect(0, 0, 1, 0), "binary": True} for _ in table
        ]

    def init_table(self):
        """
        打开视频时初始化时轴表格
        """
        self.subtitle_table.setColumnCount(self.total_frames)
        for i in range(self.total_frames):
            current_time = i / self.fps
            time_label = QTableWidgetItem(f"{i}\n{self.format_time2(current_time)}")
            self.subtitle_table.setHorizontalHeaderItem(i, time_label)
        self.table = {"default": [None] * self.total_frames}
        self.update_table(self.table)

    def roll_table(self, col):
        """
        根据时间轴滑块的值滚动字幕表格
        """
        target_position = max(0, col - 2)
        self.subtitle_table.horizontalScrollBar().setValue(target_position)

    def locate_table(self, row, col):
        """
        根据时间轴滑块的值滚动字幕表格
        """
        target_position = max(0, col - 2)
        self.subtitle_table.horizontalScrollBar().setValue(target_position)
        target_position = max(0, row)
        self.subtitle_table.verticalScrollBar().setValue(target_position)

    def complete_cell(self, row, col, content=""):
        """
        标记字幕表格中的某一单元格，表示对应的帧已经完成图像修复。
        """
        self.locate_table(row, col)
        if row > self.subtitle_table.rowCount() - 1:
            self.subtitle_table.setRowCount(row + 1)
            self.table[str(row + 1)] = [None] * self.total_frames
            for j in range(self.total_frames):
                self.set_cell(row, j, QColor("#232629"))
        if row > -1:
            self.set_cell(row, col, QColor("#14445B"), content)
        self.locate_table(row, col)

    def set_cell(self, row, col, bgcolor, text="", textcolor=QColor("#ffffff")):
        """设置表格单元格"""
        item = QTableWidgetItem(text)
        self.subtitle_table.setItem(row, col, item)
        item.setBackground(bgcolor)
        item.setForeground(textcolor)
        keys = list(self.table.keys())
        self.table[keys[row]][col] = text

    def select_region(self, logical_index):
        """
        点击行标题时，触发相应的选区绘制
        """
        self.draw_id = logical_index
        print(f"Row {logical_index} clicked, draw_id set to {self.draw_id}")

    def selected_cell(self):
        """
        单元格选中事件
        """
        selected_items = self.subtitle_table.selectedItems()
        # 选中单个单元格跳转
        if len(selected_items) == 1:
            item = selected_items[0]
            self.update_frame(item.column())
            self.time_slider.setValue(item.column())
            self.update_time_label(item.column())

    def change_region_color(self, logical_index):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("文字颜色为？")
        msg_box.setText("请选择文字颜色：")
        msg_box.addButton("黑字或白字", QMessageBox.YesRole)
        gray_button = msg_box.addButton("灰字", QMessageBox.NoRole)
        msg_box.exec_()

        binary = not (msg_box.clickedButton() == gray_button)
        self.selected_regions[logical_index]["binary"] = binary
        print(f"Row {logical_index} clicked, binary set to {binary}")

    def change_state_cell(self, row, column):
        item = self.subtitle_table.item(row, column)
        if item:
            current_color = item.background().color()
            color1 = QColor("#C5E4FD")  # 选择
            color2 = QColor("#232629")  # 未选择

            if current_color == color1:
                item.setBackground(color2)
                self.table[list(self.table.keys())[row]][column] = None
            else:
                item.setBackground(color1)
                self.table[list(self.table.keys())[row]][column] = "1"

    # 绘制红框相关事件
    def start_drawing(self, event):
        """
        开始绘制选区，响应鼠标按下事件，并记录起始点坐标。
        """
        if event.button() == Qt.LeftButton and self.cap is not None:
            self.start_point = self.region_offset(event.pos())
            self.is_drawing = True
            binary = self.selected_regions[self.draw_id]["binary"]
            self.selected_regions[self.draw_id] = {
                "region": QRect(0, 0, 0, 0),  # 清空以前的选区
                "binary": binary,
            }

    def update_drawing(self, event):
        """
        更新选区绘制，响应鼠标移动事件，根据当前鼠标位置动态绘制矩形区域。
        """
        if self.is_drawing and self.cap is not None:
            self.end_point = self.region_offset(event.pos())
            binary = self.selected_regions[self.draw_id]["binary"]
            self.selected_regions[self.draw_id] = {
                "region": QRect(self.start_point, self.end_point),
                "binary": binary,
            }
            self.update()

    def end_drawing(self, event):
        """
        结束选区绘制，响应鼠标松开事件，保存绘制完成的矩形区域。
        """
        if event.button() == Qt.LeftButton and self.cap is not None:
            self.end_point = self.region_offset(event.pos())
            binary = self.selected_regions[self.draw_id]["binary"]
            self.selected_regions[self.draw_id] = {
                "region": QRect(self.start_point, self.end_point),
                "binary": binary,
            }
            self.update()

    def paintEvent(self, event):
        """
        绘制事件（更新视频帧&红框显示）
        """
        if (
            self.cap != None
            and not self.selected_regions[self.draw_id]["region"].isNull()
        ):
            pixmap = self.pixmap.scaled(
                self.video_label_input.size(), Qt.KeepAspectRatio
            )
            painter = QPainter(pixmap)
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.selected_regions[self.draw_id]["region"])
            painter.end()
            self.video_label_input.setPixmap(pixmap)
            self.video_label_input.update()

    # 选区坐标处理相关
    def init_offset(self):
        """
        初始化选区的偏移量，视频 label 和实际视频帧之间的计算偏差。
        """
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

    def confirm_region(self, region):
        """获取区域坐标"""
        if not region.isNull():
            x1, y1 = self.region_to_video(region.topLeft())
            x2, y2 = self.region_to_video(region.bottomRight())
            return (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2))
        else:
            video_width, video_height = self.video_frame_size
            return 0, video_width - 1, 0, video_height - 1

    # 时轴处理相关
    def parse_ass_line(self, line):
        """
        解析字幕文件中的单行内容，提取出时间、字幕等信息。
        """
        # Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        pattern = r"^(Dialogue|Comment):\s*(\d+),(\d+:\d+:\d+\.\d+),(\d+:\d+:\d+\.\d+),([^,]*),([^,]*),(\d+),(\d+),(\d+),([^,]*),(.*)$"

        match = re.match(pattern, line)

        if match:
            parsed = {
                "Type": match.group(1),
                # "Layer": int(match.group(2)),
                "Start": self.calSubTime(match.group(3)),
                "End": self.calSubTime(match.group(4)),
                "Style": match.group(5),
                "Name": match.group(6),
                # "MarginL": int(match.group(7)),
                # "MarginR": int(match.group(8)),
                # "MarginV": int(match.group(9)),
                # "Effect": match.group(10),
                # "Text": match.group(11),
            }
            return parsed
        else:
            return None

    @staticmethod
    def format_time(seconds):
        """
        s -> mm:ss
        """
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def format_time2(seconds):
        """
        s -> mm:ss.ss
        """
        milliseconds = int((seconds - int(seconds)) * 1000)
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes:02d}:{int(seconds):02d}.{milliseconds:03d}"

    @staticmethod
    def calSubTime(t):
        """
        h:mm:ss.ss -> s
        """
        h, m, s = t.split(":")
        h = int(h)
        m = int(m)
        s = float(s)

        total_seconds = h * 3600 + m * 60 + (s - 0.01)
        total_seconds = max(total_seconds, 0)
        return total_seconds

    def update_time_label(self, frame_number):
        """
        更新上方控制栏时间显示
        """
        if self.cap:
            current_time = frame_number / self.fps
            total_time = self.total_frames / self.fps
            self.time_label.setText(
                f"{self.format_time(current_time)} / {self.format_time(total_time)}"
            )

    # 窗口事件
    def closeEvent(self, event):
        """
        窗口关闭事件，释放视频捕获资源。
        """
        if self.cap:
            self.cap.release()
        super().closeEvent(event)

    def resizeEvent(self, event):
        """
        窗口调整大小事件，更新视频帧显示。
        """
        super().resizeEvent(event)
        if hasattr(self, "current_frame"):
            self.update_frame()


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
