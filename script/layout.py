from PyQt5.QtWidgets import (
    QMainWindow,
    QLabel,
    QPushButton,
    QGridLayout,
    QWidget,
    QSlider,
    QProgressBar,
    QLineEdit,
    QComboBox,
    QHBoxLayout,
)
from PyQt5.QtGui import QFont, QIntValidator
from PyQt5.QtCore import Qt, QRect, QPoint

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

        self.setWindowTitle("Video Player")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QGridLayout(self.central_widget)

        # Widgets
        # Video Frame Image
        self.video_label = QLabel(self)
        self.video_label.setObjectName("videoLabel")  # 设置对象名称
        self.video_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.video_label, 0, 0, 1, 3)

        # Video Progress Slider
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setEnabled(False)
        self.layout.addWidget(self.progress_slider, 1, 0, 1, 3)

        # Video File Selection
        self.select_file_button = QPushButton("🎞Select Video", self)
        self.layout.addWidget(self.select_file_button, 2, 0, 1, 1)

        # Confirm Button
        self.confirm_button = QPushButton("🚀 Run!", self)
        self.confirm_button.setEnabled(False)
        self.layout.addWidget(self.confirm_button, 2, 1, 1, 1)

        # Settings Button
        self.settings_button = QPushButton("⚙️Settings", self)
        self.settings_button.clicked.connect(self.toggle_expand_window)
        self.layout.addWidget(self.settings_button, 2, 2, 1, 1)

        # Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar, 3, 0, 1, 3)

        # Set row stretches
        self.layout.setRowStretch(0, 10)
        self.layout.setRowStretch(1, 1)
        self.layout.setRowStretch(2, 1)
        self.layout.setRowStretch(3, 1)

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

        self.setup_ui()

    def setup_ui(self):
        # Set global style
        self.setStyleSheet(STYLE)

        # Set button icons and sizes
        self.select_file_button.setMinimumSize(120, 40)
        self.confirm_button.setMinimumSize(120, 40)
        self.settings_button.setMinimumSize(120, 40)
        self.select_file_button.setFont(QFont("Arial", 14))
        self.confirm_button.setFont(QFont("Arial", 14))
        self.settings_button.setFont(QFont("Arial", 14))

        # Set tooltips
        self.select_file_button.setToolTip("Click to select a video file")
        self.confirm_button.setToolTip("Start processing the video")
        self.settings_button.setToolTip("Set parameters")
        self.progress_slider.setToolTip("Drag to navigate through the video")

    def _cleanup_widget(self, widget):
        while widget.count():
            item = widget.takeAt(0)
            item.widget().deleteLater()
        widget.deleteLater()

    def toggle_expand_window(self):
        window_width = self.width()

        if not self.is_expanded:
            self.setFixedWidth(window_width * 2)

            # Duplicate widgets for the expanded part
            self.video_label_2 = QLabel(self)
            self.video_label_2.setObjectName("videoLabel")  # 设置对象名称
            self.video_label_2.setAlignment(Qt.AlignCenter)
            self.video_label_2.setFixedSize(800, 600)
            self.layout.addWidget(self.video_label_2, 0, 3, 1, 3)

            # First row: Algorithm 1 settings
            self.algo1_layout = QHBoxLayout()
            self.algo1_layout.addWidget(QLabel("算法1"))
            self.algo1_layout.addWidget(QLabel("区域面积"))
            self.contour_area_input = QLineEdit(self)
            self.algo1_layout.addWidget(self.contour_area_input)
            self.contour_area_input.setValidator(QIntValidator())
            self.contour_area_input.setText("0")
            self.algo1_layout.addWidget(QLabel("膨胀"))
            self.dilate_kernal_size_input = QLineEdit(self)
            self.algo1_layout.addWidget(self.dilate_kernal_size_input)
            self.dilate_kernal_size_input.setValidator(QIntValidator())
            self.dilate_kernal_size_input.setText("35")
            self.layout.addLayout(self.algo1_layout, 1, 3, 1, 3)

            # Second row: Algorithm 2 settings
            self.algo2_layout = QHBoxLayout()
            self.algo2_layout.addWidget(QLabel("算法2"))
            self.algorithm2_combobox = QComboBox(self)
            # 设置下拉列表项和对应的显示文本
            items = ["chs_v3", "chs_v4", "cht", "en", "jp", "kr", "rs"]
            display_texts = [
                "Chinese V3",
                "Chinese V4",
                "Chinese Traditional",
                "English",
                "Japanese",
                "Korean",
                "Russian",
            ]
            # 添加每个选项及其对应的显示文本
            for i in range(len(items)):
                self.algorithm2_combobox.addItem(display_texts[i], items[i])
            self.algorithm2_combobox.setCurrentText("Japanese")
            self.algo2_layout.addWidget(
                self.algorithm2_combobox, stretch=2
            )  # 设置伸展因子为 2
            self.layout.addLayout(self.algo2_layout, 2, 3, 1, 3)

            # Third row: Test buttons
            self.buttons_layout = QHBoxLayout()
            self.test1_button = QPushButton("test1", self)
            self.test1_button.clicked.connect(self.test_inpaint)
            self.test2_button = QPushButton("test2", self)
            self.test2_button.clicked.connect(self.test_inpaint2)
            self.buttons_layout.addWidget(self.test1_button)
            self.buttons_layout.addWidget(self.test2_button)
            self.layout.addLayout(self.buttons_layout, 3, 3, 1, 3)

            # Update column stretches for new columns
            self.layout.setColumnStretch(3, 1)
            self.layout.setColumnStretch(4, 1)
            self.layout.setColumnStretch(5, 1)
        else:
            self.setFixedWidth(window_width // 2)

            if self.pixmap:
                self.video_label_2.setPixmap(
                    self.pixmap.scaled(self.video_label_2.size(), Qt.KeepAspectRatio)
                )

            # Remove widgets for the collapsed part
            self.video_label_2.deleteLater()
            self._cleanup_widget(self.algo1_layout)
            self._cleanup_widget(self.algo2_layout)
            self._cleanup_widget(self.buttons_layout)

            # Reset column stretches
            self.layout.setColumnStretch(3, 0)
            self.layout.setColumnStretch(4, 0)
            self.layout.setColumnStretch(5, 0)

        self.is_expanded = not self.is_expanded
        self.adjustSize()

    def test_inpaint(self):
        pass

    def test_inpaint2(self):
        pass
