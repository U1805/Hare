<div align=center><img width="320" height="320" src="./md/hare_momotalk.png"/></div>

![maven](https://img.shields.io/badge/Python-3.8%2B-blue) 
![maven](https://img.shields.io/badge/OpenCV-4.10.0-yellow) 
![maven](https://img.shields.io/badge/pyQt-5.15.10-red)

# 视频文字清除工具

****

“今天，晴会保佑你，不管写什么代码，都不会出现漏洞。” —— 小钩晴 [▶️](https://static.kivo.wiki/voices/students/%E5%B0%8F%E9%92%A9%20%E6%99%B4/guF8G61lNHMhqdeztHSHTAMMEmCG1qy1.ogg)

****

此项目基于 OpenCV 和 pyQt5 开发，用于清除游戏剧情录屏中的字幕，方便汉化

## 下载

[release](https://github.com/U1805/Hare/releases/tag/v1.1.2r) <- 从这里下载

下载 `Hare.zip`，解压压缩包后你应该得到下面的文件结构

```
Hare
├─runtime
├─site-packages
│   ├─cv2
│   ├─numpy
│   └─PyQt5
├─resources
├─ffmpeg.exe
├─Hare.exe    <- 双击运行
├─Hare.int
└─script.egg
```

## 效果

![blueaka](./md/blueaka.png)

![gukamas](./md/gakumas2.png)

## 快速上手

> 优先使用 INPAINT_NS

1. 加载视频文件
   - 点击左上角的 `文件` -> `选择视频`，打开视频文件
   - 加载后，可以通过滑动视频上方的进度条预览视频内容
2. 创建修复区域
   - 在视频的左侧视频输入区域，按住鼠标左键并拖动，  
   创建红色的标记区域，表示需要消除的部分
   - 如果想查看当前帧的修复效果，可以点击 `测试当前帧`，  
   右侧视频输出区域显示效果
3. 调整修复算法
   - 在 `修复算法` 中，选择合适的算法进行处理：
      - **MASK**：掩码算法，用于测试需要消除的对象，  
      请确保有目标文字时掩码完全覆盖，没有文字时无掩码
      - **INPAINT**：INPAINT 开头为修复算法，  
      不透明/半透明背景建议 INPAINT_NS (耗时 1.5x)，  
      透明静态背景建议 INPAINT_FSR_PARA (耗时 5x)，  
      透明动态背景私密马赛没有好办法
   - 在 `参数设置` 中，调整修复参数：
      - **最小面积**：设定过小会导致噪点，设定过大会  
      漏掉小字符（如句号、省略号等）
      - **最大面积**：设定过小会导致部分文字无法检测到，  
      设定过大则可能误选中非文字区域
      - **描边**：对掩码区域加粗，以确保字符被完整覆盖
4. 运行修复
   - 设置完成后，点击 `开始运行` 按钮，开始视频
   - 修复完成后，处理后的文件将保存在与原视频相同的目录下，  
   文件名以 output 结尾

## 精确时间区间 / 多区域修复

1. 加载字幕文件
   - 在加载视频文件后，点击 `文件` -> `选择字幕`，  
   导入对应的视频字幕文件
   - 导入字幕后，界面下方的表格区域将根据字幕内容自动更新
2. 按说话对象创建修复区域
   - 点击表格中的行标题单元格，然后在左侧视频输入区创建红色修复区域
3. 按字幕时轴修复
   - 当开始运行时，将仅修复字幕对应的时间区间内的帧，  
   处理每个修复区域对应的修复区域。

## 调试

1. 下载代码  
`git clone https://github.com/U1805/Hare.git --depth=1`
2. 下载 Python3.8 嵌入式环境，解压获得 `runtime` 目录  
[Windows x86-64 embeddable zip file](https://www.python.org/downloads/release/python-380/)
1. 获得 Python3.8 对应的依赖
   1. 创建虚拟环境 `\path\to\py38\python.exe venv test`
   2. 进入 Scripts 目录，运行 `activate`
   3. pip 安装依赖 `opencv-contrib-python` `numpy` `PyQt5`
   4. 到 Lib/site-packages 目录复制依赖
2. 新建 `site-packages` 目录，将获得的依赖复制进去
3. 运行 `./Hare.exe` 或者在虚拟环境中 `python ./Hare.int`

## TODO

- [ ] 更好的掩码算法
  - [ ] 检测到半透明/渐隐的字
- [ ] 更好的修复算法
  - [x] INPAINT_FSR_FAST
  - [x] INPAINT_FSR_BEST
  - [x] INPAINT_FSR_PARA (并发的FAST,速度约快一倍)
- [ ] 多线程并发加速
- [x] 参数持久化
- [x] 多区域修复
- [x] ass时轴导入获取区间
- [ ] 单元格修复状态设置

## License

[MIT license](./LICENSE)

## 感谢

- [FFmpeg](http://ffmpeg.org/) - 伟大，无需多言
- [skywind3000/PyStand](https://github.com/skywind3000/PyStand) - 🚀 超方便的 Python 独立部署环境