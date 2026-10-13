"""Enchufes para datos futuros sin inventar ni estimar información.

1. Fecha de salida al mercado: lee 'datos/ingresos.xlsx' (SKU, fecha, unidades). Si no existe, estado vacío claro.
2. Comisión real: parámetro configurable en entorno (.env) para referencia gerencial.
3. TRM histórica por fecha: función preparada para conversión día a día cuando se active.
"""
import os
import pandas as pd
import streamlit as st
from core.config import FILE_INGRESOS, COMISION_REAL_NEGOCIADA
from core.data.stock_loader import _sku_str, sku_valido


def leer_fechas_ingreso(path_archivo=FILE_INGRESOS):
    """Lee el archivo opcional datos/ingresos.xlsx para conocer la fecha real de lanzamiento al mercado."""
    if not os.path.exists(path_archivo):
        return None, "Archivo de fechas de ingreso ('datos/ingresos.xlsx') no detectado. Enchufe listo para cuando se suministre."

    try:
        df = pd.read_excel(path_archivo)
        # Normalizar columnas
        cols = {str(c).lower().strip(): c for c in df.columns}
        col_sku = next((cols[k] for k in ["sku", "sellersku", "codigo 21", "código 21"] if k in cols), None)
        col_fecha = next((cols[k] for k in ["fecha", "fecha_ingreso", "lanzamiento", "salida_mercado"] if k in cols), None)

        if not col_sku or not col_fecha:
            return None, "El archivo 'datos/ingresos.xlsx' no contiene columnas identificables de 'sku' y 'fecha'."

        out = pd.DataFrame({
            "sku": df[col_sku].apply(_sku_str),
            "fecha_ingreso": pd.to_datetime(df[col_fecha], errors="coerce"),
        })
        out = out[out["sku"].apply(sku_valido).astype(bool) & out["fecha_ingreso"].notna()]
        return out.drop_duplicates(subset="sku"), "Datos de ingreso al mercado cargados correctamente."
    except Exception as e:
        return None, f"Error al procesar 'datos/ingresos.xlsx': {e}"


def obtener_comision_configurada():
    """Retorna la comisión negociada del Seller Center si está definida en variables de entorno."""
    if COMISION_REAL_NEGOCIADA:
        try:
            return float(COMISION_REAL_NEGOCIADA)
        except ValueError:
            pass
    return None
