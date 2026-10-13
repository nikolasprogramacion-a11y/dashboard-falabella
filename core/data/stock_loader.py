"""Lee el archivo de stock que se descarga manualmente del Seller Center
(pestaña 'Stock' -> 'Descargar todo'). Solo se confía en el SKU y la
cantidad: las demás columnas (bodega, nombre...) pueden cambiar de un
archivo a otro y no se usan.
"""
import pandas as pd
import numpy as np

POSIBLES_SKU = ["sellersku", "seller_sku", "sku vendedor", "sku", "codigo 21", "código 21"]
POSIBLES_QTY = ["quantityfalabella", "inventario disponible", "quantity", "cantidad", "stock"]
SKU_NULOS = {"", "nan", "none", "null", "<na>", "nat"}


def _col(df, posibles):
    cols = {c.lower().strip(): c for c in df.columns}
    for p in posibles:
        if p in cols:
            return cols[p]
    for key, original in cols.items():
        if any(p in key for p in posibles):
            return original
    return None


def _sku_str(x):
    """Excel guarda los SKU numéricos con decimales (210114094 -> 210114094.0).
    Esto los deja como texto limpio, sin ese '.0' de más."""
    if x is None:
        return ""
    try:
        f = float(x)
        if f.is_integer():
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return str(x).strip()


def sku_valido(v):
    """False si el SKU viene vacío o nulo (None, NaN, 'nan', 'None', etc.)."""
    return v is not None and str(v).strip().lower() not in SKU_NULOS


def leer_stock_manual(path_o_buffer, nombre_archivo=""):
    if str(nombre_archivo).lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path_o_buffer)
    else:
        df = pd.read_csv(path_o_buffer)
    col_sku = _col(df, POSIBLES_SKU)
    col_qty = _col(df, POSIBLES_QTY)
    if col_sku is None or col_qty is None:
        raise ValueError(f"No encontré columnas de SKU/cantidad. Columnas: {list(df.columns)}")
    out = df[[col_sku, col_qty]].copy()
    out.columns = ["sku", "cantidad"]
    out["sku"] = out["sku"].apply(_sku_str)
    out["cantidad"] = pd.to_numeric(out["cantidad"], errors="coerce").fillna(0).astype(int)
    return out.groupby("sku", as_index=False)["cantidad"].sum()


def limpiar_stock(df_sku_cantidad):
    """Deja solo las filas con SKU y cantidad válidos (las demás se omiten)."""
    d = df_sku_cantidad.copy()
    d["cantidad"] = pd.to_numeric(d["cantidad"], errors="coerce")
    ok = d["sku"].apply(sku_valido).astype(bool) & d["cantidad"].notna()
    d = d[ok].copy()
    d["cantidad"] = d["cantidad"].astype(int)
    return d
