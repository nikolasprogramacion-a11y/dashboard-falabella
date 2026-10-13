"""Script para automatizar la captura de pantallas en 1440px, 1024px y 390px."""
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "docs" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RESOLUCIONES = [
    ("desktop_1440", 1440, 900),
    ("tablet_1024", 1024, 768),
    ("mobile_390", 390, 844),
]

PESTANAS = [
    ("resumen", 0),
    ("presupuesto", 1),
    ("ventas", 2),
    ("productos", 3),
    ("inventario", 4),
]


def capturar_todas():
    print(f"[SCREENSHOTS] Guardando capturas en {OUTPUT_DIR}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        for res_nombre, ancho, alto in RESOLUCIONES:
            print(f"\n--- Probando resolución {res_nombre} ({ancho}x{alto}) ---")
            context = browser.new_context(
                viewport={"width": ancho, "height": alto},
                device_scale_factor=2,
            )
            page = context.new_page()
            page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Si pide contraseña
            if page.locator("input[type='password']").count() > 0:
                print("Detectada pantalla de login, ingresando...")
                page.fill("input[type='password']", os.getenv("DASHBOARD_PASSWORD", "cambia_esta_clave_segura_2026"))
                page.keyboard.press("Enter")
                time.sleep(3)

            # En mobile (390px), si la barra lateral está abierta, cerrarla
            if ancho <= 640:
                btn_close = page.locator("button[data-testid='stSidebarCollapseButton']")
                if btn_close.count() > 0:
                    try:
                        btn_close.click()
                        time.sleep(1)
                    except Exception:
                        pass

            for tab_id, tab_idx in PESTANAS:
                try:
                    tabs = page.locator("[role='tab']")
                    if tabs.count() > tab_idx:
                        tabs.nth(tab_idx).click(force=True)
                        time.sleep(2)
                        try:
                            # Esperar que desaparezca el indicador de "Running"
                            page.locator("div:has-text('Running...')").wait_for(state="detached", timeout=5000)
                        except Exception:
                            pass
                        time.sleep(2.5)

                    archivo_salida = OUTPUT_DIR / f"{tab_id}_{res_nombre}.png"
                    page.screenshot(path=str(archivo_salida), full_page=False)
                    print(f" [OK] Capturado: {archivo_salida.name} ({ancho}px)")
                except Exception as e:
                    print(f" [ERROR] Error capturando tab {tab_id}: {e}")

            context.close()
        browser.close()
    print("\n[ÉXITO] Todas las capturas generadas correctamente.")


if __name__ == "__main__":
    capturar_todas()
