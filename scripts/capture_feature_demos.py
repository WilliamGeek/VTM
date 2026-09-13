import os
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

PHYSIOLOGY_HTML = Path(r"F:\yt-dlp\downloads\生理学丨带背丨10小时丨思维导图丨期末速成丨考研冲刺丨期末突击丨不挂科丨记忆卡片丨口诀丨 p02 生理带背第一章\生理学丨带背丨10小时丨思维导图丨期末速成丨考研冲刺丨期末突击丨不挂科丨记忆卡片丨口诀丨 p02 生理带背第一章_mindmap.html").as_uri()
REN_HTML = Path(r"F:\yt-dlp\downloads\【墙内被删】任剑涛教授封神演讲：精准预测当今圣上！中国已被权势集团挟持，进入毫无生气的20年！内容极其大胆劲爆！\【墙内被删】任剑涛教授封神演讲：精准预测当今圣上！中国已被权势集团挟持，进入毫无生气的20年！内容极其大胆劲爆！_mindmap.html").as_uri()

OUT_DIR = Path(r"F:\skills\video-to-mindmap\assets\demo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        # 1920x1080 viewport with scale factor 2 -> 3840x2160 crisp resolution
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
        page = context.new_page()

        coords_data = {}

        # =====================================================================
        # 1. 实时搜索与自动定位 (Ren Jiantao Speech - Light Theme)
        # =====================================================================
        print("[1/4] Capturing 01_feature_search.png (Ren Jiantao - Light Theme)...")
        page.goto(REN_HTML)
        page.wait_for_selector("#mindmap-svg")
        # Set light theme
        page.evaluate("() => document.documentElement.setAttribute('data-theme', 'light')")
        time.sleep(0.5)

        # Search for "合法性"
        page.evaluate("""() => {
            const input = document.getElementById('search-input');
            input.value = '合法性';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }""")
        time.sleep(0.8)

        # Focus match 0
        page.evaluate("""() => {
            if (typeof focusMatch === 'function') focusMatch(0);
        }""")
        time.sleep(1.0)

        search_coords = page.evaluate("""() => {
            const input = document.getElementById('search-input').getBoundingClientRect();
            const count = document.getElementById('search-count').getBoundingClientRect();
            const nextBtn = document.getElementById('search-next').getBoundingClientRect();
            
            // Find highlighted mark or active node
            const marks = document.querySelectorAll('mark.search-highlight');
            let target = null;
            if (marks.length > 0) {
                target = marks[0].getBoundingClientRect();
            }
            return {
                searchInput: { x: input.x, y: input.y, width: input.width, height: input.height },
                searchCount: { x: count.x, y: count.y, width: count.width, height: count.height },
                searchNav: { x: nextBtn.x, y: nextBtn.y, width: nextBtn.width, height: nextBtn.height },
                highlightTarget: target ? { x: target.x, y: target.y, width: target.width, height: target.height } : null
            };
        }""")
        coords_data["search"] = search_coords
        raw_search_path = OUT_DIR / "raw_feature_search.png"
        page.screenshot(path=str(raw_search_path))
        print(f"  -> Saved {raw_search_path}")

        # =====================================================================
        # 2. 图片预览与缩放 (Physiology - Light Theme)
        # =====================================================================
        print("[2/4] Capturing 02_feature_lightbox.png (Physiology - Light Theme)...")
        page.goto(PHYSIOLOGY_HTML)
        page.wait_for_selector("#mindmap-svg")
        page.evaluate("() => document.documentElement.setAttribute('data-theme', 'light')")
        time.sleep(0.5)

        # Expand branches and trigger lightbox on circuit diagram
        page.evaluate("""() => {
            document.getElementById('btn-expand').click();
            const target = document.querySelector('.markmap-foreign img, image, img');
            const lb = document.getElementById('lightbox');
            const lbImg = document.getElementById('lightbox-img');
            const lbCaption = document.getElementById('lightbox-caption');
            if (target && lb && lbImg) {
                lbImg.src = target.src || './images/p02_negative_feedback_circuit.png';
                lbCaption.textContent = '闭环负反馈控制系统结构图解与调定点机制';
                if (typeof resetLightbox === 'function') resetLightbox();
                lb.classList.add('active');
            }
        }""")
        time.sleep(1.2)

        lightbox_coords = page.evaluate("""() => {
            const lb = document.getElementById('lightbox').getBoundingClientRect();
            const lbImg = document.getElementById('lightbox-img').getBoundingClientRect();
            const dock = document.querySelector('.lightbox-dock').getBoundingClientRect();
            const downloadBtn = document.getElementById('lightbox-download').getBoundingClientRect();
            const zoomInBtn = document.getElementById('lightbox-zoom-in').getBoundingClientRect();
            return {
                lightbox: { x: lb.x, y: lb.y, width: lb.width, height: lb.height },
                lightboxImg: { x: lbImg.x, y: lbImg.y, width: lbImg.width, height: lbImg.height },
                dock: { x: dock.x, y: dock.y, width: dock.width, height: dock.height },
                downloadBtn: { x: downloadBtn.x, y: downloadBtn.y, width: downloadBtn.width, height: downloadBtn.height },
                zoomInBtn: { x: zoomInBtn.x, y: zoomInBtn.y, width: zoomInBtn.width, height: zoomInBtn.height }
            };
        }""")
        coords_data["lightbox"] = lightbox_coords
        raw_lightbox_path = OUT_DIR / "raw_feature_lightbox.png"
        page.screenshot(path=str(raw_lightbox_path))
        print(f"  -> Saved {raw_lightbox_path}")

        # =====================================================================
        # 3. 多格式导出菜单 (Physiology - Light Theme)
        # =====================================================================
        print("[3/4] Capturing 03_feature_export.png (Physiology - Light Theme)...")
        # Close lightbox and reset view
        page.evaluate("""() => {
            document.getElementById('lightbox').classList.remove('active');
            document.getElementById('btn-fold-2').click();
            document.getElementById('export-dropdown').classList.add('active');
        }""")
        time.sleep(0.8)

        export_coords = page.evaluate("""() => {
            const btn = document.getElementById('btn-export-menu').getBoundingClientRect();
            const dropdown = document.getElementById('export-dropdown').getBoundingClientRect();
            const xmindBtn = document.getElementById('export-xmind').getBoundingClientRect();
            const pngBtn = document.getElementById('export-png').getBoundingClientRect();
            const svgBtn = document.getElementById('export-svg').getBoundingClientRect();
            const mdBtn = document.getElementById('export-markdown').getBoundingClientRect();
            return {
                btnExport: { x: btn.x, y: btn.y, width: btn.width, height: btn.height },
                dropdown: { x: dropdown.x, y: dropdown.y, width: dropdown.width, height: dropdown.height },
                xmind: { x: xmindBtn.x, y: xmindBtn.y, width: xmindBtn.width, height: xmindBtn.height },
                png: { x: pngBtn.x, y: pngBtn.y, width: pngBtn.width, height: pngBtn.height },
                svg: { x: svgBtn.x, y: svgBtn.y, width: svgBtn.width, height: svgBtn.height },
                md: { x: mdBtn.x, y: mdBtn.y, width: mdBtn.width, height: mdBtn.height }
            };
        }""")
        coords_data["export"] = export_coords
        raw_export_path = OUT_DIR / "raw_feature_export.png"
        page.screenshot(path=str(raw_export_path))
        print(f"  -> Saved {raw_export_path}")

        # =====================================================================
        # 4. 深浅色主题对比 (Theme Comparison - Dark vs Light)
        # =====================================================================
        print("[4/4] Capturing theme comparison shots (Physiology)...")
        page.evaluate("() => document.getElementById('export-dropdown').classList.remove('active')")
        
        # 4.1 Dark theme capture
        page.evaluate("() => { document.documentElement.setAttribute('data-theme', 'dark'); document.getElementById('btn-fold-2').click(); document.getElementById('btn-fit').click(); }")
        time.sleep(1.2)
        raw_dark_path = OUT_DIR / "raw_theme_dark.png"
        page.screenshot(path=str(raw_dark_path))

        # 4.2 Light theme capture
        page.evaluate("() => { document.documentElement.setAttribute('data-theme', 'light'); document.getElementById('btn-fit').click(); }")
        time.sleep(1.2)
        raw_light_path = OUT_DIR / "raw_theme_light.png"
        page.screenshot(path=str(raw_light_path))

        theme_coords = page.evaluate("""() => {
            const btn = document.getElementById('btn-theme').getBoundingClientRect();
            return {
                btnTheme: { x: btn.x, y: btn.y, width: btn.width, height: btn.height }
            };
        }""")
        coords_data["theme"] = theme_coords

        with open(OUT_DIR / "feature_coords.json", "w", encoding="utf-8") as f:
            json.dump(coords_data, f, ensure_ascii=False, indent=2)
        print("Done capturing all raw feature screenshots!")

        browser.close()

if __name__ == "__main__":
    run()
