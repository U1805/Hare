# Blue_Archive_VideoTextBlur
烤肉机part1，去除文字 📜

### 依赖包：

`opencv`

[OPENCV2 图像修复 — 去除文字（下）_learn_sunzhuli的专栏-CSDN博客](https://blog.csdn.net/learn_sunzhuli/article/details/47791519)

[Python-OpenCV中的cv2.inpaint()函数 - Rogn - 博客园 (cnblogs.com)](https://www.cnblogs.com/lfri/p/10618417.html)

<img src="./images/202201261125651.png" alt="cv2.inpaint()" width="400"/>

`pysubs2`

[python 提取字幕_使用 Python 提取字幕文件_weixin_39830906的博客-CSDN博客](https://blog.csdn.net/weixin_39830906/article/details/110778737)

`alive_progress`

[酷炫的 Python 进度条开源库：alive-progress-技术圈 (proginn.com)](https://jishuin.proginn.com/p/763bfbd55bf8)

### 当前进度：

- [x] openCV-inpaint 实现单张图片去除文字
- [x] pysubs2 处理字幕标记时间轴
- [x] 视频去除文字并输出
- [x] 字幕样式
- [x] 多线程
- [x] 声音
- [x] 字幕视频压制
- [x] 字幕文本换行
- [x] 进度条
- [x] 字幕打字机效果
- [x] 地点字幕样式
- [x] 渐变过场画面修补效果优化
- [x] 字幕样式优化
- [x] 打包可执行文件
- [x] 地点渐变修补优化

目前效果：

<img src="./images/202201241902935.gif" width="400"/>

使用：

1. 复制 `ffmpeg` 到 `C:\Windows`

2. 保证字幕(.ass)和视频(.mp4)同名，并与 `run.exe` 、 `config.txt` 同级目录，运行 `run.exe`

### todo

- 三选项字幕样式
- 预处理优化


### 更新 22/1/25

- 优化渐变过场画面

- 修复相对路径错误 ❗

- 打包可执行文件 🗹

- 字幕样式优化

### 更新 22/1/24

- 添加字幕打字机效果 🌟

<img src="./images/202201241902935.gif" width="400"/>

- 添加地点字幕样式 🏘

<img src="./images/202201241851671.png" width="400"/>

- 渐变过场画面修补效果优化

- 字幕样式优化

### 更新 22/1/23

- 添加学生名和社团样式 ☁

<img src="./images/202201241904229.png" width="400"/>

- 添加多线程 🌠

测试视频用时 （预处理用时+修复用时）

（时长：2m10s）11m 5.7s → 2m 20.4s + 2m 53.3s

同时切分合并预处理减小文件体积 

135 MB → 26.2 MB

153 MB → 40.1 MB

- 合并原视频音轨 ♪

- ffmpeg 硬字幕压制

- 添加 alive-progress 进度条 

<img src="./images/202201241853115.png" width="400"/>

- 字幕文本实现换行
