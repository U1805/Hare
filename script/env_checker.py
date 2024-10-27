import importlib
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

DEBUG = True

python_executable = (
    os.path.join(os.path.dirname(sys.executable), "runtime", "python.exe")
    if not DEBUG
    else sys.executable
)


class InstallThread(QtCore.QThread):
    progress_signal = QtCore.pyqtSignal(str)
    status_signal = QtCore.pyqtSignal(str)

    def __init__(self, packages):
        super().__init__()
        self.packages = packages

    def run(self):
        """Executes package installation tasks in a background thread"""
        self.progress_signal.emit("pip")
        self.status_signal.emit("检查 pip...")
        self.enable_pip()

        # Install torch (only if NVIDIA driver is detected)
        driver_version = get_nvidia_driver_version()
        if driver_version:
            for pkg in self.packages[:2]:
                package_name = pkg["package_name"]
                version = pkg.get("version")
                import_name = pkg.get("import_name")
                self.check_and_install_package(package_name, import_name, version)

            # torch = importlib.import_module("torch")
            # device = "cuda" if torch.cuda.is_available() else "cpu"
            # self.status_signal.emit(f"Using device: {device}")
        else:
            self.progress_signal.emit("torch")
            self.progress_signal.emit("torchvision")
            self.status_signal.emit("未检测到 NVIDIA 驱动。请检查环境配置。")

        # Install other packages
        for pkg in self.packages[2:]:
            package_name = pkg["package_name"]
            version = pkg.get("version")
            import_name = pkg.get("import_name")
            self.check_and_install_package(package_name, import_name, version)

        self.progress_signal.emit("big-lama.pt")
        self.status_signal.emit("检查 big-lama.pt...")
        if driver_version:
            self.download_model()

        clear_command = [python_executable, "-m", "pip", "cache", "purge"]
        self.run_command(clear_command, "清理 pip 缓存...")
        self.progress_signal.emit("complete")

    def check_and_install_package(self, package_name, import_name, version=None):
        """Checks and installs the specified package and version"""
        self.progress_signal.emit(package_name)
        try:
            if version:
                pkg_version = importlib.metadata.version(package_name)
                if pkg_version == version:
                    self.status_signal.emit(f"{package_name} 版本 {version} 已安装")
                    return importlib.import_module(import_name)
            else:
                importlib.metadata.version(import_name)
                self.status_signal.emit(f"{package_name} 已安装")
                return importlib.import_module(import_name)
        except importlib.metadata.PackageNotFoundError:
            if version:
                package_with_version = f"{package_name}=={version}"
                self.status_signal.emit(f"安装 {package_with_version}...")
            else:
                package_with_version = package_name
                self.status_signal.emit(f"安装最新版本的 {package_name}...")
            self.install_package_with_fallback(package_with_version)

    def install_package_with_fallback(self, package_with_version):
        """Tries to install the package with Tsinghua mirror; falls back to default mirror on failure"""
        command = [python_executable, "-m", "pip", "install", package_with_version]
        command += ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]

        try:
            if package_with_version.startswith("torch"):
                command = command[:-2]
                command += ["-i", "https://download.pytorch.org/whl/cu118"]
                command += ["--trusted-host", "pypi.tuna.tsinghua.edu.cn"]
            self.run_command(command, f"从清华源安装 {package_with_version}...")
        except subprocess.CalledProcessError:
            command = command[:-2]
            self.run_command(
                command,
                f"清华源安装失败，尝试从默认源安装 {package_with_version}...",
            )

    def enable_pip(self):
        """Checks if pip is installed, and downloads and installs it if missing"""
        try:
            self.status_signal.emit("检查 pip")          
            subprocess.check_call(
                [python_executable, "-m", "pip", "--version"],
                startupinfo=subprocess.STARTUPINFO(),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except subprocess.CalledProcessError:
            # get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
            get_pip_url = "http://mirrors.aliyun.com/pypi/get-pip.py"
            get_pip_path = os.path.join(os.path.dirname(sys.executable), "get-pip.py")
            command = ["curl", "-L", "-o", get_pip_path, get_pip_url]
            self.run_command(command, f"下载 get-pip.py...")

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags &= ~subprocess.STARTF_USESHOWWINDOW
            process = subprocess.Popen(
                [python_executable, get_pip_path],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            process.wait()
            os.remove(get_pip_path)

    def download_model(self):
        if os.path.exists("big-lama.pt"):
            return

        model_url = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
        accelerated_urls = ["https://gh.llkk.cc/", "https://github.moeyy.xyz/"]
        get_model_path = "big-lama.pt"

        # 尝试加速 URL
        for url in accelerated_urls:
            try:
                command = ["curl", "-L", "-o", get_model_path, url + model_url]
                self.run_command(command, f"尝试从 {url} 下载模型...")
                self.status_signal.emit("下载成功!")
                return
            except Exception as e:
                self.status_signal.emit(f"从 {url} 下载失败: {e}")
        # 如果所有加速链接都失败，使用原始链接
        try:
            command = ["curl", "-L", "-o", get_model_path, model_url]
            self.run_command(command, f"尝试从原始 URL 下载模型...")
            self.status_signal.emit("下载成功!")
        except Exception as e:
            self.status_signal.emit(f"从原始 URL 下载失败: {e}")

    def run_command(self, command, status_message):
        """Runs a command and shows terminal window"""
        self.status_signal.emit(status_message)
        # Show terminal window when running pip commands
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags &= ~subprocess.STARTF_USESHOWWINDOW
        process = subprocess.Popen(
            command,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        process.wait()


class InstallProgressWindow(QtWidgets.QWidget):
    def __init__(self, packages):
        super().__init__()
        self.setWindowTitle("软件包安装进度")
        self.setGeometry(400, 400, 400, 150)

        # Set up labels and progress bar
        self.label = QtWidgets.QLabel("准备安装所需软件包...", self)
        self.label.setGeometry(30, 20, 340, 30)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setGeometry(30, 70, 340, 30)

        # Set progress bar range
        self.progress_bar.setMaximum(len(packages) + 2)  # pip、lama.pt
        self.progress = 0

    def update_progress(self, package_name):
        if self.progress >= self.progress_bar.maximum():
            self.final_message()
        else:
            self.label.setText(f"正在安装 {package_name}...")
            self.progress_bar.setValue(self.progress)
            QtWidgets.QApplication.processEvents()
        self.progress += 1

    def update_status(self, message):
        """Updates the status label with current operation"""
        self.label.setText(message)
        QtWidgets.QApplication.processEvents()

    def final_message(self):
        """Updates the progress bar to completion and shows a final message"""
        self.label.setText("环境配置完成。请重新启动。")
        self.progress_bar.setValue(self.progress_bar.maximum())
        QtWidgets.QApplication.processEvents()


def get_nvidia_driver_version():
    """Retrieves NVIDIA driver version"""
    try:
        output = subprocess.check_output(
            ["nvidia-smi"], stderr=subprocess.STDOUT
        ).decode("utf-8")
        for line in output.split("\n"):
            if "Driver Version" in line:
                version = line.split("Driver Version:")[1].strip().split(" ")[0]
                return version
    except Exception as e:
        print("无法检测到 NVIDIA 驱动版本:", e)


def install_window(packages):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    app = QtWidgets.QApplication(sys.argv)
    resources_path = Path("resources")

    qss_path = resources_path / "qdark.qss"
    with open(qss_path, "r") as qss_file:
        app.setStyleSheet(qss_file.read())
    app.setFont(QtGui.QFont("Microsoft YaHei", 9))

    progress_window = InstallProgressWindow(packages)
    progress_window.setWindowFlags(
        progress_window.windowFlags() | QtCore.Qt.WindowStaysOnTopHint
    )
    progress_window.show()
    install_thread = InstallThread(packages)
    install_thread.progress_signal.connect(progress_window.update_progress)
    install_thread.status_signal.connect(progress_window.update_status)
    install_thread.start()

    sys.exit(app.exec_())


def main():
    packages = [
        {"package_name": "torch", "import_name": "torch"},
        {
            "package_name": "torchvision",
            "import_name": "torchvision",
        },
        {"package_name": "numpy", "import_name": "numpy", "version": "1.24.4"},
        {
            "package_name": "opencv-contrib-python-headless",
            "import_name": "cv2",
            "version": "4.10.0.84",
        },
    ]

    missing_packages = []
    for pkg in packages:
        try:
            importlib.import_module(pkg["import_name"])
        except ImportError:
            print(f"{pkg['import_name']} 未安装")
            missing_packages.append(pkg)

    if missing_packages:
        print("检测到部分包未安装，开始安装...")
        install_window(packages)
        return False
    else:
        print("所有包已成功导入，无需安装。")
        return True


if __name__ == "__main__":
    main()
