import subprocess
import sys
import os
import importlib
import importlib.metadata
import urllib.request
from pathlib import Path
from PyQt5 import QtWidgets, QtCore, QtGui


class InstallThread(QtCore.QThread):
    # 定义信号，用于更新主线程中的进度条
    progress_signal = QtCore.pyqtSignal(str, int)

    def __init__(self, packages):
        super().__init__()
        self.packages = packages

    def run(self):
        """后台线程执行包安装任务"""
        enable_pip()
        self.progress_signal.emit("pip", 1)  # 更新进度

        # 安装 onnxruntime（仅当检测到 NVIDIA 驱动时）
        driver_version = get_nvidia_driver_version()
        if driver_version:
            onnxruntime = self.check_and_install_package(
                "onnxruntime-gpu",
                import_name="onnxruntime",
                index=1,
            )
            if onnxruntime:
                providers = (
                    ["CUDAExecutionProvider"]
                    if "CUDAExecutionProvider" in onnxruntime.get_available_providers()
                    else ["CPUExecutionProvider"]
                )
                print(f"当前使用的Execution Provider: {providers}")
        else:
            print("未检测到安装 NVIDIA 驱动，请检查环境")
            self.progress_signal.emit("onnxruntime", 2)

        # 安装其余包
        for index, pkg in enumerate(self.packages[1:], start=2):
            package_name = pkg["package_name"]
            version = pkg.get("version")
            import_name = pkg.get("import_name")
            self.check_and_install_package(
                package_name,
                import_name,
                version,
                index,
            )

    def check_and_install_package(
        self, package_name, import_name, version=None, index=0
    ):
        """检查并安装指定的包和版本"""
        try:
            # 如果指定了版本，检查该版本是否已安装
            if version:
                pkg_version = importlib.metadata.version(package_name)
                if pkg_version == version:
                    print(f"{package_name} 版本 {version} 已安装")
                    return importlib.import_module(import_name)
            else:
                importlib.metadata.version(import_name)
                print(f"{package_name} 已安装")
                return importlib.import_module(import_name)
        except importlib.metadata.PackageNotFoundError:
            # 包未安装或版本不符，安装指定版本
            if version:
                package_with_version = f"{package_name}=={version}"
                print(f"安装 {package_with_version}...")
            else:
                package_with_version = package_name
                print(f"安装最新版本的 {package_name}...")
            install_package_with_fallback(package_with_version)
            self.progress_signal.emit(package_name, index + 1)  # 更新进度


class InstallProgressWindow(QtWidgets.QWidget):
    def __init__(self, packages):
        super().__init__()
        self.setWindowTitle("Package Installation Progress")
        self.setGeometry(400, 400, 400, 150)

        # 设置标签和进度条
        self.label = QtWidgets.QLabel("Preparing to install packages...", self)
        self.label.setGeometry(30, 20, 340, 30)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setGeometry(30, 70, 340, 30)

        # 设定进度条的范围
        self.progress_bar.setMaximum(len(packages) + 1)
        self.progress = 0

    def update_progress(self, package_name):
        self.progress += 1
        self.label.setText(f"Installing {package_name}...")
        self.progress_bar.setValue(self.progress)
        QtWidgets.QApplication.processEvents()  # 刷新界面以显示更新的进度


def enable_pip():
    """检查是否安装 pip，如果没有则自动下载并安装 get-pip.py"""
    python_executable = os.path.join(
        os.path.dirname(sys.executable), "runtime", "python.exe"
    )
    try:
        subprocess.check_call([python_executable, "-m", "pip", "--version"])
        print("pip 已安装")
    except subprocess.CalledProcessError:
        # 如果没有 pip，则下载并安装 get-pip.py
        print("未检测到 pip，正在下载 get-pip.py...")
        get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
        get_pip_path = os.path.join(os.path.dirname(sys.executable), "get-pip.py")
        urllib.request.urlretrieve(get_pip_url, get_pip_path)
        print("正在安装 pip...")
        subprocess.check_call([python_executable, get_pip_path])
        os.remove(get_pip_path)
        print("pip 安装完成")


def install_package_with_fallback(package_with_version):
    """优先使用清华源安装指定包和版本，失败则切换到默认源"""
    python_executable = os.path.join(
        os.path.dirname(sys.executable), "runtime", "python.exe"
    )
    try:
        # 使用清华源安装
        print(f"尝试从清华源安装 {package_with_version}...")
        subprocess.check_call(
            [
                python_executable,
                "-m",
                "pip",
                "install",
                package_with_version,
                "--index-url",
                "https://pypi.tuna.tsinghua.edu.cn/simple",
            ]
        )
        print(f"{package_with_version} 安装成功 (清华源)")
    except subprocess.CalledProcessError:
        # 若清华源失败，尝试使用默认源安装
        print(f"清华源安装失败，尝试从默认源安装 {package_with_version}...")
        subprocess.check_call(
            [python_executable, "-m", "pip", "install", package_with_version]
        )
        print(f"{package_with_version} 安装成功 (默认源)")


def get_nvidia_driver_version():
    """获取NVIDIA驱动版本"""
    try:
        output = subprocess.check_output(
            ["nvidia-smi"], stderr=subprocess.STDOUT
        ).decode("utf-8")
        for line in output.split("\n"):
            if "Driver Version" in line:
                version = line.split("Driver Version:")[1].strip().split(" ")[0]
                return version
    except Exception as e:
        print("无法检测到NVIDIA驱动版本:", e)


def main():
    """
    返回是否需要重启
    所有包已成功导入，无需安装 -> False
    检测到部分包未安装，安装后 -> True
    """

    # 定义所需的包
    packages = [
        {"package_name": "onnxruntime-gpu", "import_name": "onnxruntime"},
        {"package_name": "numpy", "import_name": "numpy", "version": "1.24.4"},
        {
            "package_name": "opencv-contrib-python-headless",
            "import_name": "cv2",
            "version": "4.10.0.84",
        },
    ]

    # 尝试导入所有包，记录无法导入的包
    missing_packages = []
    for pkg in packages:
        try:
            importlib.import_module(pkg["import_name"])
        except ImportError:
            print(f"{pkg['import_name']} 未安装")
            missing_packages.append(pkg)

    # 如果存在无法导入的包，开始安装过程
    if missing_packages:
        print("检测到部分包未安装，开始安装...")

        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        app = QtWidgets.QApplication(sys.argv)
        resources_path = Path("resources")

        # Apply QSS styling
        qss_path = resources_path / "qdark.qss"
        with open(qss_path, "r") as qss_file:
            app.setStyleSheet(qss_file.read())
        app.setFont(QtGui.QFont("Microsoft YaHei", 9))

        progress_window = InstallProgressWindow(packages)
        progress_window.show()
        install_thread = InstallThread(packages)
        install_thread.progress_signal.connect(progress_window.update_progress)
        install_thread.start()
        sys.exit(app.exec_())

        return True
    else:
        print("所有包已成功导入，无需安装。")
        return False


if __name__ == "__main__":
    main()
