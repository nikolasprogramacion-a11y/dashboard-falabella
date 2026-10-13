"""Vista Ventas: análisis diario, semanal, mensual, interanual, ticket, UPT y cancelaciones."""
import numpy as np
import pandas as pd
import streamlit as st
from core.config import EXCLUIDOS
from core.ui import kpi_card, descargar_dataframe
from core.charts import mostrar, barras_simple
from dashboards.falabella.logic import fmt, pct, usd_corto


def render_ventas(context):
    """Renderiza la pestaña de Ventas detallada."""
    df = context.get("df")
    df_per = context.get("df_per")
    diario = context.get("diario")
    diario_per = context.get("diario_per")
    fx = context.get("fx")
    hoy = context.get("hoy")
    desde = context.get("desde")
    etiquetas_sku = context.get("etiquetas_sku", {})

    st.subheader("Pulso Diario y Semanal")
    v_hoy = diario["ventas"].get(hoy, 0.0)
    v_ayer = diario["ventas"].get(hoy - pd.Timedelta(days=1), 0.0)
    v_sem_pasada = diario["ventas"].get(hoy - pd.Timedelta(days=7), 0.0)
    dias_semana_nombres = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    dia_semana_actual = dias_semana_nombres[hoy.weekday()]

    d = st.columns(4)
    with d[0]:
        delta_ayer = f"{pct(v_hoy, v_ayer):+.0f}% vs ayer" if v_ayer else None
        kpi_card(st, "Hoy", fmt(v_hoy, fx), delta=delta_ayer, delta_positivo=(v_hoy >= v_ayer))
    with d[1]:
        delta_sem = f"{pct(v_hoy, v_sem_pasada):+.0f}% vs hace 7 días" if v_sem_pasada else "Sin dato previo"
        kpi_card(st, f"Hoy vs {dia_semana_actual} pasado", fmt(v_hoy, fx), delta=delta_sem, delta_positivo=(v_hoy >= v_sem_pasada))
    with d[2]:
        sem = diario["ventas"].loc[hoy - pd.Timedelta(days=6):hoy].sum()
        sem_ant = diario["ventas"].loc[hoy - pd.Timedelta(days=13):hoy - pd.Timedelta(days=7)].sum()
        delta_7d = f"{pct(sem, sem_ant):+.0f}% vs 7 días previos" if sem_ant else None
        kpi_card(st, "Últimos 7 días", fmt(sem, fx), delta=delta_7d, delta_positivo=(sem >= sem_ant))
    with d[3]:
        kpi_card(st, "Órdenes hoy", int(diario["ordenes"].get(hoy, 0)), help_text="Número de compras completadas hoy.")

    # Gráficas de tendencia
    if desde is None:
        st.markdown("**Ventas diarias · últimos 30 días (US$)**")
        st.bar_chart(diario["ventas"].loc[hoy - pd.Timedelta(days=29):hoy] / fx)
    else:
        st.markdown("**Ventas diarias · período seleccionado (US$)**")
        st.bar_chart(diario_per["ventas"] / fx)

    cg1, cg2 = st.columns(2)
    with cg1:
        st.markdown("**Hoy vs. Ayer vs. Mismo día de la semana pasada (US$)**")
        etq_c = ["Hoy", "Ayer", f"{dia_semana_actual.capitalize()} pasado"]
        mostrar(
            barras_simple(
                pd.DataFrame({
                    "Día": etq_c,
                    "ventas": [float(v_hoy) / fx, float(v_ayer) / fx, float(v_sem_pasada) / fx],
                }),
                "Día",
                "ventas",
                etq_c,
            )
        )
    with cg2:
        st.markdown("**Últimos 7 días vs. 7 días previos (US$)**")
        serie14 = diario["ventas"].reindex(pd.date_range(hoy - pd.Timedelta(days=13), hoy)).fillna(0).values / fx
        st.line_chart(pd.DataFrame({"Últimos 7 días": serie14[7:], "7 días previos": serie14[:7]}, index=range(1, 8)))

    # --- Consultar un día específico ---
    st.divider()
    st.subheader("Consulta de Día Específico")
    dia_min = diario.index.min().date() if not diario.empty else hoy.date()
    dia_sel_input = st.date_input(
        "Seleccione fecha a auditar",
        value=hoy.date(),
        min_value=dia_min,
        max_value=hoy.date(),
        key="dia_consulta_input",
    )
    dia_sel = pd.Timestamp(dia_sel_input)
    ventas_validas = df[~df["estado"].fillna("").astype(str).str.lower().isin(EXCLUIDOS)].copy()
    ventas_validas["fecha"] = pd.to_datetime(ventas_validas["created_at"]).dt.normalize()
    del_dia = ventas_validas[ventas_validas["fecha"] == dia_sel]
    nombre_dia_sel = dias_semana_nombres[dia_sel.weekday()]
    v_dia = diario["ventas"].get(dia_sel, 0.0)
    compras_dia = int(diario["ordenes"].get(dia_sel, 0))
    dia_previo = dia_sel - pd.Timedelta(days=7)
    v_previo = diario["ventas"].get(dia_previo, 0.0)

    st.markdown(f"**{nombre_dia_sel.capitalize()} {dia_sel:%d-%m-%Y}**")
    q = st.columns(4)
    with q[0]:
        delta_d = f"{pct(v_dia, v_previo):+.0f}% vs {dia_previo:%d-%m}" if v_previo else None
        kpi_card(st, "Ventas del día", fmt(v_dia, fx), delta=delta_d, delta_positivo=(v_dia >= v_previo))
    with q[1]:
        kpi_card(st, "Compras / Órdenes", compras_dia)
    with q[2]:
        kpi_card(st, "Unidades vendidas", len(del_dia))
    with q[3]:
        kpi_card(st, "Ticket promedio", fmt(v_dia / compras_dia, fx) if compras_dia else "-")

    if len(del_dia):
        productos_dia = del_dia.groupby("sku").agg(
            unidades=("order_id", "count"), ventas_cop=("precio_pagado", "sum")
        ).reset_index()
        productos_dia["ventas_usd"] = productos_dia["ventas_cop"] / fx
        productos_dia["producto"] = productos_dia["sku"].map(lambda s: etiquetas_sku.get(s, s))
        
        st.dataframe(
            productos_dia[["producto", "unidades", "ventas_usd"]]
            .rename(columns={"producto": "Producto", "unidades": "Unidades", "ventas_usd": "Ventas US$"})
            .sort_values("Ventas US$", ascending=False)
            .style.format({"Ventas US$": "US$ {:,.0f}"}),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No se registraron ventas en la fecha seleccionada.")

    # --- Comparativo interanual ---
    st.divider()
    st.subheader("Comparativo Interanual")
    c_ty1, c_ty2 = st.columns(2)
    with c_ty1:
        fecha_ly1 = hoy - pd.Timedelta(days=365)
        v_ly1 = diario["ventas"].get(fecha_ly1, None)
        delta_ly1 = f"{pct(v_hoy, v_ly1):+.0f}% vs {fecha_ly1.date()}" if v_ly1 else "Sin histórico de hace 1 año"
        kpi_card(st, "Interanual · Misma fecha", fmt(v_hoy, fx), delta=delta_ly1, delta_positivo=(v_hoy >= (v_ly1 or 0)))
    with c_ty2:
        fecha_ly2 = hoy - pd.Timedelta(days=364)
        v_ly2 = diario["ventas"].get(fecha_ly2, None)
        delta_ly2 = f"{pct(v_hoy, v_ly2):+.0f}% vs {fecha_ly2.date()}" if v_ly2 else "Sin histórico de hace 1 año"
        kpi_card(st, "Interanual · Mismo día de la semana", fmt(v_hoy, fx), delta=delta_ly2, delta_positivo=(v_hoy >= (v_ly2 or 0)))

    if v_ly1 or v_ly2:
        etq_i = ["Hoy", "Misma fecha año anterior", "Mismo día sem. año anterior"]
        mostrar(
            barras_simple(
                pd.DataFrame({
                    "Día": etq_i,
                    "ventas": [float(v_hoy) / fx, float(v_ly1 or 0) / fx, float(v_ly2 or 0) / fx],
                }),
                "Día",
                "ventas",
                etq_i,
            )
        )

    # --- Mes a mes ---
    st.divider()
    st.subheader("Comportamiento Mes a Mes")
    ini_mes = hoy.replace(day=1)
    ini_prev = (ini_mes - pd.Timedelta(days=1)).replace(day=1)
    fin_prev = min(ini_prev + pd.Timedelta(days=hoy.day - 1), ini_mes - pd.Timedelta(days=1))
    m_act = diario["ventas"].loc[ini_mes:hoy].sum()
    m_prev = diario["ventas"].loc[ini_prev:fin_prev].sum()
    
    delta_m = f"{pct(m_act, m_prev):+.0f}% vs mismo tramo del mes anterior" if m_prev else None
    kpi_card(st, f"Mes en curso (Día 1 al {hoy.day})", fmt(m_act, fx), delta=delta_m, delta_positivo=(m_act >= m_prev))

    cum_act = diario["ventas"].reindex(pd.date_range(ini_mes, hoy)).fillna(0).cumsum().values / fx
    cum_prev = diario["ventas"].reindex(pd.date_range(ini_prev, fin_prev)).fillna(0).cumsum().values / fx
    n_tramo = len(cum_act)
    st.markdown("**Acumulado del mes en curso vs. Mismo tramo del mes anterior (US$)**")
    st.line_chart(
        pd.DataFrame({
            "Mes en curso": cum_act,
            "Mes anterior": np.pad(cum_prev, (0, max(n_tramo - len(cum_prev), 0)), constant_values=np.nan)[:n_tramo],
        }, index=range(1, n_tramo + 1))
    )

    mensual = diario_per["ventas"].groupby(diario_per.index.to_period("M").astype(str)).sum() / fx
    tabla_mensual = pd.DataFrame({"Ventas US$": mensual, "Variación %": mensual.pct_change() * 100}).reset_index()
    tabla_mensual.columns = ["Año/Mes", "Ventas US$", "Variación %"]
    st.markdown("**Evolución mensual histórica**")
    st.bar_chart(mensual)
    st.dataframe(
        tabla_mensual.style.format({"Ventas US$": "US$ {:,.0f}", "Variación %": "{:+.1f}%"}, na_rep="-"),
        width="stretch",
        hide_index=True,
    )
    descargar_dataframe(tabla_mensual, "ventas_mensuales", "Descargar Ventas Mensuales")

    # --- Ticket promedio y UPT ---
    st.divider()
    st.subheader("Ticket Promedio y Unidades por Transacción (UPT)")

    def _calc_t_upt(sub):
        ords = sub["order_id"].nunique()
        units = len(sub)
        rev = sub["precio_pagado"].sum()
        ticket = (rev / ords) if ords else None
        upt = (units / ords) if ords else None
        return ticket, upt, ords

    t_tot, u_tot, ord_tot = _calc_t_upt(ventas_validas)
    t_mes, u_mes, ord_mes = _calc_t_upt(ventas_validas[ventas_validas["fecha"] >= ini_mes])

    tu = st.columns(4)
    with tu[0]:
        kpi_card(st, "Ticket promedio (acumulado)", fmt(t_tot, fx) if t_tot else "-")
    with tu[1]:
        kpi_card(st, "UPT (acumulado)", f"{u_tot:.1f}" if u_tot else "-")
    with tu[2]:
        kpi_card(st, "Ticket promedio (mes)", fmt(t_mes, fx) if t_mes else "-")
    with tu[3]:
        kpi_card(st, "UPT (mes)", f"{u_mes:.1f}" if u_mes else "-")

    vp_ticket = df_per[~df_per["estado"].fillna("").astype(str).str.lower().isin(EXCLUIDOS)].copy()
    vp_ticket["fecha"] = pd.to_datetime(vp_ticket["created_at"]).dt.normalize()
    vv = vp_ticket.assign(mes=vp_ticket["fecha"].dt.to_period("M").astype(str))
    tm = vv.groupby("mes").agg(
        ingreso=("precio_pagado", "sum"),
        ordenes=("order_id", "nunique"),
        unidades=("order_id", "count"),
    )
    tm["Ticket promedio US$"] = tm["ingreso"] / tm["ordenes"] / fx
    tm["UPT"] = tm["unidades"] / tm["ordenes"]
    if len(tm):
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Ticket promedio por mes (US$)**")
            st.line_chart(tm["Ticket promedio US$"])
        with g2:
            st.markdown("**UPT por mes**")
            st.line_chart(tm["UPT"])

    # --- Cancelaciones y devoluciones ---
    st.divider()
    st.subheader("Auditoría de Cancelaciones y Devoluciones")
    st.caption("Los pedidos cancelados o devueltos no suman a ventas, pero representan costo de oportunidad y demanda insatisfecha.")
    
    estado_min = df_per["estado"].fillna("").astype(str).str.lower()
    excl = df_per[estado_min.isin(EXCLUIDOS)]
    pedidos_total = df_per["order_id"].nunique()
    n_cancel = excl["order_id"].nunique()
    tasa_cancel = (n_cancel / pedidos_total * 100.0) if pedidos_total else None
    valor_no_vendido = excl["precio_pagado"].sum() / fx if fx else 0.0

    cc = st.columns(4)
    with cc[0]:
        kpi_card(st, "Pedidos cancelados/devueltos", n_cancel)
    with cc[1]:
        kpi_card(st, "Tasa de cancelación", f"{tasa_cancel:.1f}%" if tasa_cancel is not None else "-", help_text="Pedidos excluidos ÷ pedidos totales del período.")
    with cc[2]:
        kpi_card(st, "Valor no vendido (con IVA)", usd_corto(valor_no_vendido), help_text="Importe total de pedidos cancelados/devueltos.")
    with cc[3]:
        kpi_card(st, "Pedidos totales", pedidos_total)

    with st.expander("🔍 Ver desglose de estados detectados en el Seller Center"):
        estados_det = (
            df_per.assign(estado=df_per["estado"].fillna("(sin estado)").astype(str).str.lower())
            .groupby("estado")
            .agg(pedidos=("order_id", "nunique"))
            .reset_index()
        )
        estados_det["¿Cuenta como venta?"] = np.where(estados_det["estado"].isin(EXCLUIDOS), "No", "Sí")
        st.dataframe(estados_det.rename(columns={"estado": "Estado", "pedidos": "Pedidos"}), width="stretch", hide_index=True)

    if len(excl):
        g_c1, g_c2 = st.columns(2)
        with g_c1:
            st.markdown("**Cancelaciones por estado**")
            por_estado = (
                excl.assign(estado=excl["estado"].astype(str).str.lower())
                .groupby("estado")
                .agg(pedidos=("order_id", "nunique"), valor=("precio_pagado", "sum"))
                .reset_index()
            )
            por_estado["valor_usd"] = por_estado["valor"] / fx
            st.dataframe(
                por_estado[["estado", "pedidos", "valor_usd"]]
                .rename(columns={"estado": "Estado", "pedidos": "Pedidos", "valor_usd": "Valor US$"})
                .style.format({"Valor US$": "US$ {:,.0f}"}),
                width="stretch",
                hide_index=True,
            )

            top_c = (
                excl[excl["sku"] != "(sin SKU)"]
                .groupby("sku")["order_id"]
                .nunique()
                .sort_values(ascending=False)
                .head(5)
                .reset_index()
            )
            if len(top_c):
                st.markdown("**Top 5 productos con más cancelaciones**")
                top_c["producto"] = top_c["sku"].map(lambda s: etiquetas_sku.get(s, s))
                st.dataframe(
                    top_c[["producto", "order_id"]].rename(columns={"producto": "Producto", "order_id": "Pedidos cancelados"}),
                    width="stretch",
                    hide_index=True,
                )
        with g_c2:
            st.markdown("**Tasa de cancelación por mes (%)**")
            mes_todos = pd.to_datetime(df_per["created_at"]).dt.to_period("M").astype(str)
            mes_excl = pd.to_datetime(excl["created_at"]).dt.to_period("M").astype(str)
            tot_m = df_per.groupby(mes_todos)["order_id"].nunique()
            can_m = excl.groupby(mes_excl)["order_id"].nunique()
            tasa_m = (can_m.reindex(tot_m.index).fillna(0) / tot_m * 100.0).fillna(0)
            tasa_m.index.name = "Año/Mes"
            st.bar_chart(tasa_m)
    else:
        st.info("No se registraron pedidos cancelados ni devueltos en el período analizado.")
