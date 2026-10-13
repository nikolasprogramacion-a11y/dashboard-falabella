"""Vista Resumen Ejecutivo ('¿Cómo vamos en 5 segundos?')."""
import pandas as pd
import streamlit as st
from core.ui import kpi_card, semaforo_badge
from core.charts import mostrar
from dashboards.falabella.logic import usd_corto, fmt


def render_resumen(context):
    """Renderiza la pestaña Resumen Ejecutivo con jerarquía visual de alto impacto."""
    meses = context.get("meses")
    mes_cur = context.get("mes_cur")
    q_cur_datos = context.get("q_cur_datos")
    meta_total = context.get("meta_total")
    real_total = context.get("real_total")
    esperado_total = context.get("esperado_total")
    grafico_ruta = context.get("grafico_ruta")
    fx = context.get("fx")
    v_hoy = context.get("v_hoy")
    sem = context.get("sem")
    margen_acum = context.get("margen_acum")
    tasa_cancel = context.get("tasa_cancel")
    n_criticos = context.get("n_criticos")
    n_sin_mov = context.get("n_sin_mov")
    n_quiebre = context.get("n_quiebre")
    n_riesgo = context.get("n_riesgo")
    n_sin_venta = context.get("n_sin_venta")

    st.markdown("### 🎯 Pulso del Presupuesto")
    if meses is not None and meta_total:
        c1, c2, c3 = st.columns(3)
        with c1:
            if mes_cur is not None:
                sem_mes = semaforo_badge(mes_cur["real"], mes_cur["esperado"], mes_cur["meta"])
                kpi_card(
                    st,
                    f"Mes en curso ({mes_cur['periodo']})",
                    f"{mes_cur['real'] / mes_cur['meta'] * 100:.1f}%" if mes_cur["meta"] else "-",
                    delta=f"{usd_corto(mes_cur['real'])} de {usd_corto(mes_cur['meta'])}",
                    delta_positivo=mes_cur["real"] >= mes_cur["esperado"],
                    help_text=f"Estado: {sem_mes}. Meta total mensual dividida equitativamente entre los días del mes.",
                )
            else:
                kpi_card(st, "Mes en curso", "-", help_text="No hay mes activo del presupuesto en la fecha actual.")
        with c2:
            if q_cur_datos is not None:
                sem_q = semaforo_badge(q_cur_datos["real"], q_cur_datos["esperado"], q_cur_datos["meta"])
                kpi_card(
                    st,
                    f"Trimestre ({q_cur_datos['nombre']})",
                    f"{q_cur_datos['real'] / q_cur_datos['meta'] * 100:.1f}%" if q_cur_datos["meta"] else "-",
                    delta=f"{usd_corto(q_cur_datos['real'])} de {usd_corto(q_cur_datos['meta'])}",
                    delta_positivo=q_cur_datos["real"] >= q_cur_datos["esperado"],
                    help_text=f"Estado: {sem_q}. Acumulado del trimestre actual.",
                )
            else:
                kpi_card(st, "Trimestre actual", "-", help_text="Fuera del rango de trimestres presupuestados.")
        with c3:
            sem_tot = semaforo_badge(real_total, esperado_total, meta_total)
            kpi_card(
                st,
                "Proyecto 2026-2028",
                f"{real_total / meta_total * 100:.1f}%",
                delta=f"{usd_corto(real_total)} de {usd_corto(meta_total)}",
                delta_positivo=real_total >= esperado_total,
                help_text=f"Estado general: {sem_tot}. Avance sobre la meta total de 24 meses.",
            )

        if grafico_ruta is not None and not grafico_ruta.empty:
            st.markdown("**Acumulado real vs. ruta esperada del presupuesto (US$)**")
            st.line_chart(grafico_ruta)
    else:
        st.info("Carga el archivo de presupuesto en datos/presupuesto.xlsx para visualizar el avance de metas.")

    st.divider()
    st.markdown("### ⚡ Operación Comercial y Calidad de Venta")
    o = st.columns(4)
    with o[0]:
        kpi_card(st, "Ventas hoy", fmt(v_hoy, fx), help_text="Ventas netas aprobadas del día de hoy en dólares.")
    with o[1]:
        kpi_card(st, "Últimos 7 días", fmt(sem, fx), help_text="Ventas acumuladas de la última semana móvil.")
    with o[2]:
        kpi_card(
            st,
            "Margen real de venta",
            f"{margen_acum:.1f}%" if margen_acum is not None else "-",
            help_text="Margen ponderado real: (ingreso neto - costo con factor) / ingreso neto.",
        )
    with o[3]:
        kpi_card(
            st,
            "Tasa de cancelación",
            f"{tasa_cancel:.1f}%" if tasa_cancel is not None else "-",
            delta_positivo=False if (tasa_cancel or 0) > 10 else True,
            help_text="Porcentaje de pedidos en estados cancelados, fallidos o devueltos sobre pedidos totales.",
        )

    st.divider()
    st.markdown("### 🚨 Semáforo de Inventario y Abastecimiento")
    o2 = st.columns(4)
    with o2[0]:
        kpi_card(
            st,
            "SKUs en quiebre (Stock 0)",
            n_quiebre if n_quiebre is not None else "-",
            help_text="Productos sin existencias disponibles en Seller Center.",
        )
    with o2[1]:
        kpi_card(
            st,
            "SKUs en riesgo (<2 semanas)",
            n_riesgo if n_riesgo is not None else "-",
            help_text="Productos con existencias para menos de 2 semanas según ritmo de venta de los últimos 28 días.",
        )
    with o2[2]:
        kpi_card(
            st,
            "SKUs sin ventas (28 días)",
            n_sin_mov if n_sin_mov is not None else "-",
            help_text="Productos que tienen inventario pero no registran ninguna venta en 28 días.",
        )
    with o2[3]:
        kpi_card(
            st,
            "Productos sin ventas en período",
            n_sin_venta if n_sin_venta is not None else "-",
            help_text="Productos del catálogo que no tuvieron ninguna venta en el período seleccionado.",
        )
