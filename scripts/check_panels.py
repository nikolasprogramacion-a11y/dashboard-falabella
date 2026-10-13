import sys
from bs4 import BeautifulSoup

with open("page_dump.html", "r", encoding="utf-8", errors="ignore") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

panels = soup.find_all(attrs={"data-testid": "stTabPanel"})
print("Found tab panels:", len(panels))
for i, p in enumerate(panels):
    texts = [t.strip() for t in p.stripped_strings if len(t.strip()) > 2]
    # safe print without cp1252 crash
    txt_out = " | ".join(texts[:10])
    sys.stdout.buffer.write(f"Panel {i}: count={len(texts)} -> {txt_out}\n".encode("utf-8", "ignore"))
