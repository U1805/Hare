import json
import os
import re

import gradio as gr


def get_list(type):
    with open(".\\modules\\config.json", "r", encoding='utf-8') as fp:
        data = fp.read()
        data = json.loads(data)
        size_list = [item["size"] for item in data[type]]
    return size_list

def get_list2(type):
    with open(".\\modules\\config.json", "r", encoding='utf-8') as fp:
        data = fp.read()
        data = json.loads(data)
        size_list = [item["size"] for item in data["频道打轴"][type]]
    return size_list

def typer(text, num=35):
    cnt = 1
    s = ""
    for word in text:
        s = s+"{\\1a&HFF&\\3a&HFF&\\4a&HFF&}{\\t("+str(cnt*33)+","+str(cnt*33+1)+",\\1a&H00&\\3a&H00&\\4a&H00&)}"+word
        if cnt % num == 0:
            s += "\\N{\\fs 0}\\N"
        cnt=cnt+1
    return s

def downloader(url, browser):
    output_path_ = os.path.abspath(os.path.join(".\\", "output"))
    if not os.path.exists(output_path_):
        os.makedirs(output_path_)
        print('create filefolder：', output_path_)
    path = f'yt-dlp --paths {os.path.abspath("output")} --cookies-from-browser {browser} -f  \"bv[ext=mp4]+ba[ext=m4a]\"   --embed-metadata --merge-output-format mp4 \"{url}\"'
    path = path.replace("\\\\","\\")
    try:
        os.system(path)
    except Exception:
        print("Funtion Downloader yt-dlp error")
        pass
    
    for _,_,k in os.walk(".\\output"):
        for s in k:
            if re.findall(r".*\[(.*)\].*",s) and ".mp4" in s:
                return os.path.join(".\\output", s)

def subtitle(video, ass):
    video_path = os.path.abspath(video)
    ass_path = os.path.abspath(ass.name)
    ass_path = ass_path.replace("\\","\\\\").replace(":","\\:")
    _, filename = os.path.split(os.path.normpath(video))
    output_path = os.path.abspath(".\\output\\"+filename)
    output_path_ = os.path.abspath(os.path.join(".\\", "output"))
    if not os.path.exists(output_path_):
        os.makedirs(output_path_)
        print('create filefolder：', output_path_)
    try:
        os.system(f"ffmpeg -y -i \"{video_path}\" -vf subtitles=\"\'{ass_path}\'\" \"{output_path}\"")
    except Exception:
        print("Function Subtitle ffmpeg error")
        pass
    return output_path

def convert(video):
    video = video.name
    path, filename = os.path.split(os.path.normpath(video))
    video_path = os.path.abspath(video)
    output_path = os.path.abspath(".\\output\\"+filename+".mp4")
    output_path_ = os.path.abspath(os.path.join(".\\", "output"))
    if not os.path.exists(output_path_):
        os.makedirs(output_path_)
        print('create filefolder：', output_path_)
    try:
        os.system(f"ffmpeg -y -i \"{video_path}\" -c copy \"{output_path}\"")
    except Exception:
        print("Function convert ffmpeg error")
        pass
    return output_path
    

