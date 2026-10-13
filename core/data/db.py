"""Manejo de base de datos SQLite optimizada con índices para ventas y stock."""
import os
import sqlite3
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from core.config import DB_PATH
from core.data.stock_loader import sku_valido


def init_db(db_path=DB_PATH):
    """Inicializa la base de datos SQLite y asegura los índices de rendimiento."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Tablas maestras
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        order_item_id TEXT PRIMARY KEY,
        order_id TEXT,
        created_at TEXT,
        updated_at TEXT,
        sku TEXT,
        producto TEXT,
        estado TEXT,
        precio_pagado REAL,
        precio_item REAL,
        envio REAL,
        moneda TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_snapshots (
        fecha TEXT,
        sku TEXT,
        cantidad INTEGER,
        PRIMARY KEY (fecha, sku)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_state (
        clave TEXT PRIMARY KEY,
        valor TEXT
    );
    """)

    # Índices clave para acelerar consultas con 3+ años de ventas
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_sku ON order_items (sku);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_created_at ON order_items (created_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_estado ON order_items (estado);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_snapshots_fecha ON stock_snapshots (fecha);")

    con.commit()
    con.close()


def datos_vacios():
    """Devuelve el esquema esperado sin generar datos comerciales ficticios."""
    return pd.DataFrame(columns=[
        "order_item_id", "order_id", "created_at", "updated_at", "sku",
        "producto", "estado", "precio_pagado", "precio_item", "envio", "moneda"
    ])

@st.cache_data(ttl=300, show_spinner=False)
def cargar_ventas(db_path=DB_PATH):
    """Carga los registros de order_items desde SQLite con caché optimizada."""
    if os.path.exists(db_path):
        con = sqlite3.connect(db_path)
        try:
            df = pd.read_sql("SELECT * FROM order_items", con)
        except Exception:
            df = pd.DataFrame()
        finally:
            con.close()
        if len(df):
            return df, False
    return datos_vacios(), True


def cargar_stock_historico(db_path=DB_PATH):
    """Recupera los snapshots históricos de stock."""
    if not os.path.exists(db_path):
        return pd.DataFrame(columns=["fecha", "sku", "cantidad"])
    con = sqlite3.connect(db_path)
    try:
        df = pd.read_sql("SELECT * FROM stock_snapshots ORDER BY fecha ASC", con)
    except Exception:
        df = pd.DataFrame(columns=["fecha", "sku", "cantidad"])
    finally:
        con.close()
    if len(df):
        df = df[df["sku"].apply(sku_valido).astype(bool) & df["cantidad"].notna()]
    return df


def guardar_stock(df_sku_cantidad, db_path=DB_PATH):
    """Inserta o actualiza el snapshot del día actual en la base de datos."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    hoy_str = str(date.today())
    filas = [(hoy_str, str(r["sku"]), int(r["cantidad"])) for _, r in df_sku_cantidad.iterrows()]
    cur.executemany("INSERT OR REPLACE INTO stock_snapshots (fecha, sku, cantidad) VALUES (?, ?, ?)", filas)
    con.commit()
    con.close()
