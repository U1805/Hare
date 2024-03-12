import re


def ms_to_times_2(ms) -> str:
    ms = int(ms)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    s = s + ms / 1000
    s = int(s * 10**2) / (10**2)
    sgn = "-" if ms < 0 else ""
    return f"{sgn}{h:01d}:{m:02d}:{s:05.2f}"


def insertSub_2(path, fps, start, end, text="", style="Default"):
    with open(path, "a", encoding="utf-8") as fp:
        # frame->ms->time  e.g. 216->3603->0:00:03.603
        start = ms_to_times_2(start * 1000 / fps)
        end = ms_to_times_2(end * 1000 / fps)
        fp.write(f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}\n")


def modifyLastEnd(path, fps, new_time):
    import re

    lines = []
    with open(path, "r", encoding="utf-8") as fp:
        lines = fp.readlines()
        new_time = ms_to_times_2(new_time * 1000 / fps)
        lines[-1] = re.sub(
            r",(\d+:\d+:\d+.\d+),Default", f",{ new_time },Default", lines[-1]
        )
    with open(path, "w", encoding="utf-8") as fp:
        fp.writelines(lines)
