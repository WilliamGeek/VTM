#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py
------
video-to-mindmap 统一工业级命令行控制中枢 (Unified CLI & Doctor)。
提供环境自检与自愈诊断 (doctor)、平台账号免密扫码登录 (login)、
视频元数据与时间戳文稿抓取 (fetch)、突变高熵抽帧 (detect)、
高精度自适应截帧红框批注 (annotate) 与交互式导图编译 (render)。

支持针对人类开发者的友好彩色报告与针对 AI Agent 的标准 --json 机器可读协议。
"""

import os
import sys
import json
import shutil
import platform
import subprocess
import argparse
from pathlib import Path

# 确保能加载 scripts 内部模块
ROOT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ANSI 颜色定义 (兼容 Windows Terminal / Linux / macOS)
USE_COLOR = sys.stdout.isatty() or os.getenv("TERM") is not None
CLR_RESET = "\033[0m" if USE_COLOR else ""
CLR_BOLD = "\033[1m" if USE_COLOR else ""
CLR_GREEN = "\033[32m" if USE_COLOR else ""
CLR_RED = "\033[31m" if USE_COLOR else ""
CLR_YELLOW = "\033[33m" if USE_COLOR else ""
CLR_CYAN = "\033[36m" if USE_COLOR else ""
CLR_GRAY = "\033[90m" if USE_COLOR else ""


# ==============================================================================
# 1. 环境自检自愈引擎 (Doctor Diagnostics & Self-Healing)
# ==============================================================================

class SystemDoctor:
    """环境依赖与健康状况诊断自愈引擎"""

    @classmethod
    def run_diagnostics(cls, auto_fix: bool = False) -> dict:
        results = {
            "status": "HEALTHY",
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "python": {
                "version": platform.python_version(),
                "path": sys.executable,
                "status": "PASS"
            },
            "dependencies": {},
            "python_packages": {},
            "auth_vault": {},
            "remediations": []
        }

        # 1. 校验 Python 版本
        py_major, py_minor = sys.version_info[:2]
        if py_major < 3 or (py_major == 3 and py_minor < 9):
            results["python"]["status"] = "FAIL"
            results["status"] = "DEGRADED"
            results["remediations"].append({
                "component": "python",
                "issue": f"Python 版本过低 ({platform.python_version()})，推荐 Python 3.10+",
                "command": "请升级 Python 至 3.10 或以上版本。"
            })

        # 2. 检查系统外部依赖：ffmpeg
        ffmpeg_res = cls._check_ffmpeg()
        results["dependencies"]["ffmpeg"] = ffmpeg_res
        if ffmpeg_res["status"] == "FAIL":
            results["status"] = "DEGRADED"
            fix_cmd = "winget install Gyan.FFmpeg" if platform.system() == "Windows" else "brew install ffmpeg"
            results["remediations"].append({
                "component": "ffmpeg",
                "issue": "未在系统 PATH 或工具目录找到 ffmpeg 可执行文件",
                "command": fix_cmd
            })

        # 3. 检查系统外部依赖：yt-dlp
        ytdlp_res = cls._check_ytdlp()
        results["dependencies"]["yt-dlp"] = ytdlp_res
        if ytdlp_res["status"] == "FAIL":
            results["status"] = "DEGRADED"
            fix_cmd = "winget install yt-dlp.yt-dlp" if platform.system() == "Windows" else "pip install -U yt-dlp"
            results["remediations"].append({
                "component": "yt-dlp",
                "issue": "未在系统 PATH 中找到最新版 yt-dlp",
                "command": fix_cmd
            })

        # 4. 检查核心 Python 包依赖
        packages = ["PIL", "qrcode"]
        for pkg in packages:
            pkg_res = cls._check_python_package(pkg)
            results["python_packages"][pkg] = pkg_res
            if pkg_res["status"] == "FAIL":
                results["status"] = "DEGRADED"
                results["remediations"].append({
                    "component": pkg,
                    "issue": f"缺少推荐 Python 库: {pkg}",
                    "command": f"{sys.executable} -m pip install -r requirements.txt"
                })

        # 5. 检查多平台 Cookie 仓与登录凭证
        auth_res = cls._check_auth_vault()
        results["auth_vault"] = auth_res
        if auth_res.get("bilibili", {}).get("status") != "PASS":
            results["remediations"].append({
                "component": "bilibili_auth",
                "issue": "未配置有效的 B站 Cookie (可能受限仅能抓取 480P)",
                "command": f"{sys.executable} cli.py login bilibili"
            })

        # 自动修复
        if auto_fix and results["remediations"]:
            cls._apply_auto_fix(results)

        return results

    @classmethod
    def _check_ffmpeg(cls) -> dict:
        candidates = [
            shutil.which("ffmpeg"),
            os.getenv("FFMPEG_BIN"),
            ROOT_DIR / "tools" / "ffmpeg.exe",
            Path(r"F:\yt-dlp\ffmpeg.exe"),
            Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe")
        ]
        found_path = None
        for c in candidates:
            if c and os.path.exists(str(c)):
                found_path = str(c)
                break
        
        if not found_path:
            return {"status": "FAIL", "path": None, "version": None}
        
        try:
            out = subprocess.run([found_path, "-version"], capture_output=True, text=True, timeout=8)
            first_line = out.stdout.splitlines()[0] if out.stdout else "ffmpeg version unknown"
            return {"status": "PASS", "path": found_path, "version": first_line}
        except Exception as e:
            return {"status": "WARN", "path": found_path, "version": f"检测异常: {e}"}

    @classmethod
    def _check_ytdlp(cls) -> dict:
        candidates = [
            shutil.which("yt-dlp"),
            os.getenv("YT_DLP_BIN"),
            ROOT_DIR / "tools" / "yt-dlp.exe",
            Path(r"F:\yt-dlp\yt-dlp.exe")
        ]
        found_path = None
        for c in candidates:
            if c and os.path.exists(str(c)):
                found_path = str(c)
                break
        
        if not found_path:
            # 检查是否有 python 模块
            try:
                import yt_dlp
                return {"status": "PASS", "path": "python -m yt_dlp", "version": yt_dlp.version.__version__}
            except ImportError:
                return {"status": "FAIL", "path": None, "version": None}
        
        try:
            out = subprocess.run([found_path, "--version"], capture_output=True, text=True, timeout=8)
            ver = out.stdout.strip() if out.stdout else "unknown"
            return {"status": "PASS", "path": found_path, "version": ver}
        except Exception as e:
            return {"status": "WARN", "path": found_path, "version": f"检测异常: {e}"}

    @classmethod
    def _check_python_package(cls, pkg_name: str) -> dict:
        try:
            if pkg_name == "PIL":
                import PIL
                return {"status": "PASS", "version": getattr(PIL, "__version__", "installed")}
            mod = __import__(pkg_name)
            return {"status": "PASS", "version": getattr(mod, "__version__", "installed")}
        except ImportError:
            return {"status": "FAIL", "version": None}

    @classmethod
    def _check_auth_vault(cls) -> dict:
        try:
            from auth_manager import get_vault_dir, CookieVault
            vault = get_vault_dir()
            bili_cookie = CookieVault.get_cookie_file("bilibili")
            yt_cookie = CookieVault.get_cookie_file("youtube")

            res = {
                "vault_dir": str(vault),
                "bilibili": {
                    "path": str(bili_cookie),
                    "exists": bili_cookie.exists(),
                    "status": "PASS" if (bili_cookie.exists() and bili_cookie.stat().st_size > 50) else "WARN"
                },
                "youtube": {
                    "path": str(yt_cookie),
                    "exists": yt_cookie.exists(),
                    "status": "PASS" if yt_cookie.exists() else "INFO"
                }
            }
            return res
        except Exception as e:
            return {"status": "WARN", "error": str(e)}

    @classmethod
    def _apply_auto_fix(cls, results: dict):
        print(f"\n{CLR_YELLOW}[*] 正在尝试自动修复缺失依赖...{CLR_RESET}")
        for rem in results.get("remediations", []):
            cmd = rem.get("command")
            if cmd and "pip install" in cmd:
                try:
                    print(f"[*] 执行: {cmd}")
                    subprocess.run(cmd, shell=True, check=True)
                except Exception as e:
                    print(f"[!] 自动修复失败: {e}")

    @classmethod
    def print_pretty_report(cls, res: dict):
        print(f"\n{CLR_BOLD}{CLR_CYAN}======================================================{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_CYAN}       video-to-mindmap 环境自检与就绪诊断报告        {CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_CYAN}======================================================{CLR_RESET}\n")

        overall = res.get("status")
        status_color = CLR_GREEN if overall == "HEALTHY" else CLR_YELLOW
        status_icon = "✓ HEALTHY (一切就绪)" if overall == "HEALTHY" else "⚠ DEGRADED (需要完善)"
        print(f"系统环境: {res.get('os')}")
        print(f"总体状态: {status_color}{CLR_BOLD}{status_icon}{CLR_RESET}\n")

        # 1. 核心运行时
        py = res.get("python", {})
        py_icon = f"{CLR_GREEN}[✓]{CLR_RESET}" if py.get("status") == "PASS" else f"{CLR_RED}[✗]{CLR_RESET}"
        print(f"{py_icon} Python 运行环境: {py.get('version')} ({py.get('path')})")

        # 2. 系统可执行程序
        for name, dep in res.get("dependencies", {}).items():
            st = dep.get("status")
            if st == "PASS":
                icon = f"{CLR_GREEN}[✓]{CLR_RESET}"
                extra = f"{CLR_GRAY}({dep.get('path')}){CLR_RESET}"
                print(f"{icon} {name:<10}: {dep.get('version', '就绪')} {extra}")
            elif st == "WARN":
                icon = f"{CLR_YELLOW}[!]{CLR_RESET}"
                print(f"{icon} {name:<10}: {dep.get('version', '异常')}")
            else:
                icon = f"{CLR_RED}[✗]{CLR_RESET}"
                print(f"{icon} {name:<10}: {CLR_RED}未在系统 PATH 中找到！{CLR_RESET}")

        # 3. Python 依赖库
        for name, pkg in res.get("python_packages", {}).items():
            st = pkg.get("status")
            icon = f"{CLR_GREEN}[✓]{CLR_RESET}" if st == "PASS" else f"{CLR_RED}[✗]{CLR_RESET}"
            print(f"{icon} 库 {name:<8}: {pkg.get('version', '未安装')}")

        # 4. 账号与 Cookie 状态
        vault = res.get("auth_vault", {})
        bili = vault.get("bilibili", {})
        if bili.get("status") == "PASS":
            b_icon = f"{CLR_GREEN}[✓]{CLR_RESET}"
            b_text = "已配置有效凭证 (支持高清/会员视频解析)"
        else:
            b_icon = f"{CLR_YELLOW}[!]{CLR_RESET}"
            b_text = "未配置或文件过小 (仅支持公开低码率预览)"
        print(f"{b_icon} B站账号鉴权: {b_text}")

        # 5. 修复与建议清单
        rems = res.get("remediations", [])
        if rems:
            print(f"\n{CLR_BOLD}{CLR_YELLOW}【待处理事项与一键修复指引】{CLR_RESET}")
            for idx, rem in enumerate(rems, 1):
                print(f" {idx}. {CLR_BOLD}{rem.get('issue')}{CLR_RESET}")
                print(f"    ↳ 一键修复命令: {CLR_CYAN}{rem.get('command')}{CLR_RESET}")
        else:
            print(f"\n{CLR_GREEN}环境检查通过，所有必需依赖均已就绪。{CLR_RESET}")
        print("")


# ==============================================================================
# 2. 核心子命令调度器 (Subcommands Dispatcher)
# ==============================================================================

def cmd_doctor(args):
    res = SystemDoctor.run_diagnostics(auto_fix=args.fix)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        SystemDoctor.print_pretty_report(res)
    sys.exit(0 if res.get("status") == "HEALTHY" else 1)


def cmd_login(args):
    """快捷启动免密扫码登录"""
    try:
        from auth_manager import interactive_login_loop
        success = interactive_login_loop(args.platform, timeout=args.timeout)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"{CLR_RED}[!] 启动登录失败: {e}{CLR_RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_fetch(args):
    """抓取视频与时间戳文稿"""
    from process_video import main as process_main
    sys.argv = ["process_video.py", args.url]
    if args.output_dir:
        sys.argv.extend(["-o", args.output_dir])
    if args.audio_only:
        sys.argv.append("--audio-only")
    if getattr(args, "skip_download", False):
        sys.argv.append("--skip-download")
    if getattr(args, "slice_minutes", 0):
        sys.argv.extend(["--slice-minutes", str(args.slice_minutes)])
    process_main()


def cmd_detect(args):
    """场景突变自适应抽帧"""
    from detect_keyframes import main as detect_main
    sys.argv = ["detect_keyframes.py", args.video_path]
    if args.max_frames:
        sys.argv.extend(["--max-frames", str(args.max_frames)])
    if args.threshold:
        sys.argv.extend(["--threshold", str(args.threshold)])
    if args.output_dir:
        sys.argv.extend(["-o", args.output_dir])
    detect_main()


def cmd_annotate(args):
    """自适应截帧与高级知识批注 (对标 CleanShot X / Shottr 工业标准)"""
    from extract_frame import main as extract_main
    sys.argv = ["extract_frame.py", args.video_path, "-o", args.output]
    if args.timestamp:
        sys.argv.extend(["-t", args.timestamp])
    if getattr(args, "timestamps", None):
        sys.argv.extend(["--timestamps", args.timestamps])
    if args.mode:
        sys.argv.extend(["--mode", args.mode])
    if args.box:
        sys.argv.extend(["--box", args.box])
    if getattr(args, "boxes", None):
        sys.argv.extend(["--boxes", args.boxes])
    if args.label:
        sys.argv.extend(["--label", args.label])
    if getattr(args, "labels", None):
        sys.argv.extend(["--labels", args.labels])
    if args.spotlight:
        sys.argv.append("--spotlight")
    if getattr(args, "steps", None):
        sys.argv.extend(["--steps", args.steps])
    if getattr(args, "zoom", None):
        sys.argv.extend(["--zoom", args.zoom])
    if getattr(args, "zoom_scale", None):
        sys.argv.extend(["--zoom-scale", str(args.zoom_scale)])
    if getattr(args, "zoom_pos", None):
        sys.argv.extend(["--zoom-pos", args.zoom_pos])
    if getattr(args, "highlight", None):
        sys.argv.extend(["--highlight", args.highlight])
    if getattr(args, "highlight_color", None):
        sys.argv.extend(["--highlight-color", args.highlight_color])
    if getattr(args, "arrow", None):
        sys.argv.extend(["--arrow", args.arrow])
    if getattr(args, "blur", None):
        sys.argv.extend(["--blur", args.blur])
    if getattr(args, "pixelate", None):
        sys.argv.extend(["--pixelate", args.pixelate])
    if getattr(args, "crop", None):
        sys.argv.extend(["--crop", args.crop])
    if getattr(args, "crop_focus", False):
        sys.argv.append("--crop-focus")
    if getattr(args, "strip_subtitles", False):
        sys.argv.append("--strip-subtitles")
    if getattr(args, "strip_header", False):
        sys.argv.append("--strip-header")
    extract_main()


def cmd_render(args):
    """Markdown 导图编译为工业级交互式 HTML 视界"""
    from generate_html import main as render_main
    sys.argv = ["generate_html.py", args.md_file]
    if args.output:
        sys.argv.extend(["-o", args.output])
    if args.title:
        sys.argv.extend(["-t", args.title])
    if args.embed_images:
        sys.argv.append("--embed-images")
    render_main()


def cmd_pipeline(args):
    """端到端全流程极速启动流水线"""
    print(f"{CLR_BOLD}{CLR_CYAN}[*] 启动 video-to-mindmap 自动化全流程流水线...{CLR_RESET}")
    # 1. 预检环境 (纯文本跳过下载模式下不强求 ffmpeg)
    if not getattr(args, "skip_download", False):
        diag = SystemDoctor.run_diagnostics()
        if diag["dependencies"].get("ffmpeg", {}).get("status") == "FAIL":
            print(f"{CLR_RED}[!] 错误: ffmpeg 未安装，流水线无法处理音视频！请先运行 `python cli.py doctor` 查看修复方案。{CLR_RESET}", file=sys.stderr)
            sys.exit(1)

    # 2. 抓取视频与字幕
    from process_video import main as process_main
    print(f"\n{CLR_BOLD}[第 1 步] 解析视频元数据与时间戳文稿...{CLR_RESET}")
    sys.argv = ["process_video.py", args.url]
    if getattr(args, "skip_download", False):
        sys.argv.append("--skip-download")
    if getattr(args, "slice_minutes", 0):
        sys.argv.extend(["--slice-minutes", str(args.slice_minutes)])
    process_main()


# ==============================================================================
# 3. 主入口命令行解析定义
# ==============================================================================

def build_parser():
    parser = argparse.ArgumentParser(
        prog="video-mindmap",
        description="video-to-mindmap: 视频转思维导图与多模态知识提取工具",
        epilog="示例: python cli.py doctor | python cli.py login bilibili | python cli.py render mindmap.md --embed-images"
    )
    subparsers = parser.add_subparsers(dest="action", help="选择执行的操作")

    # 1. doctor: 环境体检
    p_doc = subparsers.add_parser("doctor", help="环境依赖、运行时与账号凭证体检诊断")
    p_doc.add_argument("--json", action="store_true", help="输出机器可读的标准 JSON 数据格式 (适合 Agent 调用)")
    p_doc.add_argument("--fix", action="store_true", help="尝试自动执行可执行的修复命令")

    # 2. login: 平台扫码登录
    p_log = subparsers.add_parser("login", help="多平台 (B站/YouTube) 账号免密扫码自愈登录")
    p_log.add_argument("platform", nargs="?", default="bilibili", choices=["bilibili", "youtube", "douyin"], help="平台名称 (默认 bilibili)")
    p_log.add_argument("--timeout", type=int, default=180, help="扫码等待超时时间 (秒)")

    # 3. fetch: 抓取与清洗
    p_fet = subparsers.add_parser("fetch", help="抓取视频音视频流与字幕文稿，创建项目专属目录")
    p_fet.add_argument("url", help="视频链接或分享短链")
    p_fet.add_argument("-o", "--output-dir", help="自定义输出目录路径")
    p_fet.add_argument("--audio-only", action="store_true", help="仅下载纯音频轨与字幕")
    p_fet.add_argument("--skip-download", action="store_true", help="仅提取字幕和元数据，不下载视频 (纯文本极速模式)")
    p_fet.add_argument("--slice-minutes", type=int, default=0, help="长视频自动分段切片阈值 (分钟，如 45 或 60，0 表示不切片)")

    # 4. detect: 镜头突变高熵帧检测
    p_det = subparsers.add_parser("detect", help="基于场景突变率自适应提炼候选关键帧")
    p_det.add_argument("video_path", help="视频文件路径 (.mp4)")
    p_det.add_argument("-m", "--max-frames", type=int, default=20, help="最大抽帧数量 (默认 20)")
    p_det.add_argument("-t", "--threshold", type=float, default=0.35, help="镜头突变阈值 (默认 0.35)")
    p_det.add_argument("-o", "--output-dir", help="输出关键帧目录")

    # 5. annotate: 图像自适应批注
    p_ann = subparsers.add_parser("annotate", help="截取关键帧并绘制顶级知识批注 (双层对比框/步骤球/放大镜/荧光笔/箭头/脱敏)")
    p_ann.add_argument("video_path", help="视频文件路径")
    p_ann.add_argument("-t", "--timestamp", help="截帧时间戳 (如 '03:15' 或秒数)")
    p_ann.add_argument("--timestamps", help="多时间戳胶卷拼接，逗号分隔 (如 '01:00,02:00')")
    p_ann.add_argument("-o", "--output", required=True, help="输出图片文件路径")
    p_ann.add_argument("-m", "--mode", default="auto", choices=["pure", "focus", "dual", "filmstrip", "auto"], help="视觉呈现模式")
    p_ann.add_argument("-b", "--box", help="单矩形框坐标 'x1,y1,x2,y2' (支持 0~1 比例或像素)")
    p_ann.add_argument("--boxes", help="多矩形框坐标 (分号分隔)")
    p_ann.add_argument("-l", "--label", help="角标说明文字")
    p_ann.add_argument("--labels", help="多角标文字 (分号分隔)")
    p_ann.add_argument("--spotlight", action="store_true", help="启用焦点聚光灯暗角高亮")
    p_ann.add_argument("--steps", help="立体递增步骤序号球 'x1,y1[:标签];x2,y2[:标签]'")
    p_ann.add_argument("--zoom", help="画中画局部放大镜 'cx,cy,r'")
    p_ann.add_argument("--zoom-scale", type=float, default=2.5, help="放大镜倍率 (默认 2.5)")
    p_ann.add_argument("--zoom-pos", help="放大镜视窗目标中心 'tx,ty'")
    p_ann.add_argument("--highlight", help="真实荧光笔高亮区域 'x1,y1,x2,y2;...'")
    p_ann.add_argument("--highlight-color", choices=["yellow", "green", "cyan", "pink"], default="yellow", help="荧光笔色彩")
    p_ann.add_argument("--arrow", help="双层对比定向流程箭头 'x1,y1->x2,y2[:标签];...'")
    p_ann.add_argument("--blur", help="局部高斯平滑模糊脱敏 'x1,y1,x2,y2;...'")
    p_ann.add_argument("--pixelate", help="局部网格马赛克脱敏 'x1,y1,x2,y2;...'")
    p_ann.add_argument("--crop", help="显式剪聚焦 ROI 区域 'x1,y1,x2,y2'")
    p_ann.add_argument("--crop-focus", action="store_true", help="自动以目标框为核心进行主体智能剪聚焦")
    p_ann.add_argument("--strip-subtitles", action="store_true", help="强制剔除底部字幕/控制栏危险区域")
    p_ann.add_argument("--strip-header", action="store_true", help="剔除顶部浏览器栏与状态栏")

    # 6. render: 编译交互导图
    p_ren = subparsers.add_parser("render", help="将 Markdown 导图编译为工业级自包含 HTML 视界")
    p_ren.add_argument("md_file", help="输入思维导图 Markdown 路径")
    p_ren.add_argument("-o", "--output", help="输出 HTML 路径")
    p_ren.add_argument("-t", "--title", help="导图主标题")
    p_ren.add_argument("--embed-images", action="store_true", help="将本地相对图片转为 Base64 内嵌为独立单文件")

    # 7. pipeline: 端到端快速启动
    p_pip = subparsers.add_parser("pipeline", help="端到端自动化分析流水线入口")
    p_pip.add_argument("url", help="视频链接")
    p_pip.add_argument("--skip-download", action="store_true", help="仅提取字幕和元数据，不下载视频 (纯文本极速模式)")
    p_pip.add_argument("--slice-minutes", type=int, default=0, help="长视频自动分段切片阈值 (分钟，如 45 或 60，0 表示不切片)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.action:
        # 默认无参数时直接执行 doctor 诊断
        print(f"{CLR_BOLD}未指定子命令，默认启动环境诊断 (输入 `python cli.py -h` 查看完整指令){CLR_RESET}")
        cmd_doctor(argparse.Namespace(json=False, fix=False))
        return

    dispatch = {
        "doctor": cmd_doctor,
        "login": cmd_login,
        "fetch": cmd_fetch,
        "detect": cmd_detect,
        "annotate": cmd_annotate,
        "render": cmd_render,
        "pipeline": cmd_pipeline
    }

    handler = dispatch.get(args.action)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
