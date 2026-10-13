"""Lógica de negocio, cálculos y transformaciones para el Dashboard de Falabella."""
from datetime import date
import numpy as np
import pandas as pd
from core.config import (
    EXCLUIDOS,
    IVA_FACTOR,
    UMBRAL_CRITICO,
    UMBRAL_ATENCION,
    DIAS_SIN_VENTAS,
    SEMAFORO_VERDE,
    SEMAFORO_AMARILLO,
)
from core.data.budget_loader import periodo_a_fechas
from core.ui import semaforo_texto_puro


def fmt(cop_amount, fx):
    """Convierte monto en COP a USD y formatea sin decimales."""
    if cop_amount is None or fx is None or fx == 0:
        return "-"
    return f"US$ {cop_amount / fx:,.0f}"


def pct(a, b):
    """Calcula variación porcentual entre dos valores: (a / b - 1) * 100."""
    if b is None or b == 0 or a is None:
        return None
    return (a / b - 1.0) * 100.0


def usd_corto(v):
    """Formato abreviado para tarjetas: US$ 11.01 M para >=1M; US$ 2,492 para menores."""
    if v is None:
        return "-"
    if abs(v) >= 1e6:
        return f"US$ {v / 1e6:,.2f} M"
    return f"US$ {v:,.0f}"


def preparar(df, ini=None, fin=None):
    """Agrupa ventas y órdenes por día en un rango continuo.
    Excluye estrictamente estados cancelados, fallidos o devueltos.
    """
    df = df.copy()
    if df.empty:
        hoy_ = pd.Timestamp(date.today())
        ini = ini if ini is not None else hoy_
        fin = fin if fin is not None else hoy_
        vacio = pd.DataFrame({"ventas": [0.0], "ordenes": [0]}, index=[ini])
        return vacio.reindex(pd.date_range(ini, fin), fill_value=0)

    df["fecha"] = pd.to_datetime(df["created_at"]).dt.normalize()
    # Excluir pedidos en estados cancelados/devueltos
    df = df[~df["estado"].fillna("").astype(str).str.lower().isin(EXCLUIDOS)]
    
    diario = df.groupby("fecha").agg(
        ventas=("precio_pagado", "sum"),
        ordenes=("order_id", "nunique"),
    )
    hoy_ = pd.Timestamp(date.today())
    ini = ini if ini is not None else (diario.index.min() if len(diario) else hoy_)
    fin = fin if fin is not None else hoy_
    return diario.reindex(pd.date_range(ini, fin), fill_value=0)


def calcular_meses(ppto, diario, fx, hoy):
    """Genera la tabla analítica mensual del presupuesto:
    meta, venta real, esperado a la fecha, faltante, venta diaria requerida y semáforo.
    """
    filas = []
    for _, r in ppto.iterrows():
        ini_m, fin_m = (pd.Timestamp(x) for x in periodo_a_fechas(r["periodo"]))
        meta = float(r["presupuesto_usd"])
        real = float(diario["ventas"].loc[ini_m:fin_m].sum()) / fx if fx else 0.0
        falta = max(meta - real, 0.0)
        dias_mes = (fin_m - ini_m).days + 1

        if hoy > fin_m:
            estado = "Cerrado"
            req = None
            esperado = meta
        elif hoy >= ini_m:
            estado = "En curso"
            dias_transcurridos = (hoy - ini_m).days + 1
            esperado = meta * (dias_transcurridos / dias_mes)
            dias_restantes = (fin_m - hoy).days + 1
            req = falta / dias_restantes if dias_restantes > 0 else 0.0
        else:
            estado = "Por iniciar"
            esperado = 0.0
            req = meta / dias_mes if dias_mes > 0 else 0.0

        filas.append({
            "trimestre": r["trimestre"],
            "periodo": r["periodo"],
            "ini": ini_m,
            "fin": fin_m,
            "meta": meta,
            "real": real,
            "esperado": esperado,
            "falta": falta,
            "estado": estado,
            "req": req,
            "semaforo": semaforo_texto_puro(real, esperado, meta),
        })
    return pd.DataFrame(filas)


