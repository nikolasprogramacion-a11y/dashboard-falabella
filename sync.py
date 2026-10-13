"""Baja órdenes del Seller Center y las guarda en SQLite (incremental).

Uso:
    python sync.py                    # desde la última sincronización (o 30 días atrás)
    python sync.py --desde 2026-09-01 # forzar fecha de inicio
Se puede programar con cron / Programador de tareas cada hora o cada día.
"""
import argparse
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from falabella_client import FalabellaClient, normalizar_item

ESQUEMA = """
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id TEXT PRIMARY KEY, order_id TEXT, created_at TEXT, updated_at TEXT,
    sku TEXT, producto TEXT, estado TEXT,
    precio_pagado REAL, precio_item REAL, envio REAL, moneda TEXT
);
CREATE TABLE IF NOT EXISTS sync_state (clave TEXT PRIMARY KEY, valor TEXT);
"""
COLS = ["order_item_id", "order_id", "created_at", "updated_at", "sku", "producto",
        "estado", "precio_pagado", "precio_item", "envio", "moneda"]


def sincronizar(cliente, db_path, desde=None):
    inicio_corrida = datetime.now(timezone.utc)
    con = sqlite3.connect(db_path)
    con.executescript(ESQUEMA)
    if desde is None:
        fila = con.execute("SELECT valor FROM sync_state WHERE clave='last_sync'").fetchone()
        # Se resta 2 días: las órdenes cambian de estado (ej. se cancelan) después de crearse.
        desde = (datetime.fromisoformat(fila[0]) - timedelta(days=2)) if fila \
            else inicio_corrida - timedelta(days=30)
    ordenes = cliente.get_orders(updated_after=desde)
    n_items = 0
    for orden in ordenes:
        for it in cliente.get_order_items(orden["OrderId"]):
            fila = normalizar_item(it, orden)
            con.execute(
                f"INSERT OR REPLACE INTO order_items ({','.join(COLS)}) "
                f"VALUES ({','.join('?' * len(COLS))})",
                [fila[c] for c in COLS],
            )
            n_items += 1
    con.execute("INSERT OR REPLACE INTO sync_state VALUES ('last_sync', ?)",
                (inicio_corrida.isoformat(),))
    con.commit()
    con.close()
    return len(ordenes), n_items


if __name__ == "__main__":
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", help="YYYY-MM-DD")
    args = ap.parse_args()
    desde = datetime.fromisoformat(args.desde).replace(tzinfo=timezone.utc) if args.desde else None
    cli = FalabellaClient(os.environ["FALABELLA_USER_ID"], os.environ["FALABELLA_API_KEY"])
    n_ord, n_it = sincronizar(cli, os.getenv("DB_PATH", "ventas.db"), desde)
    print(f"Listo: {n_ord} órdenes, {n_it} ítems guardados.")
