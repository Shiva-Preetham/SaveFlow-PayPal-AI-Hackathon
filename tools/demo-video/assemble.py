"""Mix narration clips at their scene start times, burn sentence-level captions, output 1080p MP4."""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = Path(sys.argv[1])
scenes = {s["id"]: s for s in json.loads((HERE / "scenes.json").read_text("utf-8"))}
tl = json.loads((HERE / "timeline.json").read_text("utf-8"))
video = tl["video"]


def dur(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


# Captions: split each scene's caption into sentences, timed in proportion to their length.
srt, n = [], 1
for item in tl["scenes"]:
    sid, start = item["id"], item["start"]
    if sid in ("title", "eval", "end"):
        continue  # the cards already show this text
    d = dur(HERE / f"audio_{sid}.wav")
    parts = [p.strip() for p in re.split(r"(?<=[.?!:])\s+(?=[A-Z0-9])", scenes[sid]["caption"]) if p.strip()]
    total_chars = sum(len(p) for p in parts)
    t = start
    for p in parts:
        span = d * len(p) / total_chars
        srt.append(f"{n}\n{ts(t)} --> {ts(t + span + 0.25)}\n{p}\n")
        n, t = n + 1, t + span
(HERE / "captions.srt").write_text("\n".join(srt), "utf-8")

end = tl["scenes"][-1]["start"] + dur(HERE / "audio_end.wav") + 1.2
inputs, delays = ["-i", video], []
for i, item in enumerate(tl["scenes"], start=1):
    inputs += ["-i", str(HERE / f"audio_{item['id']}.wav")]
    ms = int(item["start"] * 1000) + 150
    delays.append(f"[{i}:a]adelay={ms}|{ms},aresample=48000[a{i}]")
mix = "".join(f"[a{i}]" for i in range(1, len(tl["scenes"]) + 1))
style = ("FontName=Segoe UI,FontSize=15,PrimaryColour=&H00FFFFFF,BackColour=&HA0000000,"
         "BorderStyle=3,Outline=6,Shadow=0,MarginV=16")
graph = ";".join(delays) + f";{mix}amix=inputs={len(tl['scenes'])}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad[aout];" \
        f"[0:v]trim=0:{end:.2f},setpts=PTS-STARTPTS,scale=1920:1080:flags=lanczos," \
        f"subtitles=captions.srt:force_style='{style}',fade=in:0:15,fade=out:st={end - 0.8:.2f}:d=0.8[vout]"
cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
       "-t", f"{end:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
       "-r", "30", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(OUT)]
subprocess.run(cmd, check=True, cwd=HERE)
print(f"wrote {OUT} ({end:.1f}s, {len(srt)} captions)")