def calcular_metricas_cancelaciones(df_per, fx):
    """Mide pedidos cancelados, fallidos o devueltos sin alterar las ventas reales."""
    estado_min = df_per["estado"].fillna("").astype(str).str.lower()
    excl = df_per[estado_min.isin(EXCLUIDOS)]
    pedidos_total = df_per["order_id"].nunique()
    n_cancel = excl["order_id"].nunique()
    tasa_cancel = (n_cancel / pedidos_total * 100.0) if pedidos_total else None
    valor_no_vendido = (excl["precio_pagado"].sum() / fx) if fx else 0.0

    return {
        "pedidos_total": pedidos_total,
        "n_cancel": n_cancel,
        "tasa_cancel": tasa_cancel,
        "valor_no_vendido_usd": valor_no_vendido,
        "excl_df": excl,
    }


def calcular_metricas_inventario(hist, df, sel_skus, hoy):
    """Calcula Sell-Through, Semanas de Stock (WOS), inventario restante y alertas de quiebre."""
    if hist.empty:
        return None, 0, 0, 0, 0, 0

    ultimo_dia = hist["fecha"].max()
    dias_desde_carga = (hoy - pd.Timestamp(ultimo_dia)).days

    stock_hoy = hist[hist["fecha"] == ultimo_dia].set_index("sku")["cantidad"]
    validas = df[~df["estado"].fillna("").astype(str).str.lower().isin(EXCLUIDOS)].copy()
    validas["fecha_ts"] = pd.to_datetime(validas["created_at"])
    hoy_ts = pd.Timestamp(hoy).normalize()
    limite_28d = hoy_ts - pd.DateOffset(days=28)
    limite_nd = hoy_ts - pd.DateOffset(days=int(DIAS_SIN_VENTAS))
    
    vendido_total = validas.groupby("sku")["order_id"].count()
    v28 = validas[validas["fecha_ts"] >= limite_28d].groupby("sku")["order_id"].count()
    vN = validas[validas["fecha_ts"] >= limite_nd].groupby("sku")["order_id"].count()

    tabla = pd.DataFrame({"stock_actual": stock_hoy}).join(
        pd.DataFrame({"vendido_total": vendido_total})
    ).join(
        pd.DataFrame({"vendido_28d": v28})
    ).join(
        pd.DataFrame({"vendido_ventana": vN})
    ).fillna(0)

    if sel_skus:
        tabla = tabla[tabla.index.isin(sel_skus)].copy()

    tabla["ingresado_estimado"] = tabla["stock_actual"] + tabla["vendido_total"]
    tabla["sell_through_%"] = (
        tabla["vendido_total"] / tabla["ingresado_estimado"].replace(0, np.nan) * 100.0
    )
    venta_semanal = tabla["vendido_28d"] / 4.0
    tabla["semanas_de_stock"] = tabla["stock_actual"] / venta_semanal.replace(0, np.nan)

    # % restante del inventario
    tabla["inventario_restante_%"] = (
        tabla["stock_actual"] / tabla["ingresado_estimado"].replace(0, np.nan) * 100.0
    )

    # Estados: Crítico si WOS < 2 o % restante <= 50; Atención si % restante <= 65
    es_critico = (tabla["semanas_de_stock"] < 2) | (tabla["inventario_restante_%"] <= UMBRAL_CRITICO)
    es_atencion = tabla["inventario_restante_%"] <= UMBRAL_ATENCION

    tabla["estado"] = np.select(
        [es_critico, es_atencion],
        ["🔴 Crítico", "🟡 Atención requerida"],
        default="🟢 OK",
    )

    # Alerta sin ventas
    sin_mov = (tabla["stock_actual"] > 0) & (tabla["vendido_ventana"] == 0)
    tabla["alerta_movimiento"] = np.where(sin_mov, f"⚪ Sin ventas en {DIAS_SIN_VENTAS} días", "")

    # Días en inventario desde primer snapshot
    primer_reg = pd.to_datetime(hist[hist["cantidad"] > 0].groupby("sku")["fecha"].min())
    tabla["dias_en_inventario"] = (hoy - primer_reg.reindex(tabla.index)).dt.days

    n_criticos = int((tabla["estado"] == "🔴 Crítico").sum())
    n_sin_mov = int(sin_mov.sum())
    quiebre = tabla["stock_actual"] <= 0
    riesgo = (~quiebre) & (tabla["semanas_de_stock"] < 2)
    n_quiebre, n_riesgo = int(quiebre.sum()), int(riesgo.sum())

    return tabla, n_criticos, n_sin_mov, n_quiebre, n_riesgo, dias_desde_carga
