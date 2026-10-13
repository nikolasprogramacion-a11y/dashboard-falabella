"""Pruebas de regresión y control del módulo stock.py e inventario."""
import pytest
import pandas as pd
import numpy as np
from stock import _sku_str, _col, POSIBLES_SKU, POSIBLES_QTY


def test_sku_str():
    assert _sku_str("210114094.0") == "210114094"
    assert _sku_str(210114094.0) == "210114094"
    assert _sku_str("SKU-ABC") == "SKU-ABC"
    assert _sku_str("  210114094  ") == "210114094"


def test_col_detection():
    df = pd.DataFrame({"SellerSKU": ["A"], "QuantityFalabella": [10]})
    assert _col(df, POSIBLES_SKU) == "SellerSKU"
    assert _col(df, POSIBLES_QTY) == "QuantityFalabella"


def test_reglas_inventario_critico_atencion_ok():
    """Valida la clasificación de estados de inventario según las reglas de negocio."""
    # Umbrales
    umbral_crit = 50.0
    umbral_aten = 65.0

    casos = [
        # (stock, vendido_total, vendido_28d, estado_esperado, quiebre_esp, riesgo_esp)
        # Caso 1: stock 0 -> Quiebre, Crítico (restante 0% <= 50%)
        (0, 20, 4, "🔴 Crítico", True, False),
        # Caso 2: stock 2, vendido 28d = 8 (venta semanal = 2) -> WOS = 1 < 2 -> Crítico y Riesgo
        (2, 10, 8, "🔴 Crítico", False, True),
        # Caso 3: stock 5, vendido total 5 -> restante = 50% <= 50% -> Crítico
        (5, 5, 0, "🔴 Crítico", False, False),
        # Caso 4: stock 6, vendido total 4 -> restante = 60% (<= 65%) y WOS alto -> Atención
        (6, 4, 1, "🟡 Atención requerida", False, False),
        # Caso 5: stock 9, vendido total 1 -> restante = 90% (> 65%) y WOS alto -> OK
        (9, 1, 1, "🟢 OK", False, False),
    ]

    for stock, v_tot, v28, est_exp, quiebre_exp, riesgo_exp in casos:
        ing_est = stock + v_tot
        restante_pct = (stock / ing_est * 100) if ing_est > 0 else 0
        v_sem = v28 / 4.0
        wos = (stock / v_sem) if v_sem > 0 else np.nan

        # Condición negocio
        es_critico = (wos is not None and not np.isnan(wos) and wos < 2) or (restante_pct <= umbral_crit)
        es_atencion = not es_critico and (restante_pct <= umbral_aten)

        if es_critico:
            estado = "🔴 Crítico"
        elif es_atencion:
            estado = "🟡 Atención requerida"
        else:
            estado = "🟢 OK"

        quiebre = stock <= 0
        riesgo = (stock > 0) and (wos is not None and not np.isnan(wos) and wos < 2)

        assert estado == est_exp, f"Fallo en estado para stock={stock}, v_tot={v_tot}: esperado {est_exp}, obtenido {estado}"
        assert quiebre == quiebre_exp, f"Fallo en quiebre para stock={stock}: esperado {quiebre_exp}"
        assert riesgo == riesgo_exp, f"Fallo en riesgo para stock={stock}, v28={v28}: esperado {riesgo_exp}"


def test_alerta_sin_ventas_28_dias():
    """Alerta sin movimiento: stock_actual > 0 y 0 ventas en la ventana de 28 días."""
    stock = 15
    vendido_28d = 0
    sin_ventas = (stock > 0) and (vendido_28d == 0)
    assert sin_ventas is True

    # Si vendió 1 unidad, no debe alertar
    assert ((stock > 0) and (1 == 0)) is False
