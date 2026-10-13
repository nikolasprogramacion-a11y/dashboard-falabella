"""Script de respaldo automático para Finart S.A.S.
Respalda ventas.db y la carpeta datos/ en un archivo ZIP con marca de tiempo.
Mantiene una política de retención de los últimos 30 días.
"""
import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUPS_DIR = BASE_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
DATOS_DIR = BASE_DIR / "datos"
DB_FILE = BASE_DIR / "ventas.db"
DIAS_RETENCION = 30


def crear_respaldo():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = BACKUPS_DIR / f"finart_respaldo_{timestamp}.zip"
    print(f"[{datetime.now().isoformat()}] Creando respaldo en: {zip_path.name}...")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Respaldar base de datos si existe
        if DB_FILE.exists():
            zipf.write(DB_FILE, arcname="ventas.db")
            print(f" - Agregado: ventas.db ({DB_FILE.stat().st_size:,} bytes)")
        else:
            print(" - Aviso: ventas.db no existe aún.")

        # Respaldar carpeta datos
        if DATOS_DIR.exists():
            for root, _, files in os.walk(DATOS_DIR):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(BASE_DIR)
                    zipf.write(full_p, arcname=str(rel_p))
                    print(f" - Agregado: {rel_p}")

    print(f"[{datetime.now().isoformat()}] Respaldo completado exitosamente: {zip_path}")
    limpiar_respaldos_antiguos()


def limpiar_respaldos_antiguos():
    limite = datetime.now() - timedelta(days=DIAS_RETENCION)
    eliminados = 0
    for archivo in BACKUPS_DIR.glob("finart_respaldo_*.zip"):
        try:
            mtime = datetime.fromtimestamp(archivo.stat().st_mtime)
            if mtime < limite:
                archivo.unlink()
                eliminados += 1
                print(f" - Eliminado por retención (>30 días): {archivo.name}")
        except Exception as e:
            print(f" - Error al evaluar archivo {archivo.name}: {e}")
    if eliminados:
        print(f"Se depuraron {eliminados} respaldos antiguos.")


if __name__ == "__main__":
    crear_respaldo()
