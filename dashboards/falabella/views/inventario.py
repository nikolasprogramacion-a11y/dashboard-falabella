"""Vista Inventario: Sell-Through, semanas de stock (WOS), quiebres y alertas operativas."""
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from core.config import UMBRAL_CRITICO, UMBRAL_ATENCION, DIAS_SIN_VENTAS, FINART_PALETTE
from core.data.stock_loader import leer_stock_manual, limpiar_stock
from core.data.db import guardar_stock
from core.ui import kpi_card, tarjeta_inventario, descargar_dataframe
from core.charts import mostrar
from dashboards.falabella.future_plugs import leer_fechas_ingreso


def render_inventario(context):
    """Renderiza la pestaña de Inventario con carga manual y cálculo de riesgos."""
    hist = context.get("hist")
    tabla_inv = context.get("tabla_inv")
    n_criticos = context.get("n_criticos")
    n_sin_mov = context.get("n_sin_mov")
    n_quiebre = context.get("n_quiebre")
    n_riesgo = context.get("n_riesgo")
    dias_desde_carga = context.get("dias_desde_carga")
    etiquetas_sku = context.get("etiquetas_sku", {})
    hoy = context.get("hoy")

    st.subheader("Control de Inventario y Abastecimiento (Carga Manual)")
    st.caption("Suba el archivo de stock descargado del Seller Center (pestaña 'Stock' -> 'Descargar todo'). Solo se utiliza SKU y cantidad.")

    archivo_stock = st.file_uploader("Actualizar archivo de stock (.csv o .xlsx)", type=["csv", "xlsx"], key="uploader_stock_file")
    if archivo_stock is not None:
        try:
            nuevo = leer_stock_manual(archivo_stock, archivo_stock.name)
            limpio = limpiar_stock(nuevo)
            guardar_stock(limpio)
            omitidas = len(nuevo) - len(limpio)
            st.success(f"Inventario actualizado: {len(limpio)} SKUs guardados con fecha de hoy." + (f" Se omitieron {omitidas} filas sin SKU o sin cantidad válida." if omitidas else ""))
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Error al procesar el archivo de stock: {e}")

    # Enchufe de datos futuros: fecha de salida al mercado
    with st.expander("🔌 Enchufe: Fechas de Salida al Mercado / Lote (datos/ingresos.xlsx)"):
        df_ingresos, msg_ingresos = leer_fechas_ingreso()
        if df_ingresos is not None and not df_ingresos.empty:
            st.success(msg_ingresos)
            st.dataframe(df_ingresos, width="stretch", hide_index=True)
        else:
            st.info(f"ℹ️ {msg_ingresos}")

    if hist is None or hist.empty or tabla_inv is None or tabla_inv.empty:
        st.info("Aún no se ha registrado ningún snapshot de inventario. Suba un archivo para habilitar las métricas de Sell-Through y Semanas de Stock.")
        return

    # Mensaje de frescura de inventario
    ultimo_dia = hist["fecha"].max()
    if dias_desde_carga >= 14:
        st.error(f"⚠️ El stock lleva **{dias_desde_carga} días sin actualizarse** (última carga: {ultimo_dia}). Las semanas de stock y sell-through pueden diferir de la realidad.")
    elif dias_desde_carga >= 7:
        st.warning(f"🔔 El stock lleva **{dias_desde_carga} días sin actualizarse** (última carga: {ultimo_dia}). Se recomienda subir un archivo nuevo pronto.")
    else:
        st.success(f"✅ Stock al día (actualizado hace {dias_desde_carga} día(s), última carga: {ultimo_dia}).")

    # Resumen visual
    st.markdown("**Resumen de Inventario**")
    ing_est = tabla_inv["ingresado_estimado"].sum()
    st_prom = (tabla_inv["vendido_total"].sum() / ing_est * 100.0) if ing_est else 0.0

    k = st.columns(5)
    tarjeta_inventario(k[0], FINART_PALETTE["semantic_green"], "SKUs Estado OK", int((tabla_inv["estado"] == "🟢 OK").sum()), "Inventario >65% restante y semanas de stock saludables.")
    tarjeta_inventario(k[1], FINART_PALETTE["semantic_amber"], f"Atención (Queda ≤{UMBRAL_ATENCION:.0f}%)", int((tabla_inv["estado"] == "🟡 Atención requerida").sum()), "Inventario restante entre 51% y 65%.")
    tarjeta_inventario(k[2], FINART_PALETTE["semantic_red"], f"Críticos (≤{UMBRAL_CRITICO:.0f}% o WOS < 2)", n_criticos, "Riesgo inminente de agotamiento.")
    tarjeta_inventario(k[3], FINART_PALETTE["semantic_gray"], f"Sin ventas ({DIAS_SIN_VENTAS}d)", n_sin_mov, "Con stock disponible pero cero ventas en 28 días.")
    tarjeta_inventario(k[4], FINART_PALETTE["navy_primary"], "Sell-Through Promedio", f"{st_prom:.0f}%", "Unidades vendidas ÷ Ingresadas estimadas.")

    # Alerta de quiebre de stock
    st.divider()
    st.markdown("### ⚠️ Alerta de Quiebre y Riesgo de Stock")
    qa = st.columns(3)
    with qa[0]:
        kpi_card(st, "SKUs en quiebre (Stock 0)", n_quiebre, help_text="Agotados completamente.")
    with qa[1]:
        kpi_card(st, "SKUs en riesgo (< 2 semanas)", n_riesgo, help_text="Se agotarán en menos de 14 días al ritmo actual.")
    with qa[2]:
        kpi_card(st, "SKUs con stock disponible", int((tabla_inv["stock_actual"] > 0).sum()))

    quiebre = tabla_inv["stock_actual"] <= 0
    riesgo = (~quiebre) & (tabla_inv["semanas_de_stock"] < 2)
    en_alerta = tabla_inv[quiebre | riesgo][["stock_actual", "vendido_28d", "semanas_de_stock"]].copy()
    en_alerta["situación"] = np.where(en_alerta["stock_actual"] <= 0, "🔴 Quiebre", "🟡 Riesgo de quiebre")
    
    if len(en_alerta):
        en_alerta_m = en_alerta.reset_index()
        en_alerta_m["producto"] = en_alerta_m["sku"].map(lambda s: etiquetas_sku.get(s, s))
        st.dataframe(
            en_alerta_m[["producto", "stock_actual", "vendido_28d", "semanas_de_stock", "situación"]]
            .rename(columns={
                "producto": "Producto",
                "stock_actual": "Stock",
                "vendido_28d": "Vendido 28d",
                "semanas_de_stock": "Semanas de Stock (WOS)",
                "situación": "Situación",
            })
            .sort_values("Semanas de Stock (WOS)")
            .style.format({"Semanas de Stock (WOS)": "{:.1f}"}, na_rep="-"),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No hay SKUs en quiebre ni en riesgo de quiebre.")

    # Tabla maestra de inventario
    st.divider()
    st.markdown("### 📋 Matriz Detallada de Inventario")
    tabla_mostrar = tabla_inv[[
        "stock_actual", "vendido_total", "inventario_restante_%", "sell_through_%",
        "semanas_de_stock", "dias_en_inventario", "estado", "alerta_movimiento"
    ]].reset_index()
    tabla_mostrar["producto"] = tabla_mostrar["sku"].map(lambda s: etiquetas_sku.get(s, s))

    tabla_final = tabla_mostrar[[
        "producto", "stock_actual", "vendido_total", "inventario_restante_%", "sell_through_%",
        "semanas_de_stock", "dias_en_inventario", "estado", "alerta_movimiento"
    ]].rename(columns={
        "producto": "Producto",
        "stock_actual": "Stock Actual",
        "vendido_total": "Venta Histórica",
        "inventario_restante_%": "Inv. Restante %",
        "sell_through_%": "Sell-Through %",
        "semanas_de_stock": "WOS (Semanas)",
        "dias_en_inventario": "Días en Inv.",
        "estado": "Estado",
        "alerta_movimiento": "Alerta Movimiento",
    }).sort_values("Inv. Restante %")

    st.dataframe(
        tabla_final.style.format({
            "Inv. Restante %": "{:.0f}%",
            "Sell-Through %": "{:.0f}%",
            "WOS (Semanas)": "{:.1f}",
            "Días en Inv.": "{:.0f}",
        }, na_rep="-"),
        width="stretch",
        hide_index=True,
    )
    descargar_dataframe(tabla_final, "inventario_falabella", "Descargar Inventario")

    # Gráfica de barras de inventario restante
    ch = tabla_inv.reset_index()
    ch["restante"] = ch["inventario_restante_%"].astype(float)
    ch["nivel"] = ch["estado"].map({
        "🔴 Crítico": "Crítico",
        "🟡 Atención requerida": "Atención requerida",
        "🟢 OK": "OK",
    })
    ch["producto"] = ch["sku"].map(lambda s: etiquetas_sku.get(s, s))

    if len(ch) > 40:
        ch = ch.nsmallest(40, "restante")
    orden_i = list(ch.sort_values("restante")["sku"])

    barras_i = (
        alt.Chart(ch)
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
        .encode(
            x=alt.X("sku:N", sort=orden_i, title=None, axis=alt.Axis(labelAngle=-90)),
            y=alt.Y("restante:Q", title="% de inventario restante", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "nivel:N",
                legend=alt.Legend(title=None, orient="bottom"),
                scale=alt.Scale(
                    domain=["Crítico", "Atención requerida", "OK"],
                    range=[FINART_PALETTE["semantic_red"], FINART_PALETTE["semantic_amber"], FINART_PALETTE["semantic_green"]],
                ),
            ),
            tooltip=["producto", alt.Tooltip("restante:Q", title="Restante %", format=".0f"), "nivel"],
        )
    )
    lineas_i = (
        alt.Chart(pd.DataFrame({"y": [UMBRAL_CRITICO, UMBRAL_ATENCION]}))
        .mark_rule(strokeDash=[6, 4], color="#64748B")
        .encode(y="y:Q")
    )
    st.markdown("**Inventario restante por SKU**" + (" (los 40 con menor existencia)" if len(ch) >= 40 else ""))
    mostrar((barras_i + lineas_i).properties(height=320))
