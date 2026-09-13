import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ASSETS_DIR = PROJECT_DIR / "assets" / "demo"

FONT_BOLD = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 32)
FONT_CHINESE = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)

def draw_badge(img, x, y, num_str, label=None, color=(37, 99, 235), target_point=None, label_left=False):
    """
    Renders a crisp Apple-style numbered badge with drop shadow, outer ring, and optional callout stem.
    """
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # 1. Stem
    if target_point:
        tx, ty = target_point
        draw.line([(tx, ty), (x, y)], fill=(255, 255, 255, 220), width=5)
        draw.line([(tx, ty), (x, y)], fill=(*color, 240), width=3)
        draw.ellipse([tx - 7, ty - 7, tx + 7, ty + 7], fill=(255, 255, 255, 255), outline=(*color, 255), width=3)

    # 2. Badge Shadow
    radius = 28
    shadow_img = Image.new("RGBA", (radius * 4, radius * 4), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_img)
    sc = radius * 2
    s_draw.ellipse([sc - radius, sc - radius, sc + radius, sc + radius], fill=(0, 0, 0, 140))
    b_shadow = shadow_img.filter(ImageFilter.GaussianBlur(radius=6))
    overlay.paste(b_shadow, (int(x - sc), int(y - sc + 4)), b_shadow)

    # 3. Badge Circles
    draw = ImageDraw.Draw(overlay)
    draw.ellipse([x - radius - 3, y - radius - 3, x + radius + 3, y + radius + 3], fill=(255, 255, 255, 255))
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=(*color, 255))

    # 4. Text
    bbox = draw.textbbox((0, 0), str(num_str), font=FONT_BOLD)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x - tw / 2 - bbox[0], y - th / 2 - bbox[1]), str(num_str), font=FONT_BOLD, fill=(255, 255, 255, 255))

    # 5. Pill Label
    if label:
        l_bbox = draw.textbbox((0, 0), label, font=FONT_CHINESE)
        lw = l_bbox[2] - l_bbox[0]
        lh = l_bbox[3] - l_bbox[1]
        
        if label_left:
            cap_x2 = x - radius - 10
            cap_x1 = cap_x2 - lw - 28
        else:
            cap_x1 = x + radius + 10
            cap_x2 = cap_x1 + lw + 28
            
        cap_y1 = y - radius + 2
        cap_y2 = y + radius - 2
        
        p_shadow = Image.new("RGBA", (int(cap_x2 - cap_x1 + 24), int(cap_y2 - cap_y1 + 24)), (0, 0, 0, 0))
        p_draw = ImageDraw.Draw(p_shadow)
        p_draw.rounded_rectangle([6, 6, cap_x2 - cap_x1 + 6, cap_y2 - cap_y1 + 6], radius=16, fill=(0, 0, 0, 130))
        p_shadow_b = p_shadow.filter(ImageFilter.GaussianBlur(radius=6))
        overlay.paste(p_shadow_b, (int(cap_x1 - 6), int(cap_y1 - 6 + 3)), p_shadow_b)
        
        draw = ImageDraw.Draw(overlay)
        draw.rounded_rectangle([cap_x1, cap_y1, cap_x2, cap_y2], radius=16, fill=(24, 28, 42, 240), outline=(255, 255, 255, 200), width=2)
        draw.text((cap_x1 + 14, cap_y1 + (cap_y2 - cap_y1 - lh) / 2 - l_bbox[1]), label, font=FONT_CHINESE, fill=(255, 255, 255, 255))

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def render_all():
    print("[*] Generating production-ready feature demo screenshots...")

    # =========================================================================
    # 1. 01_feature_search.png (Ren Jiantao - Light Theme)
    # =========================================================================
    print("[1/4] Rendering 01_feature_search.png...")
    im1 = Image.open(ASSETS_DIR / "raw_feature_search.png")
    
    # 1: Search Input
    im1 = draw_badge(im1, 980, 150, "1", "关键词即时检索 (/ 或 Ctrl+F)", color=(59, 130, 246), target_point=(1180, 70), label_left=True)
    # 2: Search Nav
    im1 = draw_badge(im1, 1480, 150, "2", "匹配计数与前后跳转 (Enter/Shift+Enter)", color=(245, 158, 11), target_point=(1355, 70), label_left=False)
    # 3: Deep Path Unfold
    im1 = draw_badge(im1, 560, 960, "3", "沿途折叠分支自动穿透展开", color=(16, 185, 129), target_point=(680, 960), label_left=True)
    # 4: Target Node Glow - perfectly placed in empty whitespace below branch 1.1.2
    im1 = draw_badge(im1, 1020, 1280, "4", "匹配节点强化高亮与视口居中", color=(239, 68, 68), target_point=(1280, 1150), label_left=False)
    
    im1.convert("RGB").save(ASSETS_DIR / "01_feature_search.png", quality=95)
    print("  -> Saved 01_feature_search.png")

    # =========================================================================
    # 2. 02_feature_lightbox.png (Physiology - Light Theme)
    # =========================================================================
    print("[2/4] Rendering 02_feature_lightbox.png...")
    im2 = Image.open(ASSETS_DIR / "raw_feature_lightbox.png")
    
    # 1: High-entropy Mechanism Diagram inside Lightbox
    im2 = draw_badge(im2, 800, 350, "1", "关键机制图谱高精度呈现", color=(59, 130, 246), target_point=(1300, 360), label_left=True)
    # 2: Lightbox Modal
    im2 = draw_badge(im2, 2950, 1100, "2", "全屏无级缩放与平移查看器", color=(139, 92, 246), target_point=(2870, 1100), label_left=False)
    # 3: Controls Dock
    im2 = draw_badge(im2, 2180, 1920, "3", "浮动工具栏（1:1复位 / 原图下载 / 缩放）", color=(16, 185, 129), target_point=(2250, 2030), label_left=False)
    
    im2.convert("RGB").save(ASSETS_DIR / "02_feature_lightbox.png", quality=95)
    print("  -> Saved 02_feature_lightbox.png")

    # =========================================================================
    # 3. 03_feature_themes.png (Side-by-Side Complete Comparison)
    # =========================================================================
    print("[3/4] Rendering 03_feature_themes.png...")
    im_dark = Image.open(ASSETS_DIR / "raw_theme_dark.png")
    im_light = Image.open(ASSETS_DIR / "raw_theme_light.png")
    
    cw, ch = 3840, 1320
    canvas = Image.new("RGBA", (cw, ch), (15, 23, 42, 255))
    font_title = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)

    card_w = 1830
    card_h = 1130
    header_h = 60
    y_card = 140
    x_dark = 60
    x_light = 1950

    thumb_w = card_w
    thumb_h = int(thumb_w * 2160 / 3840)

    dark_thumb = im_dark.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
    light_thumb = im_light.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)

    # 3.1 Dark Card
    card1 = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    c1_draw = ImageDraw.Draw(card1)
    c1_draw.rounded_rectangle([0, 0, card_w, card_h], radius=16, fill=(26, 27, 38, 255), outline=(65, 72, 104, 200), width=3)
    c1_draw.rounded_rectangle([0, 0, card_w, header_h + 16], radius=16, fill=(36, 40, 59, 255))
    c1_draw.rectangle([0, 20, card_w, header_h], fill=(36, 40, 59, 255))
    c1_draw.line([(0, header_h), (card_w, header_h)], fill=(65, 72, 104, 150), width=2)
    c1_draw.ellipse([25, 22, 41, 38], fill=(255, 95, 87))
    c1_draw.ellipse([53, 22, 69, 38], fill=(254, 188, 46))
    c1_draw.ellipse([81, 22, 97, 38], fill=(40, 200, 64))
    c1_draw.text((120, 14), "Tokyo Night 深色拟态模式 (代码与沉浸夜读)", font=font_title, fill=(192, 202, 245))
    card1.paste(dark_thumb, (0, header_h))

    # 3.2 Light Card
    card2 = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    c2_draw = ImageDraw.Draw(card2)
    c2_draw.rounded_rectangle([0, 0, card_w, card_h], radius=16, fill=(248, 250, 252, 255), outline=(203, 213, 225, 220), width=3)
    c2_draw.rounded_rectangle([0, 0, card_w, header_h + 16], radius=16, fill=(241, 245, 249, 255))
    c2_draw.rectangle([0, 20, card_w, header_h], fill=(241, 245, 249, 255))
    c2_draw.line([(0, header_h), (card_w, header_h)], fill=(203, 213, 225, 200), width=2)
    c2_draw.ellipse([25, 22, 41, 38], fill=(255, 95, 87))
    c2_draw.ellipse([53, 22, 69, 38], fill=(254, 188, 46))
    c2_draw.ellipse([81, 22, 97, 38], fill=(40, 200, 64))
    c2_draw.text((120, 14), "Clean Minimal 极简浅色模式 (高对比清晰易读 · 推荐日常阅读)", font=font_title, fill=(15, 23, 42))
    card2.paste(light_thumb, (0, header_h))

    canvas.paste(card1, (x_dark, y_card), card1)
    canvas.paste(card2, (x_light, y_card), card2)

    # Badges at top - clean vertical lines down to card top borders
    canvas = draw_badge(canvas, 1680, 65, "1", "一键主题无缝秒切 (快捷键 T)", color=(139, 92, 246), target_point=None, label_left=False)
    canvas = draw_badge(canvas, 975, 65, "2", "Tokyo Night 沉浸夜读", color=(59, 130, 246), target_point=(975, y_card), label_left=False)
    canvas = draw_badge(canvas, 2865, 65, "3", "Clean Minimal 清晰易读 (推荐日常)", color=(16, 185, 129), target_point=(2865, y_card), label_left=False)

    canvas.convert("RGB").save(ASSETS_DIR / "03_feature_themes.png", quality=95)
    print("  -> Saved 03_feature_themes.png")

    # =========================================================================
    # 4. 04_feature_export.png (Physiology - Light Theme)
    # =========================================================================
    print("[4/4] Rendering 04_feature_export.png...")
    im4 = Image.open(ASSETS_DIR / "raw_feature_export.png")
    
    # 1: Export Menu Button on Dock
    im4 = draw_badge(im4, 2850, 130, "1", "控制坞离线导出入口", color=(59, 130, 246), target_point=(2700, 68), label_left=False)
    # 2: Native XMind
    im4 = draw_badge(im4, 2220, 180, "2", "原生 .xmind 一键打包", color=(239, 68, 68), target_point=(2570, 180), label_left=True)
    # 3: Other formats
    im4 = draw_badge(im4, 2220, 320, "3", "4K PNG / 矢量 SVG / Markdown", color=(16, 185, 129), target_point=(2570, 320), label_left=True)
    
    im4.convert("RGB").save(ASSETS_DIR / "04_feature_export.png", quality=95)
    print("  -> Saved 04_feature_export.png")

    print("[SUCCESS] All 4 production demo screenshots rendered successfully!")

if __name__ == "__main__":
    render_all()
