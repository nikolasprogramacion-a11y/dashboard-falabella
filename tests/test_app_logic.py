"""Pruebas de regresión para la lógica de negocio central (preparar, semáforos, cancelaciones, rankings)."""
import pytest
import pandas as pd
import numpy as np
from datetime import date

# Importar funciones de app.py
from app import (
    preparar,
    calcular_meses,
    semaforo,
    sku_valido,
    limpiar_stock,
    EXCLUIDOS,
    SEMAFORO_VERDE,
    SEMAFORO_AMARILLO,
)


def test_sku_valido():
    assert sku_valido("210114094") is True
    assert sku_valido(210114094) is True
    assert sku_valido("") is False
    assert sku_valido("nan") is False
    assert sku_valido("None") is False
    assert sku_valido("null") is False
    assert sku_valido(None) is False
    assert sku_valido(np.nan) is False


def test_limpiar_stock():
    df_raw = pd.DataFrame({
        "sku": ["210114094", "", "nan", None, "210114099", "210114101"],
        "cantidad": ["15", "10", 5, 8, "invalido", 20]
    })
    limpio = limpiar_stock(df_raw)
    assert len(limpio) == 2
    assert list(limpio["sku"]) == ["210114094", "210114101"]
    assert list(limpio["cantidad"]) == [15, 20]


def test_preparar_exclusion_estados():
    """Verifica que 'canceled', 'cancelled', 'failed', 'returned' se excluyan de las ventas."""
    fechas = ["2026-09-01", "2026-09-01", "2026-09-01", "2026-09-02"]
    estados = ["delivered", "canceled", "returned", "shipped"]
    precios = [100000.0, 50000.0, 30000.0, 200000.0]
    order_ids = ["O1", "O2", "O3", "O4"]

    df = pd.DataFrame({
        "created_at": fechas,
        "estado": estados,
        "precio_pagado": precios,
        "order_id": order_ids
    })

    diario = preparar(df, pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-02"))
    
    # 2026-09-01 solo debe sumar O1 (100.000)
    assert diario.loc[pd.Timestamp("2026-09-01"), "ventas"] == 100000.0
    assert diario.loc[pd.Timestamp("2026-09-01"), "ordenes"] == 1

    # 2026-09-02 debe sumar O4 (200.000)
    assert diario.loc[pd.Timestamp("2026-09-02"), "ventas"] == 200000.0
    assert diario.loc[pd.Timestamp("2026-09-02"), "ordenes"] == 1


def test_semaforo_logica():
    assert semaforo(100, 100, 200) == "🟢 En ritmo"
    assert semaforo(120, 100, 200) == "🟢 En ritmo"
    assert semaforo(85, 100, 200) == "🟡 Atención requerida"
    assert semaforo(79, 100, 200) == "🔴 Atrasado"
    assert semaforo(0, 0, 0) == "⚪ Sin meta"
    assert semaforo(50, 0, 100) == "⚪ Por iniciar"


def test_calcular_meses_distribucion_diaria():
    ppto = pd.DataFrame([
        {"periodo": "sep-26", "trimestre": "Q4", "presupuesto_usd": 3000.0},
        {"periodo": "oct-26", "trimestre": "Q4", "presupuesto_usd": 3100.0},
    ])
    # Sep tiene 30 días, meta diaria = 100 USD/día
    # Oct tiene 31 días, meta diaria = 100 USD/día
    hoy = pd.Timestamp("2026-09-15")  # Día 15 de septiembre
    fx = 4000.0

    # Crear ventas diarias simuladas: 15 días con 400.000 COP cada uno = 100 USD/día -> Total 1500 USD
    dias = pd.date_range("2026-09-01", "2026-09-15")
    diario = pd.DataFrame({"ventas": [400000.0] * 15, "ordenes": [2] * 15}, index=dias)

    res = calcular_meses(ppto, diario, fx, hoy)
    assert len(res) == 2

    fila_sep = res[res["periodo"] == "sep-26"].iloc[0]
    assert fila_sep["estado"] == "En curso"
    assert fila_sep["meta"] == 3000.0
    assert pytest.approx(fila_sep["real"], abs=0.1) == 1500.0
    # Esperado al día 15 de 30 días = 1500 USD
    assert pytest.approx(fila_sep["esperado"], abs=0.1) == 1500.0
    assert fila_sep["semaforo"] == "🟢 En ritmo"

    # Octubre está por iniciar
    fila_oct = res[res["periodo"] == "oct-26"].iloc[0]
    assert fila_oct["estado"] == "Por iniciar"
    assert fila_oct["real"] == 0.0
    assert fila_oct["esperado"] == 0.0
    assert fila_oct["semaforo"] == "⚪ Por iniciar"


def test_cancelaciones_y_devoluciones_metricas(df_ordenes_sintetico):
    """Prueba el cálculo de la tasa de cancelación, valor no vendido y desglose."""
    fx = 4000.0
    df = df_ordenes_sintetico.copy()
    estado_min = df["estado"].fillna("").str.lower()
    excl = df[estado_min.isin(EXCLUIDOS)]

    pedidos_total = df["order_id"].nunique()
    pedidos_cancelados = excl["order_id"].nunique()
    tasa_cancel = pedidos_cancelados / pedidos_total * 100

    # En df_ordenes_sintetico hay 30 pedidos, de los cuales varios están en canceled, returned o failed
    assert pedidos_cancelados > 0
    assert 0 < tasa_cancel < 100

    # Valor no vendido con IVA convertido a dólares
    valor_no_vendido_usd = excl["precio_pagado"].sum() / fx
    assert valor_no_vendido_usd > 0
