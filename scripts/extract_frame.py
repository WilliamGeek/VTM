#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_frame.py
----------------
视频关键帧精准截取与多场景自适应高级知识批注工具。
对标 CleanShot X、Shottr、Snipaste 顶级工业级批注标准。

支持的核心视觉呈现模式与顶级图元：
1. 模式 0 pure (零标注客观纯景): 智能去黑边，保持系统全景与架构拓扑的客观平权；
2. 模式 1 focus (微观局部焦点): 极细双层对比框 + 智能避让角标 + 可选聚光灯暗角 (spotlight)；
3. 模式 2 dual (双向平权对比): 对称多区域双框/双色批注 (冷青蓝 vs 暖珊瑚红 vs 暖橙)；
4. 模式 3 filmstrip (时序胶卷条带): 跨时间戳多帧水平等高拼接 + 胶卷序列角标；
5. 顶级图元扩展 (可独立或正交组合)：
   - steps: 自动递增立体步骤序号球 (① ② ③) + 自适应药丸胶囊文本 (对标 CleanShot X)；
   - zoom: 局部画中画放大镜 (Lanczos 超分放大 + 柔和投影 + 准星雷达引导虚线)；
   - highlight: 真实光学质感荧光笔半透明涂抹 (Multiply 正片叠底效果)；
   - arrow: 几何双层对比定向流程箭头 (带定位锚点与中央说明徽章)；
   - blur / pixelate: 隐私敏感信息局部高斯平滑模糊与马赛克脱敏；
