"""Benchmark de rendimiento: certifica que el procesamiento responda en <2 segundos con 3 años de ventas y 500 SKU."""
import os
import time
import tempfile
import sqlite3
import pandas as pd
import numpy as np
import pytest

from core.data.db import init_db
from dashboards.falabella.logic import (
    preparar,
    calcular_meses,
    calcular_metricas_cancelaciones,
    calcular_metricas_inventario,
)
from core.data.budget_loader import leer_presupuesto
from core.data.margin_loader import leer_margenes


def test_benchmark_3_anios_500_skus():
    """Genera 3 años de datos y 500 SKU para validar tiempo de respuesta < 2.0s."""
    rng = np.random.default_rng(42)
    fechas = pd.date_range("2024-01-01", "2026-12-31", freq="D")
    skus = [f"210{i:06d}" for i in range(500)]
    estados = ["delivered", "shipped", "canceled", "returned", "failed"]
    p_estados = [0.75, 0.15, 0.05, 0.03, 0.02]

    # Generar 40.000 items de venta
    n_records = 40000
    sample_fechas = rng.choice(fechas, size=n_records)
    sample_skus = rng.choice(skus, size=n_records)
    sample_estados = rng.choice(estados, size=n_records, p=p_estados)
    sample_precios = rng.choice([59900.0, 89900.0, 109900.0, 149900.0, 199900.0], size=n_records)
    sample_orders = [f"ORD_{rng.integers(100000, 120000)}" for _ in range(n_records)]

    df_ventas = pd.DataFrame({
        "order_item_id": [f"item_{i}" for i in range(n_records)],
        "order_id": sample_orders,
        "created_at": sample_fechas,
        "updated_at": sample_fechas,
        "sku": sample_skus,
        "producto": "Joyería Finart",
        "estado": sample_estados,
        "precio_pagado": sample_precios,
        "precio_item": sample_precios,
        "envio": 0.0,
        "moneda": "COP",
    })

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "benchmark.db")
        init_db(db_path)
        con = sqlite3.connect(db_path)
        df_ventas.to_sql("order_items", con, if_exists="append", index=False)
        con.close()

        # Inicio de medición de tiempo de ejecución
        t0 = time.perf_counter()

        # 1. Lectura desde SQLite
        con = sqlite3.connect(db_path)
        df_loaded = pd.read_sql("SELECT * FROM order_items", con)
        con.close()

        # 2. Preparar diario
        diario = preparar(df_loaded, ini=fechas.min(), fin=fechas.max())

        # 3. Presupuesto
        path_ppto = os.path.join(os.path.dirname(os.path.dirname(__file__)), "datos", "presupuesto.xlsx")
        ppto = leer_presupuesto(path_ppto)
        hoy = pd.Timestamp("2026-10-05")
        fx = 4000.0
        meses = calcular_meses(ppto, diario, fx, hoy)

        # 4. Cancelaciones
        cancel_info = calcular_metricas_cancelaciones(df_loaded, fx)

        # 5. Inventario simulado
        hist_stock = pd.DataFrame({
            "fecha": ["2026-10-05"] * 500,
            "sku": skus,
            "cantidad": rng.integers(0, 50, size=500),
        })
        tabla_inv, n_crit, n_sm, n_q, n_r, _ = calcular_metricas_inventario(hist_stock, df_loaded, [], hoy)

        t_total = time.perf_counter() - t0

        print(f"\n[BENCHMARK] Procesados {n_records:,} registros (3 años, 500 SKU) en {t_total:.3f} segundos.")
        assert t_total < 2.0, f"Tiempo de respuesta {t_total:.3f}s supera el umbral de 2.0s"
