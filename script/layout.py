from PyQt5.QtWidgets import (
    QMainWindow,
    QLabel,
    QPushButton,
    QGridLayout,
    QWidget,
    QSlider,
    QProgressBar,
    QLineEdit,
    QHBoxLayout,
    QSpinBox,
    QColorDialog,
    QCheckBox,
    QSizePolicy,
    QLayout,
    QLayoutItem,
    QMessageBox,
)
from PyQt5.QtGui import QFont, QRegularExpressionValidator, QColor, QValidator
from PyQt5.QtCore import Qt, QPoint, QRegularExpression, pyqtSignal, QRect

STYLE = """
    QMainWindow {
        background-color: #f0f0f0;
    }
    #videoLabel {
        background-color: #333333;
        border: 2px solid #555555;
        border-radius: 10px;
    }
    QPushButton {
        background-color: #FEC282;
        color: #EB742D;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-size: 18px;
        font-weight:bold;
    }
    QPushButton:hover {
        background-color: #FEDEB8;
    }
    QPushButton:pressed {
        background-color: #FEDEB7;
    }
    QPushButton:disabled {
        background-color: #FEDDB5;
    }
    QSlider::groove:horizontal {
        border: 1px solid #bbb;
        background: white;
        height: 10px;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: #FF7C00;
        border: 1px solid #5c5c5c;
        width: 18px;
        margin: -2px 0;
        border-radius: 3px;
    }
    QProgressBar {
        border: 2px solid grey;
        border-radius: 5px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #FEC282;
        width: 10px;
        margin: 0.5px;
    }
"""


