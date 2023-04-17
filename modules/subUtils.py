import re


def times_to_ms(time:str) -> int:
    ms = 0
    (h, m, s) = re.match(r'(.*):(.*):(.*)',time).groups()
    ms += float(s) * 1000
    ms += int(m) * 60000
    ms += int(h) * 3600000
    return int(ms)

def ms_to_frames(ms , fps) -> int:
    ms = int(ms)
    return int((ms / 1000) * fps)

def ms_to_times(ms) -> str:
    ms = int(ms)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    s = s + ms / 1000
    sgn = "-" if ms < 0 else ""
    return f"{sgn}{h:01d}:{m:02d}:{s:05.2f}" # h:mm:ss.ms 的格式，否则 FFmpeg 字幕压缩异常

def insertSub(path, fps, start, end, text="", style="Default"):
    with open(path, 'a', encoding='utf-8') as fp:
        # frame->ms->time  e.g. 216->3603->0:00:03.603
        start = ms_to_times(start*1000/fps)
        end = ms_to_times(end*1000/fps)
        fp.write(f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}\n")

def readSub(path):
    with open(path, 'r', encoding='utf-8') as fp:
        lines = fp.readlines()
        ans = []
        for line in lines:
            if line.startswith("Dialogue"):
                sub = re.match( r'Dialogue: 0,(.*),(.*),(.*),,0,0,0,,(.*)\n', line, re.M|re.I).groups()
                ans.append({'start':times_to_ms(sub[0]),'end':times_to_ms(sub[1]),'style':sub[2],'text':sub[3]}) 
    return ans

def saveSub(save_path, orig_path, subs):
    with open(save_path, 'w', encoding='utf-8') as wf:
        with open(orig_path,'r', encoding='utf-8') as rf:
            lines = rf.readlines()
            for line in lines:
                if not line.startswith("Dialogue"):
                    wf.write(line)
        for sub in subs:
            line = f'Dialogue: 0,{ms_to_times(sub["start"])},{ms_to_times(sub["end"])},{sub["style"]},,0,0,0,, {sub["text"]}\n'
            wf.write(line)
