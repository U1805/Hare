import json
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QProgressBar,
    QFileDialog,
    QVBoxLayout,
    QComboBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import arona

config = {}  # 选中配置
configs = {}  # 全部配置
video_path = ""
output_path = ""
video_type = None


class Worker(QThread):
    updateProgressBar = pyqtSignal(int)

    def run(self):
        global configs, video_path, video_type, config

        config = configs[video_type]
        print(f"Selected config: {video_type}\t{config}")
        arona.run(
            str(video_path),
            str(output_path),
            video_type,
            config,
            self.updateProgressBar.emit,
        )


class FileSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("标题随便放点字在这里先")
        self.setGeometry(300, 300, 300, 150)

        layout = QVBoxLayout()

        # 文件选择器
        self.btn_select_file = QPushButton("选择文件", self)
        self.btn_select_file.clicked.connect(self.selectFile)
        layout.addWidget(self.btn_select_file)

        # 下拉列表
        self.combo_box = QComboBox(self)
        self.loadComboBoxItems()
        layout.addWidget(self.combo_box)

        # 开始按钮
        self.btn_start = QPushButton("🚀Start!", self)
        self.btn_start.clicked.connect(self.start_thread)
        layout.addWidget(self.btn_start)

        # 进度条
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

        # 子线程执行任务
        self.my_thread = Worker()
        self.my_thread.updateProgressBar.connect(self.updateProgressBar)

    def selectFile(self):
        global video_path, video_type, output_path

        filter = "视频文件 (*.mp4)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter)
        if file_path:
            video_path = Path(file_path)
            output_path = Path(video_path.parent / (video_path.stem + ".ass"))
            if len(video_path.stem) > 13:
                self.btn_select_file.setText(
                    video_path.stem[:5] + "..." + video_path.stem[-5:]
                )
            else:
                self.btn_select_file.setText(video_path.stem)
            print(f"Selected file: {video_path}")
            print(f"Output file: {output_path}")

    def loadComboBoxItems(self):
        global configs

        with open("./site-packages/configs.json", "r", encoding="utf-8") as file:
            configs = json.load(file)
            for key in configs.keys():
                self.combo_box.addItem(key)

    def start_thread(self):
        global video_type

        if not self.my_thread.isRunning():
            video_type = self.combo_box.currentText()
            self.my_thread.start()

    def updateProgressBar(self, cnt):
        self.progress_bar.setValue(cnt)


def main():
    app = QApplication(sys.argv)
    ex = FileSelector()
    ex.show()
    sys.exit(app.exec_())
