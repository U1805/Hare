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

[release](https://github.com/U1805/Hare/releases/latest) <- 从这里下载

下载 `Hare.zip`，解压压缩包后你应该得到下面的文件结构

```
📁 Hare
├─📁 resources
├─📁 runtime
├─📁 script
├─📁 site-packages
├─⚙️ ffmpeg.exe
├─🚀 Hare.exe   <- 双击运行
└─⚙️ Hare.int
```

[遇到报错？](#安装报错)

## 效果

![blueaka](./md/blueaka.png)

![gukamas](./md/gakumas2.png)

## 快速上手

![region](./md/intro.png)

1. 加载视频文件
   - 打开文件：菜单栏的 `文件` -> `选择视频`
   - 预览视频：滑动控制栏的进度条预览视频内容
2. 加载时轴文件
   - 打开文件：菜单栏的 `文件` -> `选择字幕`
3. 创建修复区域
   - 点击一个行标题
   - 如果修复灰色文字，双击行标题选择灰色
   - 在左侧视频输入区域，按住鼠标左键并拖动
   - 不同的修复区域红框不会同时显示
   - 算法选择 **MASK**，点击 `测试当前帧` 
4. 选择修复算法
   - 算法选择 **INPAINT**，点击 `测试当前帧`
5. 运行修复算法
   - 设置完成后，点击 `开始运行` 按钮
   - 结果文件在视频同目录，文件名以 output 结尾

## 算法选择
  
- **MASK**：掩码算法，红色部分是修复算法会处理的区域  
<!-- - **AUTOSUB**：自动打轴算法 -->
- **INPAINT**：INPAINT 开头为修复算法，  
      INPAINT_LAMA (GPU 算法，耗时 1.5x)  
      INPAINT_NS (CPU 算法，耗时 1.5x)  
      INPAINT_FSR_PARA (CPU 算法，耗时 5x)

> 优先使用 INPAINT_LAMA

<!-- ## 自动打轴

1. 加载视频文件
2. 创建修复区域
3. 选择算法：**AUTOSUB**
4. 开始运行 -->

## 安装报错

> 报错信息：WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'SSLError(SSLEOFError(8, 'EOF occurred in violation of protocol (_ssl.c:1131)'))': xxx
>
> 解决方法：关闭 VPN

## 调试

1. 下载代码  
   `git clone https://github.com/U1805/Hare.git --depth=1`
2. conda 创建 Python3.8 环境  
   `conda create --name hare python=3.8`
3. 运行 `python ./Hare.int`

## TODO

- [ ] 更好的掩码算法
  - [ ] 检测到半透明/渐隐的字
- [ ] 更好的修复算法
  - [x] INPAINT_FSR_FAST
  - [x] INPAINT_FSR_BEST
  - [x] INPAINT_FSR_PARA (并发的FAST,速度约快一倍)
  - [x] INPAINT_LAMA

## License

[GNU license](./LICENSE)

## 感谢

- [FFmpeg](http://ffmpeg.org/) - A complete, cross-platform solution to record, convert and stream audio and video. 
- [advimman/lama](https://github.com/advimman/lama) - 🦙 LaMa Image Inpainting, Resolution-robust Large Mask Inpainting with Fourier Convolutions, WACV 2022
- [skywind3000/PyStand](https://github.com/skywind3000/PyStand) - 🚀 Python Standalone Deploy Environment !! 