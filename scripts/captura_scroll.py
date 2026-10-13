"""Capture the bottom 3 panels of tab Presupuesto to verify donut and code leak fixes."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle")
    time.sleep(4)

    # Click Presupuesto tab
    page.evaluate("""() => {
        const all = document.querySelectorAll('[role="tab"], button, [data-testid*="tab"] button');
        for (const el of all) {
            if ((el.innerText || "").toLowerCase().includes("presupuesto")) {
                el.click();
                return;
            }
        }
    }""")
    time.sleep(4)

    # Full page screenshot of Presupuesto
    page.screenshot(path="capturas/ppto_fullpage.png", full_page=True)

    # Scroll down to bottom panels and capture viewport
    page.evaluate("""() => {
        const main = document.querySelector('[data-testid="stMainBlockContainer"]')
            || document.querySelector('.block-container')
            || document.querySelector('section.main');
        if (main) main.scrollIntoView({block: 'end'});
        window.scrollTo(0, document.body.scrollHeight);
    }""")
    time.sleep(2)
    page.screenshot(path="capturas/ppto_bottom_viewport.png", full_page=False)

    browser.close()
    print("OK: ppto_fullpage.png + ppto_bottom_viewport.png")
