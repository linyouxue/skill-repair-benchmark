#!/usr/bin/env python3
"""End-to-end silence/pause removal pipeline for a video workspace.

The entrypoint intentionally uses only the Python standard library for audio
analysis. ffmpeg and ffprobe are required only for media I/O and are checked
before any intermediate files are created.
"""
from __future__ import annotations
import argparse, json, math, shutil, struct, subprocess, tempfile, wave
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"required executable not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail=(exc.stderr or exc.stdout or "").strip().splitlines()[-1:]
        raise RuntimeError(f"command failed ({cmd[0]}): {' '.join(detail)}") from exc


def duration(path: Path) -> float:
    out=run(["ffprobe","-v","error","-show_entries","format=duration",
             "-of","default=noprint_wrappers=1:nokey=1",str(path)]).stdout.strip()
    try: return max(0.0,float(out))
    except ValueError as exc: raise RuntimeError(f"ffprobe returned invalid duration for {path}") from exc


def rms_windows(wav: Path, seconds: float=1.0) -> list[float]:
    with wave.open(str(wav), "rb") as f:
        rate, width, channels, frames=f.getframerate(), f.getsampwidth(), f.getnchannels(), f.getnframes()
        raw=f.readframes(frames)
    if width != 2: raise RuntimeError("audio extractor must produce 16-bit PCM WAV")
    step=max(1,int(rate*seconds)*channels*width); values=[]
    for pos in range(0,len(raw),step):
        chunk=raw[pos:pos+step]; count=len(chunk)//2
        if not count: continue
        samples=struct.unpack("<"+"h"*count,chunk[:count*2])
        values.append(math.sqrt(sum(x*x for x in samples)/count))
    return values


def detect_segments(energy: list[float], ratio: float=0.5, minimum: int=2) -> list[dict]:
    if not energy: return []
    span=30; result=[]; start=None
    for i,value in enumerate(energy):
        lo=max(0,i-span//2); hi=min(len(energy),i+span//2+1)
        avg=sum(energy[lo:hi])/max(1,hi-lo)
        low=value < avg*ratio and avg > 0
        if low and start is None: start=i
        if not low and start is not None:
            if i-start >= minimum: result.append({"start":start,"end":i})
            start=None
    if start is not None and len(energy)-start >= minimum: result.append({"start":start,"end":len(energy)})
    return result


def normalize(segments: list[dict], total: float) -> list[dict]:
    clean=[]
    for s in sorted(segments,key=lambda x: float(x["start"])):
        a=max(0.0,min(total,float(s["start"]))); b=max(a,min(total,float(s["end"])))
        if b-a >= 1.0:
            if clean and a <= clean[-1]["end"]:
                clean[-1]["end"]=max(clean[-1]["end"],b)
            else: clean.append({"start":a,"end":b})
    for s in clean: s["duration"]=round(s["end"]-s["start"],3)
    return clean


def process(inp: Path, out: Path, segments: list[dict]) -> None:
    total=duration(inp); keep=[]; cursor=0.0
    for s in segments:
        if s["start"] > cursor: keep.append((cursor,s["start"]))
        cursor=max(cursor,s["end"])
    if cursor < total: keep.append((cursor,total))
    if not keep: raise RuntimeError("pause detection removed the entire video")
    if len(keep)==1 and keep[0][0] <= 0.001 and keep[0][1] >= total-0.001:
        run(["ffmpeg","-y","-i",str(inp),"-c","copy",str(out)]); return
    parts=[]
    for i,(a,b) in enumerate(keep):
        parts += [f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]",
                  f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]"]
    vs="".join(f"[v{i}]" for i in range(len(keep))); as_="".join(f"[a{i}]" for i in range(len(keep)))
    parts += [f"{vs}concat=n={len(keep)}:v=1:a=0[outv]",f"{as_}concat=n={len(keep)}:v=0:a=1[outa]"]
    run(["ffmpeg","-y","-i",str(inp),"-filter_complex",";".join(parts),"-map","[outv]","-map","[outa]","-c:v","libx264","-preset","veryfast","-c:a","aac",str(out)])


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",default="/root/input_video.mp4")
    p.add_argument("--output",default="/root/compressed_video.mp4")
    p.add_argument("--report",default="/root/compression_report.json")
    p.add_argument("--min-duration",type=int,default=2)
    args=p.parse_args(); inp=Path(args.input); out=Path(args.output); report=Path(args.report)
    if not inp.is_file(): raise SystemExit(f"input video not found: {inp}")
    for tool in ("ffmpeg","ffprobe"):
        if shutil.which(tool) is None: raise SystemExit(f"required executable missing: {tool}")
    with tempfile.TemporaryDirectory(prefix="video-silence-") as td:
        wav=Path(td)/"audio.wav"
        run(["ffmpeg","-y","-i",str(inp),"-vn","-acodec","pcm_s16le","-ar","16000","-ac","1",str(wav)])
        energy=rms_windows(wav); segments=normalize(detect_segments(energy,minimum=args.min_duration),duration(inp))
    out.parent.mkdir(parents=True,exist_ok=True); process(inp,out,segments)
    original=duration(inp); compressed=duration(out)
    payload={"original_duration_seconds":round(original,3),"compressed_duration_seconds":round(compressed,3),"removed_duration_seconds":round(max(0,original-compressed),3),"compression_percentage":round(max(0,original-compressed)/original*100,2) if original else 0,"segments_removed":segments}
    report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps(payload,indent=2)+"\n")
    print(json.dumps(payload,indent=2)); return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except RuntimeError as exc: raise SystemExit(str(exc))
