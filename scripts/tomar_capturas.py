"""
Script final para capturar las 5 pestañas del dashboard FINART.
Corrige el problema de encoding en consola Windows.
"""
import sys
import io
import time
from pathlib import Path

# Forzar stdout a UTF-8 en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

OUTPUT_DIR = Path(__file__).parent.parent / "capturas"
OUTPUT_DIR.mkdir(exist_ok=True)

URL = "http://localhost:8501"

# Nombres limpios (sin emojis) para identificar cada pestaña
TABS = [
    ("Resumen",      "Resumen"),
    ("Presupuesto",  "Presupuesto"),
    ("Ventas",       "Ventas"),
    ("Productos",    "Productos"),
    ("Inventario",   "Inventario"),
]

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

def safe_print(*args):
    try:
        print(*args)
    except UnicodeEncodeError:
        cleaned = " ".join(str(a).encode('ascii', 'replace').decode('ascii') for a in args)
        print(cleaned)

def wait_for_streamlit_content(page, timeout_ms=50000):
    """Espera hasta que Streamlit haya renderizado contenido real."""
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        try:
            content_len = page.evaluate("""() => {
                const selectors = [
                    '[data-testid="stMainBlockContainer"]',
                    '[data-testid="stMain"]',
                    '.block-container',
                    '.main .block-container',
                    'section.main'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.length > 300) return el.innerText.length;
                }
                return document.body.innerText.length;
            }""")
            if content_len > 300:
                safe_print(f"    Contenido detectado: {content_len} chars")
                return True
        except Exception as e:
            pass
        time.sleep(1.5)
    return False

def click_tab_by_name(page, tab_name):
    """Hace clic en la pestaña con el nombre dado, sin usar print con emojis."""
    # Contar tabs disponibles
    try:
        count = page.locator('button[role="tab"]').count()
        safe_print(f"    Tabs con role=tab: {count}")
        for i in range(count):
            tab = page.locator('button[role="tab"]').nth(i)
            text = tab.inner_text()
            safe_print(f"      Tab {i}: texto={repr(text[:30])}")
            if tab_name.lower() in text.lower():
                tab.click()
                safe_print(f"    --> Clic en tab que contiene '{tab_name}'")
                return True
    except Exception as e:
        safe_print(f"    Error locator: {e}")

    # Estrategia JS
    result = page.evaluate(f"""() => {{
        const all = document.querySelectorAll('[role="tab"], button, [data-testid*="tab"] button');
        for (const el of all) {{
            const txt = (el.innerText || el.textContent || "").toLowerCase();
            if (txt.includes("{tab_name.lower()}")) {{
                el.click();
                return "JS-click-OK";
            }}
        }}
        return null;
    }}""")
    safe_print(f"    JS click result: {result}")
    return result is not None

def screenshot_all():
    safe_print(f"=== Iniciando capturas para {URL} ===")

    with sync_playwright() as p:
        browser = None
        for launch_args in [
            {"channel": "msedge", "headless": True},
            {"headless": True},
        ]:
            try:
                browser = p.chromium.launch(**launch_args)
                safe_print(f"  Navegador OK: {launch_args}")
                break
            except Exception as e:
                safe_print(f"  Fallo {launch_args}: {e}")

        if not browser:
            safe_print("ERROR: No se pudo lanzar navegador")
            return

        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        safe_print(f"Cargando {URL}...")
        try:
            page.goto(URL, wait_until="load", timeout=30000)
        except PWTimeout:
            safe_print("  Timeout en load — continuando de todas formas")

        safe_print("Esperando contenido de Streamlit...")
        loaded = wait_for_streamlit_content(page, timeout_ms=50000)
        safe_print(f"Contenido cargado: {loaded}")

        # Espera adicional para el primer tab (Presupuesto, activo por defecto)
        page.wait_for_timeout(3000)

        results = []
        for name, label in TABS:
            safe_print(f"\n--- Pestaña: {name} ---")
            clicked = click_tab_by_name(page, label)
            page.wait_for_timeout(3000)

            out_path = OUTPUT_DIR / f"tab_{name.lower()}.png"
            try:
                page.screenshot(path=str(out_path), full_page=True)
                size = out_path.stat().st_size
                safe_print(f"  Guardado: {out_path.name} ({size:,} bytes)")
                results.append((name, out_path, size, clicked))
            except Exception as e:
                safe_print(f"  ERROR screenshot: {e}")
                results.append((name, out_path, 0, clicked))

        browser.close()

        safe_print("\n=== RESUMEN ===")
        for name, path, size, clicked in results:
            status = "OK" if size > 50000 else "PEQUEÑA"
            click_info = "tab-OK" if clicked else "tab-FALLO"
            safe_print(f"  [{status}] {name}: {size:,} bytes | {click_info}")
        
        safe_print(f"\nCapturas en: {OUTPUT_DIR}")

if __name__ == "__main__":
    screenshot_all()
