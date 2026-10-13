"""Pruebas de regresión y control del módulo budget.py."""
import pytest
import pandas as pd
from budget import leer_presupuesto, periodo_a_fechas


def test_periodo_a_fechas():
    ini, fin = periodo_a_fechas("sep-26")
    assert ini == pd.Timestamp("2026-09-01")
    assert fin == pd.Timestamp("2026-09-30")

    ini2, fin2 = periodo_a_fechas("feb-28")
    assert ini2 == pd.Timestamp("2028-02-01")
    assert fin2 == pd.Timestamp("2028-02-29")  # Año bisiesto 2028


def test_lectura_presupuesto_control_valores(path_presupuesto):
    """Valida los valores reales del presupuesto ARDP 2026-2028."""
    df = leer_presupuesto(path_presupuesto)

    assert len(df) == 24, f"Se esperaban 24 meses, se leyeron {len(df)}"
    assert df["periodo"].iloc[0] == "sep-26"
    assert df["periodo"].iloc[-1] == "ago-28"

    # La hoja contiene una meta oficial anual separada de los valores mensuales.
    metas = df.attrs.get("metas_anuales", {})
    assert pytest.approx(metas[1], abs=0.01) == 1500000
    assert pytest.approx(metas[2], abs=0.01) == 4787723.076923077

    # Los valores mensuales se conservan exactamente como están documentados.
    p_dict = dict(zip(df["periodo"], df["presupuesto_usd"]))
    assert p_dict["sep-26"] == 0.0
    assert pytest.approx(p_dict["oct-26"], abs=0.01) == 2492.307692307692
    assert pytest.approx(p_dict["nov-26"], abs=0.01) == 32400
    assert pytest.approx(p_dict["dic-26"], abs=0.01) == 44861.53846153846

    # La suma mensual del Año 1 es distinta de la meta oficial del Año 1.
    # No se fuerza la distribución de la diferencia a ningún mes.
    suma_anio1 = sum(p_dict[m] for m in [
        "sep-26", "oct-26", "nov-26", "dic-26", "ene-27", "feb-27",
        "mar-27", "abr-27", "may-27", "jun-27", "jul-27", "ago-27"
    ])
    assert pytest.approx(suma_anio1, abs=0.01) == 1443046.1538461538

    # El Año 2 sí coincide con su suma mensual documentada.
    suma_anio2 = sum(p_dict[m] for m in [
        "sep-27", "oct-27", "nov-27", "dic-27", "ene-28", "feb-28",
        "mar-28", "abr-28", "may-28", "jun-28", "jul-28", "ago-28"
    ])
    assert pytest.approx(suma_anio2, abs=0.01) == 4787723.076923077


def test_trimestres_con_meses_especiales(path_presupuesto):
    """Q4 2026 tiene 4 meses y Q3 2028 tiene 2 meses."""
    df = leer_presupuesto(path_presupuesto)
    
    # Comprobar meses por trimestre
    q4_meses = df[df["trimestre"] == "Q4"]["periodo"].tolist()
    # sep-26, oct-26, nov-26, dic-26
    assert "sep-26" in q4_meses
    assert "dic-26" in q4_meses
    
    # El último trimestre en el Excel es Q3 con 2 meses (jul-28, ago-28)
    q3_final_meses = df[df["periodo"].isin(["jul-28", "ago-28"])]["trimestre"].tolist()
    assert all(t == "Q3" for t in q3_final_meses)
