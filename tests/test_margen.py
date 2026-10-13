"""Pruebas de regresión y control del módulo margen.py."""
import pytest
import pandas as pd
import numpy as np
from margen import leer_margenes, _sku_texto, _norm


def test_norm_headers():
    assert _norm("Comisión ") == "COMISION"
    assert _norm("Código 21") == "CODIGO 21"
    assert _norm("  RENT   FINAL  ") == "RENT FINAL"
    assert _norm(None) == ""


def test_sku_texto():
    assert _sku_texto(210114094.0) == "210114094"
    assert _sku_texto("210114094") == "210114094"
    assert _sku_texto(" 210114094 ") == "210114094"


def test_lectura_margenes_control_valores(path_costos):
    """Valida los 54 SKU y el SKU de control 210114094."""
    df = leer_margenes(path_costos)

    # El catálogo debe tener 54 SKU únicos
    assert len(df) == 54, f"Se esperaban 54 SKU, se encontraron {len(df)}"
    assert df["sku"].nunique() == 54

    # RENT entre 13,4% y 68,3%
    min_rent = df["margen_lista_%"].min()
    max_rent = df["margen_lista_%"].max()
    assert 13.4 <= min_rent <= 13.5, f"Min rent {min_rent} fuera de rango esperado [13.4, 13.5]"
    assert 68.3 <= max_rent <= 68.4, f"Max rent {max_rent} fuera de rango esperado [68.3, 68.4]"

    # SKU de control: 210114094
    sku_row = df[df["sku"] == "210114094"]
    assert len(sku_row) == 1, "No se encontró el SKU de control 210114094"
    r = sku_row.iloc[0]

    pv = float(r["precio_lista_cop"])
    costo_factor = float(r["costo_real_cop"])
    rent_calc = (1.0 - costo_factor / (pv / 1.19)) * 100

    assert pv == 109900.0, f"PV esperado 109.900, obtenido {pv}"
    assert pytest.approx(costo_factor, abs=0.01) == 48546.0, f"Costo con factor esperado 48.546, obtenido {costo_factor}"
    assert pytest.approx(r["margen_lista_%"], abs=0.01) == 47.43
    assert pytest.approx(rent_calc, abs=0.01) == 47.43


def test_calculo_margen_real_de_venta():
    """Valida la fórmula de margen real de venta:
    (precio pagado / 1.19 - costo_real * unidades) / (precio pagado / 1.19)."""
    precio_pagado = 109900.0  # Con IVA 19%
    costo_real = 48546.0
    unidades = 1

    ingreso_neto = precio_pagado / 1.19
    costo_total = costo_real * unidades
    margen_real = (ingreso_neto - costo_total) / ingreso_neto * 100

    assert pytest.approx(margen_real, abs=0.01) == 47.43

    # Caso con 5 unidades y descuento en precio (ej: 99.900 por unidad)
    precio_pagado_promo = 99900.0 * 5
    unidades_5 = 5
    ingreso_neto_5 = precio_pagado_promo / 1.19
    costo_total_5 = costo_real * unidades_5
    margen_real_5 = (ingreso_neto_5 - costo_total_5) / ingreso_neto_5 * 100

    # Margen real debe ser menor al de lista debido al descuento
    assert margen_real_5 < 47.43
    assert pytest.approx(margen_real_5, abs=0.01) == 42.18
