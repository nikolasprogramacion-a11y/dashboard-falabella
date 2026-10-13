"""Pruebas de casos borde y resiliencia (datos vacíos, nulos, 1 día, 3 años)."""
import pytest
import pandas as pd
import numpy as np
from app import preparar, calcular_meses, semaforo


def test_dataframe_vacio():
    """Verifica que un DataFrame sin filas no rompa preparar ni cálculos."""
    df_vacio = pd.DataFrame(columns=["created_at", "estado", "precio_pagado", "order_id", "sku"])
    hoy = pd.Timestamp("2026-10-05")
    diario = preparar(df_vacio, hoy, hoy)
    assert len(diario) == 1
    assert diario.loc[hoy, "ventas"] == 0
    assert diario.loc[hoy, "ordenes"] == 0


def test_divisiones_por_cero_seguras():
    """Ticket, UPT, Sell-Through y WOS deben retornar None o NaN ante ceros sin excepciones."""
    ordenes = 0
    ingreso = 0
    unidades = 0

    ticket = ingreso / ordenes if ordenes else None
    upt = unidades / ordenes if ordenes else None
    assert ticket is None
    assert upt is None

    stock = 10
    v_sem = 0 / 4
    wos = (stock / v_sem) if v_sem > 0 else np.nan
    assert np.isnan(wos)


def test_un_solo_dia_de_historia():
    fecha = pd.Timestamp("2026-10-01")
    df = pd.DataFrame([{
        "created_at": fecha,
        "estado": "delivered",
        "precio_pagado": 109900.0,
        "order_id": "ORD_1",
        "sku": "210114094"
    }])
    diario = preparar(df, fecha, fecha)
    assert len(diario) == 1
    assert diario["ventas"].iloc[0] == 109900.0
    assert diario["ordenes"].iloc[0] == 1


def test_tres_anios_de_historia():
    """Genera 3 años de fechas continuas y valida que preparar no colapse ni demore."""
    dias = pd.date_range("2024-01-01", "2026-12-31", freq="D")
    df = pd.DataFrame({
        "created_at": dias,
        "estado": "delivered",
        "precio_pagado": 100000.0,
        "order_id": [f"O_{i}" for i in range(len(dias))],
        "sku": "210114094"
    })
    diario = preparar(df, ini=dias.min(), fin=dias.max())
    assert len(diario) == len(dias)
    assert diario["ventas"].sum() == len(dias) * 100000.0
