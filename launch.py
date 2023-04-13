import os
import platform
import subprocess
import sys

python = sys.executable

def check_python_version():
    is_windows = platform.system() == "Windows"
    major = sys.version_info.major
    minor = sys.version_info.minor
    micro = sys.version_info.micro

    if is_windows:
        supported_minors = [10]
    else:
        supported_minors = [7, 8, 9, 10, 11]

    if not (major == 3 and minor in supported_minors):
        import modules.errors

        modules.errors.print_error_explanation(f"""
INCOMPATIBLE PYTHON VERSION

This program is tested with 3.10.6 Python, but you have {major}.{minor}.{micro}.
If you encounter an error with "RuntimeError: Couldn't install torch." message,
or any other error regarding unsuccessful package (library) installation,
please downgrade (or upgrade) to the latest version of 3.10 Python
and delete current Python and "venv" folder in WebUI's directory.

You can download 3.10 Python from here: https://www.python.org/downloads/release/python-3109/

Use --skip-python-version-check to suppress this warning.
""")


def run(command, desc=None, errdesc=None, custom_env=None):
    if desc is not None:
        print(desc)

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, env=os.environ if custom_env is None else custom_env)

    if result.returncode != 0:
        message = f"""{errdesc or 'Error running command'}.
Command: {command}
Error code: {result.returncode}
stdout: {result.stdout.decode(encoding="utf8", errors="ignore") if len(result.stdout)>0 else '<empty>'}
stderr: {result.stderr.decode(encoding="utf8", errors="ignore") if len(result.stderr)>0 else '<empty>'}
"""
        raise RuntimeError(message)

    return result.stdout.decode(encoding="utf8", errors="ignore")


def run_pip(args, desc=None):
    return run(f'"{python}" -m pip {args}', desc=f"Installing {desc}", errdesc=f"Couldn't install {desc}")


def prepare_environment():
    print(f"Python {sys.version}")
    
    i = "-i https://pypi.tuna.tsinghua.edu.cn/simple some-package"
    # requirements_file = os.environ.get('REQS_FILE', "requirements.txt")
    # run(f'"{python}" -m pip install -r {requirements_file}', desc=f"Installing requirements", errdesc=f"Couldn't install requirements")
    run_pip(f"install alive_progress {i}", "alive_progress")
    run_pip(f"install easyocr {i}", "easyocr")
    run_pip(f"install opencv_python_headless {i}", "opencv_python_headless")
    # run_pip(f"install pysubs2 {i}", "pysubs2")

def start():
    import autosub
    import inpaint
    choice = input("""
------------
1) 打轴器
2) 打码器
0) 退出
""")
    if choice=="1":
        autosub.run()
    elif choice=="2":
        inpaint.run()

if __name__ == "__main__":
    prepare_environment()
    start()