6. 模式 auto: 根据传入参数智能推导最优视觉呈现策略。
"""

import os
import sys
import math
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
    """查找可用的 ffmpeg 可执行程序"""
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
        "请确保 ffmpeg 已安装并加入 PATH，或设置环境变量 FFMPEG_BIN。\n"
        "安装提示: Windows 执行 'winget install Gyan.FFmpeg'，macOS 执行 'brew install ffmpeg'"
    )


def parse_timestamp_to_seconds(ts_str):
    """将时间戳 (01:23:45, 12:34, 或 123.5) 转换为浮点秒数"""
    ts_str = str(ts_str).strip()
    parts = ts_str.split(':')
    try:
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        pass
    raise ValueError(f"无法解析时间戳格式: {ts_str}，请使用 MM:SS 或 HH:MM:SS 格式")


def extract_raw_frame(video_path, timestamp_sec, output_img_path, ffmpeg_bin="ffmpeg"):
    """使用 ffmpeg 截取指定时间戳的高清帧"""
    os.makedirs(os.path.dirname(os.path.abspath(output_img_path)), exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss", str(timestamp_sec),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_img_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg 截帧失败 (code {res.returncode}):\n{res.stderr}")
    if not os.path.exists(output_img_path):
        raise FileNotFoundError(f"截帧未生成文件: {output_img_path}")
    return output_img_path


def trim_black_borders(img, tolerance=15):
    """自动裁切图片边缘的纯黑/近黑边框"""
    from PIL import ImageChops, Image
    bg = Image.new(img.mode, img.size, (0, 0, 0) if img.mode == 'RGB' else 0)
    diff = ImageChops.difference(img, bg)
    diff = ImageChops.add(diff, diff, 2.0, -tolerance)
    bbox = diff.getbbox()
    if bbox:
        # 预留 2px 安全内边距
        w, h = img.size
        x1, y1, x2, y2 = bbox
        if x2 - x1 > 50 and y2 - y1 > 50:
            return img.crop((x1, y1, x2, y2))
    return img


# ==============================================================================
# 坐标与数据解析器 (全线原生支持 0.0~1.0 比例 与 绝对像素)
# ==============================================================================

def parse_box_str(box_str, img_width, img_height):
    """
    解析单个矩形框坐标: x1,y1,x2,y2
    支持绝对像素或 0~1 浮点比例
    """
    parts = [float(p.strip()) for p in box_str.split(',')]
    if len(parts) != 4:
        raise ValueError("矩形框参数必须包含 4 个数值: x1,y1,x2,y2")
    
    if all(0.0 <= p <= 1.0 for p in parts):
        x1 = int(parts[0] * img_width)
        y1 = int(parts[1] * img_height)
        x2 = int(parts[2] * img_width)
        y2 = int(parts[3] * img_height)
    else:
        x1, y1, x2, y2 = [int(p) for p in parts]
    
    x1 = max(0, min(x1, img_width - 1))
    y1 = max(0, min(y1, img_height - 1))
    x2 = max(x1 + 5, min(x2, img_width))
    y2 = max(y1 + 5, min(y2, img_height))
    return (x1, y1, x2, y2)


def parse_point_str(pt_str, img_width, img_height):
    """解析单点坐标: x,y"""
    parts = [float(p.strip()) for p in pt_str.split(',')]
    if len(parts) != 2:
        raise ValueError(f"坐标点格式无效: {pt_str}，需为 'x,y'")
    if 0.0 <= parts[0] <= 1.0 and 0.0 <= parts[1] <= 1.0:
        px = int(parts[0] * img_width)
        py = int(parts[1] * img_height)
    else:
        px = int(parts[0])
        py = int(parts[1])
    return (max(0, min(px, img_width - 1)), max(0, min(py, img_height - 1)))


def parse_steps_str(steps_str, img_width, img_height):
    """
    解析步骤序列: 'x1,y1[:标签];x2,y2[:标签]'
    """
    results = []
    items = [s.strip() for s in steps_str.split(';') if s.strip()]
    for idx, item in enumerate(items):
        label = None
        if ':' in item:
            coord_str, label = item.split(':', 1)
            coord_str = coord_str.strip()
            label = label.strip()
        else:
            coord_str = item
        px, py = parse_point_str(coord_str, img_width, img_height)
        results.append({
            "x": px,
            "y": py,
            "num": idx + 1,
            "label": label
        })
    return results


def parse_zoom_str(zoom_str, img_width, img_height):
    """
    解析放大镜中心与半径: 'cx,cy,r' 或 'cx,cy'
    """
    parts = [float(p.strip()) for p in zoom_str.split(',')]
    if len(parts) < 2:
        raise ValueError("放大镜参数必须至少提供 'cx,cy'")
    
    if 0.0 <= parts[0] <= 1.0 and 0.0 <= parts[1] <= 1.0:
        cx = int(parts[0] * img_width)
        cy = int(parts[1] * img_height)
    else:
        cx = int(parts[0])
        cy = int(parts[1])

    if len(parts) >= 3:
        raw_r = parts[2]
        r = int(raw_r * min(img_width, img_height)) if 0.0 < raw_r <= 1.0 else int(raw_r)
    else:
        r = int(min(img_width, img_height) * 0.08)

    r = max(20, min(r, int(min(img_width, img_height) * 0.35)))
    return {"cx": cx, "cy": cy, "r": r}


def parse_arrow_str(arrow_str, img_width, img_height):
    """
    解析箭头参数: 'x1,y1->x2,y2[:标签];...'
    """
    results = []
    items = [a.strip() for a in arrow_str.split(';') if a.strip()]
    for item in items:
        label = None
        if ':' in item:
            coords_part, label = item.split(':', 1)
            coords_part = coords_part.strip()
            label = label.strip()
        else:
            coords_part = item

        if '->' not in coords_part:
            continue
        p1_str, p2_str = coords_part.split('->', 1)
        p1 = parse_point_str(p1_str.strip(), img_width, img_height)
        p2 = parse_point_str(p2_str.strip(), img_width, img_height)
        results.append({"from": p1, "to": p2, "label": label})
    return results


def parse_regions_str(regions_str, img_width, img_height):
    """
    解析多个区域: 'x1,y1,x2,y2;...'
    """
    results = []
    items = [r.strip() for r in regions_str.split(';') if r.strip()]
    for item in items:
        results.append(parse_box_str(item, img_width, img_height))
    return results


def get_preferred_font(size):
    """获取清晰的中文字体"""
    from PIL import ImageFont
    font_candidates = [
        "msyhbd.ttc",        # Windows 微软雅黑 Bold
        "msyh.ttc",          # Windows 微软雅黑
        "simhei.ttf",        # Windows 黑体
        "Arial Bold.ttf",
        "Arial.ttf"
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ==============================================================================
# 顶级视觉呈现与图元渲染引擎 (CleanShot X / Shottr 标准)
# ==============================================================================

def render_box_and_tag(draw, box_coords, label, img_size, color=(255, 45, 85)):
    """
    在图像上绘制精致的双层高对比度边框与自适应避让角标
    """
    x1, y1, x2, y2 = box_coords
    w, h = img_size
    border_w = max(2, int(min(w, h) * 0.004))

    # 1. 浅色半透明高亮背底
    draw.rectangle([x1, y1, x2, y2], fill=(color[0], color[1], color[2], 22))

    # 2. 精致双层边框 (外层暗色微影，内层高亮主色)
    outer_dark = (max(0, color[0] - 90), max(0, color[1] - 90), max(0, color[2] - 90), 220)
    main_color = (color[0], color[1], color[2], 255)
    
    # 绘制外暗框
    draw.rectangle([x1 - 1, y1 - 1, x2 + 1, y2 + 1], outline=outer_dark, width=1)
    # 绘制主高亮线
    for i in range(border_w):
        draw.rectangle([x1 + i, y1 + i, x2 - i, y2 - i], outline=main_color)

    # 3. 智能避让角标
    if label:
        font_size = max(13, int(min(w, h) * 0.022))
        font = get_preferred_font(font_size)
        text = f" {label} "
        
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except Exception:
            text_w = len(text) * font_size * 0.6
            text_h = font_size

        # 智能位置决策：如果靠近图片顶部，则标签贴在框内上方或框外下方
        if y1 - text_h - 8 < 0:
            tag_y1 = y1 + border_w + 2
            tag_y2 = tag_y1 + text_h + 4
        else:
            tag_y2 = y1 - 1
            tag_y1 = tag_y2 - text_h - 4

        tag_x1 = max(0, x1)
        tag_x2 = min(w, tag_x1 + text_w + 6)

        # 绘制角标圆润背景与文字
        draw.rounded_rectangle([tag_x1, tag_y1, tag_x2, tag_y2], radius=3, fill=(color[0], color[1], color[2], 245))
        draw.text((tag_x1 + 3, tag_y1 + 1), text, fill=(255, 255, 255, 255), font=font)


def render_step_pins(img, steps_data, img_size):
    """
    绘制对标 CleanShot X / SoM 的立体递增序号球 (Step Pins) 与自适应胶囊药丸文本
    """
    from PIL import Image, ImageDraw
    w, h = img_size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    r = max(14, int(min(w, h) * 0.022))
    font_size = max(12, int(r * 1.15))
    font = get_preferred_font(font_size)
    label_font = get_preferred_font(max(11, int(r * 0.95)))

    colors = [
        (0, 122, 255),    # 科技蓝 (Step 1)
        (255, 149, 0),    # 活力橙 (Step 2)
        (52, 199, 89),    # 薄荷绿 (Step 3)
        (175, 82, 222),   # 优雅紫 (Step 4)
        (255, 45, 85),    # 绯红 (Step 5)
    ]

    for idx, item in enumerate(steps_data):
        cx, cy = item["x"], item["y"]
        num = item["num"]
        label = item.get("label")
        theme_col = colors[idx % len(colors)]

        # 1. 柔和投影 (Drop Shadow)
        draw.ellipse([cx - r - 1, cy - r + 1, cx + r + 1, cy + r + 3], fill=(0, 0, 0, 90))

        # 2. 双层外圈对比边框 (外暗内亮)
        draw.ellipse([cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1], outline=(255, 255, 255, 230), width=2)
        draw.ellipse([cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2], outline=(0, 0, 0, 150), width=1)

        # 3. 序号球内胆实体
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(theme_col[0], theme_col[1], theme_col[2], 255))

        # 4. 居中数字
        num_str = str(num)
        try:
            nb = draw.textbbox((0, 0), num_str, font=font)
            nw, nh = nb[2] - nb[0], nb[3] - nb[1]
        except Exception:
            nw, nh = font_size * 0.6, font_size
        draw.text((cx - nw / 2, cy - nh / 2 - 1), num_str, fill=(255, 255, 255, 255), font=font)

        # 5. 展开自适应药丸胶囊文本 (Capsule Pill Badge)
        if label:
            pill_text = f" {label} "
            try:
                pb = draw.textbbox((0, 0), pill_text, font=label_font)
                pw, ph = pb[2] - pb[0], pb[3] - pb[1]
            except Exception:
                pw, ph = len(pill_text) * font_size * 0.6, font_size

            # 避让逻辑：若右侧空间不足，则向左侧展开
            pill_h = max(20, int(r * 1.6))
            pill_w = pw + 12
            if cx + r + 6 + pill_w <= w - 10:
                px1 = cx + r + 4
                px2 = px1 + pill_w
            else:
                px2 = cx - r - 4
                px1 = max(10, px2 - pill_w)
            py1 = int(cy - pill_h / 2)
            py2 = py1 + pill_h

            # 胶囊底色与文字
            draw.rounded_rectangle([px1, py1, px2, py2], radius=pill_h // 2, fill=(24, 24, 28, 235), outline=(255, 255, 255, 180), width=1)
            draw.text((px1 + 6, py1 + (pill_h - ph) / 2 - 1), pill_text, fill=(255, 255, 255, 255), font=label_font)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def render_magnifier(img, zoom_data, img_size, scale=2.5, target_pos=None):
    """
    绘制对标 Shottr / CleanShot X 的局部画中画超分放大镜 (Loupe) 与雷达指引虚线
    """
    from PIL import Image, ImageDraw, ImageFilter
    w, h = img_size
    cx, cy = zoom_data["cx"], zoom_data["cy"]
    r = zoom_data["r"]
    scale = max(1.5, min(scale, 4.0))

    # 1. 放大目标尺寸与位置判定
    R = int(r * scale)
    R = min(R, int(min(w, h) * 0.30))

    if target_pos:
        tx, ty = target_pos
    else:
        # 智能对角线空旷角标选择
        margin = 35
        tx = w - R - margin if cx < w / 2 else R + margin
        ty = h - R - margin if cy < h / 2 else R + margin

    # 2. 从原图以 (cx, cy) 为中心高保真截取并放大
    pad = r + 4
    padded_img = Image.new("RGB", (w + pad * 2, h + pad * 2), (20, 20, 25))
    padded_img.paste(img, (pad, pad))
    crop_box = [cx + pad - r, cy + pad - r, cx + pad + r, cy + pad + r]  # 在 padded 坐标系中，精准以 (cx+pad, cy+pad) 为圆心
    cropped = padded_img.crop(crop_box)
    magnified = cropped.resize((R * 2, R * 2), Image.Resampling.LANCZOS)

    # 3. 创建圆形视窗蒙版 (带 2x 超采样抗锯齿)
    mask_scale = 2
    mask_large = Image.new("L", (R * 2 * mask_scale, R * 2 * mask_scale), 0)
    draw_mask = ImageDraw.Draw(mask_large)
    draw_mask.ellipse([0, 0, R * 2 * mask_scale, R * 2 * mask_scale], fill=255)
    circle_mask = mask_large.resize((R * 2, R * 2), Image.Resampling.LANCZOS)

    # 4. 合成视窗底层阴影与主体
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    # 雷达准星与导向线 (从原点连到放大镜视窗)
    draw_ov.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 45, 85, 230), outline=(255, 255, 255, 255), width=1)
    draw_ov.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 45, 85, 120), width=1)

    # 连接虚线/细导向线
    angle = math.atan2(ty - cy, tx - cx)
    line_start_x = cx + r * math.cos(angle)
    line_start_y = cy + r * math.sin(angle)
    line_end_x = tx - R * math.cos(angle)
    line_end_y = ty - R * math.sin(angle)

    # 带阴影的引导线
    draw_ov.line([(line_start_x + 1, line_start_y + 1), (line_end_x + 1, line_end_y + 1)], fill=(0, 0, 0, 120), width=2)
    draw_ov.line([(line_start_x, line_start_y), (line_end_x, line_end_y)], fill=(255, 255, 255, 220), width=1)

    # 放大镜悬浮投影
    draw_ov.ellipse([tx - R - 2, ty - R + 3, tx + R + 2, ty + R + 7], fill=(0, 0, 0, 100))

    base_composite = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # 贴合放大视窗
    win_x = tx - R
    win_y = ty - R
    base_composite.paste(magnified, (win_x, win_y), circle_mask)

    # 5. 精致双层金属镜框轮廓
    final_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    final_draw = ImageDraw.Draw(final_overlay)
    # 外部深色阴影环
    final_draw.ellipse([tx - R - 1, ty - R - 1, tx + R + 1, ty + R + 1], outline=(0, 0, 0, 180), width=2)
    # 内部高亮银白环
    final_draw.ellipse([tx - R, ty - R, tx + R, ty + R], outline=(255, 255, 255, 240), width=2)
    # 极细高光内圈
    final_draw.ellipse([tx - R + 2, ty - R + 2, tx + R - 2, ty + R - 2], outline=(0, 122, 255, 160), width=1)

    return Image.alpha_composite(base_composite.convert("RGBA"), final_overlay).convert("RGB")


def render_highlighter(img, highlight_regions, img_size, color_name="yellow"):
    """
    绘制真实光学质感的荧光笔涂抹 (高亮不遮挡字迹)
    """
    from PIL import Image, ImageDraw
    w, h = img_size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    palette = {
        "yellow": (255, 225, 0, 85),
        "green": (50, 255, 120, 80),
        "cyan": (0, 215, 255, 80),
        "pink": (255, 55, 140, 80)
    }
    hl_color = palette.get(color_name.lower(), palette["yellow"])

    for box in highlight_regions:
        x1, y1, x2, y2 = box
        rad = max(2, int((y2 - y1) * 0.15))
        draw.rounded_rectangle([x1, y1, x2, y2], radius=rad, fill=hl_color)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def render_directional_arrow(img, arrows_data, img_size):
    """
    绘制带双层抗背景描边与实心定位锚点的定向流程箭头 (Arrow)
    """
    from PIL import Image, ImageDraw
    w, h = img_size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for item in arrows_data:
        p1 = item["from"]
        p2 = item["to"]
        label = item.get("label")

        x1, y1 = p1
        x2, y2 = p2
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 10:
            continue

        ux = dx / length
        uy = dy / length

        arrow_len = max(14, int(min(w, h) * 0.022))
        arrow_half_w = arrow_len * 0.55

        # 箭头基底点
        bx = x2 - arrow_len * ux
        by = y2 - arrow_len * uy

        # 垂直法向量
        vx = -uy
        vy = ux

        c_left = (bx + arrow_half_w * vx, by + arrow_half_w * vy)
        c_right = (bx - arrow_half_w * vx, by - arrow_half_w * vy)
        tip = (x2, y2)

        main_color = (255, 45, 85, 255)
        dark_outline = (0, 0, 0, 210)
        line_w = max(2, int(min(w, h) * 0.0035))

        # 1. 绘制起点定位锚点圆
        anchor_r = line_w + 3
        draw.ellipse([x1 - anchor_r - 1, y1 - anchor_r - 1, x1 + anchor_r + 1, y1 + anchor_r + 1], fill=dark_outline)
        draw.ellipse([x1 - anchor_r, y1 - anchor_r, x1 + anchor_r, y1 + anchor_r], fill=main_color)

        # 2. 绘制箭身暗色双层描边与主线
        draw.line([(x1, y1), (bx, by)], fill=dark_outline, width=line_w + 2)
        draw.line([(x1, y1), (bx, by)], fill=main_color, width=line_w)

        # 3. 绘制三角形箭头头部 (外暗内亮)
        poly = [tip, c_left, (bx + (arrow_len * 0.25) * ux, by + (arrow_len * 0.25) * uy), c_right]
        draw.polygon(poly, fill=main_color, outline=dark_outline)

        # 4. 绘制箭头中轴标签徽章
        if label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            font = get_preferred_font(max(11, int(min(w, h) * 0.018)))
            txt = f" {label} "
            try:
                tb = draw.textbbox((0, 0), txt, font=font)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
            except Exception:
                tw, th = len(txt) * 10, 14
            draw.rounded_rectangle([mx - tw / 2 - 4, my - th / 2 - 3, mx + tw / 2 + 4, my + th / 2 + 3], radius=4, fill=(20, 20, 24, 230), outline=(255, 255, 255, 180), width=1)
            draw.text((mx - tw / 2, my - th / 2 - 1), txt, fill=(255, 255, 255, 255), font=font)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def render_blur_pixelate(img, regions_data, img_size, mode="blur"):
    """
    局部敏感信息脱敏：平滑高斯模糊或均匀马赛克
    """
    from PIL import Image, ImageFilter
    w, h = img_size
    res_img = img.copy()

    for box in regions_data:
        x1, y1, x2, y2 = box
        bw, bh = x2 - x1, y2 - y1
        if bw <= 4 or bh <= 4:
            continue

        cropped = res_img.crop((x1, y1, x2, y2))

        if mode == "pixelate":
            # 网格马赛克
            block_size = max(8, int(min(bw, bh) * 0.15))
            sw = max(1, bw // block_size)
            sh = max(1, bh // block_size)
            tiny = cropped.resize((sw, sh), Image.Resampling.NEAREST)
            processed = tiny.resize((bw, bh), Image.Resampling.NEAREST)
        else:
            # 高斯平滑模糊
            radius = max(6, int(min(bw, bh) * 0.12))
            processed = cropped.filter(ImageFilter.GaussianBlur(radius=radius))

        res_img.paste(processed, (x1, y1))

    return res_img


# ==============================================================================
# 视觉呈现主流程管线
# ==============================================================================

def process_image(
    img,
    mode="pure",
    boxes=None,
    labels=None,
    spotlight=False,
    steps=None,
    zoom_config=None,
    zoom_scale=2.5,
    zoom_pos=None,
    highlights=None,
    highlight_color="yellow",
    arrows=None,
    blurs=None,
    pixelates=None
):
    """
    根据模式与高级批注图元对图像进行工业级视觉多模态处理
    """
    from PIL import Image, ImageDraw
    w, h = img.size

    # 1. 优先执行局部隐私脱敏 (高斯模糊 / 马赛克)
    if blurs:
        img = render_blur_pixelate(img, blurs, (w, h), mode="blur")
    if pixelates:
        img = render_blur_pixelate(img, pixelates, (w, h), mode="pixelate")

    # 2. 聚光灯暗角压暗处理 (Spotlight)
    if spotlight and boxes:
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        draw_ov.rectangle([0, 0, w, h], fill=(0, 0, 0, 55))
        # 挖空焦点区域
        x1, y1, x2, y2 = boxes[0]
        draw_ov.rectangle([x1, y1, x2, y2], fill=(0, 0, 0, 0))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # 3. 荧光笔高亮图元
    if highlights:
        img = render_highlighter(img, highlights, (w, h), color_name=highlight_color)

    # 4. 焦点框模式处理 (pure, focus, dual)
    if mode == "focus" and boxes:
        draw = ImageDraw.Draw(img, "RGBA")
        lbl = labels[0] if labels and len(labels) > 0 else None
        render_box_and_tag(draw, boxes[0], lbl, (w, h), color=(255, 45, 85))
    elif mode == "dual" and boxes:
        draw = ImageDraw.Draw(img, "RGBA")
        colors = [
            (0, 199, 190),   # 对比方 A (青蓝)
            (255, 59, 48),   # 对比方 B (亮红)
            (255, 149, 0),   # 备选 C (暖橙)
        ]
        for idx, box in enumerate(boxes):
            c = colors[idx % len(colors)]
            lbl = labels[idx] if labels and idx < len(labels) else None
            render_box_and_tag(draw, box, lbl, (w, h), color=c)
    elif boxes and mode not in ["pure", "filmstrip"]:
        # 兼容自定义框
        draw = ImageDraw.Draw(img, "RGBA")
        for idx, box in enumerate(boxes):
            lbl = labels[idx] if labels and idx < len(labels) else None
            render_box_and_tag(draw, box, lbl, (w, h), color=(255, 45, 85))

    # 5. 定向流程箭头
    if arrows:
        img = render_directional_arrow(img, arrows, (w, h))

    # 6. 自动递增步骤序号球
    if steps:
        img = render_step_pins(img, steps, (w, h))

    # 7. 画中画放大镜 (置于最顶层，避免被其他图元遮盖)
    if zoom_config:
        img = render_magnifier(img, zoom_config, (w, h), scale=zoom_scale, target_pos=zoom_pos)

    return img


def stitch_filmstrip(image_paths, output_path, step_labels=None):
    """
    模式 3：时序胶卷条带模式
    将多张关键帧水平等高拼接为一张流程演进图
    """
    from PIL import Image, ImageDraw

    images = [Image.open(p).convert("RGB") for p in image_paths]
    if not images:
        return output_path

    # 对每张子图裁剪黑边
    images = [trim_black_borders(im) for im in images]

    # 以最小高度作为基准进行等比例缩放
    min_h = min(im.height for im in images)
    target_h = min(min_h, 720)

    resized_images = []
    for im in images:
        scale = target_h / im.height
        new_w = int(im.width * scale)
        resized_images.append(im.resize((new_w, target_h), Image.Resampling.LANCZOS))

    gap = 4
    total_w = sum(im.width for im in resized_images) + gap * (len(resized_images) - 1)
    filmstrip = Image.new("RGB", (total_w, target_h), (30, 30, 46))

    cur_x = 0
    draw = ImageDraw.Draw(filmstrip, "RGBA")
    for idx, im in enumerate(resized_images):
        filmstrip.paste(im, (cur_x, 0))
        
        # 绘制步骤胶卷角标
        step_text = step_labels[idx] if step_labels and idx < len(step_labels) else f"Step {idx + 1}"
        font = get_preferred_font(max(14, int(target_h * 0.035)))
        try:
            bbox = draw.textbbox((0, 0), f" {step_text} ", font=font)
            bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            bw, bh = 80, 24
        
        draw.rounded_rectangle([cur_x + 8, 8, cur_x + 8 + bw + 4, 8 + bh + 4], radius=3, fill=(255, 45, 85, 230))
        draw.text((cur_x + 10, 9), f" {step_text} ", fill=(255, 255, 255, 255), font=font)

        cur_x += im.width + gap

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    filmstrip.save(output_path, "PNG", optimize=True)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="多场景自适应视频关键帧截取与顶级知识批注工具")
    parser.add_argument("video_path", help="视频源文件路径 (.mp4 / .mkv / .webm)")
    parser.add_argument("--timestamp", "-t", default=None, help="截帧时间戳，如 '03:45' 或 '01:12:30'")
    parser.add_argument("--timestamps", default=None, help="多时间戳拼接 (用于胶卷模式)，逗号分隔: '01:15,02:30,03:45'")
    parser.add_argument("--output", "-o", required=True, help="输出图片绝对路径 (建议存放在导图目录下的 images/ 子目录)")
    
    # 模式选择与参数
    parser.add_argument("--mode", "-m", choices=["pure", "focus", "dual", "filmstrip", "auto"], default="auto",
                        help="视觉呈现模式: pure(零标注纯景), focus(单焦点引导), dual(双向平权对比), filmstrip(胶卷拼接), auto(自动判定)")
    parser.add_argument("--box", "-b", default=None, help="单矩形框坐标: 'x1,y1,x2,y2' (支持像素或 0~1 比例)")
    parser.add_argument("--boxes", default=None, help="多矩形框坐标 (分号分隔): '0.1,0.2,0.4,0.8;0.6,0.2,0.9,0.8'")
    parser.add_argument("--label", "-l", default=None, help="单角标文字，如 '核心机制'、'关键循环'")
    parser.add_argument("--labels", default=None, help="多角标文字 (分号分隔): '客户端;服务端'")
    parser.add_argument("--spotlight", action="store_true", help="焦点模式下开启微量聚光灯背景暗角效果")
    parser.add_argument("--no-trim", action="store_true", help="不自动裁切边缘黑边")

    # 顶级批注扩展图元 (CleanShot X / Shottr 标准)
    parser.add_argument("--steps", default=None, help="立体步骤序号球: 'x1,y1[:标签];x2,y2[:标签]' (支持比例或绝对像素)")
    parser.add_argument("--zoom", default=None, help="画中画放大镜: 'cx,cy,r' (支持比例或绝对像素)")
    parser.add_argument("--zoom-scale", type=float, default=2.5, help="放大镜倍率 (默认 2.5)")
    parser.add_argument("--zoom-pos", default=None, help="放大镜视窗目标中心: 'tx,ty' (默认自适应空旷角落)")
    parser.add_argument("--highlight", default=None, help="真实荧光笔高亮涂抹区域: 'x1,y1,x2,y2;...'")
    parser.add_argument("--highlight-color", choices=["yellow", "green", "cyan", "pink"], default="yellow", help="荧光笔色彩")
    parser.add_argument("--arrow", default=None, help="双层对比定向流程箭头: 'x1,y1->x2,y2[:标签];...'")
    parser.add_argument("--blur", default=None, help="局部高斯平滑模糊脱敏: 'x1,y1,x2,y2;...'")
    parser.add_argument("--pixelate", default=None, help="局部网格马赛克脱敏: 'x1,y1,x2,y2;...'")

    # 智能剪聚焦与去字幕增强
    parser.add_argument("--crop", default=None, help="显式指定裁剪窗口: 'x1,y1,x2,y2' (支持 0~1 比例或像素)")
    parser.add_argument("--crop-focus", action="store_true", help="自动以目标框为核心进行主体智能剪聚焦 (剔除无用大黑底与边框)")
    parser.add_argument("--strip-subtitles", action="store_true", help="强制剔除底部 14%% 的字幕/控制栏危险区域，杜绝半截字幕残留")
    parser.add_argument("--strip-header", action="store_true", help="剔除顶部 10%% 的浏览器栏与状态栏")

    args = parser.parse_args()

    ffmpeg_bin = find_ffmpeg()

    # 1. 自动推断模式
    mode = args.mode
    if mode == "auto":
        if args.timestamps:
            mode = "filmstrip"
        elif args.boxes and ";" in args.boxes:
            mode = "dual"
        elif args.box or (args.boxes and ";" not in args.boxes) or args.spotlight:
            mode = "focus"
        else:
            mode = "pure"

    # 2. 处理胶卷模式 (Filmstrip)
    if mode == "filmstrip":
        ts_list = [t.strip() for t in (args.timestamps or args.timestamp or "").split(',') if t.strip()]
        if not ts_list:
            raise ValueError("胶卷拼接模式必须提供 --timestamps 'T1,T2,T3'")
        
        tmp_files = []
        try:
            for idx, ts in enumerate(ts_list):
                sec = parse_timestamp_to_seconds(ts)
                tmp_p = str(Path(args.output).with_suffix(f".tmp_{idx}.png"))
                print(f"[*] 胶卷切片 [{idx+1}/{len(ts_list)}]: 正在截取 [{ts}] ...")
                extract_raw_frame(args.video_path, sec, tmp_p, ffmpeg_bin)
                tmp_files.append(tmp_p)

            lbl_list = [l.strip() for l in (args.labels or args.label or "").split(';') if l.strip()]
            stitch_filmstrip(tmp_files, args.output, lbl_list)
            print(f"[+] 时序胶卷条带已生成并归档: {args.output}")
            return
        finally:
            for f in tmp_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass

    # 3. 处理单帧模式 (pure, focus, dual + 组合图元)
    input_path = Path(args.video_path)
    is_direct_image = input_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp", ".bmp"] and input_path.exists()

    if not is_direct_image and not args.timestamp:
        raise ValueError("从视频源截帧必须指定 --timestamp 时间戳！若处理现有关键帧图片，请直接提供图片路径。")

    tmp_raw = None
    try:
        from PIL import Image
        if is_direct_image:
            print(f"[*] 检测到直接输入关键帧图像 [{input_path.name}]，直接载入进行高级批注...")
            img = Image.open(input_path).convert("RGB")
        else:
            sec = parse_timestamp_to_seconds(args.timestamp)
            tmp_raw = str(Path(args.output).with_suffix(".tmp.png"))
            print(f"[*] 正在从视频 [{input_path.name}] 截取 [{args.timestamp}] (第 {sec} 秒) 高清关键帧...")
            extract_raw_frame(str(input_path), sec, tmp_raw, ffmpeg_bin)
            with Image.open(tmp_raw) as im:
                img = im.convert("RGB")

        if not args.no_trim:
            img = trim_black_borders(img)

        # 智能去除顶部/底部字幕干扰区
        orig_w, orig_h = img.size
        top_cut = int(orig_h * 0.10) if args.strip_header else 0
        bottom_cut = int(orig_h * 0.86) if args.strip_subtitles else orig_h
        if top_cut > 0 or bottom_cut < orig_h:
            img = img.crop((0, top_cut, orig_w, bottom_cut))
            print(f"[*] 已安全剥离周边杂质 (y: {top_cut} ~ {bottom_cut})")

        w, h = img.size

        # 解析坐标框与标签
        parsed_boxes = []
        raw_boxes_str = args.boxes or args.box
        if raw_boxes_str:
            for b_str in raw_boxes_str.split(';'):
                b_str = b_str.strip()
                if b_str:
                    parsed_boxes.append(parse_box_str(b_str, w, h))

        parsed_labels = []
        raw_labels_str = args.labels or args.label
        if raw_labels_str:
            parsed_labels = [l.strip() for l in raw_labels_str.split(';') if l.strip()]

        # 智能剪聚焦 (Smart Focus Crop) 处理
        if args.crop:
            crop_rect = parse_box_str(args.crop, w, h)
            img = img.crop(crop_rect)
            print(f"[*] 已应用显式剪聚焦 ROI: {crop_rect} -> {img.size}")
            w, h = img.size
        elif args.crop_focus and parsed_boxes:
            # 自动计算所有框的并集外接矩形
            min_x1 = min(b[0] for b in parsed_boxes)
            min_y1 = min(b[1] for b in parsed_boxes)
            max_x2 = max(b[2] for b in parsed_boxes)
            max_y2 = max(b[3] for b in parsed_boxes)
            # 向外扩展舒适呼吸边距
            pad_x = max(25, int((max_x2 - min_x1) * 0.08))
            pad_y = max(30, int((max_y2 - min_y1) * 0.12))
            crop_x1 = max(0, min_x1 - pad_x)
            crop_y1 = max(0, min_y1 - pad_y)
            crop_x2 = min(w, max_x2 + pad_x)
            crop_y2 = min(h, max_y2 + pad_y)
            img = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
            # 重映射框到裁剪后的视口
            parsed_boxes = [(b[0] - crop_x1, b[1] - crop_y1, b[2] - crop_x1, b[3] - crop_y1) for b in parsed_boxes]
            print(f"[*] 已应用自动核心剪聚焦 (Padding +{pad_x}px, +{pad_y}px) -> {img.size}")
            w, h = img.size

        # 解析扩展图元 (在裁剪后的最终视口坐标系中解析)
        parsed_steps = parse_steps_str(args.steps, w, h) if args.steps else None
        parsed_zoom = parse_zoom_str(args.zoom, w, h) if args.zoom else None
        parsed_zoom_pos = parse_point_str(args.zoom_pos, w, h) if args.zoom_pos else None
        parsed_highlights = parse_regions_str(args.highlight, w, h) if args.highlight else None
        parsed_arrows = parse_arrow_str(args.arrow, w, h) if args.arrow else None
        parsed_blurs = parse_regions_str(args.blur, w, h) if args.blur else None
        parsed_pixelates = parse_regions_str(args.pixelate, w, h) if args.pixelate else None

        active_addons = []
        if parsed_steps: active_addons.append("步骤球(Steps)")
        if parsed_zoom: active_addons.append("画中画放大镜(Zoom)")
        if parsed_highlights: active_addons.append("荧光笔(Highlight)")
        if parsed_arrows: active_addons.append("流程箭头(Arrow)")
        if parsed_blurs: active_addons.append("高斯模糊(Blur)")
        if parsed_pixelates: active_addons.append("马赛克(Pixelate)")

        addon_msg = f" + 扩展图元: [{', '.join(active_addons)}]" if active_addons else ""
        print(f"[*] 正在应用视觉呈现策略: 【模式 {mode}】{addon_msg} ...")

        final_img = process_image(
            img,
            mode=mode,
            boxes=parsed_boxes,
            labels=parsed_labels,
            spotlight=args.spotlight,
            steps=parsed_steps,
            zoom_config=parsed_zoom,
            zoom_scale=args.zoom_scale,
            zoom_pos=parsed_zoom_pos,
            highlights=parsed_highlights,
            highlight_color=args.highlight_color,
            arrows=parsed_arrows,
            blurs=parsed_blurs,
            pixelates=parsed_pixelates
        )

        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        final_img.save(args.output, "PNG", optimize=True)
        print(f"[+] 关键帧视觉呈现完成并已归档: {args.output}")

    finally:
        if tmp_raw and os.path.exists(tmp_raw):
            try:
                os.remove(tmp_raw)
            except Exception:
                pass


if __name__ == "__main__":
    main()
