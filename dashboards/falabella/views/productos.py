"""Vista Productos: rentabilidad real, márgenes de lista, top sellers y slow movers."""
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from core.config import EXCLUIDOS, IVA_FACTOR, FINART_PALETTE
from core.ui import kpi_card, descargar_dataframe
from core.charts import mostrar
from dashboards.falabella.logic import fmt


def render_productos(context):
    """Renderiza la pestaña de Productos y Márgenes."""
    df_per = context.get("df_per")
    margenes = context.get("margenes")
    tabla_inv = context.get("tabla_inv")
    etiquetas_sku = context.get("etiquetas_sku", {})
    sel_skus = context.get("sel_skus")
    fx = context.get("fx")

    # Contenedor para ubicar los rankings en la parte superior según diseño original
    rank_box = st.container()

    st.divider()
    st.subheader("Rentabilidad y Márgenes de Catálogo")
    st.caption("Fórmula estricta: RENT de lista = 1 − Costo con factor / (PV / 1,19). Margen real de venta = (Venta neta − Costo total) / Venta neta.")

    if margenes is not None and not margenes.empty:
        df_m = df_per
        vendido_sku = (
            df_m[~df_m["estado"].fillna("").astype(str).str.lower().isin(EXCLUIDOS)]
            .groupby("sku")
            .agg(unidades=("order_id", "count"), ingreso_cop=("precio_pagado", "sum"))
        )
        m = margenes.set_index("sku").join(vendido_sku).fillna({"unidades": 0, "ingreso_cop": 0})
        if sel_skus:
            m = m[m.index.isin(sel_skus)]

        m["costo_total_cop"] = m["costo_real_cop"] * m["unidades"]
        m["ingreso_neto_cop"] = m["ingreso_cop"] / IVA_FACTOR
        m["margen_real_%"] = np.where(
            m["ingreso_neto_cop"] > 0,
            (m["ingreso_neto_cop"] - m["costo_total_cop"]) / m["ingreso_neto_cop"] * 100.0,
            np.nan,
        )

        ing_tot = m["ingreso_neto_cop"].sum()
        costo_tot = m["costo_total_cop"].sum()
        ganancia_tot = ing_tot - costo_tot
        margen_acum = (ganancia_tot / ing_tot * 100.0) if ing_tot else None

        e = st.columns(3)
        with e[0]:
            kpi_card(st, "Margen real de venta (acumulado)", f"{margen_acum:.1f}%" if margen_acum is not None else "-")
        with e[1]:
            kpi_card(st, "Ganancia acumulada (sin IVA)", fmt(ganancia_tot, fx) if ing_tot else "-")
        with e[2]:
            kpi_card(st, "Unidades vendidas en período", int(m["unidades"].sum()))

        tabla_m = m[["ref", "unidades", "ingreso_neto_cop", "costo_total_cop", "margen_real_%", "margen_lista_%"]].copy()
        tabla_m["ingreso_usd"] = tabla_m["ingreso_neto_cop"] / fx
        tabla_m["costo_total_usd"] = tabla_m["costo_total_cop"] / fx
        tabla_m = tabla_m.reset_index()
        tabla_m["producto"] = tabla_m["sku"].map(lambda s: etiquetas_sku.get(s, s))

        tabla_mostrar = tabla_m[[
            "producto", "unidades", "ingreso_usd", "costo_total_usd", "margen_real_%", "margen_lista_%"
        ]].rename(columns={
            "producto": "Producto",
            "unidades": "Unidades",
            "ingreso_usd": "Ingreso neto (US$)",
            "costo_total_usd": "Costo total (US$)",
            "margen_real_%": "Margen Real %",
            "margen_lista_%": "Margen Lista %",
        }).sort_values("Ingreso neto (US$)", ascending=False)

        st.dataframe(
            tabla_mostrar.style.format({
                "Ingreso neto (US$)": "US$ {:,.0f}",
                "Costo total (US$)": "US$ {:,.0f}",
                "Margen Real %": "{:.1f}%",
                "Margen Lista %": "{:.1f}%",
            }, na_rep="-"),
            width="stretch",
            hide_index=True,
        )
        descargar_dataframe(tabla_mostrar, "margenes_productos", "Descargar Márgenes")

        # Gráficas de producto
        g = tabla_m.copy()
        g["unidades"] = g["unidades"].astype(float)
        g["ingreso_usd"] = g["ingreso_usd"].astype(float)
        g["margen_real"] = g["margen_real_%"].astype(float)
        g["margen_lista"] = g["margen_lista_%"].astype(float)

        c1, c2 = st.columns(2)
        with c1:
            g_m = g if len(g) <= 40 else pd.concat([g.nlargest(20, "margen_lista"), g.nsmallest(20, "margen_lista")])
            st.markdown("**Margen a precio de lista por producto**" + (" (los 20 mayores y 20 menores)" if len(g) > 40 else ""))
            orden_m = list(g_m.sort_values("margen_lista", ascending=False)["sku"])
            mostrar(
                alt.Chart(g_m)
                .mark_bar(color=FINART_PALETTE["navy_primary"])
                .encode(
                    x=alt.X("sku:N", sort=orden_m, title=None, axis=alt.Axis(labelAngle=-90)),
                    y=alt.Y("margen_lista:Q", title="Margen %"),
                    tooltip=["producto", alt.Tooltip("margen_lista:Q", title="Margen Lista %", format=".1f")],
                )
                .properties(height=300)
            )
        with c2:
            st.markdown("**Top 10 productos por ingreso (sin IVA)**")
            top = g[g["unidades"] > 0].nlargest(10, "ingreso_usd")
            if len(top):
                mostrar(
                    alt.Chart(top)
                    .mark_bar(color=FINART_PALETTE["semantic_green"])
                    .encode(
                        y=alt.Y("producto:N", sort="-x", title=None),
                        x=alt.X("ingreso_usd:Q", title="US$"),
                        tooltip=["producto", "unidades", alt.Tooltip("ingreso_usd:Q", title="Venta neta (US$)", format=",.0f"), alt.Tooltip("margen_real:Q", title="Margen Real %", format=".1f")],
                    )
                    .properties(height=300)
                )
            else:
                st.info("Aún no se registran ventas para estos productos en el período seleccionado.")

        vendidos = g[g["unidades"] > 0]
        if len(vendidos) >= 3:
            st.markdown("**Margen real vs. Unidades vendidas (Dispersión)**")
            mostrar(
                alt.Chart(vendidos)
                .mark_circle(size=120, opacity=0.8, color=FINART_PALETTE["gold_primary"])
                .encode(
                    x=alt.X("unidades:Q", title="Unidades vendidas"),
                    y=alt.Y("margen_real:Q", title="Margen real %"),
                    size=alt.Size("ingreso_usd:Q", title="Venta neta (US$)", legend=None),
                    tooltip=["producto", "unidades", alt.Tooltip("ingreso_usd:Q", title="Ingreso (US$)", format=",.0f"), alt.Tooltip("margen_real:Q", title="Margen Real %", format=".1f")],
                )
                .properties(height=320)
            )
    else:
        st.warning("Falta el archivo de costos: verifique su existencia en 'datos/costos.xlsx'.")

    # --- Rankings de productos en la caja superior ---
    with rank_box:
        st.subheader("Rankings de Desempeño Comercial")
        vp_r = df_per[~df_per["estado"].fillna("").astype(str).str.lower().isin(EXCLUIDOS)]
        base_r = vp_r.groupby("sku").agg(unidades=("order_id", "count"), ingreso=("precio_pagado", "sum"))
        base_r = base_r[base_r.index != "(sin SKU)"]
        base_r["ingreso_usd"] = base_r["ingreso"] / IVA_FACTOR / fx

        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**⭐ Best Sellers (Top 5 por unidades)**")
            top5 = base_r.sort_values(["unidades", "ingreso_usd"], ascending=False).head(5)
            if len(top5):
                t5 = top5.reset_index()
                t5["producto"] = t5["sku"].map(lambda s: etiquetas_sku.get(s, s))
                st.dataframe(
                    t5[["producto", "unidades", "ingreso_usd"]]
                    .rename(columns={"producto": "Producto", "unidades": "Unidades", "ingreso_usd": "Ingreso neto (US$)"})
                    .style.format({"Ingreso neto (US$)": "US$ {:,.0f}"}),
                    width="stretch",
                    hide_index=True,
                )
                mostrar(
                    alt.Chart(t5)
                    .mark_bar(color=FINART_PALETTE["semantic_green"], cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
                    .encode(
                        y=alt.Y("producto:N", sort="-x", title=None),
                        x=alt.X("unidades:Q", title="Unidades"),
                        tooltip=["producto", "unidades", alt.Tooltip("ingreso_usd:Q", title="Ingreso (US$)", format=",.0f")],
                    )
                    .properties(height=220)
                )
            else:
                st.info("Sin ventas registradas en el período.")

        with r2:
            st.markdown("**🐢 Slow Movers (Top 5 con stock y menor venta)**")
            if tabla_inv is not None and not tabla_inv.empty:
                con_stock = (
                    tabla_inv[tabla_inv["stock_actual"] > 0][["stock_actual", "dias_en_inventario"]]
                    .join(base_r[["unidades"]])
                    .fillna({"unidades": 0})
                )
                sm = con_stock.sort_values(["unidades", "stock_actual"], ascending=[True, False]).head(5).reset_index()
                sm["producto"] = sm["sku"].map(lambda s: etiquetas_sku.get(s, s))
                st.dataframe(
                    sm[["producto", "unidades", "stock_actual", "dias_en_inventario"]]
                    .rename(columns={
                        "producto": "Producto",
                        "unidades": "Vendidas",
                        "stock_actual": "Stock",
                        "dias_en_inventario": "Días en inv.",
                    })
                    .style.format({"Vendidas": "{:.0f}", "Días en inv.": "{:.0f}"}, na_rep="-"),
                    width="stretch",
                    hide_index=True,
                )
                mostrar(
                    alt.Chart(sm)
                    .mark_bar(color=FINART_PALETTE["semantic_amber"], cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
                    .encode(
                        y=alt.Y("producto:N", sort="-x", title=None),
                        x=alt.X("stock_actual:Q", title="Stock"),
                        tooltip=["producto", "stock_actual", "unidades"],
                    )
                    .properties(height=220)
                )
            else:
                st.info("Cargue el inventario para calcular los slow movers.")

        universo = set(tabla_inv.index) if (tabla_inv is not None and not tabla_inv.empty) else set(etiquetas_sku)
        if sel_skus:
            universo &= set(sel_skus)
        sin_venta = sorted(universo - set(base_r.index))

        st.markdown("**Productos sin ninguna venta en el período**")
        kv = st.columns(3)
        with kv[0]:
            kpi_card(st, "Productos con venta cero", len(sin_venta))
        with kv[1]:
            kpi_card(st, "Universo analizado", len(universo))

        if sin_venta:
            filas_cero = []
            for s in sin_venta:
                fc = {"Producto": etiquetas_sku.get(s, s)}
                if tabla_inv is not None and s in tabla_inv.index:
                    fc["Stock"] = tabla_inv.at[s, "stock_actual"]
                    fc["Días en inventario"] = tabla_inv.at[s, "dias_en_inventario"]
                filas_cero.append(fc)
            st.dataframe(
                pd.DataFrame(filas_cero).style.format({"Días en inventario": "{:.0f}"}, na_rep="-"),
                width="stretch",
                hide_index=True,
            )
