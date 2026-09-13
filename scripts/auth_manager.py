#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_manager.py
----------------
多平台（B站、YouTube、抖音等）Cookie 凭证管理、健康检查、自动保活与自愈交互调度器。
统一归档管理至 F:\\yt-dlp\\cookies\\ 目录，避免与日常浏览器抢占数据库锁。
"""

import os
import sys
import re
import json
import time
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_vault_dir():
    """获取 Cookie 统一存储仓库目录"""
    env_dir = os.getenv("YT_DLP_COOKIES_DIR")
    if env_dir and os.path.exists(env_dir):
        return Path(env_dir)
    
    # 优先使用本地 F:\yt-dlp\cookies，若无则使用 video-to-mindmap 本地 cookies
    candidates = [
        Path(r"F:\yt-dlp\cookies"),
        Path(__file__).resolve().parent.parent / "cookies",
        Path.cwd() / "cookies"
    ]
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            return c
        except Exception:
            continue
    
    fallback = Path.home() / ".config" / "yt-dlp" / "cookies"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback

class PlatformRouter:
    """多平台 URL 路由与规范化解析"""
    
    @staticmethod
    def resolve(url_or_domain: str):
        """
        输入 URL，解析所属平台、规范化后的目标 URL 以及默认根域名。
        同时自动解析并展开短链接（如 b23.tv / youtu.be）。
        返回: (platform_name, canonical_url, cookie_domain)
        """
        raw = url_or_domain.strip()
        
        # 1. Bilibili 短链处理 (b23.tv)
        if "b23.tv" in raw:
            canonical = PlatformRouter._resolve_b23_shortlink(raw)
            return "bilibili", canonical, ".bilibili.com"
        
        # 2. Bilibili 正常链接
        if "bilibili.com" in raw:
            canonical = PlatformRouter._clean_bilibili_url(raw)
            return "bilibili", canonical, ".bilibili.com"
        
        # 3. YouTube (youtube.com / youtu.be)
        if "youtube.com" in raw or "youtu.be" in raw:
            canonical = PlatformRouter._clean_youtube_url(raw)
            return "youtube", canonical, ".youtube.com"
        
        # 4. 抖音 / TikTok
        if "douyin.com" in raw or "iesdouyin.com" in raw:
            return "douyin", raw, ".douyin.com"
        if "tiktok.com" in raw:
            return "tiktok", raw, ".tiktok.com"
            
        # 5. 快手 / 小红书 / 知乎
        if "kuaishou.com" in raw:
            return "kuaishou", raw, ".kuaishou.com"
        if "xiaohongshu.com" in raw or "xhslink.com" in raw:
            return "xiaohongshu", raw, ".xiaohongshu.com"
            
        # 6. 通用平台提取 domain
        try:
            parsed = urllib.parse.urlparse(raw)
            domain = parsed.netloc.split(":")[0]
            if domain:
                clean_name = re.sub(r'^(www|m)\.', '', domain).split('.')[0]
                return clean_name, raw, f".{domain}"
        except Exception:
            pass
            
        return "generic", raw, ".generic"

    @staticmethod
    def _resolve_b23_shortlink(short_url):
        """解析 b23.tv 短链并清理无用跟踪参数，保留核心 p= 分P参数"""
        try:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            opener = urllib.request.build_opener(NoRedirect)
            req = urllib.request.Request(short_url, headers={'User-Agent': USER_AGENT})
            try:
                opener.open(req)
                return short_url
            except urllib.error.HTTPError as e:
                location = e.headers.get('Location')
                if location:
                    return PlatformRouter._clean_bilibili_url(location)
        except Exception as err:
            print(f"[!] 解析 b23.tv 短链异常: {err}", file=sys.stderr)
        return short_url

    @staticmethod
    def _clean_bilibili_url(url):
        """清理 B站 移动端分享产生的超长追踪参数，仅保留 BV 与 p 参数"""
        try:
            parsed = urllib.parse.urlparse(url)
            # 提取 BV 号
            bv_match = re.search(r'BV[a-zA-Z0-9]+', parsed.path)
            if bv_match:
                bv_id = bv_match.group(0)
                # 检查 query 中是否有 p= 参数
                query_dict = urllib.parse.parse_qs(parsed.query)
                p_val = query_dict.get('p', [None])[0]
                if p_val:
                    return f"https://www.bilibili.com/video/{bv_id}?p={p_val}"
                return f"https://www.bilibili.com/video/{bv_id}"
        except Exception:
            pass
        return url

    @staticmethod
    def _clean_youtube_url(url):
        """规范化 YouTube 链接"""
        try:
            parsed = urllib.parse.urlparse(url)
            if "youtu.be" in parsed.netloc:
                video_id = parsed.path.strip('/')
                return f"https://www.youtube.com/watch?v={video_id}"
            elif "watch" in parsed.path:
                q = urllib.parse.parse_qs(parsed.query)
                v = q.get('v')
                if v:
                    return f"https://www.youtube.com/watch?v={v[0]}"
        except Exception:
            pass
        return url

class CookieVault:
    """Netscape 格式 Cookie 统一存储与序列化"""
    
    @staticmethod
    def get_cookie_file(platform: str) -> Path:
        vault = get_vault_dir()
        return vault / f"{platform}_cookies.txt"

    @staticmethod
    def get_meta_file(platform: str) -> Path:
        vault = get_vault_dir()
        return vault / f"{platform}_cookies.json"

    @staticmethod
    def parse_cookie_file(cookie_file: Path) -> dict:
        """从 Netscape cookies.txt 中解析键值对"""
        cookies = {}
        if not cookie_file.exists():
            return cookies
        try:
            with open(cookie_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6]
        except Exception as e:
            print(f"[!] 读取 Cookie 文件失败: {e}", file=sys.stderr)
        return cookies

    @staticmethod
    def write_netscape_cookies(platform: str, domain: str, cookies_dict: dict, meta: dict = None):
        """将 Cookie 字典保存为标准 Netscape 格式文本"""
        cookie_file = CookieVault.get_cookie_file(platform)
        lines = [
            "# Netscape HTTP Cookie File",
            "# Automatically generated by video-to-mindmap auth_manager",
            f"# Platform: {platform} | Domain: {domain}",
            ""
        ]
        expire_time = int(time.time()) + 180 * 86400  # 默认180天
        for k, v in cookies_dict.items():
            if not k or v is None:
                continue
            # domain, flag, path, secure, expiration, name, value
            lines.append(f"{domain}\tTRUE\t/\tTRUE\t{expire_time}\t{k}\t{v}")
        
        with open(cookie_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        
        if meta:
            meta_file = CookieVault.get_meta_file(platform)
            meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
        return cookie_file

    @staticmethod
    def import_raw_string(platform: str, raw_str: str, domain: str = None):
        """解析用户复制的 raw cookie header 字符串（如 a=1; b=2）并保存"""
        if not domain:
            _, _, domain = PlatformRouter.resolve(f"https://{platform}.com")
        
        cookie_pairs = {}
        for item in raw_str.split(";"):
            item = item.strip()
            if not item:
                continue
            if "=" in item:
                k, v = item.split("=", 1)
                cookie_pairs[k.strip()] = v.strip()
        
        if not cookie_pairs:
            raise ValueError("未从输入内容中解析出有效 Cookie 键值对！")
            
        return CookieVault.write_netscape_cookies(platform, domain, cookie_pairs)

class BilibiliAuthHandler:
    """Bilibili 专属鉴权、自动轮换保活与免密扫码自愈"""

    @staticmethod
    def check_auth(cookie_file: Path):
        """
        通过官方接口验证 Cookie 是否有效并获取当前登录用户信息
        调用 /x/web-interface/nav
        """
        if not cookie_file.exists():
            return {"valid": False, "reason": "Cookie 文件不存在"}
            
        cookies = CookieVault.parse_cookie_file(cookie_file)
        sessdata = cookies.get("SESSDATA")
        if not sessdata:
            return {"valid": False, "reason": "Cookie 中缺少 SESSDATA 会话凭证"}

        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        req = urllib.request.Request(
            "https://api.bilibili.com/x/web-interface/nav",
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://www.bilibili.com/",
                "Cookie": cookie_header
            }
        )
        for retry in range(2):
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                        d = data["data"]
                        return {
                            "valid": True,
                            "uname": d.get("uname"),
                            "mid": d.get("mid"),
                            "level": d.get("level_info", {}).get("current_level"),
                            "vip": d.get("vipStatus", 0) == 1,
                            "expires_info": "存活"
                        }
                    else:
                        return {
                            "valid": False,
                            "code": data.get("code"),
                            "reason": data.get("message", "登录态已失效")
                        }
            except Exception as e:
                if retry == 0:
                    time.sleep(1)
                    continue
                # 若网络临时抖动但本地已存有效 SESSDATA 凭据，允许放行
                if sessdata and len(sessdata) > 10:
                    return {
                        "valid": True,
                        "uname": "本地已存凭据 (探测超时放行)",
                        "warning": f"网络探测异常: {e}"
                    }
                return {"valid": False, "reason": f"网络探测异常: {e}"}

    @staticmethod
    def start_qr_login(save_qr_path: str = None):
        """生成 B站 扫码登录二维码"""
        req = urllib.request.Request(
            "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") != 0:
                raise RuntimeError(f"生成二维码失败: {res.get('message')}")
            
            data = res["data"]
            url = data["url"]
            qrcode_key = data["qrcode_key"]

        # 生成图片或终端显示
        if not save_qr_path:
            save_qr_path = str(get_vault_dir() / "bilibili_login_qr.png")
            
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(save_qr_path)
            has_image = True
        except Exception as e:
            has_image = False
            print(f"[!] 生成本地二维码图片失败 (可直接使用 URL): {e}", file=sys.stderr)

        return {
            "qrcode_key": qrcode_key,
            "url": url,
            "qr_image": save_qr_path if has_image else None
        }

    @staticmethod
    def poll_qr_login(qrcode_key: str):
        """
        轮询二维码扫码状态
        返回: (status_code, message, cookies_dict)
        0: 成功
        86101: 未扫码
        86090: 已扫码未确认
        86038: 二维码失效
        """
        poll_url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}"
        req = urllib.request.Request(poll_url, headers={"User-Agent": USER_AGENT})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                # 捕获 Set-Cookie
                headers = resp.headers
                body = resp.read().decode("utf-8")
                res = json.loads(body)
                code = res.get("data", {}).get("code", -1)
                msg = res.get("data", {}).get("message", "")
                
                if code == 0:
                    cookies = {}
                    # 从 Set-Cookie 响应头中解析登录凭证
                    raw_cookies = headers.get_all("Set-Cookie") or []
                    for sc in raw_cookies:
                        item = sc.split(";")[0]
                        if "=" in item:
                            k, v = item.split("=", 1)
                            cookies[k.strip()] = v.strip()
                    
                    # 补全可能缺失的指纹
                    if "buvid3" not in cookies:
                        try:
                            spi_req = urllib.request.Request("https://api.bilibili.com/x/frontend/finger/spi", headers={"User-Agent": USER_AGENT})
                            with urllib.request.urlopen(spi_req, timeout=5) as spi_res:
                                spi_data = json.loads(spi_res.read().decode("utf-8")).get("data", {})
                                cookies["buvid3"] = spi_data.get("b_3", "")
                                cookies["buvid4"] = spi_data.get("b_4", "")
                        except Exception:
                            pass
                            
                    refresh_token = res.get("data", {}).get("refresh_token", "")
                    return 0, "登录成功", cookies, refresh_token
                
                return code, msg, {}, ""
        except Exception as e:
            return -1, f"网络重试中 ({e})", {}, ""

class YouTubeAuthHandler:
    """YouTube 凭证检查"""
    @staticmethod
    def check_auth(cookie_file: Path):
        if not cookie_file.exists():
            return {"valid": False, "reason": "Cookie 文件不存在"}
        cookies = CookieVault.parse_cookie_file(cookie_file)
        if "LOGIN_INFO" in cookies or "SAPISID" in cookies or "SID" in cookies:
            return {"valid": True, "uname": "YouTube Account (Cookie Verified)"}
        return {"valid": False, "reason": "Cookie 中缺少 YouTube 关键认证字段 (LOGIN_INFO / SID)"}

class GenericAuthHandler:
    """通用平台检查"""
    @staticmethod
    def check_auth(cookie_file: Path):
        if not cookie_file.exists():
            return {"valid": False, "reason": "Cookie 文件不存在"}
        cookies = CookieVault.parse_cookie_file(cookie_file)
        if len(cookies) >= 1:
            return {"valid": True, "uname": f"Generic Verified ({len(cookies)} cookies)"}
        return {"valid": False, "reason": "Cookie 文件内容为空"}

def get_handler_for_platform(platform: str):
    if platform == "bilibili":
        return BilibiliAuthHandler
    elif platform == "youtube":
        return YouTubeAuthHandler
    else:
        return GenericAuthHandler

def ensure_authenticated(url_or_domain: str):
    """
    通用鉴权入口：检查指定 URL 所属平台的 Cookie 状态
    返回结构化字典：
    {
        "status": "OK" | "AUTH_REQUIRED",
        "platform": "bilibili",
        "canonical_url": "...",
        "cookie_file": "...",
        "user_info": {...},
        "reason": "..."
    }
    """
    platform, canonical_url, domain = PlatformRouter.resolve(url_or_domain)
    cookie_file = CookieVault.get_cookie_file(platform)
    handler = get_handler_for_platform(platform)
    
    auth_result = handler.check_auth(cookie_file)
    if auth_result.get("valid"):
        return {
            "status": "OK",
            "platform": platform,
            "canonical_url": canonical_url,
            "cookie_file": str(cookie_file),
            "user_info": auth_result
        }
    else:
        return {
            "status": "AUTH_REQUIRED",
            "platform": platform,
            "canonical_url": canonical_url,
            "cookie_file": str(cookie_file),
            "reason": auth_result.get("reason", "未登录或登录凭据已失效"),
            "domain": domain
        }

def interactive_login_loop(platform: str, timeout_seconds: int = 600, max_retries: int = 5):
    """
    针对支持扫码的平台执行自动化等待与自愈循环（支持过期自动续期重绘）
    """
    if platform != "bilibili":
        print(f"[*] 平台 [{platform}] 不支持免密扫码登录 (官方未提供公开免密登录 API)。")
        print(f"[*] 请在浏览器中登录后，通过以下方式导入凭证：")
        print(f"    - 方法 1 (推荐): 按 F12 打开网络面板刷新，复制请求标头中的 Cookie 字符串，运行:")
        print(f"      `python scripts/auth_manager.py import-cookie {platform} --cookie-str \"<Cookie内容>\"`")
        print(f"    - 方法 2: 使用扩展导出 Netscape 格式 cookies.txt，放入 F:\\yt-dlp\\cookies\\{platform}_cookies.txt 或运行:")
        print(f"      `python scripts/auth_manager.py import-file {platform} --file \"<cookies.txt路径>\"`")
        return False
        
    start_time = time.time()
    for attempt in range(1, max_retries + 1):
        print(f"[*] 正在为平台 [{platform}] 生成第 {attempt}/{max_retries} 次官方扫码凭据...")
        qr_data = BilibiliAuthHandler.start_qr_login()
        qrcode_key = qr_data["qrcode_key"]
        login_url = qr_data["url"]
        qr_img = qr_data.get("qr_image")

        print("\n" + "="*60)
        print(f"【B站 手机客户端扫码登录 (第 {attempt} 次)】")
        if qr_img:
            print(f" 二维码图片已生成: file:///{qr_img}")
        print(f" 扫码链接: {login_url}")
        print(" 请使用 哔哩哔哩 手机客户端【扫一扫】进行确认登录")
        print("="*60 + "\n", flush=True)

        last_msg = ""
        while time.time() - start_time < timeout_seconds:
            code, msg, cookies, refresh_token = BilibiliAuthHandler.poll_qr_login(qrcode_key)
            if code == 0:
                # 登录成功，写入 vault
                meta = {"refresh_token": refresh_token}
                saved_path = CookieVault.write_netscape_cookies("bilibili", ".bilibili.com", cookies, meta)
                print(f"\n[√] 扫码登录成功！凭证已标准化固化至: {saved_path}", flush=True)
                return True
            elif code == 86038:
                print(f"\n[*] 当前二维码已到期，正在自动无缝刷新生成新二维码...", flush=True)
                break  # 跳出当前内层循环，进入下一次 attempt
                
            if msg != last_msg:
                print(f"[*] 当前状态: {msg} (等待确认中...)", flush=True)
                last_msg = msg
                
            time.sleep(2)
            
        if time.time() - start_time >= timeout_seconds:
            break
            
    print("\n[!] 扫码登录整体超时！", flush=True)
    return False

def main():
    parser = argparse.ArgumentParser(description="多平台 Cookie 凭据管理与鉴权调度器")
    subparsers = parser.add_subparsers(dest="action", help="执行动作")

    # 1. 检查鉴权状态
    check_parser = subparsers.add_parser("check", help="检查指定 URL 或平台的鉴权状态")
    check_parser.add_argument("target", help="视频 URL 或平台标识 (如 bilibili, youtube, https://b23.tv/xxx)")

    # 2. 规范化 URL (展开短链)
    resolve_parser = subparsers.add_parser("resolve", help="解析并规范化视频 URL")
    resolve_parser.add_argument("url", help="原始视频链接")

    # 3. 扫码登录 (B站等)
    login_parser = subparsers.add_parser("login-qr", help="启动二维码免密扫码登录")
    login_parser.add_argument("platform", default="bilibili", nargs="?", help="平台名称 (默认 bilibili)")
    login_parser.add_argument("--timeout", type=int, default=180, help="轮询超时时间 (秒)")

    # 4. 导入原始 Cookie 字符串
    import_str_parser = subparsers.add_parser("import-cookie", help="粘贴 Raw Cookie 字符串并转换为标准 Netscape 格式")
    import_str_parser.add_argument("platform", help="平台名称 (如 bilibili, youtube, douyin)")
    import_str_parser.add_argument("--cookie-str", required=True, help="原始 Cookie 字符串 (key=value; ...)")
    import_str_parser.add_argument("--domain", default=None, help="指定根域名 (可选)")

    # 5. 导入已有 Cookie 文件
    import_file_parser = subparsers.add_parser("import-file", help="导入外部 Netscape cookies.txt 文件")
    import_file_parser.add_argument("platform", help="平台名称")
    import_file_parser.add_argument("--file", required=True, help="现有 Cookie 文件路径")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    if args.action == "resolve":
        p, canon, d = PlatformRouter.resolve(args.url)
        print(json.dumps({"platform": p, "canonical_url": canon, "domain": d}, ensure_ascii=False, indent=2))

    elif args.action == "check":
        res = ensure_authenticated(args.target)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if res["status"] != "OK":
            sys.exit(2)  # 特殊退出码表示需要认证

    elif args.action == "login-qr":
        success = interactive_login_loop(args.platform, args.timeout)
        sys.exit(0 if success else 1)

    elif args.action == "import-cookie":
        saved = CookieVault.import_raw_string(args.platform, args.cookie_str, args.domain)
        print(f"[√] Cookie 已成功导入至: {saved}")

    elif args.action == "import-file":
        src = Path(args.file)
        if not src.exists():
            print(f"[!] 源文件不存在: {src}", file=sys.stderr)
            sys.exit(1)
        dest = CookieVault.get_cookie_file(args.platform)
        import shutil
        shutil.copyfile(src, dest)
        print(f"[√] 外部 Cookie 文件已成功归档至: {dest}")

if __name__ == "__main__":
    main()
