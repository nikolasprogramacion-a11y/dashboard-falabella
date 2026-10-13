from bs4 import BeautifulSoup

with open("page_dump.html", "r", encoding="utf-8", errors="ignore") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

tabs_div = soup.find(attrs={"data-testid": "stTabs"})
if tabs_div:
    print("Found stTabs element!")
    print("Children:", [c.name for c in tabs_div.children if c.name])
    tablist = tabs_div.find(attrs={"role": "tablist"})
    if tablist:
        print("Found tablist! Children:", len(tablist.contents))
        for btn in tablist.find_all(True):
            print("  - tag:", btn.name, "role:", btn.get("role"), "text:", btn.get_text())
    else:
        print("tablist NOT found inside stTabs!")
        print("stTabs inner HTML preview:", str(tabs_div)[:500])
else:
    print("stTabs NOT found in page_dump.html!")