with gr.Blocks(css=".file,.unpadded_box{ height: 60px!important;min-height: auto!important;flex-grow: 0!important;}",
                title="视频处理工具") as demo:
    gr.Markdown("""# 碧蓝档案视频处理工具 🛠️
视频打开真的很慢，总之你先别急 🖐️""")
    with gr.Tab("剧情打轴"):
        with gr.Row():
            with gr.Column():
                video_input = gr.Video(format='mp4', label="输入视频")
                video_size = gr.Dropdown(get_list("剧情打轴"), value="1920*1080", label="设置参数", info="选择视频分辨率", )
                fill = gr.Checkbox(label="是否 ocr 填轴", value=True)
            with gr.Column():
                ass_output = gr.File(interactive=False, label="输出文件", elem_classes="file")
                ass_output_preview = gr.TextArea(label="输出预览",)
        with gr.Row():
            autosub_button = gr.Button("🚀Start!")
    
    from modules import autosub
    autosub_button.click(autosub.run, 
                inputs=[video_input, video_size, fill], 
                outputs=[ass_output, ass_output_preview])

    with gr.Tab("剧情打码"):
        with gr.Row():
            with gr.Column():
                video_input2 = gr.Video(format='mp4', label="输入视频")
                ass_input2 = gr.File(file_types=[".ass"], label="时间轴", elem_classes="file")
                video_size2 = gr.Dropdown(get_list("剧情打码"), value="1920*1080", label="设置参数", info="选择视频分辨率", )
            with gr.Column():
                # video_output = gr.File(interactive=False, label="输出文件")
                video_output_preview = gr.Video(interactive=False, label="输出预览")
        with gr.Row():
            inpaint_button = gr.Button("🚀Start!")

    from modules import inpaint
    inpaint_button.click(inpaint.run, 
                inputs=[video_input2, video_size2, ass_input2], 
                outputs=[video_output_preview])
    

    
    with gr.Tab("频道对帧轴"):
        with gr.Row():
            with gr.Column():
                video_input3 = gr.Video(format='mp4', label="输入视频")
                video_size3 = gr.Dropdown(get_list2("阿罗娜"), value="--请选择--", label="设置参数", info="选择视频分辨率", )
                video_type3 = gr.Dropdown(["阿罗娜", "爱丽丝"], value="阿罗娜", label="设置参数", info="选择视频类型", )
                fill3 = gr.Checkbox(label="是否 ocr 填轴", value=True)
            with gr.Column():
                ass_output3 = gr.File(interactive=False, label="输出文件", elem_classes="file")
                ass_output_preview3 = gr.TextArea(interactive=False, label="输出预览")
        with gr.Row():
            autosub_button3 = gr.Button("🚀Start!")

    video_type3.change(fn=lambda value: gr.update(choices=get_list2(value)), inputs=video_type3, outputs=video_size3)
    from modules import arona
    autosub_button3.click(arona.run, 
                inputs=[video_input3, video_size3, video_type3, fill3], 
                outputs=[ass_output3, ass_output_preview3])

    with gr.Tab("小工具"):
        gr.Markdown("# 📥视频下载")
        with gr.Row():
            with gr.Column():
                url_input = gr.Text(label="输入 youtube 链接")
                browser_input = gr.Dropdown(["edge", "chrome", "firefox", "safari"], value="edge", label="浏览器cookie", info="如果下载的视频需要登录 请选择登录过账号的浏览器", )
            with gr.Column():
                video_output_preview4 = gr.Video(interactive=False, label="视频预览")
        download_button = gr.Button("🚀Download!")

        gr.Markdown("# 🏷️字幕压制")
        with gr.Row():
            with gr.Column():
                subtitle_video = gr.Video(format='mp4', label="视频")
                subtitle_ass = gr.File(file_types=[".ass"], label="字幕", elem_classes="file")
            with gr.Column():
                subtitle_output_preview = gr.Video(interactive=False, label="输出预览")
        subtitle_button = gr.Button("🚀Start!")

        gr.Markdown("# 📼转换为 mp4")
        with gr.Row():
            convert_input = gr.File(label="原始视频")
            convert_output = gr.Video(interactive=False, label="输出视频")
        convert_button = gr.Button("🚀Start!")

        gr.Markdown("# 🖨️打字机效果代码")
        with gr.Row():
            typer_input = gr.Textbox(placeholder="输入要显示打字机效果的文字", label="INPUT")
            typer_output = gr.Textbox(placeholder="输出特效代码", label="OUTPUT")
        num = gr.Slider(2, 100, value=35, label="每行字数", step=1)
        typer_button = gr.Button("🚀Start!")
    
    download_button.click(downloader, inputs=[url_input, browser_input], outputs=[video_output_preview4])
    subtitle_button.click(subtitle, inputs=[subtitle_video, subtitle_ass], outputs=[subtitle_output_preview])
    convert_button.click(convert, inputs=[convert_input], outputs=[convert_output])
    typer_button.click(typer, [typer_input, num], typer_output)

    with gr.Accordion("Open for More!", open=False):
        gr.Markdown("""\
字体：大小 `{\\fs256}` 字体名 `{\\fn微软雅黑}` 间距 `{\\fsp5}` 边框 `{\\bord1}` 阴影 `{\\shad1}` 颜色 `{\\1c&H颜色代码}`

淡入淡出 `{\\fad(t1,t2)}`

选项块 `{\\bord0\\shad0\\fscx2200\\fscy160\\c&HFFFFFF&\\pos(976.8,478.8)}■`

[提交Bug](https://github.com/u1805/Blue_Archive_Timerstamper/issues)
""")

if __name__ == "__main__":
    demo.launch()
