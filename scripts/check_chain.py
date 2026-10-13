from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle")
    page.wait_for_timeout(3000)
    
    res = page.evaluate("""() => {
        let el = document.querySelector('.ardp-page');
        let chain = [];
        while (el) {
            let cs = window.getComputedStyle(el);
            chain.push({
                tag: el.tagName,
                cls: el.className,
                w: el.offsetWidth,
                h: el.offsetHeight,
                display: cs.display,
                visibility: cs.visibility,
                position: cs.position
            });
            el = el.parentElement;
        }
        return chain;
    }""")
    for r in res:
        print(r)
    browser.close()
