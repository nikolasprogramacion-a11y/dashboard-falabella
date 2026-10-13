"""Prueba manual de humo para las cinco secciones del dashboard.

Requiere que Streamlit esté ejecutándose en http://localhost:8501 y que
Playwright tenga instalado Chromium (playwright install chromium).
"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto("http://localhost:8501", wait_until="domcontentloaded", timeout=30000)
    tabs = page.locator("[data-testid='stTabs'] [role='tab']")
    assert tabs.count() == 5, f"Se esperaban 5 secciones y se encontraron {tabs.count()}"
    for i in range(tabs.count()):
        tab = tabs.nth(i)
        label = tab.inner_text().strip()
        tab.click()
        page.wait_for_timeout(500)
        assert tab.get_attribute("aria-selected") == "true", f"No se pudo activar: {label}"
        print(f"OK: {label}")
    browser.close()
