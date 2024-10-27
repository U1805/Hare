@echo off
:: 环境变量
set install=https://pypi.tuna.tsinghua.edu.cn/simple
set path=%cd%\modules;%cd%\python38;%cd%\python38\Scripts;%path%
:: 安装pip
python modules\get-pip.py
:: 安装依赖库
python -m pip install alive-progress -i %install%
python -m pip install opencv_python_headless -i %install%
cd modules\ffmpy-0.3.0
python setup.py install
cd ..\..
python -m pip install gradio -i %install%
:: 运行
cls
python webui.py