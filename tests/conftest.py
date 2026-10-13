"""Configuración de pytest y fixtures compartidos."""
import os
import sys
import pytest
import pandas as pd
import numpy as np

# Asegurar que el directorio raíz del proyecto esté en sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

@pytest.fixture
def datos_dir():
    return os.path.join(BASE_DIR, "datos")

@pytest.fixture
def path_presupuesto(datos_dir):
    return os.path.join(datos_dir, "presupuesto.xlsx")

@pytest.fixture
def path_costos(datos_dir):
    return os.path.join(datos_dir, "costos.xlsx")

@pytest.fixture
def df_ordenes_sintetico():
    """Genera un DataFrame de prueba con casos representativos de ventas y cancelaciones."""
    fechas = pd.date_range("2026-09-01", "2026-09-30", freq="D")
    filas = []
    skus = ["210114094", "210114099", "210114101", None, "nan", "210114094"]
    estados = ["delivered", "shipped", "canceled", "returned", "failed", "delivered"]
    precios = [109900.0, 59900.0, 89900.0, 109900.0, 89900.0, 109900.0]
    
    order_id = 1000
    for i, fecha in enumerate(fechas):
        idx = i % len(skus)
        filas.append({
            "order_item_id": f"item_{i}",
            "order_id": f"ORD_{order_id}",
            "created_at": fecha.strftime("%Y-%m-%d %H:%M:%S"),
            "sku": skus[idx],
            "producto": f"Producto {idx}",
            "estado": estados[idx],
            "precio_pagado": precios[idx],
            "moneda": "COP"
        })
        order_id += 1
    return pd.DataFrame(filas)
