# Blue_Archive_VideoTextBlur
烤肉机part1，去除文字

当前进度：

- [x] openCV-inpaint 实现单张图片去除文字
- [x] pysubs2 处理字幕标记时间轴
- [x] 视频去除文字并输出

目前效果：

![image-20220122230513032](https://gitee.com/u1805/pic-md1/raw/master/202201222305117.png)

![image-20220122230546142](https://gitee.com/u1805/pic-md1/raw/master/202201222305246.png)

当前使用：保证字幕(.ass)和视频(.mp4)同名，与 `run.py` 同级目录，运行 `run.py`

#### todo

- 字幕文本换行
- 字幕打印机效果
- 三选项、地点
- 声音
- 多线程
- 进度条
- 输出字幕和视频
- 修补效果优化
- 字幕样式优化
- 一些 bug
- 简单的 UI 界面
