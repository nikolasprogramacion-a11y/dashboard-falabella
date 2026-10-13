"""Configuración de tema y generadores de gráficas Altair unificados para Finart."""
import altair as alt
import pandas as pd
import streamlit as st
from core.config import FINART_PALETTE

# Tema institucional Finart para Altair
FINART_ALTAIR_THEME = {
    "config": {
        "font": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "view": {"stroke": "transparent"},
        "axis": {
            "labelColor": "#64748B",
            "titleColor": "#0F172A",
            "gridColor": "#F1F5F9",
            "domainColor": "#CBD5E1",
            "tickColor": "#CBD5E1",
            "labelFontSize": 11,
            "titleFontSize": 12,
            "titleFontWeight": 600,
        },
        "legend": {
            "labelColor": "#475569",
            "titleColor": "#0F172A",
            "labelFontSize": 11,
            "titleFontSize": 12,
            "titleFontWeight": 600,
        },
        "range": {
            "category": [
                FINART_PALETTE["navy_primary"],
                FINART_PALETTE["gold_primary"],
                FINART_PALETTE["semantic_green"],
                FINART_PALETTE["semantic_amber"],
                FINART_PALETTE["semantic_red"],
                "#6366F1",
                "#EC4899",
            ]
        },
    }
}


def registrar_tema_altair():
    try:
        if hasattr(alt, "theme") and hasattr(alt.theme, "register"):
            alt.theme.register("finart_theme", lambda: FINART_ALTAIR_THEME, enable=True)
        elif hasattr(alt, "themes") and hasattr(alt.themes, "register"):
            alt.themes.register("finart_theme", lambda: FINART_ALTAIR_THEME)
            alt.themes.enable("finart_theme")
    except Exception:
        pass


def mostrar(grafico):
    """Renderiza una gráfica Altair adaptativa en el contenedor."""
    try:
        try:
            st.altair_chart(grafico, width="stretch")
        except TypeError:
            st.altair_chart(grafico, use_container_width=True)
    except Exception as e:
        st.warning(f"No fue posible renderizar la gráfica: {e}")


def grafico_meta_real(datos, x, orden):
    """Barra ancha gris = meta; barra angosta institucional = lo vendido."""
    base = alt.Chart(datos).encode(
        x=alt.X(f"{x}:N", sort=orden, title=None, axis=alt.Axis(labelAngle=0))
    )
    meta = base.mark_bar(size=44, color="#E2E8F0", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        y=alt.Y("Meta:Q", title="US$"),
        tooltip=[
            x,
            alt.Tooltip("Meta:Q", title="Meta (US$)", format=",.0f"),
            alt.Tooltip("Real:Q", title="Real (US$)", format=",.0f"),
        ],
    )
    real = base.mark_bar(size=20, color=FINART_PALETTE["navy_primary"], cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        y="Real:Q"
    )
    return (meta + real).properties(height=280)


def barras_simple(datos, x, y, orden, color=FINART_PALETTE["navy_primary"], alto=240, titulo_y="US$"):
    """Barras comparativas limpias con tooltips formateados."""
    return (
        alt.Chart(datos)
        .mark_bar(color=color, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(f"{x}:N", sort=orden, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{y}:Q", title=titulo_y),
            tooltip=[x, alt.Tooltip(f"{y}:Q", title=titulo_y, format=",.0f")],
        )
        .properties(height=alto)
    )


def grafico_diario(datos, meta_dia):
    """Ventas diarias frente a meta diaria promedio (línea de referencia dorada/roja)."""
    barras = (
        alt.Chart(datos)
        .mark_bar(color=FINART_PALETTE["navy_primary"], cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("Fecha:T", title=None, axis=alt.Axis(format="%d-%b")),
            y=alt.Y("Real:Q", title="US$"),
            tooltip=[
                alt.Tooltip("Fecha:T", title="Fecha", format="%d-%b"),
                alt.Tooltip("Real:Q", title="Venta (US$)", format=",.0f"),
            ],
        )
    )
    linea = (
        alt.Chart(pd.DataFrame({"y": [meta_dia]}))
        .mark_rule(color=FINART_PALETTE["semantic_red"], strokeDash=[6, 4], strokeWidth=2)
        .encode(y="y:Q", tooltip=[alt.Tooltip("y:Q", title="Meta Diaria Promedio", format=",.0f")])
    )
    return (barras + linea).properties(height=280)