class VideoPlayerLayout(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hare")
        self.setGeometry(100, 100, 800, 600)
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QGridLayout(self.central_widget)

        # 创建和设置主要部件
        self.create_main_widgets()
        self.setup_ui()

        self.selected_video_path = None
        self.video_capture = None
        self.total_frames = 0
        self.current_frame = 0
        self.video_fps = 30  # Assume default 30 FPS for simplicity
        self.video_label.setFixedSize(800, 600)

        # State variables
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_drawing = False
        self.selected_region = QRect()
        self.is_expanded = False

        self.video_frame_size = None
        self.pixmap = None
        self.my_thread = None

        # 若界面中存在按钮，界面焦点默认在按钮上，强制聚焦
        self.setFocusPolicy(Qt.StrongFocus)

    def create_main_widgets(self):
        # 创建视频标签、进度条、按钮等主要部件
        self.video_label = QLabel(self)
        self.video_label.setObjectName("videoLabel")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.video_label, 0, 0, 1, 3)

        first_layout = QHBoxLayout()

        self.start_label = QPushButton("Start: 0", self)
        self.start_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.start_label.clicked.connect(self.update_start_marker)
        self.start_label.setStyleSheet("background-color: #B9B4BF; color: #4C3D5C;")
        first_layout.addWidget(self.start_label)

        self.progress_slider = CustomSlider(Qt.Horizontal)
        self.progress_slider.setEnabled(False)
        self.progress_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        first_layout.addWidget(self.progress_slider)

        self.end_label = QPushButton("End: 0", self)
        self.end_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.end_label.clicked.connect(self.update_end_marker)
        self.end_label.setStyleSheet("background-color: #B9B4BF; color: #4C3D5C;")
        first_layout.addWidget(self.end_label)

        self.layout.addLayout(first_layout, 1, 0, 1, 3)

        self.select_file_button = QPushButton("🎞Select Video", self)
        self.layout.addWidget(self.select_file_button, 2, 0, 1, 1)

        self.confirm_button = QPushButton("🚀 Run!", self)
        self.confirm_button.setEnabled(False)
        self.layout.addWidget(self.confirm_button, 2, 1, 1, 1)

        self.settings_button = QPushButton("⚙️Settings", self)
        self.settings_button.clicked.connect(self.toggle_expand_window)
        self.layout.addWidget(self.settings_button, 2, 2, 1, 1)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar, 3, 0, 1, 3)

        # 设置行伸缩因子
        for i, stretch in enumerate([10, 1, 1, 1]):
            self.layout.setRowStretch(i, stretch)

    def setup_ui(self):
        self.setStyleSheet(STYLE)
        # 设置按钮大小和字体
        for button in [
            self.select_file_button,
            self.confirm_button,
            self.settings_button,
            self.start_label,
            self.end_label,
        ]:
            button.setMinimumSize(120, 40)
            button.setFont(QFont("Arial", 14))

    def update_start_marker(self):
        self.start_marker = self.progress_slider.value()
        self.start_label.setText(f"Start: {self.start_marker}")

    def update_end_marker(self):
        self.end_marker = self.progress_slider.value()
        self.end_label.setText(f"End: {self.end_marker}")

    def _cleanup_widget(self, item):
        # 递归清理部件和布局
        if item is None:
            return

        if isinstance(item, QWidget):
            item.setParent(None)
            item.deleteLater()
        elif isinstance(item, QLayout):
            while item.count():
                child = item.takeAt(0)
                self._cleanup_widget(child)
            parent_layout = item.parent()
            if parent_layout:
                parent_layout.removeItem(item)
            item.deleteLater()
        elif isinstance(item, QLayoutItem):
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            layout = item.layout()
            if layout:
                self._cleanup_widget(layout)

    def toggle_expand_window(self, window_width=None):
        if not window_width:
            window_width = self.width()

        if not self.is_expanded:
            # 扩展窗口
            self.setFixedWidth(window_width * 2)
            self.create_expanded_widgets()
        else:
            # 收缩窗口
            self.setFixedWidth(window_width // 2)
            self.remove_expanded_widgets()

        self.is_expanded = not self.is_expanded
        self.adjustSize()

    def create_expanded_widgets(self):
        # 创建扩展部分的部件
        self.create_video_label_2()
        self.create_first_row_layout()
        # self.create_second_row_layout()
        self.create_buttons_layout()
        self.update_column_stretches()

    def create_video_label_2(self):
        self.video_label_2 = QLabel(self)
        self.video_label_2.setObjectName("videoLabel")
        self.video_label_2.setAlignment(Qt.AlignCenter)
        self.video_label_2.setFixedSize(800, 600)
        self.layout.addWidget(self.video_label_2, 0, 3, 1, 3)

    def create_first_row_layout(self):
        # 创建第二行布局
        self.first_row_layout = QHBoxLayout()
        left_half_layout = QHBoxLayout()
        right_half_layout = QHBoxLayout()

        # 左半部分：噪声设置
        noise_label = QLabel("噪声")
        noise_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        left_half_layout.addWidget(noise_label)

        self.contour_area_input = QSpinBox(self)
        self.contour_area_input.setRange(0, 100)
        self.contour_area_input.setValue(0)
        self.contour_area_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_half_layout.addWidget(self.contour_area_input)

        # 右半部分：描边设置
        stroke_label = QLabel("描边")
        stroke_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        right_half_layout.addWidget(stroke_label)

        self.dilate_kernal_size_input = QSpinBox(self)
        self.dilate_kernal_size_input.setRange(0, 100)
        self.dilate_kernal_size_input.setValue(2)
        self.dilate_kernal_size_input.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        right_half_layout.addWidget(self.dilate_kernal_size_input)

        self.first_row_layout.addLayout(left_half_layout, stretch=1)
        self.first_row_layout.addLayout(right_half_layout, stretch=1)
        self.layout.addLayout(self.first_row_layout, 1, 3, 1, 3)

    def create_second_row_layout(self):
        # 创建第二行布局
        self.second_row_layout = QHBoxLayout()
        left_half_layout = QHBoxLayout()
        right_half_layout = QHBoxLayout()

        # 左半部分：复选框、字体颜色设置
        self.checkbox = QCheckBox(self)
        self.checkbox.stateChanged.connect(self.on_checkbox_state_changed)
        self.checkbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        left_half_layout.addWidget(self.checkbox)

        font_color_label = QLabel("字体颜色")
        font_color_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        left_half_layout.addWidget(font_color_label)

        self.color_picker_button = QPushButton(self)
        self.color_picker_button.setFixedSize(30, 30)
        self.color_picker_button.clicked.connect(self.pick_color)
        self.color_picker_button.setStyleSheet(
            "background-color: #dddddd; border: 1px solid #aaaaaa;"
        )

        self.color_picker_button.setEnabled(False)
        left_half_layout.addWidget(self.color_picker_button)

        self.color_display_input = ColorLineEdit(self)
        self.color_display_input.setPlaceholderText("Color (e.g., #RRGGBB)")
        self.color_display_input.setText("#FFFFFF")
        self.color_display_input.color_changed.connect(self.update_color_picker_button)
        self.color_display_input.setEnabled(False)
        self.color_display_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_half_layout.addWidget(self.color_display_input)

        # 右半部分：容差设置
        tolerance_label = QLabel("容差")
        tolerance_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        right_half_layout.addWidget(tolerance_label)

        self.color_tolerance = QSpinBox(self)
        self.color_tolerance.setRange(0, 100)
        self.color_tolerance.setValue(15)
        self.color_tolerance.setEnabled(False)
        self.color_tolerance.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        right_half_layout.addWidget(self.color_tolerance)

        self.second_row_layout.addLayout(left_half_layout, stretch=1)
        self.second_row_layout.addLayout(right_half_layout, stretch=1)
        self.layout.addLayout(self.second_row_layout, 2, 3, 1, 3)

    def create_buttons_layout(self):
        # 创建按钮布局
        self.buttons_layout = QHBoxLayout()
        self.mask_button = QPushButton("测试", self)
        self.mask_button.setFont(QFont("黑体", 14))
        self.mask_button.clicked.connect(self.test_mask)
        self.inpaint_button1 = QPushButton("修复算法1", self)
        self.inpaint_button1.setFont(QFont("黑体", 14))
        self.inpaint_button1.clicked.connect(self.test_inpaint)
        self.inpaint_button2 = QPushButton("修复算法2", self)
        self.inpaint_button2.setFont(QFont("黑体", 14))
        self.inpaint_button2.clicked.connect(self.test_inpaint2)
        self.buttons_layout.addWidget(self.mask_button)
        self.buttons_layout.addWidget(self.inpaint_button1)
        self.buttons_layout.addWidget(self.inpaint_button2)
        self.layout.addLayout(self.buttons_layout, 3, 3, 1, 3)

    def update_column_stretches(self):
        # 更新列伸缩因子
        for i in range(6):
            self.layout.setColumnStretch(i, 1)

    def remove_expanded_widgets(self):
        # 移除扩展部分的部件
        self.video_label_2.deleteLater()
        self._cleanup_widget(self.first_row_layout)
        self._cleanup_widget(self.buttons_layout)
        for i in range(3, 6):
            self.layout.setColumnStretch(i, 0)

    def test_mask(self):
        pass

    def test_inpaint(self):
        pass

    def test_inpaint2(self):
        pass

    def show_erro_message(self, title="错误", text="", informativeText=None):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(text)

        if informativeText:
            msg.setInformativeText(informativeText)

        msg.exec_()

    def show_info_message(self, title="提示", text="", informativeText=None):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(title)
        msg.setText(text)

        if informativeText:
            msg.setInformativeText(informativeText)

        msg.exec_()

    def pick_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            color_name = color.name(QColor.HexArgb)
            self.color_picker_button.setStyleSheet(f"background-color: {color.name()};")
            self.color_display_input.setText(color_name)

    def update_color_picker_button(self, color):
        self.color_picker_button.setStyleSheet(f"background-color: {color};")

    def on_checkbox_state_changed(self, state):
        enabled = state == Qt.Checked
        self.color_display_input.setEnabled(enabled)
        self.color_picker_button.setEnabled(enabled)
        self.color_tolerance.setEnabled(enabled)
        self.color_picker_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self.color_display_input.text()};
                border: 1px solid black;
            }}
            QPushButton:disabled {{
                background-color: #dddddd;
                border: 1px solid #aaaaaa;
            }}
            """
        )


class ColorLineEdit(QLineEdit):
    color_changed = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validator = QRegularExpressionValidator(
            QRegularExpression("^#([A-Fa-f0-9]{6})$")
        )
        self.setValidator(self.validator)
        self.textChanged.connect(self.on_text_changed)

    def on_text_changed(self, text):
        if self.validator.validate(text, 0)[0] == QValidator.Acceptable:
            self.color_changed.emit(text)


class CustomSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.parent().setFocus()  # 将焦点返回到主窗口
