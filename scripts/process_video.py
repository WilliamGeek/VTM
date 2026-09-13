#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_video.py
----------------
端到端视频抓取与文本提取辅助工具。
调用 yt-dlp 与 ffmpeg 下载视频/提取字幕并清洗整理，按视频标题创建专属文件夹。
"""

import os
import sys
import re
import json
import argparse
import subprocess
from pathlib import Path

# 保证能加载同级 auth_manager 模块
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

try:
    from auth_manager import ensure_authenticated, PlatformRouter, CookieVault
except ImportError:
    ensure_authenticated = None
    PlatformRouter = None
    CookieVault = None

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def find_yt_dlp(custom_path=None):
    if custom_path and os.path.exists(custom_path):
        return custom_path
    
    # 1. 环境变量
    env_bin = os.getenv("YT_DLP_BIN")
    if env_bin and os.path.exists(env_bin):
        return env_bin

    # 2. 本地常用高可用独立二进制 (优先于 venv 脚本)
    standalone_candidates = [
        Path(r"F:\yt-dlp\yt-dlp.exe"),
        Path(r"F:\yt-dlp\tools\yt-dlp.exe"),
    ]
    for c in standalone_candidates:
        if c.exists():
            return str(c)

    # 3. 系统 PATH
    import shutil
    path_bin = shutil.which("yt-dlp")
    if path_bin:
        return path_bin

    # 4. 常见目录探测
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "tools" / "yt-dlp.exe",
        script_dir.parent / "tools" / "yt-dlp.exe",
        script_dir.parent / "tools" / "yt-dlp",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    raise FileNotFoundError(
        "未找到 yt-dlp 可执行文件！\n"
        "请确保 yt-dlp 已安装并加入 PATH，或设置环境变量 YT_DLP_BIN。\n"
        "安装提示: Windows 执行 'winget install yt-dlp.yt-dlp'，macOS 执行 'brew install yt-dlp'"
    )


def find_ffmpeg(custom_path=None):
    if custom_path and os.path.exists(custom_path):
        return custom_path

    env_bin = os.getenv("FFMPEG_BIN")
    if env_bin and os.path.exists(env_bin):
        return env_bin

    import shutil
    path_bin = shutil.which("ffmpeg")
    if path_bin:
        return path_bin

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
        "请确保 ffmpeg 已安装并加入 PATH，或设置环境变量 FFMPEG_BIN。\n"
        "安装提示: Windows 执行 'winget install Gyan.FFmpeg'，macOS 执行 'brew install ffmpeg'"
    )


def get_default_output_base():
    if os.getenv("OUTPUT_BASE_DIR"):
        return os.getenv("OUTPUT_BASE_DIR")
    if os.path.exists(r"F:\yt-dlp\downloads"):
        return r"F:\yt-dlp\downloads"
    return str(Path.cwd() / "downloads")


def sanitize_folder_name(name, max_len=80):
    """清理 Windows 文件名中不允许的字符"""
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', name)
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    cleaned = cleaned.strip('. ')
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].strip('. ')
    return cleaned or "video_item"

def run_cmd(cmd, check=True):
    """运行子进程命令并返回标准输出"""
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"命令执行失败 (code {result.returncode}):\n{' '.join(cmd)}\n{result.stderr}")
    return result

def get_video_info(yt_dlp_bin, url, cookie_file=None):
    """获取视频元数据 (JSON)"""
    cmd = [yt_dlp_bin, "--dump-single-json", "--no-playlist", "--no-warnings"]
    if cookie_file and os.path.exists(cookie_file):
        cmd.extend(["--cookies", str(cookie_file)])
    cmd.append(url)
    res = run_cmd(cmd)
    try:
        data = json.loads(res.stdout)
        return data
    except Exception as e:
        raise RuntimeError(f"解析视频元数据 JSON 失败: {e}\n输出内容前500字: {res.stdout[:500]}")

def parse_timestamp_sec(ts_str):
    """解析时间戳字符串为浮点秒数 (兼容 MM:SS, HH:MM:SS, 以及带毫秒形式)"""
    try:
        clean_ts = ts_str.strip().split('.')[0]
        parts = clean_ts.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except Exception:
        pass
    return 0.0

def format_seconds_to_timestamp(sec):
    """将秒数格式化为 HH:MM:SS 或 MM:SS"""
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def blocks_to_paragraphs(clean_blocks):
    """将 [(ts, text), ...] 转换为整洁的按时间戳段落合并文本"""
    formatted_paragraphs = []
    if clean_blocks:
        cur_ts = clean_blocks[0][0]
        cur_para = []
        for ts, txt in clean_blocks:
            cur_para.append(txt)
            if len("".join(cur_para)) >= 120 or txt.endswith(('。', '！', '？', '.', '!', '?')):
                formatted_paragraphs.append(f"[{ts}] {' '.join(cur_para)}")
                cur_para = []
        if cur_para:
            formatted_paragraphs.append(f"[{cur_ts}] {' '.join(cur_para)}")
    return "\n\n".join(formatted_paragraphs)

def clean_vtt_or_srt(file_path):
    """
    清洗字幕文件（VTT/SRT），剔除时间轴标签、重复滚屏行，返回整洁文本与结构化数据
    返回: (clean_text, clean_blocks)
    """
    if not os.path.exists(file_path):
        return "", []
    
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    clean_blocks = []
    last_text = ""
    current_timestamp = "00:00"
    
    time_pattern = re.compile(r'(\d{2}:\d{2}(?::\d{2})?)\.\d{3}\s*-->')
    srt_time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}),\d{3}\s*-->')

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if line.isdigit():
            continue

        # 匹配时间戳
        m = time_pattern.search(line) or srt_time_pattern.search(line)
        if m:
            current_timestamp = m.group(1)
            continue

        # 移除样式标签与行内时间戳
        text = re.sub(r'<[^>]+>', '', line)
        text = re.sub(r'\{[^}]+\}', '', text)
        text = text.strip()

        if not text:
            continue

        # 避免滚屏自动字幕连续重复相同文本
        if text == last_text:
            continue

        clean_blocks.append((current_timestamp, text))
        last_text = text

    clean_text = blocks_to_paragraphs(clean_blocks)
    return clean_text, clean_blocks

def slice_video_and_transcript(output_dir, safe_title, raw_title, duration, slice_minutes, media_file=None, clean_blocks=None):
    """
    长视频分段切片引擎 (Chunking / Slicing):
    当视频时长超过切片阈值时，自动将媒体与文稿拆解为 45~60 分钟切片，输出 slices_manifest.json
    """
    slice_sec = int(slice_minutes * 60)
    if duration <= slice_sec or slice_sec <= 0:
        return None

    slices_dir = os.path.join(output_dir, "slices")
    os.makedirs(slices_dir, exist_ok=True)

    num_slices = (int(duration) + slice_sec - 1) // slice_sec
    print(f"[*] 视频时长达 {int(duration)} 秒 (> {slice_minutes} 分钟)，启动长视频切片机制 (自动拆解为 {num_slices} 个独立分段)...")

    ffmpeg_bin = find_ffmpeg() if media_file else None
    slices_info = []

    for i in range(num_slices):
        start_sec = i * slice_sec
        end_sec = min((i + 1) * slice_sec, int(duration))
        part_num = i + 1
        start_ts = format_seconds_to_timestamp(start_sec)
        end_ts = format_seconds_to_timestamp(end_sec)

        part_dict = {
            "part": part_num,
            "title": f"第 {part_num} 部分 ({start_ts} - {end_ts})",
            "start_sec": start_sec,
            "end_sec": end_sec,
            "start_time": start_ts,
            "end_time": end_ts,
            "duration": end_sec - start_sec,
            "video_file": None,
            "transcript_file": None
        }

        # 1. 切分时间戳文稿
        if clean_blocks:
            part_blocks = [
                b for b in clean_blocks 
                if start_sec <= parse_timestamp_sec(b[0]) < end_sec
            ]
            part_text = blocks_to_paragraphs(part_blocks)
            part_trans_file = os.path.join(slices_dir, f"{safe_title}_transcript_part{part_num:02d}.txt")
            with open(part_trans_file, "w", encoding="utf-8") as f:
                f.write(f"# 视频分段文稿: {raw_title} (Part {part_num:02d})\n")
                f.write(f"# 范围: {start_ts} - {end_ts} (时长: {end_sec - start_sec} 秒)\n\n")
                f.write(part_text)
            part_dict["transcript_file"] = part_trans_file
            print(f"  [+] 分段 {part_num:02d} 文稿已切分: {part_trans_file} ({len(part_blocks)} 句)")

        # 2. 切分视频原片 (使用 ffmpeg 流拷贝，零转码极速完成)
        if media_file and os.path.exists(media_file) and ffmpeg_bin:
            part_vid_file = os.path.join(slices_dir, f"{safe_title}_part{part_num:02d}.mp4")
            if not os.path.exists(part_vid_file):
                slice_cmd = [
                    ffmpeg_bin, "-y",
                    "-ss", str(start_sec),
                    "-to", str(end_sec),
                    "-i", media_file,
                    "-c", "copy",
                    part_vid_file
                ]
                subprocess.run(slice_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(part_vid_file):
                part_dict["video_file"] = part_vid_file
                print(f"  [+] 分段 {part_num:02d} 视频切片完成: {part_vid_file}")

        slices_info.append(part_dict)

    manifest_file = os.path.join(slices_dir, "slices_manifest.json")
    manifest_data = {
        "video_title": raw_title,
        "total_duration": duration,
        "slice_minutes": slice_minutes,
        "num_slices": num_slices,
        "slices": slices_info
    }
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    print(f"[+] 长视频分段切片清单已输出: {manifest_file}")
    return manifest_data

def main():
    parser = argparse.ArgumentParser(description="视频下载、字幕提取与文件夹归档工具")
    parser.add_argument("url", help="视频网页链接 (Bilibili / YouTube / 抖音 / 等)")
    parser.add_argument("--output-base", default=get_default_output_base(), help="输出根目录 (默认 ./downloads 或 OUTPUT_BASE_DIR 环境变量)")
    parser.add_argument("--yt-dlp-bin", default=None, help="yt-dlp 可执行文件路径")
    parser.add_argument("--cookies", default=None, help="指定 Cookie 文件路径 (默认自动从 F:\\yt-dlp\\cookies\\ 读取对应平台凭证)")
    parser.add_argument("--allow-guest", action="store_true", help="允许无 Cookie 游客模式执行 (不推荐，极易被412拦截)")
    parser.add_argument("--skip-download", action="store_true", help="仅提取字幕和元数据，不下载视频")
    parser.add_argument("--audio-only", action="store_true", help="仅下载音频并转为 m4a/mp3")
    parser.add_argument("--format", default="bestvideo[height<=1080]+bestaudio/best", help="指定下载画质格式")
    parser.add_argument("--slice-minutes", type=int, default=0, help="长视频自动分段切片阈值 (分钟，如 45 或 60，0 表示不切片)")
    args = parser.parse_args()

    # 阶段 0：前置平台识别、短链展开与身份凭据预检
    effective_cookie_file = None
    if ensure_authenticated:
        auth_info = ensure_authenticated(args.url)
        # 自动展开短链为规范目标 URL
        if auth_info.get("canonical_url"):
            args.url = auth_info["canonical_url"]
        
        platform = auth_info.get("platform", "generic")
        candidate_cookie = args.cookies or auth_info.get("cookie_file")
        if candidate_cookie and os.path.exists(candidate_cookie):
            effective_cookie_file = candidate_cookie

        if auth_info.get("status") == "OK":
            uinfo = auth_info.get("user_info", {})
            uname = uinfo.get("uname", "已认证")
            print(f"[+] 平台 [{platform}] 鉴权通过: {uname} (凭证: {candidate_cookie})")
        elif not args.allow_guest:
            # 鉴权未通过，输出人机引导指令并退出
            print(f"[!] 平台 [{platform}] 鉴权未通过: {auth_info.get('reason')}")
            if platform == "bilibili":
                print(f"[*] 提示: 请运行 `uv run python scripts/auth_manager.py login-qr bilibili` 扫码登录。")
            else:
                print(f"[*] 提示: 平台 [{platform}] 不支持扫码登录。请在浏览器中登录后获取 Cookie：")
                print(f"    - 方法1 (推荐): 按 F12 打开网络面板刷新，复制请求标头中的 Cookie 字符串，运行:")
                print(f"      `uv run python scripts/auth_manager.py import-cookie {platform} --cookie-str \"<Cookie内容>\"`")
                print(f"    - 方法2: 使用 Cookie 导出插件下载 cookies.txt 并保存为 F:\\yt-dlp\\cookies\\{platform}_cookies.txt")
            print("\n__AUTH_REQUIRED__")
            print(json.dumps(auth_info, ensure_ascii=False, indent=2))
            sys.exit(2)
        else:
            print(f"[!] 警告: 未通过鉴权，强制以游客模式继续 (可能会触发 412/限制清晰度)...")

    yt_dlp_bin = find_yt_dlp(args.yt_dlp_bin)
    print(f"[*] 使用 yt-dlp 路径: {yt_dlp_bin}")
    print(f"[*] 正在分析视频元数据: {args.url} ...")

    try:
        info = get_video_info(yt_dlp_bin, args.url, cookie_file=effective_cookie_file)
    except Exception as e:
        print(f"[!] 获取元数据失败: {e}", file=sys.stderr)
        sys.exit(1)

    raw_title = info.get("title", "untitled_video")
    safe_title = sanitize_folder_name(raw_title)
    uploader = info.get("uploader") or info.get("channel") or "Unknown"
    duration = info.get("duration", 0)
    description = info.get("description", "")
    chapters = info.get("chapters", []) or []

    # 创建视频专属文件夹
    output_dir = os.path.join(args.output_base, safe_title)
    os.makedirs(output_dir, exist_ok=True)
    print(f"[+] 视频分类目录已就绪: {output_dir}")

    # 保存元数据
    info_json_path = os.path.join(output_dir, f"{safe_title}.info.json")
    metadata_summary = {
        "title": raw_title,
        "safe_title": safe_title,
        "uploader": uploader,
        "duration": duration,
        "url": args.url,
        "description": description,
        "chapters": chapters,
        "tags": info.get("tags", []),
    }
    with open(info_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata_summary, f, ensure_ascii=False, indent=2)

    # 尝试下载字幕
    print(f"[*] 正在检查并抓取字幕...")
    sub_template = os.path.join(output_dir, f"{safe_title}.%(ext)s")
    sub_cmd = [
        yt_dlp_bin,
        "--no-playlist",
        "--write-sub",
        "--write-auto-sub",
        "--sub-lang", "ai-zh,zh-Hans,zh,zh-CN,zh-Hant,en",
        "--skip-download",
    ]
    if effective_cookie_file and os.path.exists(effective_cookie_file):
        sub_cmd.extend(["--cookies", str(effective_cookie_file)])
    sub_cmd.extend([
        "-o", sub_template,
        args.url
    ])
    run_cmd(sub_cmd, check=False)

    # 扫描生成的字幕文件并按优先级排序（人工中文字幕优先于 AI 字幕）
    candidate_subs = list(Path(output_dir).glob(f"{safe_title}*.vtt")) + list(Path(output_dir).glob(f"{safe_title}*.srt"))
    def sub_priority(p):
        name = p.name.lower()
        if "zh-hans" in name or "zh-cn" in name:
            return 0
        if ".zh." in name or name.endswith("_zh.srt") or name.endswith("_zh.vtt"):
            return 1
        if "ai-zh" in name:
            return 2
        if "zh-hant" in name:
            return 3
        if "en" in name:
            return 4
        return 5
    subtitle_files = sorted(candidate_subs, key=sub_priority)
    transcript_file = os.path.join(output_dir, f"{safe_title}_transcript.txt")
    has_subtitles = False
    clean_blocks = []

    if subtitle_files:
        print(f"[+] 发现字幕文件: {[f.name for f in subtitle_files]}")
        clean_text, clean_blocks = clean_vtt_or_srt(str(subtitle_files[0]))
        if clean_text:
            with open(transcript_file, "w", encoding="utf-8") as f:
                f.write(f"# 视频文稿/字幕: {raw_title}\n")
                f.write(f"# 来源: {args.url}\n")
                f.write(f"# 时长: {duration}秒 | 作者: {uploader}\n\n")
                f.write(clean_text)
            print(f"[+] 已清洗并生成文稿: {transcript_file}")
            has_subtitles = True

    # 视频/音频下载处理
    media_file = None
    audio_file = None
    if not args.skip_download:
        print(f"[*] 正在下载媒体文件...")
        out_media_template = os.path.join(output_dir, f"{safe_title}.%(ext)s")
        if args.audio_only:
            dl_cmd = [
                yt_dlp_bin,
                "--no-playlist",
                "-x", "--audio-format", "m4a",
            ]
        else:
            dl_cmd = [
                yt_dlp_bin,
                "--no-playlist",
                "-f", args.format,
                "--merge-output-format", "mp4",
            ]
        if effective_cookie_file and os.path.exists(effective_cookie_file):
            dl_cmd.extend(["--cookies", str(effective_cookie_file)])
        dl_cmd.extend([
            "-o", out_media_template,
            args.url
        ])
        dl_res = run_cmd(dl_cmd, check=False)
        if dl_res.returncode == 0:
            # 找到下载好的媒体文件
            for f in Path(output_dir).glob(f"{safe_title}.*"):
                if f.suffix.lower() in [".mp4", ".mkv", ".webm"]:
                    media_file = str(f)
                    break
                elif f.suffix.lower() in [".m4a", ".mp3", ".aac"]:
                    audio_file = str(f)
            if media_file:
                print(f"[+] 视频文件下载完成: {media_file}")
                # 若无字幕，自动提取一份极轻量的音频用于 ASR 语音识别
                if not has_subtitles:
                    extracted_audio = os.path.join(output_dir, f"{safe_title}_audio.m4a")
                    if not os.path.exists(extracted_audio):
                        print(f"[*] 无外挂字幕，正在抽取快速音频轨用于语音转写...")
                        ffmpeg_bin = find_ffmpeg()
                        audio_cmd = [
                            ffmpeg_bin, "-y", "-i", media_file,
                            "-vn", "-acodec", "copy",
                            extracted_audio
                        ]
                        subprocess.run(audio_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if os.path.exists(extracted_audio):
                            audio_file = extracted_audio
                            print(f"[+] 音频轨已独立提取: {audio_file}")
            elif audio_file:
                print(f"[+] 音频文件下载完成: {audio_file}")
        else:
            print(f"[!] 媒体下载遇到警告/错误: {dl_res.stderr[:300]}", file=sys.stderr)

    # 长视频分段切片逻辑 (支持视频切片与文稿切片)
    slices_data = None
    if args.slice_minutes > 0:
        slices_data = slice_video_and_transcript(
            output_dir=output_dir,
            safe_title=safe_title,
            raw_title=raw_title,
            duration=duration,
            slice_minutes=args.slice_minutes,
            media_file=media_file,
            clean_blocks=clean_blocks
        )

    result_json = {
        "status": "success",
        "title": raw_title,
        "safe_title": safe_title,
        "uploader": uploader,
        "duration": duration,
        "output_dir": output_dir,
        "info_json": info_json_path,
        "transcript_file": transcript_file if has_subtitles else None,
        "media_file": media_file,
        "audio_file": audio_file,
        "has_subtitles": has_subtitles,
        "chapters_count": len(chapters),
        "slices_manifest": os.path.join(output_dir, "slices", "slices_manifest.json") if slices_data else None,
        "slices_count": slices_data["num_slices"] if slices_data else 0
    }

    print("\n__OUTPUT_JSON__")
    print(json.dumps(result_json, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

