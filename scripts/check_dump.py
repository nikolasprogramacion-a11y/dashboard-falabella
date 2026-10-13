import re

with open("page_dump.html", "r", encoding="utf-8", errors="ignore") as f:
    html = f.read()

print("HTML length:", len(html))
print("stTabs in html:", "stTabs" in html)
print("ardp-header in html:", "ardp-header" in html)
print("finart-sidebar-brand in html:", "finart-sidebar-brand" in html)

# check for any error message
if "Traceback" in html:
    print("Found Traceback in HTML!")
    for m in re.finditer(r"Traceback.*?(?=\n\n|<)", html, re.DOTALL):
        print(m.group(0)[:500])
elif "Error" in html:
    print("Searching Error strings...")
    for m in re.finditer(r"[A-Za-z]+Error:.*?(?=\n|<)", html):
        print(m.group(0))

# print visible text fragments
matches = re.findall(r">([^<>]{4,80})<", html)
print("Visible text fragments count:", len(matches))
print("First 20 fragments:")
for m in matches[:20]:
    txt = m.strip()
    if txt:
        print("  -", txt)
