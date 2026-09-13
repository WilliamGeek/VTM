#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
detect_keyframes.py
-------------------
长视频高信息熵关键帧自适应提取工具。
基于场景切换检测（Scene Change Detection）与画面稳定性评估，从长视频中自适应提取 15~30 张
具有实质内容跃迁的候选关键帧（如幻灯片翻页、架构拓扑展示、代码演进、板书公式），
避免盲目密集等频抽帧，大幅降低多模态分析冗余度并提升处理效率。
"""

import os
import sys
import re
import json
import argparse
import subprocess
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def find_ffmpeg(custom_path=None):
    """探测可用的 ffmpeg 可执行文件路径"""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    env_bin = os.getenv("FFMPEG_BIN")
    if env_bin and os.path.exists(env_bin):
        return env_bin

    import shutil
    bin_path = shutil.which("ffmpeg")
    if bin_path:
        return bin_path

    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "tools" / "ffmpeg.exe",
        script_dir.parent / "tools" / "ffmpeg.exe",
        script_dir.parent / "tools" / "ffmpeg",
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(r"F:\yt-dlp\ffmpeg.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    raise FileNotFoundError(
        "未找到 ffmpeg 可执行文件！\n"
        "请确保 ffmpeg 已安装并配置至 PATH，或设置环境变量 FFMPEG_BIN。\n"
        "安装提示: Windows 执行 'winget install Gyan.FFmpeg'，macOS 执行 'brew install ffmpeg'"
    )


def format_seconds(seconds):
    """将秒数转为格式化时间戳 MM:SS 或 HH:MM:SS"""
    s = int(round(seconds))
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def get_video_duration(video_path, ffmpeg_bin):
    """获取视频时长（秒）"""
    cmd = [
        ffmpeg_bin,
        "-i", str(video_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 0.0


def detect_scene_changes(video_path, ffmpeg_bin, threshold=0.35, min_interval=10.0):
    """
    利用 ffmpeg select 滤镜检测场景突变时间戳
    """
    cmd = [
        ffmpeg_bin,
        "-i", str(video_path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null",
        "-"
    ]
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, errors="replace")
    
    pts_times = []
    time_pattern = re.compile(r"pts_time:([0-9\.]+)")

    for line in process.stderr:
        m = time_pattern.search(line)
        if m:
            pts = float(m.group(1))
            # 保证最小间隔，避免同一个场景内镜头快速震荡导致密集抽帧
            if not pts_times or (pts - pts_times[-1]) >= min_interval:
                pts_times.append(pts)

    process.wait()
    return pts_times


def sample_evenly(duration, count):
    """当场景检测结果过少时，进行保底均匀采样"""
    if duration <= 0 or count <= 0:
        return []
    step = duration / (count + 1)
    return [step * i for i in range(1, count + 1)]


def evaluate_frame_visual_entropy(frame_path):
    """
    基于信息论与计算机视觉特征评估候选帧的图形结构属性（Domain-Agnostic）：
    1. 灰度直方图香农熵 (Shannon Entropy):
       - 结构化图表/幻灯片/矢量图具有离散的高对比色阶与集中峰值分布 (低熵，通常 < 5.5)；
       - 自然实景摄影/主播镜头/环境空镜具有连续渐变的光学弥散与平缓分布 (高熵，通常 >= 6.5)。
    2. 边缘密度与锐度 (Edge Density):
       - 结构化图表/文字排版/网状拓扑具有高密度的清晰几何边缘；
       - 焦外虚化、平滑人像或暗角实景的边缘均值通常较低。
    """
    try:
        from PIL import Image, ImageFilter, ImageStat
        with Image.open(frame_path) as img:
            gray = img.convert('L')
            entropy = round(float(gray.entropy()), 2)
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            edge_density = round(float(edge_stat.mean[0]), 2)

            # 综合判定是否为高信息熵结构化图形/图表候选
            is_graphic = bool(entropy < 5.5 or (entropy < 6.5 and edge_density >= 8.0))
            return {
                "entropy": entropy,
                "edge_density": edge_density,
                "is_graphic_candidate": is_graphic
            }
    except Exception:
        return {
            "entropy": None,
            "edge_density": None,
            "is_graphic_candidate": None
        }


def extract_single_frame(video_path, timestamp_sec, output_path, ffmpeg_bin):
    """截取单个高清静态关键帧"""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss", f"{timestamp_sec:.2f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "3",
        str(output_path)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, errors="replace")


def main():
    parser = argparse.ArgumentParser(description="长视频自适应高信息熵关键帧提取工具")
    parser.add_argument("video_path", help="输入视频路径")
    parser.add_argument("-o", "--output-dir", default=None, help="关键帧输出目录（默认在视频同级 keyframes/）")
    parser.add_argument("--min-frames", type=int, default=10, help="最少关键帧数")
    parser.add_argument("--max-frames", type=int, default=30, help="最多关键帧数")
    parser.add_argument("--threshold", type=float, default=0.35, help="场景突变敏感度阈值 (0.0~1.0)")
    parser.add_argument("--min-interval", type=float, default=12.0, help="两帧之间的最小时间间隔（秒）")
    args = parser.parse_args()

    video_path = Path(args.video_path).resolve()
    if not video_path.exists():
        print(f"[!] 视频文件不存在: {video_path}", file=sys.stderr)
        sys.exit(1)

    ffmpeg_bin = find_ffmpeg()
    duration = get_video_duration(video_path, ffmpeg_bin)
    print(f"[*] 视频时长: {format_seconds(duration)} ({duration:.1f} 秒)")

    if not args.output_dir:
        output_dir = video_path.parent / "keyframes"
    else:
        output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] 正在执行自适应场景突变检测 (阈值={args.threshold}, 最小间隔={args.min_interval}s)...")
    detected_times = detect_scene_changes(video_path, ffmpeg_bin, threshold=args.threshold, min_interval=args.min_interval)
    print(f"[+] 检测到场景变化时间戳数量: {len(detected_times)}")

    # 帧数自适应调优：如果突变点过少（如纯幻灯片极慢翻页），补充等距点
    final_times = list(detected_times)
    if len(final_times) < args.min_frames:
        needed = args.min_frames - len(final_times)
        supplementary = sample_evenly(duration, needed)
        combined = sorted(list(set(final_times + supplementary)))
        # 再次按最小间隔过滤
        filtered = []
        for t in combined:
            if not filtered or (t - filtered[-1]) >= (args.min_interval / 2):
                filtered.append(t)
        final_times = filtered

    # 如果突变点过多，按重要性或步长均匀下采样至 max_frames
    if len(final_times) > args.max_frames:
        step = len(final_times) / args.max_frames
        final_times = [final_times[int(i * step)] for i in range(args.max_frames)]

    manifest = []
    print(f"[*] 开始提取选定的 {len(final_times)} 个高信息熵候选关键帧...")

    graphic_count = 0
    for idx, t in enumerate(final_times):
        ts_str = format_seconds(t)
        safe_ts = ts_str.replace(":", "-")
        frame_filename = f"keyframe_{idx+1:02d}_{safe_ts}.png"
        frame_path = output_dir / frame_filename

        extract_single_frame(video_path, t, frame_path, ffmpeg_bin)
        metrics = evaluate_frame_visual_entropy(frame_path)
        if metrics.get("is_graphic_candidate"):
            graphic_count += 1

        manifest.append({
            "index": idx + 1,
            "timestamp": ts_str,
            "seconds": round(t, 2),
            "filename": frame_filename,
            "path": str(frame_path),
            "visual_metrics": metrics
        })

    print(f"[+] 提取完成，共识别出 {graphic_count}/{len(manifest)} 张结构化图形/图表候选帧")

    # 保存清单
    manifest_path = output_dir / "keyframes_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "video": str(video_path),
            "duration": duration,
            "duration_formatted": format_seconds(duration),
            "total_frames": len(manifest),
            "keyframes": manifest
        }, f, ensure_ascii=False, indent=2)

    print(f"[+] 关键帧提取完成，已保存至: {output_dir}")
    print(f"[+] 索引清单: {manifest_path}")

    # 输出结构化结果供外部消费
    print("\n__OUTPUT_JSON__")
    print(json.dumps({
        "status": "success",
        "output_dir": str(output_dir),
        "manifest_file": str(manifest_path),
        "total_frames": len(manifest),
        "sample_frames": manifest[:5]
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
