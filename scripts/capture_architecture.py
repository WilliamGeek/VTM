import time
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML_PATH = Path(r"f:\skills\video-to-mindmap\assets\architecture\video-to-mindmap.workflow.html").resolve()
OUTPUT_PNG = Path(r"f:\skills\video-to-mindmap\assets\architecture\workflow_architecture.png").resolve()
OUTPUT_DARK_PNG = Path(r"f:\skills\video-to-mindmap\assets\architecture\workflow_architecture_dark.png").resolve()

def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        # High DPI viewport for ultra-crisp diagram rendering
        context = browser.new_context(viewport={"width": 1600, "height": 1050}, device_scale_factor=2)
        page = context.new_page()

        # 1. Capture Light theme (User preferred)
        url_light = f"{HTML_PATH.as_uri()}?theme=light"
        print(f"Loading {url_light}...")
        page.goto(url_light)
        page.wait_for_timeout(1000)
        
        # Archify sets theme via URL or attribute
        page.evaluate("() => { if (window.__archifySetTheme) window.__archifySetTheme('light'); document.documentElement.setAttribute('data-theme', 'light'); }")
        page.wait_for_timeout(800)

        page.screenshot(path=str(OUTPUT_PNG), full_page=False)
        print(f"Saved light architecture screenshot to {OUTPUT_PNG}")

        # 2. Also capture dark theme
        url_dark = f"{HTML_PATH.as_uri()}?theme=dark"
        page.goto(url_dark)
        page.wait_for_timeout(800)
        page.evaluate("() => { if (window.__archifySetTheme) window.__archifySetTheme('dark'); document.documentElement.setAttribute('data-theme', 'dark'); }")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUTPUT_DARK_PNG), full_page=False)
        print(f"Saved dark architecture screenshot to {OUTPUT_DARK_PNG}")

        browser.close()

if __name__ == "__main__":
    capture()
