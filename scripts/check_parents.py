from bs4 import BeautifulSoup

with open("page_dump.html", "r", encoding="utf-8", errors="ignore") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

h = soup.find(class_=lambda c: c and ("ardp-page" in c or "ardp-header" in c))
if h:
    print("Found header element:", h.name, h.get("class"))
    curr = h
    while curr:
        print("  -> Parent:", curr.name, curr.get("class"), curr.get("data-testid"))
        curr = curr.parent
else:
    print("Header element not found!")
