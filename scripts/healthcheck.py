"""Chequeo de salud del sistema (Healthcheck) para Finart S.A.S."""
import sys
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import DB_PATH, FILE_PPTO, FILE_COSTOS
from core.data.budget_loader import leer_presupuesto
from core.data.margin_loader import leer_margenes


def check_health():
    errores = []
    print("[HEALTHCHECK] Verificando componentes del dashboard...")

    # 1. Base de datos SQLite
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        tablas = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        con.close()
        for t_req in ["order_items", "stock_snapshots", "sync_state"]:
            if t_req not in tablas:
                errores.append(f"Falta tabla '{t_req}' en la base de datos.")
        print(f" - Base de datos ({DB_PATH.name}): OK (Tablas: {tablas})")
    except Exception as e:
        errores.append(f"Error conectando a SQLite: {e}")

    # 2. Archivo de presupuesto
    try:
        if FILE_PPTO.exists():
            df_p = leer_presupuesto(FILE_PPTO)
            print(f" - Presupuesto ({FILE_PPTO.name}): OK ({len(df_p)} períodos, Total: ${df_p['presupuesto_usd'].sum():,.0f} USD)")
        else:
            errores.append(f"No existe {FILE_PPTO}")
    except Exception as e:
        errores.append(f"Error leyendo {FILE_PPTO}: {e}")

    # 3. Archivo de costos
    try:
        if FILE_COSTOS.exists():
            df_m = leer_margenes(FILE_COSTOS)
            print(f" - Costos ({FILE_COSTOS.name}): OK ({len(df_m)} SKU analizados)")
        else:
            errores.append(f"No existe {FILE_COSTOS}")
    except Exception as e:
        errores.append(f"Error leyendo {FILE_COSTOS}: {e}")

    if errores:
        print("\n[FALLO] Se detectaron los siguientes problemas:")
        for err in errores:
            print(f" ❌ {err}")
        return 1

    print("\n[ÉXITO] Todos los subsistemas operan correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(check_health())
