"""Vista Presupuesto: seguimiento de metas 2026-2028 por trimestre y mes."""
import numpy as np
import pandas as pd
import streamlit as st
from core.ui import kpi_card, semaforo_badge, descargar_dataframe
from core.charts import mostrar, grafico_meta_real, grafico_diario
from dashboards.falabella.logic import usd_corto


def render_presupuesto(context):
    """Renderiza la pestaña de presupuesto."""
    ppto = context.get("ppto")
    meses = context.get("meses")
    diario_all = context.get("diario_all")
    fx = context.get("fx")
    hoy = context.get("hoy")
    sel_skus = context.get("sel_skus")
    desde = context.get("desde")
    ruta_dia = context.get("ruta_dia")

    if sel_skus or desde is not None:
        st.info("ℹ️ **Nota de negocio:** El presupuesto se mide siempre con las ventas de todo el negocio. Los filtros laterales no alteran esta sección.")

    if ppto is None or meses is None or meses.empty:
        st.warning("No se ha cargado el archivo de presupuesto o está vacío. Verifique 'datos/presupuesto.xlsx'.")
        return

    meta_total = meses["meta"].sum()
    real_total = meses["real"].sum()
    esperado_total = meses["esperado"].sum()
    falta_total = max(meta_total - real_total, 0.0)

    st.subheader("Avance de la Meta del Proyecto (2026 - 2028)")
    p = st.columns(5)
    with p[0]:
        kpi_card(st, "Meta del proyecto", usd_corto(meta_total), help_text="Total presupuestado a 24 meses.")
    with p[1]:
        kpi_card(st, "Acumulado vendido", usd_corto(real_total), help_text="Ventas netas aprobadas convertidas a dólares.")
    with p[2]:
        kpi_card(st, "Avance de meta", f"{real_total / meta_total * 100:.1f}%" if meta_total else "-", help_text="Porcentaje de cumplimiento global.")
    with p[3]:
        kpi_card(st, "Falta por vender", usd_corto(falta_total), help_text="Diferencia restante para cumplir la meta general.")
    with p[4]:
        sem_p = semaforo_badge(real_total, esperado_total, meta_total)
        kpi_card(st, "Ritmo frente al plan", sem_p, help_text="Verde ≥100%, Amarillo ≥80%, Rojo <80% de lo esperado a hoy.")

    # --- Cumplimiento por trimestre ---
    st.divider()
    st.subheader("Cumplimiento por Trimestre")
    tq = meses.groupby("trimestre", sort=False).agg(
        meta=("meta", "sum"), real=("real", "sum"), esperado=("esperado", "sum")
    ).reset_index()
    tq["cumplimiento_%"] = np.where(tq["meta"] > 0, tq["real"] / tq["meta"] * 100, np.nan)
    tq["falta"] = (tq["meta"] - tq["real"]).clip(lower=0)
    tq["estado"] = [semaforo_badge(r, e, mt) for r, e, mt in zip(tq["real"], tq["esperado"], tq["meta"])]

    tabla_q = tq[["trimestre", "meta", "real", "cumplimiento_%", "falta", "estado"]].rename(columns={
        "trimestre": "Trimestre",
        "meta": "Meta US$",
        "real": "Vendido US$",
        "cumplimiento_%": "Cumplimiento",
        "falta": "Falta US$",
        "estado": "Semáforo",
    })

    st.dataframe(
        tabla_q.style.format({
            "Meta US$": "US$ {:,.0f}",
            "Vendido US$": "US$ {:,.0f}",
            "Cumplimiento": "{:.1f}%",
            "Falta US$": "US$ {:,.0f}",
        }, na_rep="-"),
        width="stretch",
        hide_index=True,
    )
    descargar_dataframe(tabla_q, "cumplimiento_trimestral", "Descargar Trimestres")

    st.markdown("**Meta (gris) vs. Vendido (azul) por trimestre**")
    mostrar(
        grafico_meta_real(
            pd.DataFrame({"Trimestre": tq["trimestre"], "Meta": tq["meta"], "Real": tq["real"]}),
            "Trimestre",
            list(tq["trimestre"]),
        )
    )

    # --- Detalle del trimestre elegido ---
    st.divider()
    st.subheader("Detalle por Trimestre y Mes")
    trimestres = list(dict.fromkeys(meses["trimestre"]))
    idx_q = 0 if hoy < meses["ini"].min() else len(trimestres) - 1
    for i, t in enumerate(trimestres):
        sub = meses[meses["trimestre"] == t]
        if sub["ini"].min() <= hoy <= sub["fin"].max():
            idx_q = i
            break

    sel_t = st.radio(
        "Trimestre a inspeccionar",
        trimestres,
        index=idx_q,
        horizontal=True,
        key="trim_sel_radio",
        label_visibility="collapsed",
    )

    mq = meses[meses["trimestre"] == sel_t]
    meta_q = mq["meta"].sum()
    real_q = mq["real"].sum()
    esperado_q = mq["esperado"].sum()
    ini_q, fin_q = mq["ini"].min(), mq["fin"].max()
    falta_q = max(meta_q - real_q, 0.0)

    if hoy > fin_q:
        req_q = None
    elif hoy >= ini_q:
        dias_rest = (fin_q - hoy).days + 1
        req_q = falta_q / dias_rest if dias_rest > 0 else 0.0
    else:
        dias_tot = (fin_q - ini_q).days + 1
        req_q = meta_q / dias_tot if dias_tot > 0 else 0.0

    st.markdown(f"**{sel_t}** · " + " · ".join(mq["periodo"]) + f" · {semaforo_badge(real_q, esperado_q, meta_q)}")
    k = st.columns(5)
    with k[0]:
        kpi_card(st, "Meta del trimestre", usd_corto(meta_q))
    with k[1]:
        kpi_card(st, "Venta real", usd_corto(real_q))
    with k[2]:
        kpi_card(st, "Cumplimiento", f"{real_q / meta_q * 100:.1f}%" if meta_q else "-")
    with k[3]:
        kpi_card(st, "Falta por vender", usd_corto(falta_q))
    with k[4]:
        kpi_card(st, "Venta diaria requerida", usd_corto(req_q) if req_q is not None else "-", help_text="Promedio diario necesario para alcanzar la meta trimestral.")

    # Tarjetas mensuales del trimestre
    cols_m = st.columns(len(mq))
    for slot, (_, fila) in zip(cols_m, mq.iterrows()):
        with slot.container(border=True):
            st.markdown(f"**{fila['periodo']}** · {fila['estado']}")
            st.caption(f"Semáforo: {fila['semaforo']}")
            kpi_card(st, "Meta", usd_corto(fila["meta"]))
            if fila["meta"] > 0:
                prog = min(max(fila["real"] / fila["meta"], 0.0), 1.0)
                st.progress(prog, text=f"{fila['real'] / fila['meta'] * 100:.1f}%")
                st.markdown(f"""
                <div style="font-size:0.85rem; line-height: 1.4; color: #475569; margin-top: 6px;">
                    <div><b>Vendido:</b> {usd_corto(fila['real'])}</div>
                    <div><b>Falta:</b> {usd_corto(fila['falta'])}</div>
                    {f"<div><b>Diaria requerida:</b> {usd_corto(fila['req'])}</div>" if fila['req'] is not None else ""}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.caption("Sin meta asignada este mes.")

    # Gráficas del trimestre
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Meta (gris) vs. Vendido (azul) por mes**")
        mostrar(
            grafico_meta_real(
                pd.DataFrame({"Mes": mq["periodo"], "Meta": mq["meta"], "Real": mq["real"]}),
                "Mes",
                list(mq["periodo"]),
            )
        )
    with c2:
        st.markdown("**Acumulado del trimestre vs. Ruta esperada (US$)**")
        if ini_q <= hoy:
            rango_q = pd.date_range(ini_q, fin_q)
            ruta_q = ruta_dia.reindex(rango_q).fillna(0).cumsum() if ruta_dia is not None else pd.Series(dtype=float)
            real_q_dia = (diario_all["ventas"] / fx).reindex(rango_q).fillna(0).cumsum()
            real_q_dia.loc[rango_q > hoy] = np.nan
            st.line_chart(pd.DataFrame({"Acumulado real": real_q_dia, "Ruta esperada": ruta_q}))
        else:
            st.info("Este trimestre aún no ha iniciado.")

    en_curso = mq[mq["estado"] == "En curso"]
    if len(en_curso):
        fila_c = en_curso.iloc[0]
        rango_m = pd.date_range(fila_c["ini"], min(hoy, fila_c["fin"]))
        dm = pd.DataFrame({
            "Fecha": rango_m,
            "Real": (diario_all["ventas"] / fx).reindex(rango_m).fillna(0).values,
        })
        dias_total_mes = (fila_c["fin"] - fila_c["ini"]).days + 1
        meta_dia = fila_c["meta"] / dias_total_mes if dias_total_mes > 0 else 0.0
        st.markdown(f"**Ventas diarias de {fila_c['periodo']} vs. Meta diaria promedio (línea roja)**")
        mostrar(grafico_diario(dm, meta_dia))
