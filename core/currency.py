"""Gestión de tasa de cambio (TRM) USD/COP oficial y de respaldo."""
from datetime import date
import requests
import streamlit as st
from core.config import DEFAULT_FX_USD_COP


@st.cache_data(ttl=3600)
def obtener_trm_actual():
    """Consulta la TRM oficial del día.
    1) API oficial de datos abiertos del gobierno colombiano (datos.gov.co, dataset 32sa-8pi3).
    2) Respaldo internacional open.er-api.com.
    3) Tasa configurada de respaldo si ambas fallan.
    """
    hoy_iso = date.today().isoformat()
    try:
        url = "https://www.datos.gov.co/resource/32sa-8pi3.json"
        params = {
            "$where": f"vigenciadesde <= '{hoy_iso}T00:00:00.000'",
            "$order": "vigenciadesde DESC",
            "$limit": 1,
        }
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if data and "valor" in data[0]:
            return (
                float(data[0]["valor"]),
                "TRM Oficial (Superfinanciera / datos.gov.co)",
                data[0]["vigenciadesde"][:10],
            )
    except Exception:
        pass

    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if "rates" in data and "COP" in data["rates"]:
            return (
                float(data["rates"]["COP"]),
                "Mercado de divisas (open.er-api.com)",
                hoy_iso,
            )
    except Exception:
        pass

    return (
        DEFAULT_FX_USD_COP,
        "Tasa de respaldo predeterminada",
        hoy_iso,
    )


@st.cache_data(ttl=86400)
def obtener_trm_historica(fecha_str):
    """Consulta la TRM oficial para una fecha histórica específica (YYYY-MM-DD)."""
    try:
        url = "https://www.datos.gov.co/resource/32sa-8pi3.json"
        params = {
            "$where": f"vigenciadesde <= '{fecha_str}T00:00:00.000'",
            "$order": "vigenciadesde DESC",
            "$limit": 1,
        }
        resp = requests.get(url, params=params, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        if data and "valor" in data[0]:
            return float(data[0]["valor"])
    except Exception:
        pass
    return None
