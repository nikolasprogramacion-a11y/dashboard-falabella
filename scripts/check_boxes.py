from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle")
    page.wait_for_timeout(3000)
    
    # check elements
    brand = page.locator(".finart-sidebar-brand").bounding_box()
    print("brand bounding box:", brand)
    
    header = page.locator(".ardp-header, .ardp-page").first.bounding_box()
    print("header bounding box:", header)
    
    tabs = page.locator('[data-testid="stTabs"] [role="tablist"]').bounding_box()
    print("tabs bounding box:", tabs)
    
    body_box = page.locator("body").bounding_box()
    print("body box:", body_box)
    
    # evaluate computed styles
    bg = page.evaluate("() => window.getComputedStyle(document.body).backgroundColor")
    print("body computed background:", bg)
    
    color = page.evaluate("() => window.getComputedStyle(document.body).color")
    print("body computed color:", color)

    header_disp = page.evaluate("() => { let h = document.querySelector('.ardp-header, .ardp-page'); return h ? { disp: window.getComputedStyle(h).display, vis: window.getComputedStyle(h).visibility, op: window.getComputedStyle(h).opacity, w: h.offsetWidth, h: h.offsetHeight } : null; }")
    print("header computed visibility:", header_disp)
    
    browser.close()
