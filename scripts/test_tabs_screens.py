from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle")
    page.wait_for_timeout(3000)

    # find all tabs
    tabs = page.locator('[data-testid="stTabs"] button[role="tab"]').all()
    print("Found tabs:", len(tabs))
    for i, t in enumerate(tabs):
        print(f"Tab {i}: {t.inner_text()}")

    # Take screenshot of default tab
    page.screenshot(path="test_tab0.png")
    print("Saved test_tab0.png")

    # Click on Tab 1 (Presupuesto)
    if len(tabs) > 1:
        tabs[1].click()
        page.wait_for_timeout(2000)
        page.screenshot(path="test_tab1_ppto.png")
        print("Saved test_tab1_ppto.png")

    browser.close()
