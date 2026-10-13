"""Dashboard de ventas Falabella. Ejecutar:  streamlit run app.py"""
import calendar
import hmac
import io
import os
import sqlite3
from datetime import date, datetime, timedelta

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from budget import leer_presupuesto, periodo_a_fechas
from stock import leer_stock_manual, _sku_str
from margen import leer_margenes

load_dotenv()
DB = os.getenv("DB_PATH", "ventas.db")
# Datos fijos (presupuesto y costos): viven en la carpeta "datos" del proyecto, junto a app.py.
# Los gerentes no suben nada; para actualizarlos basta con reemplazar el archivo de la carpeta.
DATOS_DIR = os.getenv("DATOS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos"))
os.makedirs(DATOS_DIR, exist_ok=True)
FILE_PPTO = os.path.join(DATOS_DIR, "presupuesto.xlsx")
FILE_COSTOS = os.path.join(DATOS_DIR, "costos.xlsx")
# Cortes de inventario (% de inventario que queda) y días sin ventas para la alerta
UMBRAL_CRITICO = 50
UMBRAL_ATENCION = 65
DIAS_SIN_VENTAS = 28
# Día en que se salió al mercado (de aquí se cuentan los días en inventario)
TASA_USD_COP = 3100.0  # tasa fija oficial del ejercicio; no depende del .env
FECHA_SALIDA_MERCADO = pd.Timestamp(os.getenv("FECHA_SALIDA_MERCADO", "2026-09-28"))
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
            "septiembre", "octubre", "noviembre", "diciembre"]

def periodo_mostrar(periodo):
    """Etiqueta visual corta del mes; no muestra el año repetido."""
    texto = str(periodo).strip().lower()
    mapa = {
        "jan": "Ene", "feb": "Feb", "mar": "Mar", "apr": "Abr",
        "may": "May", "jun": "Jun", "jul": "Jul", "aug": "Ago",
        "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dic",
        "ene": "Ene", "abr": "Abr", "ago": "Ago", "dic": "Dic",
        "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
        "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
        "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
    }
    partes = texto.replace("/", "-").split("-")
    return mapa.get(partes[0], str(periodo)) if partes else str(periodo)

# Semáforo del presupuesto: % de lo que se debería llevar vendido a hoy según el plan
SEMAFORO_VERDE = 100
SEMAFORO_AMARILLO = 80
EXCLUIDOS = {e.strip().lower() for e in
             os.getenv("ESTADOS_EXCLUIDOS", "canceled,cancelled,failed,returned").split(",")}

# ===== CARGA DE ASSETS & CONFIGURACIÓN EJECUTIVA FINART =====
import base64
from functools import lru_cache

@lru_cache(maxsize=4)
def _get_b64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return ""

FONDO_HEADER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "images", "fondo_joyeria_header.jpg")
if not os.path.exists(FONDO_HEADER_PATH):
    FONDO_HEADER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "images", "fondo_joyeria_finart.png")

CSS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "estilos.css")
with open(CSS_FILE_PATH, "r", encoding="utf-8") as f:
    CSS_CONTENT = f.read()

FONDO_B64 = _get_b64(FONDO_HEADER_PATH)

st.set_page_config(page_title="Dashboard ARDP - Falabella", layout="wide")
st.markdown(f"""
<style>
{CSS_CONTENT}
/* Fondo general inmersivo de la aplicación con fotografía de joyería y overlay azul zafiro oscuro */
.stApp, [data-testid="stAppViewContainer"] {{
  background-color: #071729 !important;
  background-image: 
    linear-gradient(180deg, rgba(7, 23, 41, 0.94) 0%, rgba(7, 23, 41, 0.96) 350px, rgba(7, 23, 41, 0.98) 100%),
    url("data:image/jpeg;base64,{FONDO_B64}") !important;
  background-attachment: fixed !important;
  background-position: right top !important;
  background-repeat: no-repeat !important;
  background-size: cover !important;
}}
.ardp-header, .ardp-page {{
  background-image: linear-gradient(90deg, #0b1e33 0%, rgba(11, 30, 51, 0.97) 35%, rgba(11, 30, 51, 0.78) 65%, rgba(11, 30, 51, 0.35) 90%, rgba(11, 30, 51, 0.15) 100%), url("data:image/jpeg;base64,{FONDO_B64}") !important;
}}
.finart-sidebar-footer {{
  background-image: linear-gradient(0deg, #050f1c 0%, rgba(5, 15, 28, 0.88) 50%, rgba(5, 15, 28, 0.2) 100%), url("data:image/jpeg;base64,{FONDO_B64}") !important;
}}
</style>
""", unsafe_allow_html=True)

def page_header(eyebrow, title, subtitle, right_badge="2027"):
    badge_html = f'''<div style="background:rgba(50,124,193,0.18);border:1px solid rgba(141,200,240,0.3);border-radius:10px;padding:6px 14px;color:#cbd5e1;font-size:12px;font-weight:600;display:flex;align-items:center;gap:6px;"><span>Año</span> <strong style="color:#ffffff;">{right_badge}</strong></div>''' if right_badge else ""
    st.markdown(
        f"""<div class="ardp-page">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;position:relative;z-index:2;">
            <div>
              <div class="eyebrow">{eyebrow}</div>
              <div class="title">{title}</div>
              <p class="sub">{subtitle}</p>
            </div>
            {badge_html}
          </div>
        </div>""",
        unsafe_allow_html=True
    )

def kpi_card_exec(col, label, value, note, icon="target", accent="green", mini_gauge=None):
    icons = {
        "target": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#18B894" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
        "bars": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#087F68" stroke-width="2.2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
        "gauge": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8DC8F0" stroke-width="2.2"><path d="M12 2v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="M20 12h2"/><path d="M2 12h2"/><path d="m19.07 4.93-1.41 1.41"/><path d="M12 6a6 6 0 0 0-6 6v4a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-4a6 6 0 0 0-6-6Z"/><path d="m14 14-2-2"/></svg>',
        "coins": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E9B65B" stroke-width="2.2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>',
        "pulse": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E87575" stroke-width="2.2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
        "box": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#327CC1" stroke-width="2.2"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>',
    }
    svg_icon = icons.get(icon, icons["target"])
    extra_badge = f'<div class="mini-radial-badge">{mini_gauge}</div>' if mini_gauge is not None else ""
    
    val_style = 'color: #ffffff;'
    if icon == "pulse":
        if "atrasado" in str(value).lower():
            val_style = 'color: #E87575;'
        elif "ritmo" in str(value).lower() or "ok" in str(value).lower():
            val_style = 'color: #18B894;'
        elif "atención" in str(value).lower() or "riesgo" in str(value).lower():
            val_style = 'color: #E9B65B; font-size: 19px;'

    html_card = (
        f'<div class="ardp-kpi">'
        f'<div class="card-header-row">'
        f'<div class="card-header-left">'
        f'<div class="kpi-icon-badge {accent}">{svg_icon}</div>'
        f'<div class="label">{label}</div>'
        f'</div>'
        f'{extra_badge}'
        f'</div>'
        f'<div class="value" style="{val_style}">{value}</div>'
        f'<div class="note">{note}</div>'
        f'</div>'
    )
    col.markdown(html_card, unsafe_allow_html=True)

def render_cumplimiento_gauge(pct_val, venta_acum, meta_anual, falta_alcanzar):
    import math
    pct_clamped = min(max(pct_val, 0.0), 100.0)
    rad = math.pi * (1.0 - (pct_clamped / 100.0))
    cx, cy, r = 100, 95, 70
    x_end = cx + r * math.cos(rad)
    y_end = cy - r * math.sin(rad)
    large_arc = 1 if pct_clamped > 50 else 0
    if pct_clamped <= 0.05:
        arc_path = "M 30 95 A 70 70 0 0 1 31 94"
    else:
        arc_path = f"M 30 95 A 70 70 0 {large_arc} 1 {x_end:.1f} {y_end:.1f}"

    return (
        f'<div class="ardp-panel" style="display:flex;flex-direction:column;justify-content:space-between;height:100%;">'
        f'<div>'
        f'<div class="ardp-panel-title">'
        f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#18B894" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="m12 6 4 6h-8l4-6Z"/></svg>'
        f' Cumplimiento trimestral'
        f'</div>'
        f'<div style="text-align:center;margin:10px 0 6px;">'
        f'<svg viewBox="0 0 200 115" style="width:170px;max-width:100%;display:inline-block;">'
        f'<path d="M 30 95 A 70 70 0 0 1 170 95" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="14" stroke-linecap="round"/>'
        f'<path d="{arc_path}" fill="none" stroke="#18B894" stroke-width="14" stroke-linecap="round"/>'
        f'<text x="100" y="78" text-anchor="middle" font-size="24" font-weight="700" fill="#ffffff" font-family="\'Inter\', sans-serif">{pct_val:.3f}%</text>'
        f'<text x="100" y="94" text-anchor="middle" font-size="10.5" fill="#a3c1dc" font-family="\'Inter\', sans-serif">Avance del año</text>'
        f'</svg>'
        f'</div>'
        f'</div>'
        f'<div>'
        f'<div class="ardp-statline"><span class="name">ℹ️ Venta acumulada:</span><span class="num">{venta_acum}</span></div>'
        f'<div class="ardp-statline"><span class="name">Meta anual:</span><span class="num">{meta_anual}</span></div>'
        f'<div class="ardp-statline"><span class="name">Falta por alcanzar:</span><span class="num">{falta_alcanzar}</span></div>'
        f'</div>'
        f'</div>'
    )

def fmt(cop_amount, fx):
    """Todo se guarda en COP (así lo entrega Falabella); se muestra en USD
    porque así lo pidió el jefe, dividiendo por la tasa de cambio."""
    return "US$ " + f"{cop_amount / fx:,.0f}"


def pct(a, b):
    return (a / b - 1) * 100 if b else None


def usd_corto(v):
    """Millones para cifras grandes y separador de miles para importes menores."""
    valor = float(v or 0)
    return f"US$ {valor / 1e6:,.2f} M" if abs(valor) >= 1e6 else f"US$ {valor:,.0f}"


def kpi(contenedor, titulo, valor, fs="22px", nowrap=True):
    """Cifra con título estilizada como tarjeta ejecutiva oscura (.ardp-op).
    El signo $ va como código HTML para que Streamlit no lo lea como fórmula."""
    v = str(valor).replace("$", "&#36;")
    t = str(titulo).replace("$", "&#36;")
    ws = "nowrap" if nowrap else "normal"
    contenedor.markdown(
        f"<div class='ardp-op'>"
        f"<div class='label'>{t}</div>"
        f"<div class='value' style='font-size:{fs};white-space:{ws}'>{v}</div>"
        f"</div>",
        unsafe_allow_html=True
    )


def semaforo(real, esperado, meta):
    """Compara lo vendido con lo que se debería llevar a hoy según el presupuesto."""
    if not meta or meta <= 0:
        return "⚪ Sin meta"
    if not esperado or esperado <= 0:
        return "⚪ Por iniciar"
    r = real / esperado * 100
    if r >= SEMAFORO_VERDE:
        return "🟢 En ritmo"
    if r >= SEMAFORO_AMARILLO:
        return "🟡 Atención requerida"
    return "🔴 Atrasado"


def calcular_meses(ppto, diario, fx, hoy):
    """Una fila por mes del presupuesto: meta, venta real, lo esperado a hoy, falta,
    venta diaria requerida y semáforo."""
    filas = []
    for _, r in ppto.iterrows():
        ini_m, fin_m = (pd.Timestamp(x) for x in periodo_a_fechas(r["periodo"]))
        meta = float(r["presupuesto_usd"])
        real = float(diario["ventas"].loc[ini_m:fin_m].sum()) / fx
        falta = max(meta - real, 0)
        dias_mes = (fin_m - ini_m).days + 1
        if hoy > fin_m:
            estado, req, esperado = "Cerrado", None, meta
        elif hoy >= ini_m:
            estado, req = "En curso", falta / ((fin_m - hoy).days + 1)
            esperado = meta * ((hoy - ini_m).days + 1) / dias_mes
        else:
            estado, req, esperado = "Por iniciar", meta / dias_mes, 0.0
        filas.append({"trimestre": r["trimestre"], "periodo": r["periodo"], "ini": ini_m,
                      "fin": fin_m, "meta": meta, "real": real, "esperado": esperado,
                      "falta": falta, "estado": estado, "req": req,
                      "semaforo": semaforo(real, esperado, meta)})
    return pd.DataFrame(filas)


# ===== PALETA OFICIAL: ZAFIRO ESMERALDA PREMIUM =====
COLOR_META_AZUL = "#327CC1"       # Azul para metas y referencias
COLOR_REAL_ESMERALDA = "#087F68"  # Esmeralda para ventas reales
COLOR_JADE = "#18B894"            # Jade luminoso para segunda serie
COLOR_AZUL_HIELO = "#8DC8F0"      # Azul hielo para comparaciones
COLOR_AMBAR = "#E9B65B"           # Ámbar para atención requerida
COLOR_CORAL = "#E87575"           # Rojo suave para estados críticos
COLOR_DORADO = "#D4AF37"          # Dorado discreto de marca FINART
COLOR_TEXTO_SEC = "#A3C1DC"       # Texto secundario

VERDE_1 = COLOR_REAL_ESMERALDA    # esmeralda: serie principal / ventas reales
VERDE_2 = COLOR_JADE              # jade: comparaciones
VERDE_3 = COLOR_AZUL_HIELO        # azul hielo: referencias
VERDE_4 = COLOR_META_AZUL         # azul: metas
VERDE_5 = COLOR_META_AZUL         # metas / barras de referencia
VERDE_SUAVE = "#163859"
GRIS_GRAF = COLOR_TEXTO_SEC


def mostrar(grafico):
    """Muestra una gráfica Altair a todo el ancho (según la versión de Streamlit)."""
    try:
        # FINART ejecutivo — tema oscuro Zafiro Esmeralda: fondo transparente, ejes claros.
        try:
            grafico = grafico.properties(background="transparent")
            grafico = grafico.configure_axis(
                labelColor=COLOR_TEXTO_SEC, titleColor="#ffffff",
                domainColor="rgba(141,200,240,0.18)", tickColor="rgba(141,200,240,0.18)",
                gridColor="rgba(141,200,240,0.08)"
            )
            grafico = grafico.configure_legend(labelColor="#ffffff", titleColor=COLOR_TEXTO_SEC)
            grafico = grafico.configure_view(strokeWidth=0)
        except Exception:
            pass
        try:
            st.altair_chart(grafico, width="stretch")
        except TypeError:
            st.altair_chart(grafico, use_container_width=True)
    except Exception as e:
        st.warning(f"No pude dibujar esta gráfica: {e}")


def grafico_meta_real_agrupado(datos, x_col="Trimestre", meta_col="Meta", real_col="Real", alto=260):
    """Visualización ejecutiva de columnas agrupadas con etiquetas de valor superior.
    Paleta Zafiro Esmeralda: Meta en Azul (#327CC1), Real en Jade (#18B894)."""
    df_largo = datos.melt(
        id_vars=[x_col],
        value_vars=[meta_col, real_col],
        var_name="Serie",
        value_name="Valor"
    )
    df_largo["Serie_Label"] = df_largo["Serie"].map({meta_col: "Meta trimestral", real_col: "Venta real"}).fillna(df_largo["Serie"])
    
    orden_x = list(datos[x_col])
    color_scale = alt.Scale(
        domain=["Meta trimestral", "Venta real"],
        range=[COLOR_META_AZUL, COLOR_JADE]
    )
    
    base = alt.Chart(df_largo).encode(
        x=alt.X(f"{x_col}:N", sort=orden_x, title=None,
                axis=alt.Axis(labelAngle=0, labelFontSize=11, labelColor=COLOR_TEXTO_SEC,
                              domainColor="rgba(141,200,240,0.18)", tickColor="rgba(141,200,240,0.18)")),
        xOffset=alt.XOffset("Serie_Label:N", sort=["Meta trimestral", "Venta real"]),
        y=alt.Y("Valor:Q", title="US$", axis=alt.Axis(format=",.0f", labelColor=COLOR_TEXTO_SEC,
                                                     gridColor="rgba(141,200,240,0.08)", domain=False, tickSize=0)),
        color=alt.Color("Serie_Label:N", scale=color_scale, legend=None)
    )
    
    barras = base.mark_bar(
        cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=32
    ).encode(
        tooltip=[
            alt.Tooltip(f"{x_col}:N", title="Periodo"),
            alt.Tooltip("Serie_Label:N", title="Concepto"),
            alt.Tooltip("Valor:Q", title="US$", format=",.0f")
        ]
    )
    
    texto = base.mark_text(
        dy=-8, fontSize=11, fontWeight=600, color="#ffffff"
    ).encode(
        text=alt.Text("Valor:Q", format=",.0f")
    )
    
    return (barras + texto).properties(height=alto, background="transparent").configure_view(stroke="transparent")


def grafico_dona_distribucion(datos, cat_col, val_col, titulo_centro="US$ 1.50 M", subtitulo_centro="Meta total", alto=175):
    """Gráfico de dona ejecutiva con paleta Zafiro Esmeralda centrada y sin desbordes."""
    colores_dona = [COLOR_JADE, COLOR_META_AZUL, COLOR_REAL_ESMERALDA, COLOR_AZUL_HIELO, "#2563EB"]
    df = datos.copy()
    total = df[val_col].sum()
    df["Pct"] = (df[val_col] / total * 100).round(1) if total else 0
    
    base = alt.Chart(df).encode(
        theta=alt.Theta(f"{val_col}:Q", stack=True),
        color=alt.Color(f"{cat_col}:N", scale=alt.Scale(range=colores_dona[:len(df)]), legend=None),
        tooltip=[
            alt.Tooltip(f"{cat_col}:N", title="Categoría"),
            alt.Tooltip(f"{val_col}:Q", title="Valor US$", format=",.0f"),
            alt.Tooltip("Pct:Q", title="Participación", format=".1f")
        ]
    )
    
    dona = base.mark_arc(innerRadius=48, outerRadius=70, stroke="#071729", strokeWidth=2)
    
    texto_centro = alt.Chart(pd.DataFrame([{"t": titulo_centro, "s": subtitulo_centro}])).mark_text(
        text=titulo_centro, fontSize=13, fontWeight=700, color="#ffffff", dy=-4
    )
    sub_centro = alt.Chart(pd.DataFrame([{"t": titulo_centro, "s": subtitulo_centro}])).mark_text(
        text=subtitulo_centro, fontSize=9, fontWeight=500, color=COLOR_TEXTO_SEC, dy=11
    )
    
    return (dona + texto_centro + sub_centro).properties(
        height=alto,
        padding={"top": 12, "bottom": 8, "left": 10, "right": 10},
        background="transparent"
    ).configure_view(stroke="transparent")


def grafico_meta_real(datos, x, orden):
    """Comparación ejecutiva: meta en verde claro y venta real en verde oscuro."""
    base = alt.Chart(datos).encode(
        x=alt.X(f"{x}:N", sort=orden, title=None,
                axis=alt.Axis(labelAngle=0, labelFontSize=11, labelColor="#94a3b8",
                              domainColor="rgba(255,255,255,0.12)", tickColor="rgba(255,255,255,0.12)"))
    )
    tooltip = [x, alt.Tooltip("Meta:Q", title="Meta (US$)", format=",.0f"),
               alt.Tooltip("Real:Q", title="Venta real (US$)", format=",.0f")]
    meta = base.mark_bar(size=42, color=VERDE_5, cornerRadiusTopLeft=3,
                         cornerRadiusTopRight=3).encode(
        y=alt.Y("Meta:Q", title="US$", axis=alt.Axis(format=",.0f", labelColor="#94a3b8",
                                                     gridColor="rgba(255,255,255,0.07)", domain=False, tickSize=0)),
        tooltip=tooltip)
    real = base.mark_bar(size=20, color=VERDE_1, cornerRadiusTopLeft=3,
                         cornerRadiusTopRight=3).encode(y="Real:Q", tooltip=tooltip)
    return (meta + real).properties(height=220, background="transparent").configure_view(stroke="transparent").configure(
        axis=alt.Axis(labelFont="Arial", titleFont="Arial", titleColor="#e2e8f0", titleFontSize=11)
    )


def barras_simple(datos, x, y, orden, color=VERDE_1, alto=240):
    """Barras verticales sencillas (para comparar 2 o 3 valores)."""
    return alt.Chart(datos).mark_bar(color=color).encode(
        x=alt.X(f"{x}:N", sort=orden, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{y}:Q", title="US$"),
        tooltip=[x, alt.Tooltip(f"{y}:Q", format=",.0f")]).properties(height=alto)


def grafico_diario(datos, meta_dia):
    """Ventas de cada día del mes y línea con la meta diaria promedio."""
    barras = alt.Chart(datos).mark_bar(color=VERDE_2).encode(
        x=alt.X("Fecha:T", title=None, axis=alt.Axis(format="%d-%b")),
        y=alt.Y("Real:Q", title="US$"),
        tooltip=[alt.Tooltip("Fecha:T", format="%d-%b"), alt.Tooltip("Real:Q", format=",.0f")])
    linea = alt.Chart(pd.DataFrame({"y": [meta_dia]})).mark_rule(
        color=VERDE_3, strokeDash=[6, 4]).encode(y="y:Q")
    return (barras + linea).properties(height=245)


def grafico_acumulado(datos, serie_real="Acumulado real", serie_meta="Ruta del presupuesto", alto=300):
    """Gráfica acumulada explícita en Altair.
    Evita st.line_chart, que en algunas versiones de Streamlit/Altair
    puede fallar al inferir el tipo de la serie/columna.
    """
    df = datos.copy().reset_index()
    fecha_col = df.columns[0]
    df = df.rename(columns={fecha_col: "Fecha"})
    long = df.melt(id_vars=["Fecha"], var_name="Serie", value_name="Valor")
    long["Fecha"] = pd.to_datetime(long["Fecha"], errors="coerce")
    long["Valor"] = pd.to_numeric(long["Valor"], errors="coerce")
    long = long.dropna(subset=["Fecha", "Valor"])
    return alt.Chart(long).mark_line(point=False).encode(
        x=alt.X("Fecha:T", title=None, axis=alt.Axis(format="%d-%b", labelAngle=0)),
        y=alt.Y("Valor:Q", title="US$", axis=alt.Axis(format=",.0f")),
        color=alt.Color("Serie:N", title=None,
                        scale=alt.Scale(domain=[serie_real, serie_meta],
                                        range=[VERDE_1, VERDE_4])),
        tooltip=[alt.Tooltip("Fecha:T", format="%d-%b"),
                 alt.Tooltip("Serie:N", title="Serie"),
                 alt.Tooltip("Valor:Q", format=",.0f", title="US$")]
    ).properties(height=alto)


def grafico_resumen_ejecutivo(datos, alto=300):
    """Vista ejecutiva: barras de ruta acumulada y línea de venta acumulada real.
    Usa exclusivamente la serie diaria ya calculada desde presupuesto y ventas.
    """
    if datos is None or datos.empty:
        return alt.Chart(pd.DataFrame({"Fecha": [], "Valor": []})).mark_bar().encode(x="Fecha:T", y="Valor:Q")
    df = datos.copy().reset_index()
    df = df.rename(columns={df.columns[0]: "Fecha"})
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    for col in ["Acumulado real", "Ruta del presupuesto"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Fecha"])
    # Un punto por fin de mes mantiene el gráfico legible y evita miles de marcas.
    df["Mes"] = df["Fecha"].dt.to_period("M")
    mensual = df.groupby("Mes", sort=True).tail(1).copy()
    mensual["Periodo"] = mensual["Fecha"].dt.strftime("%b-%y")
    mensual["Acumulado real"] = mensual["Acumulado real"].where(mensual["Fecha"] <= pd.Timestamp.today().normalize())
    base = alt.Chart(mensual).encode(
        x=alt.X("Periodo:N", sort=mensual["Periodo"].tolist(), title=None,
                axis=alt.Axis(labelAngle=0, labelColor="#94a3b8", labelLimit=75)),
        tooltip=["Periodo", alt.Tooltip("Ruta del presupuesto:Q", title="Ruta acumulada (US$)", format=",.0f"),
                 alt.Tooltip("Acumulado real:Q", title="Venta acumulada (US$)", format=",.0f")]
    )
    barras = base.mark_bar(color="#1a5c45", opacity=1, size=25, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        y=alt.Y("Ruta del presupuesto:Q", title="US$", axis=alt.Axis(format=",.0f", gridColor="rgba(255,255,255,0.07)", labelColor="#94a3b8")))
    linea = base.mark_line(color="#00e599", strokeWidth=3, point=alt.OverlayMarkDef(color="#00e599", size=55)).encode(
        y=alt.Y("Acumulado real:Q", title="US$", axis=alt.Axis(format=",.0f")))
    return (barras + linea).resolve_scale(y="shared").properties(height=alto, background="transparent").configure_view(stroke="transparent").configure_legend(
        labelColor="#cbd5e1", titleColor="#e2e8f0")


@st.cache_data(show_spinner="Leyendo presupuesto...")
def _leer_ppto(ruta, modificado):
    with open(ruta, "rb") as f:
        return leer_presupuesto(io.BytesIO(f.read()))


@st.cache_data(show_spinner="Leyendo costos...")
def _leer_costos(ruta, modificado):
    with open(ruta, "rb") as f:
        return leer_margenes(io.BytesIO(f.read()))


def _trimestre_con_anio(trim, periodo):
    """'Q3' -> 'Q3 2026' (el año sale de las fechas del periodo)."""
    anio = periodo_a_fechas(periodo)[0].year
    t = str(trim)
    return t if str(anio) in t else f"{t} {anio}"


def puerta():
    """Contraseña simple para pruebas. Para compartir de verdad, usar login por correo."""
    clave = os.getenv("DASHBOARD_PASSWORD")
    if not clave or st.session_state.get("ok"):
        return
    intento = st.text_input("Contraseña", type="password")
    if intento and hmac.compare_digest(intento, clave):
        st.session_state["ok"] = True
        st.rerun()
    if intento:
        st.error("Contraseña incorrecta")
    st.stop()


def datos_vacios():
    """Esquema vacío cuando no hay ventas reales; nunca fabrica ventas de muestra."""
    return pd.DataFrame(columns=[
        "order_item_id", "order_id", "created_at", "updated_at", "sku",
        "producto", "estado", "precio_pagado", "precio_item", "envio", "moneda"
    ])

def init_db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS stock_snapshots "
                "(fecha TEXT, sku TEXT, cantidad INTEGER, PRIMARY KEY (fecha, sku))")
    con.execute("CREATE TABLE IF NOT EXISTS stock_inicial "
                "(sku TEXT PRIMARY KEY, cantidad INTEGER, fecha TEXT)")
    con.execute("""CREATE TABLE IF NOT EXISTS catalogo_productos (
                    sku TEXT PRIMARY KEY,
                    estado TEXT NOT NULL DEFAULT 'pendiente',
                    fecha_registro TEXT,
                    origen TEXT
                )""")
    con.commit()
    con.close()


@st.cache_data(ttl=300)
def cargar():
    if os.path.exists(DB):
        con = sqlite3.connect(DB)
        try:
            df = pd.read_sql("SELECT * FROM order_items", con)
        except Exception:
            df = pd.DataFrame()
        con.close()
        if len(df):
            return df, False
    return datos_vacios(), True


SKU_NULOS = {"", "nan", "none", "null", "<na>", "nat"}


def sku_valido(v):
    """False si el SKU viene vacío o nulo (None, NaN, 'nan', 'None', etc.)."""
    return v is not None and str(v).strip().lower() not in SKU_NULOS


def limpiar_stock(df_sku_cantidad):
    """Deja solo las filas con SKU y cantidad válidos (las demás se omiten)."""
    d = df_sku_cantidad.copy()
    d["cantidad"] = pd.to_numeric(d["cantidad"], errors="coerce")
    ok = d["sku"].apply(sku_valido).astype(bool) & d["cantidad"].notna()
    d = d[ok].copy()
    d["cantidad"] = d["cantidad"].astype(int)
    return d


def cargar_stock_historico():
    if not os.path.exists(DB):
        return pd.DataFrame(columns=["fecha", "sku", "cantidad"])
    con = sqlite3.connect(DB)
    try:
        df = pd.read_sql("SELECT * FROM stock_snapshots", con)
    except Exception:
        df = pd.DataFrame(columns=["fecha", "sku", "cantidad"])
    con.close()
    if len(df):
        df = df[df["sku"].apply(sku_valido).astype(bool) & df["cantidad"].notna()]
    return df


def cargar_stock_inicial():
    """Inventario con el que arrancó la operación.

    Si aún no existe un registro explícito de stock inicial, se toma como referencia
    la primera carga histórica de stock. Esto conserva el dato real ya cargado en
    Seller Center y evita pedir al usuario que lo vuelva a registrar manualmente.
    """
    vacio = pd.DataFrame(columns=["sku", "cantidad", "fecha"])
    if not os.path.exists(DB):
        return vacio
    con = sqlite3.connect(DB)
    try:
        d = pd.read_sql("SELECT sku, cantidad, fecha FROM stock_inicial", con)
    except Exception:
        d = vacio
    if len(d):
        d = d[d["sku"].apply(sku_valido).astype(bool) & d["cantidad"].notna()]
        con.close()
        return d
    try:
        h = pd.read_sql("SELECT sku, cantidad, fecha FROM stock_snapshots", con)
    except Exception:
        h = vacio
    con.close()
    if len(h):
        h = h[h["sku"].apply(sku_valido).astype(bool) & h["cantidad"].notna()].copy()
        if len(h):
            primera = h["fecha"].min()
            return h[h["fecha"].eq(primera)].copy()
    return vacio


def registrar_stock_inicial(stock_por_sku):
    """Guarda el stock dado (Serie sku -> cantidad) como inventario inicial."""
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS stock_inicial "
                "(sku TEXT PRIMARY KEY, cantidad INTEGER, fecha TEXT)")
    con.execute("DELETE FROM stock_inicial")
    for sku, cant in stock_por_sku.items():
        con.execute("INSERT OR REPLACE INTO stock_inicial VALUES (?,?,?)", (str(sku), int(cant), str(date.today())))
    con.commit()
    con.close()


def guardar_stock(df_sku_cantidad):
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS stock_snapshots "
                "(fecha TEXT, sku TEXT, cantidad INTEGER, PRIMARY KEY (fecha, sku))")
    hoy = str(date.today())
    for _, r in df_sku_cantidad.iterrows():
        con.execute("INSERT OR REPLACE INTO stock_snapshots VALUES (?,?,?)",
                    (hoy, r["sku"], int(r["cantidad"])))
    con.commit()
    con.close()


def preparar(df, ini=None, fin=None):
    """Ventas y órdenes por día. Sin ini/fin: desde la primera venta hasta hoy."""
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["created_at"]).dt.normalize()
    df = df[~df["estado"].str.lower().isin(EXCLUIDOS)]
    diario = df.groupby("fecha").agg(ventas=("precio_pagado", "sum"),
                                     ordenes=("order_id", "nunique"))
    hoy_ = pd.Timestamp(date.today())
    ini = ini if ini is not None else (diario.index.min() if len(diario) else hoy_)
    fin = fin if fin is not None else hoy_
    rango = pd.date_range(ini, fin)
    if len(rango) == 0:
        return pd.DataFrame({"ventas": pd.Series(dtype=float), "ordenes": pd.Series(dtype=int)},
                            index=pd.DatetimeIndex([]))
    return diario.reindex(rango, fill_value=0)


puerta()
init_db()
df, es_demo = cargar()
df = df[df["created_at"].notna()]
df = df.assign(sku=[_sku_str(s) if sku_valido(s) else "(sin SKU)" for s in df["sku"]])

# Catálogo persistente: conserva referencias futuras sin incorporarlas automáticamente al dashboard.
# Primera ejecución: los SKU que ya tienen ventas en la base actual se consideran activos.
# Nuevos SKU detectados en ventas, inventario inicial/histórico o costos quedan pendientes.
def _registrar_sku_catalogo(sku, estado="pendiente", origen="detección local"):
    sku = _sku_str(sku)
    if not sku_valido(sku):
        return
    con_cat = sqlite3.connect(DB)
    con_cat.execute(
        "INSERT OR IGNORE INTO catalogo_productos (sku, estado, fecha_registro, origen) VALUES (?,?,?,?)",
        (sku, estado, str(date.today()), origen)
    )
    con_cat.commit()
    con_cat.close()

def _leer_catalogo_productos():
    con_cat = sqlite3.connect(DB)
    try:
        resultado = pd.read_sql("SELECT sku, estado, fecha_registro, origen FROM catalogo_productos", con_cat)
    except Exception:
        resultado = pd.DataFrame(columns=["sku", "estado", "fecha_registro", "origen"])
    finally:
        con_cat.close()
    return resultado

# SKU actuales conocidos por ventas (solo para inicializar el catálogo una única vez).
_skus_ventas_actuales = sorted({
    _sku_str(s) for s in df["sku"].dropna().unique()
    if sku_valido(_sku_str(s))
})
_catalogo_existente = _leer_catalogo_productos()
if _catalogo_existente.empty and _skus_ventas_actuales:
    con_cat = sqlite3.connect(DB)
    for _sku in _skus_ventas_actuales:
        con_cat.execute(
            "INSERT OR IGNORE INTO catalogo_productos (sku, estado, fecha_registro, origen) VALUES (?,?,?,?)",
            (_sku, "activo", str(date.today()), "ventas existentes al iniciar catálogo")
        )
    con_cat.commit()
    con_cat.close()

# Registrar SKU que aparezcan después de crear el catálogo, sin activarlos automáticamente.
for _sku in _skus_ventas_actuales:
    _registrar_sku_catalogo(_sku, "pendiente", "ventas")
try:
    _hist_catalogo = cargar_stock_historico()
    if len(_hist_catalogo) and "sku" in _hist_catalogo.columns:
        for _sku in _hist_catalogo["sku"].dropna().unique():
            _registrar_sku_catalogo(_sku, "pendiente", "inventario histórico")
except Exception:
    pass
try:
    _ini_catalogo = cargar_stock_inicial()
    if len(_ini_catalogo) and "sku" in _ini_catalogo.columns:
        for _sku in _ini_catalogo["sku"].dropna().unique():
            _registrar_sku_catalogo(_sku, "pendiente", "inventario inicial")
except Exception:
    pass
try:
    if os.path.exists(FILE_COSTOS):
        _costos_catalogo = _leer_costos(FILE_COSTOS, os.path.getmtime(FILE_COSTOS))
        if len(_costos_catalogo) and "sku" in _costos_catalogo.columns:
            for _sku in _costos_catalogo["sku"].dropna().unique():
                _registrar_sku_catalogo(_sku, "pendiente", "archivo de costos")
except Exception:
    pass

_catalogo = _leer_catalogo_productos()

# Activar como catálogo inicial los SKU del inventario de arranque (14 referencias del baseline)
# y las ventas ya conocidas al crear el catálogo. Nuevas referencias de snapshots posteriores
# permanecen pendientes y no se suman automáticamente a los indicadores.
_skus_base = set()
try:
    _stock_base = cargar_stock_inicial()
    if len(_stock_base) and "sku" in _stock_base.columns:
        _skus_base.update(_sku_str(s) for s in _stock_base["sku"].dropna().unique() if sku_valido(_sku_str(s)))
except Exception:
    pass

if _skus_base:
    con_cat = sqlite3.connect(DB)
    for _sku in _skus_base:
        con_cat.execute(
            "INSERT INTO catalogo_productos (sku, estado, fecha_registro, origen) VALUES (?,?,?,?) "
            "ON CONFLICT(sku) DO UPDATE SET estado='activo'",
            (_sku, "activo", str(date.today()), "inventario de arranque")
        )
    con_cat.commit()
    con_cat.close()

_catalogo = _leer_catalogo_productos()
# Mostrar y calcular solo productos activos.
skus_todos = sorted(_catalogo.loc[_catalogo["estado"].eq("activo"), "sku"].astype(str).unique())
df = df[df["sku"].astype(str).isin(skus_todos)].copy()

# Convención visual: siempre SKU, sin mezclarlo con el nombre comercial.
etiquetas_sku = {str(s): str(s) for s in skus_todos}
def nombre_producto(sku):
    return str(sku)
def etiqueta_producto(sku, max_len=34):
    return str(sku)

def activar_sku_catalogo(sku):
    """Activa una referencia registrada para que participe en el dashboard."""
    con_cat = sqlite3.connect(DB)
    con_cat.execute(
        "UPDATE catalogo_productos SET estado='activo' WHERE sku=?",
        (_sku_str(sku),)
    )
    con_cat.commit()
    con_cat.close()


df_all = df
diario_all = preparar(df_all)
diario = diario_all
hoy = pd.Timestamp(date.today())


if es_demo:
    st.warning("No hay ventas reales cargadas. Ejecuta `python sync.py` para sincronizar Falabella; los indicadores de ventas permanecerán vacíos hasta entonces.")

fx = TASA_USD_COP  # Tasa fija de 3.100 COP/USD usada por el presupuesto; no se muestra en el panel.

# --- Filtros de período: se consultan y comparan dentro de la pestaña Ventas. ---
desde = hasta = None
periodo_txt = "Todo el historial"


def selector_periodo_comparacion(clave, referencia, anio_def=None, mes_def=None, dia_def=None):
    """Selector independiente para comparar dos períodos en Ventas.
    Permite Día, Mes, Año o Rango de fechas. No modifica el resto de la dashboard."""
    anios = list(range(min(referencia.index.min().year, 2026), max(2030, hoy.year) + 1))
    tipo = st.selectbox("Granularidad", ["Día", "Mes", "Año", "Rango de fechas"],
                        key=f"{clave}_tipo")
    if tipo == "Día":
        valor = st.date_input("Día", value=(dia_def or hoy.date()),
                              min_value=referencia.index.min().date(), max_value=hoy.date(),
                              key=f"{clave}_dia")
        d = pd.Timestamp(valor)
        return d, d, f"{d:%d-%m-%Y}", "dia"
    if tipo == "Mes":
        c1, c2 = st.columns(2)
        anio = c1.selectbox("Año", anios, index=anios.index(anio_def) if anio_def in anios else 0,
                            key=f"{clave}_anio")
        mes = c2.selectbox("Mes", MESES_ES, index=(mes_def - 1 if mes_def and 1 <= mes_def <= 12 else 0),
                           key=f"{clave}_mes")
        m = MESES_ES.index(mes) + 1
        n = calendar.monthrange(anio, m)[1]
        ini, fin = pd.Timestamp(anio, m, 1), pd.Timestamp(anio, m, n)
        return ini, fin, f"{mes} {anio}", "mes"
    if tipo == "Año":
        anio = st.selectbox("Año", anios, index=anios.index(anio_def) if anio_def in anios else 0,
                            key=f"{clave}_anio")
        return pd.Timestamp(anio, 1, 1), pd.Timestamp(anio, 12, 31), str(anio), "anio"
    minimo = referencia.index.min().date()
    defecto_ini = max(minimo, (hoy - pd.Timedelta(days=29)).date())
    rango = st.date_input("Desde – hasta", value=(defecto_ini, hoy.date()),
                          min_value=minimo, max_value=hoy.date(), key=f"{clave}_rango")
    if isinstance(rango, (tuple, list)) and len(rango) == 2:
        ini, fin = pd.Timestamp(rango[0]), pd.Timestamp(rango[1])
    else:
        ini = fin = pd.Timestamp(rango)
    return ini, fin, f"{ini:%d-%m-%Y} al {fin:%d-%m-%Y}", "rango"


# La selección de períodos se hace dentro de Ventas para las comparaciones.
df = df_all
diario = preparar(df)
df_per, diario_per = df, diario

# =========================================================================
# PRE-CÁLCULO EJECUTIVO DE DATOS COMPARTIDOS
# Garantiza que el Resumen y todas las pestañas se alimenten con datos reales
# calculados de manera idéntica y sin problemas de orden de ejecución.
# =========================================================================

# 1. Presupuesto y Ruta Oficial
meses = mes_cur = q_cur_datos = grafico_ruta = None
meta_total = real_total = esperado_total = None
proyecto_anio = 1

if os.path.exists(FILE_PPTO):
    try:
        _ppto_pre = _leer_ppto(FILE_PPTO, os.path.getmtime(FILE_PPTO))
        _ppto_pre["trimestre"] = [_trimestre_con_anio(t, p) for t, p in zip(_ppto_pre["trimestre"], _ppto_pre["periodo"])]
        _meses_todos = calcular_meses(_ppto_pre, diario_all, fx, hoy)
        _fechas_inicio = sorted(_meses_todos["ini"].unique())
        for i in range(0, len(_fechas_inicio), 12):
            bloque = _fechas_inicio[i:i + 12]
            if bloque and pd.Timestamp(bloque[0]) <= hoy <= pd.Timestamp(_meses_todos.loc[_meses_todos["ini"] == bloque[-1], "fin"].max()):
                proyecto_anio = i // 12 + 1
                break
        _inicio_idx = (proyecto_anio - 1) * 12
        _fin_idx = min(_inicio_idx + 12, len(_fechas_inicio))
        _inicios_anio = _fechas_inicio[_inicio_idx:_fin_idx]
        meses = _meses_todos[_meses_todos["ini"].isin(_inicios_anio)].copy()
        _metas_anuales = _ppto_pre.attrs.get("metas_anuales", {})
        meta_total = float(_metas_anuales.get(proyecto_anio, meses["meta"].sum()))
        real_total = meses["real"].sum()
        esperado_total = meses["esperado"].sum()
        _cur = meses[meses["estado"] == "En curso"]
        mes_cur = _cur.iloc[0] if len(_cur) else (meses.iloc[0] if len(meses) else None)
        
        # Trimestre actual
        if mes_cur is not None and "trimestre" in mes_cur:
            _cur_q = mes_cur["trimestre"]
            _sub_q = meses[meses["trimestre"] == _cur_q]
            q_cur_datos = {
                "trimestre": _cur_q,
                "meta": _sub_q["meta"].sum(),
                "real": _sub_q["real"].sum(),
                "esperado": _sub_q["esperado"].sum()
            }
        
        # Ruta del presupuesto acumulada
        _dias = pd.date_range(meses["ini"].min(), meses["fin"].max())
        _ruta_dia = pd.Series(0.0, index=_dias)
        for _, fila in meses.iterrows():
            rng = pd.date_range(fila["ini"], fila["fin"])
            _ruta_dia.loc[rng] = fila["meta"] / len(rng)
        _real_dia = (diario_all["ventas"] / fx).reindex(_dias).fillna(0).cumsum()
        _real_dia.loc[_dias > hoy] = np.nan
        grafico_ruta = pd.DataFrame({"Acumulado real": _real_dia, "Ruta del presupuesto": _ruta_dia.cumsum()})
    except Exception:
        pass

# 2. Margen de Costos Acumulado
margen_acum = None
if os.path.exists(FILE_COSTOS):
    try:
        _m_costos = _leer_costos(FILE_COSTOS, os.path.getmtime(FILE_COSTOS))
        if {"sku", "costo_real_cop"}.issubset(_m_costos.columns):
            _m_costos["sku"] = _m_costos["sku"].apply(_sku_str)
            _v_sku = df[~df["estado"].str.lower().isin(EXCLUIDOS)].groupby("sku").agg(
                unidades=("order_id", "count"), ingreso_cop=("precio_pagado", "sum")
            )
            _m_joined = _m_costos.set_index("sku").join(_v_sku).fillna({"unidades": 0, "ingreso_cop": 0})
            _ing_neto = _m_joined["ingreso_cop"].sum() / 1.19
            _costo_tot = (_m_joined["costo_real_cop"] * _m_joined["unidades"]).sum()
            if _ing_neto > 0:
                margen_acum = (_ing_neto - _costo_tot) / _ing_neto * 100
    except Exception:
        pass

# 3. Métricas de Inventario y Salud de Stock
tabla_inv = None
n_criticos = n_sin_mov = n_quiebre = n_riesgo = n_sin_venta = None
try:
    _hist_inv = cargar_stock_historico()
    if len(_hist_inv):
        _ult_dia_inv = _hist_inv["fecha"].max()
        _stock_hoy = _hist_inv[_hist_inv["fecha"] == _ult_dia_inv].set_index("sku")["cantidad"]
        _inicial_inv = cargar_stock_inicial()
        _df_validas_inv = df[~df["estado"].str.lower().isin(EXCLUIDOS)]
        _fechas_v_inv = pd.to_datetime(_df_validas_inv["created_at"])
        _vend_tot = _df_validas_inv.groupby("sku")["order_id"].count()
        _vend_28 = _df_validas_inv[_fechas_v_inv >= hoy - pd.Timedelta(days=28)].groupby("sku")["order_id"].count()
        _vend_mov = _df_validas_inv[_fechas_v_inv >= hoy - pd.Timedelta(days=DIAS_SIN_VENTAS)].groupby("sku")["order_id"].count()
        
        tabla_inv = pd.DataFrame({"stock_actual": _stock_hoy}).join(
            pd.DataFrame({"vendido_total": _vend_tot})).join(
            pd.DataFrame({"vendido_28d": _vend_28})).join(
            pd.DataFrame({"vendido_ventana": _vend_mov})).fillna(0)
        
        tabla_inv["ingresado_estimado"] = tabla_inv["stock_actual"] + tabla_inv["vendido_total"]
        if len(_inicial_inv):
            _ini_s = _inicial_inv.set_index("sku")["cantidad"].astype(float)
            tabla_inv["ingresado_estimado"] = _ini_s.reindex(tabla_inv.index).fillna(tabla_inv["ingresado_estimado"])
            
        _v_sem = tabla_inv["vendido_28d"] / 4
        tabla_inv["semanas_de_stock"] = tabla_inv["stock_actual"] / _v_sem.replace(0, np.nan)
        tabla_inv["inventario_restante_%"] = (tabla_inv["stock_actual"] / tabla_inv["ingresado_estimado"].replace(0, np.nan) * 100)
        tabla_inv["estado"] = np.select(
            [(tabla_inv["semanas_de_stock"] < 2) | (tabla_inv["inventario_restante_%"] <= UMBRAL_CRITICO),
             tabla_inv["inventario_restante_%"] <= UMBRAL_ATENCION],
            ["🔴 Crítico", "🟡 Atención requerida"], default="🟢 OK"
        )
        _sin_m = (tabla_inv["stock_actual"] > 0) & (tabla_inv["vendido_ventana"] == 0)
        n_criticos = int((tabla_inv["estado"] == "🔴 Crítico").sum())
        n_sin_mov = int(_sin_m.sum())
        _quiebre = tabla_inv["stock_actual"] <= 0
        _riesgo = (~_quiebre) & (tabla_inv["semanas_de_stock"] < 2)
        n_quiebre = int(_quiebre.sum())
        n_riesgo = int(_riesgo.sum())
        
        _base_r_sku = _df_validas_inv.groupby("sku")["order_id"].count()
        _base_r_sku = _base_r_sku[_base_r_sku.index != "(sin SKU)"]
        _univ = set(tabla_inv.index)
        n_sin_venta = len(sorted(_univ - set(_base_r_sku.index)))
except Exception:
    pass

# 4. Cancelaciones y Devoluciones
_excl_ped = df[df["estado"].fillna("").str.lower().isin(EXCLUIDOS)]
_ped_tot = df["order_id"].nunique()
n_cancel = _excl_ped["order_id"].nunique()
tasa_cancel = (n_cancel / _ped_tot * 100) if _ped_tot else None

st.markdown("""
<div class="finart-sidebar-brand">
  <div class="brand-word">FINART</div>
  <div class="brand-by">by Agatha</div>
  <div class="brand-line"></div>
  <div class="brand-channel">SELLER CENTER<br><strong>Falabella · Colombia</strong></div>
</div>
<div class="finart-sidebar-footer">
  <div class="sidebar-footer-text">
    JOYAS<br>
    QUE CONECTAN<br>
    HISTORIAS
  </div>
</div>
""", unsafe_allow_html=True)
tab_res, tab_ppto, tab_ventas, tab_prod, tab_inv = st.tabs(
    ["⌂  Resumen", "▣  Presupuesto", "▥  Ventas", "◉  Productos", "◫  Inventario"])

# --- Presupuesto: meta por trimestre y por mes ---
with tab_ppto:
    page_header("FINART · ARDP · FALABELLA COLOMBIA", "Presupuesto", "Avance de la meta, cumplimiento trimestral y ruta esperada · Año de proyecto vigente")
    if desde is not None:
        st.info("El presupuesto se mide siempre con las ventas de todo el negocio; el filtro de período solo afecta la lectura de las ventas.")
    ppto = None
    if os.path.exists(FILE_PPTO):
        try:
            ppto = _leer_ppto(FILE_PPTO, os.path.getmtime(FILE_PPTO))
            ppto["trimestre"] = [_trimestre_con_anio(t, p)
                                 for t, p in zip(ppto["trimestre"], ppto["periodo"])]
        except Exception as e:
            st.error(f"No pude leer el archivo: {e}")
            ppto = None
    else:
        st.info("Falta el archivo del presupuesto: colócalo en la carpeta datos como presupuesto.xlsx.")

    if ppto is not None and len(ppto):
        try:
            meses_todos = calcular_meses(ppto, diario_all, fx, hoy)

            # El dashboard muestra únicamente el año de proyecto vigente.
            # El año vigente se determina por las fechas del Excel, no por el
            # año calendario de enero-diciembre. Para este proyecto: Año 1 =
            # sep-2026 a ago-2027; Año 2 = sep-2027 a ago-2028.
            fechas_inicio = sorted(meses_todos["ini"].unique())
            proyecto_anio = None
            for i in range(0, len(fechas_inicio), 12):
                bloque = fechas_inicio[i:i + 12]
                if bloque and pd.Timestamp(bloque[0]) <= hoy <= pd.Timestamp(meses_todos.loc[meses_todos["ini"] == bloque[-1], "fin"].max()):
                    proyecto_anio = i // 12 + 1
                    break
            if proyecto_anio is None:
                if hoy < pd.Timestamp(meses_todos["ini"].min()):
                    proyecto_anio = 1
                else:
                    proyecto_anio = int(np.ceil(len(fechas_inicio) / 12))

            inicio_idx = (proyecto_anio - 1) * 12
            fin_idx = min(inicio_idx + 12, len(fechas_inicio))
            inicios_anio = fechas_inicio[inicio_idx:fin_idx]
            meses = meses_todos[meses_todos["ini"].isin(inicios_anio)].copy()

            metas_anuales = ppto.attrs.get("metas_anuales", {})
            meta_oficial_anual = float(metas_anuales.get(proyecto_anio, meses["meta"].sum()))
            real_total = meses["real"].sum()
            esperado_total = meses["esperado"].sum()
            meta_total = meta_oficial_anual
            cur = meses[meses["estado"] == "En curso"]
            mes_cur = cur.iloc[0] if len(cur) else None

            # Ruta visual del año vigente: los datos mensuales siguen siendo
            # exactamente los del Excel. La meta oficial anual solo se usa en
            # la tarjeta anual y en el avance anual.
            dias = pd.date_range(meses["ini"].min(), meses["fin"].max())
            ruta_dia = pd.Series(0.0, index=dias)
            for _, fila in meses.iterrows():
                rng = pd.date_range(fila["ini"], fila["fin"])
                ruta_dia.loc[rng] = fila["meta"] / len(rng)
            real_dia = (diario_all["ventas"] / fx).reindex(dias).fillna(0).cumsum()
            real_dia.loc[dias > hoy] = np.nan
            grafico_ruta = pd.DataFrame({"Acumulado real": real_dia,
                                         "Ruta del presupuesto": ruta_dia.cumsum()})

            # Barra de filtros y vista superior (Fiel a la referencia)
            st.markdown(f"""
            <div class="finart-controls-bar">
              <div class="finart-control-group">
                <span class="finart-control-label">Periodo:</span>
                <div style="background:rgba(255,255,255,0.06);padding:5px 12px;border-radius:8px;font-size:12px;font-weight:600;color:#ffffff;display:inline-flex;align-items:center;gap:6px;">
                  <span>📅</span> {meses['periodo'].iloc[0]} - {meses['periodo'].iloc[-1]}
                </div>
              </div>
              <div class="finart-control-group">
                <span class="finart-control-label">Año de proyecto:</span>
                <span style="background:rgba(0,229,153,0.12);color:#00e599;border:1px solid rgba(0,229,153,0.3);padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">Año {proyecto_anio}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Tarjetas KPI Ejecutivas con iconos SVG (Filas superiores de la referencia)
            p1, p2, p3, p4, p5 = st.columns(5, gap="medium")
            kpi_card_exec(p1, f"META AÑO {proyecto_anio}", usd_corto(meta_total), "Meta oficial del año", icon="target", accent="green")
            kpi_card_exec(p2, "ACUMULADO", usd_corto(real_total), "Venta real acumulada", icon="bars", accent="green")
            avance_pct = (real_total / meta_total * 100) if meta_total else 0.0
            kpi_card_exec(p3, "AVANCE DE LA META", f"{avance_pct:.3f}%", "Acumulado / meta", icon="gauge", accent="blue", mini_gauge=f"{avance_pct:.1f}%")
            kpi_card_exec(p4, "FALTA", usd_corto(max(meta_total - real_total, 0)), "Saldo frente a la meta", icon="coins", accent="gold")
            ritmo_txt = semaforo(real_total, esperado_total, meta_total).replace("🔴 ","").replace("🟡 ","").replace("🟢 ","").replace("⚪ ","")
            kpi_card_exec(p5, "ESTADO FRENTE AL PLAN", ritmo_txt, "Lectura del ritmo", icon="pulse", accent="red")

            # --- FILA CENTRAL: Gráfico agrupado principal (68%) + Panel Cumplimiento trimestral con medidor radial (32%) ---
            tq = meses.groupby("trimestre", sort=False).agg(
                meta=("meta", "sum"), real=("real", "sum"), esperado=("esperado", "sum")).reset_index()
            tq["cumplimiento"] = np.where(tq["meta"] > 0, tq["real"] / tq["meta"] * 100, 0.0)
            tq["falta"] = (tq["meta"] - tq["real"]).clip(lower=0)
            tq["estado"] = [semaforo(r, e, mt) for r, e, mt in zip(tq["real"], tq["esperado"], tq["meta"])]

            # Simplificar etiquetas de trimestre para la gráfica: "T1\nSep - Nov", "T2\nDic - Feb", etc.
            def label_trimestre(t_str):
                partes = str(t_str).split()
                return partes[0] if partes else str(t_str)
            tq["Trim_Label"] = tq["trimestre"].map(label_trimestre)

            col_main_chart, col_side_gauge = st.columns([2.1, 1.0], gap="medium")
            with col_main_chart:
                st.markdown(f"""
                <div class="ardp-panel" style="padding-bottom:12px;">
                  <div class="ardp-panel-header">
                    <div>
                      <div class="ardp-panel-title">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                        Meta vs. vendido por trimestre
                      </div>
                      <div class="ardp-panel-sub">Comparación del avance real ({COLOR_JADE}) frente a la meta trimestral ({COLOR_META_AZUL})</div>
                    </div>
                    <div style="font-size:11px;color:{COLOR_TEXTO_SEC};background:rgba(50,124,193,0.15);padding:4px 10px;border-radius:6px;border:1px solid rgba(141,200,240,0.25);">
                      Columnas agrupadas
                    </div>
                  </div>
                """, unsafe_allow_html=True)
                
                # Gráfica agrupada moderna
                chart_q = grafico_meta_real_agrupado(tq, x_col="Trim_Label", meta_col="meta", real_col="real", alto=240)
                mostrar(chart_q)
                
                st.markdown(f"""
                  <div class="ardp-chart-legend" style="justify-content:center;margin-top:6px;">
                    <span><span class="legend-swatch" style="background:{COLOR_META_AZUL};"></span> Meta trimestral</span>
                    <span><span class="legend-swatch" style="background:{COLOR_JADE};"></span> Venta real</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            with col_side_gauge:
                # Medidor SVG ejecutivo moderno de cumplimiento
                falta_val = max(meta_total - real_total, 0)
                gauge_html = render_cumplimiento_gauge(
                    avance_pct,
                    usd_corto(real_total),
                    usd_corto(meta_total),
                    usd_corto(falta_val)
                )
                st.markdown(gauge_html, unsafe_allow_html=True)

            # --- FILA INFERIOR DE 3 PANELES (Fiel a la referencia): Distribución dona (30%), Evolución mensual (38%), Detalle tabla (32%) ---
            col_b1, col_b2, col_b3 = st.columns([1.0, 1.25, 1.05], gap="medium")
            
            with col_b1:
                st.markdown(f"""
                <div class="ardp-panel">
                  <div class="ardp-panel-header">
                    <div>
                      <div class="ardp-panel-title">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>
                        Distribución de la meta anual
                      </div>
                      <div class="ardp-panel-sub">Participación de cada trimestre en la meta total</div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Gráfico de Dona para la distribución
                dona_chart = grafico_dona_distribucion(
                    tq, cat_col="Trim_Label", val_col="meta",
                    titulo_centro=usd_corto(meta_total), subtitulo_centro=f"Año {proyecto_anio}", alto=165
                )
                mostrar(dona_chart)
                
                # Leyenda con valores porcentuales sin indentación múltiple
                total_meta_q = tq["meta"].sum()
                items_leg = []
                for _, r_q in tq.iterrows():
                    pct_q = (r_q["meta"] / total_meta_q * 100) if total_meta_q else 0
                    lbl = r_q["Trim_Label"]
                    val_str = usd_corto(r_q["meta"])
                    items_leg.append(
                        f'<div class="ardp-statline" style="padding:4px 0;">'
                        f'<span class="name" style="display:flex;align-items:center;gap:6px;">'
                        f'<span style="width:8px;height:8px;border-radius:50%;background:{COLOR_JADE};display:inline-block;"></span>'
                        f'{lbl}'
                        f'</span>'
                        f'<span class="num" style="font-size:12px;">{val_str} <span style="color:#64748b;font-weight:400;">({pct_q:.0f}%)</span></span>'
                        f'</div>'
                    )
                legend_html = '<div style="margin-top:6px;padding:0 4px;">' + "".join(items_leg) + '</div>'
                st.markdown(legend_html, unsafe_allow_html=True)

            with col_b2:
                st.markdown(f"""
                <div class="ardp-panel">
                  <div class="ardp-panel-header">
                    <div>
                      <div class="ardp-panel-title">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                        Evolución mensual
                      </div>
                      <div class="ardp-panel-sub">Ventas reales ({COLOR_JADE}) vs. meta mensual ({COLOR_META_AZUL})</div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Evolución mensual con barras de meta y línea de real
                df_meses_evol = meses.copy()
                df_meses_evol["Mes_Nom"] = df_meses_evol["periodo"].map(periodo_mostrar)
                orden_meses = list(df_meses_evol["Mes_Nom"])
                
                base_ev = alt.Chart(df_meses_evol).encode(
                    x=alt.X("Mes_Nom:N", sort=orden_meses, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=10, labelColor=COLOR_TEXTO_SEC))
                )
                bars_ev = base_ev.mark_bar(color=COLOR_META_AZUL, opacity=0.45, cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=16).encode(
                    y=alt.Y("meta:Q", title="US$", axis=alt.Axis(format=",.0f", labelColor=COLOR_TEXTO_SEC, gridColor="rgba(141,200,240,0.08)")),
                    tooltip=["periodo", alt.Tooltip("meta:Q", title="Meta US$", format=",.0f"),
                             alt.Tooltip("real:Q", title="Venta real US$", format=",.0f")]
                )
                line_ev = base_ev.mark_line(color=COLOR_JADE, strokeWidth=2.8, point=alt.OverlayMarkDef(color=COLOR_JADE, size=35, fill="#071729")).encode(
                    y=alt.Y("real:Q", title="US$")
                )
                mostrar((bars_ev + line_ev).properties(height=215))
                st.markdown(f"""
                <div class="ardp-chart-legend" style="justify-content:center;margin-top:4px;">
                  <span><span class="legend-swatch" style="background:{COLOR_META_AZUL};"></span> Meta mensual</span>
                  <span><span class="legend-swatch" style="background:{COLOR_JADE};"></span> Venta real</span>
                </div>
                """, unsafe_allow_html=True)

            with col_b3:
                st.markdown(f"""
                <div class="ardp-panel">
                  <div class="ardp-panel-header">
                    <div>
                      <div class="ardp-panel-title">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                        Detalle por trimestre
                      </div>
                      <div class="ardp-panel-sub">Avance y estado de cada periodo</div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                
                rows_html = []
                for _, row in tq.iterrows():
                    st_cls = "atrasado" if "atrasado" in str(row["estado"]).lower() else ("en-ritmo" if "ritmo" in str(row["estado"]).lower() else "atencion")
                    st_txt = str(row["estado"]).replace("🔴 ","").replace("🟡 ","").replace("🟢 ","").replace("⚪ ","")
                    trim_lbl = str(row["Trim_Label"])
                    meta_str = usd_corto(row["meta"])
                    real_str = usd_corto(row["real"])
                    item_str = (
                        f'<div style="border-bottom:1px solid rgba(141,200,240,0.1);padding:8px 0;display:flex;justify-content:space-between;align-items:center;">'
                        f'<div>'
                        f'<div style="font-weight:700;color:#ffffff;font-size:13px;">{trim_lbl}</div>'
                        f'<div style="font-size:10.5px;color:{COLOR_TEXTO_SEC};">Meta: {meta_str}</div>'
                        f'</div>'
                        f'<div style="text-align:right;">'
                        f'<div style="font-weight:700;color:{COLOR_JADE};font-size:13px;">{real_str}</div>'
                        f'<div style="margin-top:2px;"><span class="badge-pill {st_cls}" style="font-size:9.5px;padding:1px 8px;">{st_txt}</span></div>'
                        f'</div>'
                        f'</div>'
                    )
                    rows_html.append(item_str)
                tabla_html = '<div style="margin-top:4px;padding:0 4px;">' + "".join(rows_html) + '</div>'
                st.markdown(tabla_html, unsafe_allow_html=True)


            # Sección colapsable con el detalle numérico exhaustivo y análisis mensual
            with st.expander("🔍 Auditoría y desglose por trimestre y mes", expanded=False):
                tabla_q = tq[["trimestre", "meta", "real", "cumplimiento", "falta", "estado"]].rename(columns={
                    "trimestre": "Trimestre", "meta": "Meta US$", "real": "Vendido US$",
                    "cumplimiento": "Cumplimiento %", "falta": "Falta US$", "estado": "Semáforo"})
                st.dataframe(
                    tabla_q.style.format({"Meta US$": "US$ {:,.0f}", "Vendido US$": "US$ {:,.0f}",
                                           "Cumplimiento %": "{:.2f}%", "Falta US$": "US$ {:,.0f}"},
                                          na_rep="-"),
                    width="stretch", hide_index=True
                )
                
                st.markdown("---")
                st.markdown("**Consulta mensual detallada**")
                periodos_originales = list(meses["periodo"])
                etiquetas_meses = [periodo_mostrar(p) for p in periodos_originales]
                indice_mes = periodos_originales.index(str(mes_cur["periodo"])) if mes_cur is not None and str(mes_cur["periodo"]) in periodos_originales else 0
                mes_visible = st.selectbox(
                    "Selecciona mes del año de proyecto",
                    etiquetas_meses,
                    index=indice_mes,
                    key="mes_detalle_ppto_fase2"
                )
                mes_sel = periodos_originales[etiquetas_meses.index(mes_visible)]
                fila_m = meses[meses["periodo"].eq(mes_sel)].iloc[0]
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Meta", usd_corto(fila_m["meta"]))
                d2.metric("Real", usd_corto(fila_m["real"]))
                d3.metric("Cumplimiento", f"{fila_m['real']/fila_m['meta']*100:.1f}%" if fila_m["meta"] else "-")
                d4.metric("Falta", usd_corto(fila_m["falta"]))
        except Exception as e:
            st.error(f"No pude armar la vista del presupuesto: {e}")

# --- Ventas: comparación compacta y gráficos conservados ---
with tab_ventas:
    page_header(
        "FINART · ARDP · FALABELLA COLOMBIA",
        "Ventas",
        "Día a día · mes a mes · año a año · comparación de períodos"
    )
    st.markdown(
        '<div class="ardp-badge">Indicador central · Venta real</div>',
        unsafe_allow_html=True
    )

    # =========================
    # KPIs PRINCIPALES
    # =========================
    v_hoy = diario["ventas"].get(hoy, 0)
    v_ayer = diario["ventas"].get(hoy - pd.Timedelta(days=1), 0)
    v_sem_pasada = diario["ventas"].get(hoy - pd.Timedelta(days=7), 0)
    sem = diario["ventas"].loc[hoy - pd.Timedelta(days=6):hoy].sum()
    sem_ant = diario["ventas"].loc[hoy - pd.Timedelta(days=13):hoy - pd.Timedelta(days=7)].sum()
    pct_ayer = f"{pct(v_hoy, v_ayer):+.0f}% vs ayer" if v_ayer else "Sin base previa"
    pct_sem = f"{pct(v_hoy, v_sem_pasada):+.0f}% vs sem. ant." if v_sem_pasada else "Sin base previa"
    pct_7d = f"{pct(sem, sem_ant):+.0f}% vs 7d prev." if sem_ant else "Sin base previa"

    k1, k2, k3, k4 = st.columns(4)
    kpi_card_exec(k1, "Ventas Hoy", fmt(v_hoy, fx), pct_ayer, icon="target", accent="green")
    kpi_card_exec(k2, "Vs. Semana Anterior", fmt(v_hoy, fx), pct_sem, icon="pulse", accent="cyan")
    kpi_card_exec(k3, "Últimos 7 Días", fmt(sem, fx), pct_7d, icon="bars", accent="green")
    kpi_card_exec(k4, "Órdenes Hoy", f"{int(diario['ordenes'].get(hoy, 0)):,} pedidos", "Actividad del día", icon="box", accent="gold")

    # =========================
    # COMPARACIÓN PRINCIPAL · PEDIDO DEL JEFE
    # =========================
    st.markdown('<div class="ardp-section">Comparación comercial directa</div>', unsafe_allow_html=True)
    st.caption("Lectura comparativa de períodos ejecutivos sin alterar fuentes de datos.")

    vv_c = df[~df["estado"].str.lower().isin(EXCLUIDOS)].copy()
    vv_c["fecha"] = pd.to_datetime(vv_c["created_at"]).dt.normalize()

    def datos_periodo(ini, fin):
        limite = min(pd.Timestamp(fin), hoy)
        d_ = vv_c[(vv_c["fecha"] >= pd.Timestamp(ini)) & (vv_c["fecha"] <= limite)].copy()
        ventas_ = d_["precio_pagado"].sum() / fx
        pedidos_ = d_["order_id"].nunique()
        unidades_ = len(d_)
        return d_, ventas_, pedidos_, unidades_

    modo = st.radio(
        "Comparar",
        ["Hoy vs ayer", "Hoy vs mismo día semana anterior", "Mes vs mes", "Año vs año", "Personalizado"],
        horizontal=True,
        key="ventas_modo_comparacion"
    )

    if modo == "Hoy vs ayer":
        ini_a = fin_a = hoy
        ini_b = fin_b = hoy - pd.Timedelta(days=1)
        txt_a, txt_b, tipo_a, tipo_b = "Hoy", "Ayer", "dia", "dia"
    elif modo == "Hoy vs mismo día semana anterior":
        ini_a = fin_a = hoy
        ini_b = fin_b = hoy - pd.Timedelta(days=7)
        txt_a, txt_b, tipo_a, tipo_b = "Hoy", "Mismo día semana anterior", "dia", "dia"
    elif modo == "Mes vs mes":
        ini_a, fin_a = hoy.replace(day=1), hoy
        fin_b = ini_a - pd.Timedelta(days=1)
        ini_b = fin_b.replace(day=1)
        txt_a, txt_b, tipo_a, tipo_b = ini_a.strftime("%B %Y"), ini_b.strftime("%B %Y"), "mes", "mes"
    elif modo == "Año vs año":
        ini_a, fin_a = pd.Timestamp(hoy.year, 1, 1), hoy
        ini_b, fin_b = pd.Timestamp(hoy.year - 1, 1, 1), pd.Timestamp(hoy.year - 1, 12, 31)
        txt_a, txt_b, tipo_a, tipo_b = str(hoy.year), str(hoy.year - 1), "anio", "anio"
    else:
        ca, cb = st.columns(2)
        with ca:
            st.markdown("**Período A**")
            ini_a, fin_a, txt_a, tipo_a = selector_periodo_comparacion("ventas_A", diario_all, anio_def=hoy.year, mes_def=hoy.month, dia_def=hoy.date())
        with cb:
            st.markdown("**Período B**")
            ini_b, fin_b, txt_b, tipo_b = selector_periodo_comparacion("ventas_B", diario_all, anio_def=hoy.year, mes_def=max(1, hoy.month - 1), dia_def=(hoy - pd.Timedelta(days=7)).date())

    da, va, pa, ua = datos_periodo(ini_a, fin_a)
    db, vb, pb, ub = datos_periodo(ini_b, fin_b)
    var_pct = pct(va, vb) if vb else None

    # Tarjetas ejecutivas en fila compacta
    c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 0.9, 1.0, 1.0])
    kpi(c1, f"Venta · {txt_a}", usd_corto(va))
    kpi(c2, f"Venta · {txt_b}", usd_corto(vb))
    kpi(c3, "Variación", f"{var_pct:+.1f}%" if var_pct is not None else "Sin base")
    kpi(c4, "Órdenes A / B", f"{pa:,} / {pb:,}")
    ticket_a = va / pa if pa else None
    ticket_b = vb / pb if pb else None
    kpi(c5, "Ticket A / B", f"{usd_corto(ticket_a)} / {usd_corto(ticket_b)}" if ticket_a is not None and ticket_b is not None else "Sin dato")

    # Gráfica principal adaptada a la lectura: comparación puntual, evolución o año completo.
    if tipo_a == tipo_b == "dia":
        comp = pd.DataFrame({"Periodo": [txt_a, txt_b], "Ventas": [va, vb]})
        x_max = max(comp["Ventas"].max(), 1)
        base = alt.Chart(comp).encode(y=alt.Y("Periodo:N", sort=[txt_a, txt_b], title=None))
        rule = alt.Chart(pd.DataFrame({"x1": [min(va, vb)], "x2": [max(va, vb)], "y": [txt_a]})).mark_rule(strokeWidth=6, color=COLOR_AZUL_HIELO).encode(
            x=alt.X("x1:Q", title="US$"), x2="x2:Q", y=alt.Y("y:N", title=None)
        )
        pts = base.mark_circle(size=170, color=COLOR_JADE).encode(
            x=alt.X("Ventas:Q", title="US$", scale=alt.Scale(domain=[0, x_max * 1.15])),
            tooltip=[alt.Tooltip("Periodo:N", title="Periodo"), alt.Tooltip("Ventas:Q", title="Venta", format=",.2f")]
        )
        labels = base.mark_text(align="left", dx=10, fontWeight="bold", color=COLOR_JADE).encode(
            x="Ventas:Q", text=alt.Text("Ventas:Q", format=",.0f")
        )
        mostrar((rule + pts + labels).properties(height=145))

    elif tipo_a == tipo_b == "mes":
        def acumulado_por_dia(d_, fin_):
            z = d_.groupby(d_["fecha"].dt.day)["precio_pagado"].sum().reindex(range(1, fin_ + 1), fill_value=0)
            return z.cumsum() / fx
        n = max((fin_a - ini_a).days + 1, (fin_b - ini_b).days + 1)
        ma = acumulado_por_dia(da, min(n, (fin_a - ini_a).days + 1))
        mb = acumulado_por_dia(db, min(n, (fin_b - ini_b).days + 1))
        comp = pd.DataFrame({"Día": range(1, n + 1), txt_a: ma.reindex(range(1, n + 1)), txt_b: mb.reindex(range(1, n + 1))})
        long = comp.melt("Día", var_name="Periodo", value_name="Ventas acumuladas").dropna()
        chart = alt.Chart(long).mark_line(point=True, strokeWidth=2.5).encode(
            x=alt.X("Día:Q", title="Día del mes"),
            y=alt.Y("Ventas acumuladas:Q", title="US$", axis=alt.Axis(format=",.0f")),
            color=alt.Color("Periodo:N", title=None, scale=alt.Scale(range=[COLOR_JADE, COLOR_META_AZUL])),
            tooltip=["Día", "Periodo", alt.Tooltip("Ventas acumuladas:Q", format=",.2f")]
        ).properties(height=250)
        mostrar(chart)

    elif tipo_a == tipo_b == "anio":
        ma = da.groupby(da["fecha"].dt.month)["precio_pagado"].sum().reindex(range(1,13), fill_value=0) / fx
        mb = db.groupby(db["fecha"].dt.month)["precio_pagado"].sum().reindex(range(1,13), fill_value=0) / fx
        comp = pd.DataFrame({"Mes": [m[:3].title() for m in MESES_ES], txt_a: ma.values, txt_b: mb.values})
        long = comp.melt("Mes", var_name="Periodo", value_name="Ventas")
        chart = alt.Chart(long).mark_line(point=True, strokeWidth=2.5).encode(
            x=alt.X("Mes:N", sort=[m[:3].title() for m in MESES_ES], title=None),
            y=alt.Y("Ventas:Q", title="US$", axis=alt.Axis(format=",.0f")),
            color=alt.Color("Periodo:N", title=None, scale=alt.Scale(range=[COLOR_JADE, COLOR_META_AZUL])),
            tooltip=["Mes", "Periodo", alt.Tooltip("Ventas:Q", format=",.2f")]
        ).properties(height=260)
        mostrar(chart)

    else:
        # Comparación personalizada: si ambos cortes son del mismo tipo, reutiliza la lectura adecuada.
        comp = pd.DataFrame({"Periodo": [f"A · {txt_a}", f"B · {txt_b}"], "Ventas": [va, vb]})
        chart = alt.Chart(comp).mark_bar(size=56, cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color=COLOR_JADE).encode(
            x=alt.X("Periodo:N", title=None),
            y=alt.Y("Ventas:Q", title="US$", axis=alt.Axis(format=",.0f")),
            tooltip=[alt.Tooltip("Periodo:N", title="Periodo"), alt.Tooltip("Ventas:Q", title="Venta", format=",.2f")]
        ).properties(height=230)
        mostrar(chart)

    with st.expander("⚙️ Comparación personalizada", expanded=False):
        st.caption("Usa este filtro cuando necesites comparar fechas diferentes a las opciones rápidas.")
        ca, cb = st.columns(2)
        with ca:
            ini_xa, fin_xa, txt_xa, tipo_xa = selector_periodo_comparacion("ventas_XA", diario_all, anio_def=hoy.year, mes_def=hoy.month, dia_def=hoy.date())
        with cb:
            ini_xb, fin_xb, txt_xb, tipo_xb = selector_periodo_comparacion("ventas_XB", diario_all, anio_def=hoy.year, mes_def=max(1,hoy.month-1), dia_def=(hoy-pd.Timedelta(days=7)).date())
        _, vx_a, px_a, _ = datos_periodo(ini_xa, fin_xa)
        _, vx_b, px_b, _ = datos_periodo(ini_xb, fin_xb)
        x1,x2,x3=st.columns(3)
        x1.metric(f"A · {txt_xa}", usd_corto(vx_a))
        x2.metric(f"B · {txt_xb}", usd_corto(vx_b))
        x3.metric("Variación", f"{pct(vx_a,vx_b):+.1f}%" if vx_b else "Sin dato")

    # =========================
    # EVOLUCIÓN DE VENTAS · PANELES MODERNOS
    # =========================
    st.markdown('<div class="ardp-section">Evolución y dinámica comercial</div>', unsafe_allow_html=True)
    g1, g2 = st.columns(2, gap="medium")

    with g1:
        st.markdown(f"""
        <div class="ardp-panel">
          <div class="ardp-panel-header">
            <div>
              <div class="ardp-panel-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
                Ritmo diario · Últimos 30 días
              </div>
              <div class="ardp-panel-sub">Venta diaria en dólares (área con línea de tendencia)</div>
            </div>
            <div style="font-size:11px;color:{COLOR_TEXTO_SEC};background:rgba(255,255,255,0.05);padding:4px 10px;border-radius:6px;border:1px solid rgba(255,255,255,0.08);">
              Tendencia 30D
            </div>
          </div>
        """, unsafe_allow_html=True)
        ult30 = diario["ventas"].loc[hoy - pd.Timedelta(days=29):hoy] / fx
        ult30_df = ult30.rename("Ventas").reset_index().rename(columns={"index":"Fecha"})
        
        base_30 = alt.Chart(ult30_df).encode(
            x=alt.X("Fecha:T", title=None, axis=alt.Axis(format="%d-%b", labelAngle=0, labelColor=COLOR_TEXTO_SEC))
        )
        area_30 = base_30.mark_area(
            color=COLOR_REAL_ESMERALDA, opacity=0.35
        ).encode(
            y=alt.Y("Ventas:Q", title="US$", axis=alt.Axis(format=",.0f", gridColor="rgba(141,200,240,0.08)", labelColor=COLOR_TEXTO_SEC))
        )
        line_30 = base_30.mark_line(
            color=COLOR_JADE, strokeWidth=2.8, point=alt.OverlayMarkDef(color=COLOR_JADE, size=30, fill="#071729")
        ).encode(
            y=alt.Y("Ventas:Q", title="US$"),
            tooltip=[alt.Tooltip("Fecha:T", format="%d-%b", title="Fecha"), alt.Tooltip("Ventas:Q", format=",.2f", title="Venta US$")]
        )
        mostrar((area_30 + line_30).properties(height=230))
        st.markdown('</div>', unsafe_allow_html=True)

    with g2:
        st.markdown(f"""
        <div class="ardp-panel">
          <div class="ardp-panel-header">
            <div>
              <div class="ardp-panel-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                Ventas mensuales y media móvil 3M
              </div>
              <div class="ardp-panel-sub">Facturación mensual y promedio móvil trimestral</div>
            </div>
            <div style="font-size:11px;color:{COLOR_TEXTO_SEC};background:rgba(255,255,255,0.05);padding:4px 10px;border-radius:6px;border:1px solid rgba(255,255,255,0.08);">
              Barras + Media
            </div>
          </div>
        """, unsafe_allow_html=True)
        mensual = diario["ventas"].groupby(diario.index.to_period("M").astype(str)).sum() / fx
        mensual_df = mensual.rename("Ventas").reset_index().rename(columns={mensual.index.name or "index":"Mes"})
        mensual_df["Promedio 3M"] = mensual_df["Ventas"].rolling(3, min_periods=1).mean()
        
        base_m = alt.Chart(mensual_df).encode(
            x=alt.X("Mes:N", title=None, axis=alt.Axis(labelAngle=0, labelColor=COLOR_TEXTO_SEC))
        )
        bars_m = base_m.mark_bar(
            color=COLOR_META_AZUL, opacity=0.6, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=24
        ).encode(
            y=alt.Y("Ventas:Q", title="US$", axis=alt.Axis(format=",.0f", gridColor="rgba(141,200,240,0.08)", labelColor=COLOR_TEXTO_SEC)),
            tooltip=["Mes", alt.Tooltip("Ventas:Q", format=",.2f", title="Venta mensual US$")]
        )
        trend_m = base_m.mark_line(
            color=COLOR_JADE, point=alt.OverlayMarkDef(color=COLOR_JADE, size=40, fill="#071729"), strokeWidth=2.8
        ).encode(
            y=alt.Y("Promedio 3M:Q"),
            tooltip=["Mes", alt.Tooltip("Promedio 3M:Q", format=",.2f", title="Media móvil 3M US$")]
        )
        mostrar((bars_m + trend_m).properties(height=230))
        st.markdown('</div>', unsafe_allow_html=True)

    # Día seleccionado: se conserva, pero compacto.
    with st.expander("Consultar un día específico", expanded=False):
        dia_sel = pd.Timestamp(st.date_input(
            "Elige el día",
            value=hoy.date(),
            min_value=diario.index.min().date(),
            max_value=hoy.date(),
            key="dia_consulta_compacta"
        ))
        ventas_dia = df[~df["estado"].str.lower().isin(EXCLUIDOS)].copy()
        ventas_dia["fecha"] = pd.to_datetime(ventas_dia["created_at"]).dt.normalize()
        del_dia = ventas_dia[ventas_dia["fecha"] == dia_sel]
        v_dia = diario["ventas"].get(dia_sel, 0)
        compras_dia = int(diario["ordenes"].get(dia_sel, 0))
        q = st.columns(4)
        q[0].metric("Ventas", fmt(v_dia, fx))
        q[1].metric("Compras", compras_dia)
        q[2].metric("Unidades", len(del_dia))
        q[3].metric("Ticket", fmt(v_dia / compras_dia, fx) if compras_dia else "-")

        if len(del_dia):
            prod = (
                del_dia.groupby("sku")
                .agg(Unidades=("order_id", "count"), Ventas_COP=("precio_pagado", "sum"))
            )
            prod["Ventas_USD"] = prod["Ventas_COP"] / fx
            st.dataframe(
                prod[["Unidades", "Ventas_USD"]]
                .sort_values("Ventas_USD", ascending=False)
                .style.format({"Ventas_USD": "US$ {:,.0f}"}),
                width="stretch",
                hide_index=False
            )
        else:
            st.info("No hubo ventas este día.")

    # Interanual: solo aparece cuando existe histórico real.
    ly1 = diario["ventas"].get(hoy - pd.Timedelta(days=365), None)
    ly2 = diario["ventas"].get(hoy - pd.Timedelta(days=364), None)
    if ly1 is not None or ly2 is not None:
        st.markdown('<div class="subsection">Comparativo interanual</div>', unsafe_allow_html=True)
        inter_df = pd.DataFrame({"Período":["Hoy","Misma fecha año anterior","Mismo día semana año anterior"],"Ventas":[float(v_hoy)/fx,float(ly1 or 0)/fx,float(ly2 or 0)/fx]})
        mostrar(alt.Chart(inter_df).mark_bar().encode(x=alt.X("Período:N", title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y("Ventas:Q", title="US$"), tooltip=["Período", alt.Tooltip("Ventas:Q", format=",.2f")]).properties(height=300))

    # Ticket y UPT se mantienen.
    st.markdown('<div class="subsection">Ticket promedio y UPT</div>', unsafe_allow_html=True)
    ventas_validas = df[~df["estado"].str.lower().isin(EXCLUIDOS)].copy()
    ventas_validas["fecha"] = pd.to_datetime(ventas_validas["created_at"]).dt.normalize()

    ordenes_tot = ventas_validas["order_id"].nunique()
    unidades_tot = len(ventas_validas)
    ingreso_tot = ventas_validas["precio_pagado"].sum()
    ticket_tot = ingreso_tot / ordenes_tot if ordenes_tot else None
    upt_tot = unidades_tot / ordenes_tot if ordenes_tot else None

    tu = st.columns(2)
    tu[0].metric("Ticket promedio acumulado", fmt(ticket_tot, fx) if ticket_tot else "-")
    tu[1].metric("UPT acumulado", f"{upt_tot:.1f}" if upt_tot else "-")


# --- Productos: margen ---
with tab_prod:
    page_header("FINART · ARDP · FALABELLA COLOMBIA", "Productos", "Desempeño por SKU, ventas y margen · lectura ejecutiva del portafolio")
    st.markdown('<div class="ardp-badge">Indicador central · Producto / SKU</div>', unsafe_allow_html=True)
    rank_box = st.container()
    # El espacio del filtro queda después de la lectura rápida (Best Sellers / Slow Movers).
    # Se crea antes del análisis de margen para que la selección pueda aplicarse a sus datos.
    filtro_sku_slot = st.empty()
    with filtro_sku_slot.container():
        with st.container(border=True):
            st.markdown("**Filtrar análisis por SKU**")
            producto_prod = st.selectbox(
                "Código de producto",
                options=["Todos los productos"] + list(skus_todos),
                format_func=lambda s: str(s) if s != "Todos los productos" else s,
                key="productos_sku_foco",
                help="Selecciona un SKU para enfocar el análisis de margen y los detalles del portafolio.")
            st.caption(
                f"Vista filtrada por SKU: {producto_prod}"
                if producto_prod != "Todos los productos"
                else f"Vista general · {len(skus_todos)} SKU activos"
            )
    sel_skus_prod = [] if producto_prod == "Todos los productos" else [producto_prod]
    st.divider()
    st.markdown('<div class="ardp-section">Margen</div>', unsafe_allow_html=True)
    if os.path.exists(FILE_COSTOS):
        try:
            margenes = _leer_costos(FILE_COSTOS, os.path.getmtime(FILE_COSTOS))
            requeridas = {"sku", "costo_real_cop", "margen_lista_%"}
            faltan = requeridas - set(margenes.columns)
            if faltan:
                raise ValueError(f"al archivo le faltan columnas: {sorted(faltan)}. "
                                 f"Columnas que sí encontré: {list(margenes.columns)}")
            margenes["sku"] = margenes["sku"].apply(_sku_str)
            df_m = df_per
            vendido_sku = df_m[~df_m["estado"].str.lower().isin(EXCLUIDOS)].groupby("sku").agg(
                unidades=("order_id", "count"), ingreso_cop=("precio_pagado", "sum"))
            m = margenes.set_index("sku").join(vendido_sku).fillna({"unidades": 0, "ingreso_cop": 0})
            if sel_skus_prod:
                m = m[m.index.isin(sel_skus_prod)]
            m["costo_total_cop"] = m["costo_real_cop"] * m["unidades"]
            # El precio pagado incluye IVA (19%). El RENT del Excel lo calcula sobre el
            # precio sin IVA: 1 - costo / (PV / 1.19). Se hace igual aquí para que cuadre.
            m["ingreso_neto_cop"] = m["ingreso_cop"] / 1.19
            m["margen_real_%"] = np.where(
                m["ingreso_neto_cop"] > 0,
                (m["ingreso_neto_cop"] - m["costo_total_cop"]) / m["ingreso_neto_cop"] * 100, np.nan)

            ing_tot, costo_tot = m["ingreso_neto_cop"].sum(), m["costo_total_cop"].sum()
            margen_acum = (ing_tot - costo_tot) / ing_tot * 100 if ing_tot else None
            e = st.columns(3)
            e[0].metric("Margen real de venta (acumulado)",
                        f"{(ing_tot - costo_tot) / ing_tot * 100:.0f}%" if ing_tot else "-")
            e[1].metric("Ganancia acumulada", fmt(ing_tot - costo_tot, fx) if ing_tot else "-")
            e[2].metric("Unidades vendidas", int(m["unidades"].sum()))

            tabla_m = m[["unidades", "ingreso_neto_cop", "costo_total_cop", "margen_real_%",
                         "margen_lista_%"]].copy()
            tabla_m["ingreso_usd"] = tabla_m["ingreso_neto_cop"] / fx
            tabla_m["costo_total_usd"] = tabla_m["costo_total_cop"] / fx
            vista_tabla = (
                tabla_m[["unidades", "ingreso_usd", "costo_total_usd", "margen_real_%",
                         "margen_lista_%"]]
                .rename(columns={"margen_lista_%": "margen_a_precio_lista_%"})
                .sort_values("ingreso_usd", ascending=False)
            )
            with st.expander(f"Ver detalle de {len(vista_tabla):,} SKU", expanded=False):
                st.dataframe(
                    vista_tabla.style.format({
                        "ingreso_usd": "US$ {:,.0f}", "costo_total_usd": "US$ {:,.0f}",
                        "margen_real_%": "{:.0f}%", "margen_a_precio_lista_%": "{:.0f}%"
                    }, na_rep="-"),
                    width="stretch", height=320
                )

            # --- Gráficas de productos ---
            g = m.rename_axis("sku").reset_index()
            g = pd.DataFrame({"sku": g["sku"].astype(str),
                              "unidades": g["unidades"].astype(float),
                              "ingreso_usd": (g["ingreso_neto_cop"] / fx).astype(float),
                              "margen_real": g["margen_real_%"].astype(float),
                              "margen_lista": g["margen_lista_%"].astype(float)})
            c1, c2 = st.columns(2)
            with c1:
                # Esta gráfica debe representar exclusivamente el catálogo activo.
                # No alteramos el universo de la tabla/KPIs ni la gráfica de ingresos.
                g_activos = g[g["sku"].astype(str).isin(set(map(str, skus_todos)))].copy()
                g_m = (g_activos if len(g_activos) <= 40 else
                       pd.concat([g_activos.nlargest(20, "margen_lista"),
                                  g_activos.nsmallest(20, "margen_lista")]))
                st.markdown("**Margen a precio de lista por producto**" +
                            (" (los 20 mayores y los 20 menores)" if len(g_activos) > 40 else " (SKU activos)"))
                orden_m = list(g_m.sort_values("margen_lista", ascending=False)["sku"])
                mostrar(alt.Chart(g_m).mark_bar(color=COLOR_META_AZUL).encode(
                    x=alt.X("sku:N", sort=orden_m, title=None, axis=alt.Axis(labelAngle=-90)),
                    y=alt.Y("margen_lista:Q", title="Margen %"),
                    tooltip=["sku", alt.Tooltip("margen_lista:Q", format=".1f")]).properties(height=255))
            with c2:
                st.markdown("**Top productos por ingreso (sin IVA)**")
                top = g[g["unidades"] > 0].nlargest(10, "ingreso_usd")
                if len(top):
                    mostrar(alt.Chart(top).mark_bar(color=COLOR_REAL_ESMERALDA).encode(
                        y=alt.Y("sku:N", sort="-x", title=None),
                        x=alt.X("ingreso_usd:Q", title="US$"),
                        tooltip=["sku", "unidades", alt.Tooltip("ingreso_usd:Q", format=",.0f"),
                                 alt.Tooltip("margen_real:Q", format=".1f")]).properties(height=255))
                else:
                    st.markdown("Todavía no hay ventas de estos productos.")
            vendidos = g[g["unidades"] > 0].copy()
            if len(vendidos):
                st.markdown("**Margen real por producto**")
                st.caption("Comparación del margen real de los productos vendidos. Los umbrales de inventario no se aplican aquí.")
                vendidos["producto"] = vendidos["sku"].map(nombre_producto)
                vendidos["producto_corto"] = vendidos["sku"].map(lambda x: etiqueta_producto(x, 34))
                orden_mr = list(vendidos.sort_values("margen_real")["producto_corto"])
                barras_mr = alt.Chart(vendidos).mark_bar(cornerRadiusEnd=4).encode(
                    y=alt.Y("producto_corto:N", sort=orden_mr, title=None),
                    x=alt.X("margen_real:Q", title="Margen real %", scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color("margen_real:Q", title=None,
                                    scale=alt.Scale(domain=[0, 100], range=[COLOR_META_AZUL, COLOR_JADE]),
                                    legend=None),
                    tooltip=[alt.Tooltip("sku:N", title="SKU"), alt.Tooltip("producto:N", title="Producto"),
                             alt.Tooltip("unidades:Q", title="Unidades"),
                             alt.Tooltip("ingreso_usd:Q", format=",.0f", title="Ingreso US$"),
                             alt.Tooltip("margen_real:Q", format=".1f", title="Margen real %")]
                ).properties(height=max(220, min(420, 30 * len(vendidos))))
                mostrar(barras_mr)
        except Exception as e:
            st.error(f"No pude leer el archivo: {e}")
    else:
        st.info("Falta el archivo de costos: colócalo en la carpeta datos como costos.xlsx.")


# --- Inventario (manual): Sell-through y semanas de stock ---
with tab_inv:
    # La pestaña de Inventario presenta siempre todos los SKU activos; el filtro individual
    # se conserva únicamente en Productos, donde enfoca el análisis de margen.
    sel_skus_inv = []
    page_header("FINART · ARDP · FALABELLA COLOMBIA", "Inventario", "Existencias, rotación y alertas · actualización manual desde Seller Center")
    st.caption("Actualización manual: carga aquí el archivo de la pestaña 'Stock' de Seller Center. "
               "Solo se usan el SKU y la cantidad; los demás campos se ignoran.")
    archivo_stock = st.file_uploader("Stock (.csv o .xlsx)", type=["csv", "xlsx"], key="stock")
    if archivo_stock is not None:
        try:
            nuevo = leer_stock_manual(archivo_stock, archivo_stock.name)
            limpio = limpiar_stock(nuevo)
            guardar_stock(limpio)
            omitidas = len(nuevo) - len(limpio)
            st.success(f"Guardado: stock de hoy para {len(limpio)} SKU."
                       + (f" Se omitieron {omitidas} fila(s) sin SKU o sin cantidad." if omitidas else ""))
            st.cache_data.clear()
        except Exception as e:
            st.error(f"No pude leer el archivo: {e}")

    hist = cargar_stock_historico()
    if len(hist):
        ultimo_dia = hist["fecha"].max()
        dias_desde_carga = (hoy - pd.Timestamp(ultimo_dia)).days

        if dias_desde_carga >= 14:
            st.error(f"⚠️ El stock lleva **{dias_desde_carga} días** sin actualizarse "
                     f"(última carga: {ultimo_dia}). El Sell-through y WOS de abajo pueden "
                     "estar muy desactualizados — sube un archivo nuevo.")
        elif dias_desde_carga >= 7:
            st.warning(f"El stock lleva **{dias_desde_carga} días** sin actualizarse "
                       f"(última carga: {ultimo_dia}). Te recomiendo subir uno nuevo pronto.")
        else:
            st.success(f"Stock actualizado hace {dias_desde_carga} día(s) (última carga: {ultimo_dia}).")

        umbral_crit, umbral_aten, dias_mov = UMBRAL_CRITICO, UMBRAL_ATENCION, DIAS_SIN_VENTAS

        stock_hoy = hist[hist["fecha"] == ultimo_dia].set_index("sku")["cantidad"]

        inicial = cargar_stock_inicial()  # Se conserva para los cálculos; no se muestra como indicador independiente.
        df_sku = df
        validas = df_sku[~df_sku["estado"].str.lower().isin(EXCLUIDOS)]
        fechas_v = pd.to_datetime(validas["created_at"])
        vendido = validas.groupby("sku")["order_id"].count()
        v28 = validas[fechas_v >= hoy - pd.Timedelta(days=28)].groupby("sku")["order_id"].count()
        vN = validas[fechas_v >= hoy - pd.Timedelta(days=dias_mov)].groupby("sku")["order_id"].count()

        tabla_inv = pd.DataFrame({"stock_actual": stock_hoy}).join(
            pd.DataFrame({"vendido_total": vendido})).join(
            pd.DataFrame({"vendido_28d": v28})).join(
            pd.DataFrame({"vendido_ventana": vN})).fillna(0)
        if sel_skus_inv:
            tabla_inv = tabla_inv[tabla_inv.index.isin(sel_skus_inv)].copy()
        # Inventario con el que se arrancó: el registrado como inicial; si un SKU no está ahí,
        # se estima como stock actual + vendido.
        tabla_inv["ingresado_estimado"] = tabla_inv["stock_actual"] + tabla_inv["vendido_total"]
        if len(inicial):
            ini_stock = inicial.set_index("sku")["cantidad"].astype(float)
            tabla_inv["ingresado_estimado"] = ini_stock.reindex(tabla_inv.index).fillna(
                tabla_inv["ingresado_estimado"])
        tabla_inv["sell_through_%"] = (tabla_inv["vendido_total"] /
                                        tabla_inv["ingresado_estimado"].replace(0, np.nan) * 100)
        venta_semanal = tabla_inv["vendido_28d"] / 4
        tabla_inv["semanas_de_stock"] = (tabla_inv["stock_actual"] /
                                          venta_semanal.replace(0, np.nan))

        # % del inventario que todavía queda (stock actual / lo ingresado estimado).
        # Ej.: ingresaron 12, hoy quedan 6 -> 50%.
        tabla_inv["inventario_restante_%"] = (tabla_inv["stock_actual"] /
                                              tabla_inv["ingresado_estimado"].replace(0, np.nan) * 100)
        # Estado: crítico = queda el % crítico o menos del inventario, o WOS < 2 (se agota pronto)
        tabla_inv["estado"] = np.select(
            [(tabla_inv["semanas_de_stock"] < 2) | (tabla_inv["inventario_restante_%"] <= umbral_crit),
             tabla_inv["inventario_restante_%"] <= umbral_aten],
            ["🔴 Crítico", "🟡 Atención requerida"], default="🟢 OK")
        # Alerta aparte: tiene stock pero no ha vendido nada en la ventana de días elegida
        sin_mov = (tabla_inv["stock_actual"] > 0) & (tabla_inv["vendido_ventana"] == 0)
        tabla_inv["alerta_movimiento"] = np.where(sin_mov, f"⚪ Sin ventas en {dias_mov} días", "")

        # Días en inventario: desde la salida al mercado (FECHA_SALIDA_MERCADO)
        tabla_inv["dias_en_inventario"] = max((hoy - FECHA_SALIDA_MERCADO).days, 0)
        n_criticos = int((tabla_inv["estado"] == "🔴 Crítico").sum())
        n_sin_mov = int(sin_mov.sum())
        quiebre = tabla_inv["stock_actual"] <= 0
        riesgo = (~quiebre) & (tabla_inv["semanas_de_stock"] < 2)
        n_quiebre, n_riesgo = int(quiebre.sum()), int(riesgo.sum())

        st.markdown('<div class="ardp-section">Salud y rotación del inventario</div>', unsafe_allow_html=True)
        ing_est = tabla_inv["ingresado_estimado"].sum()
        st_prom = tabla_inv["vendido_total"].sum() / ing_est * 100 if ing_est else 0
        k = st.columns(5)
        kpi_card_exec(k[0], "Catálogo OK", f"{int((tabla_inv['estado'] == '🟢 OK').sum())} SKU", "Sin alertas de rotación", icon="target", accent="green")
        kpi_card_exec(k[1], "Atención", f"{int((tabla_inv['estado'] == '🟡 Atención requerida').sum())} SKU", f"Queda ≤{umbral_aten}% stock", icon="pulse", accent="gold")
        kpi_card_exec(k[2], "Críticos", f"{int((tabla_inv['estado'] == '🔴 Crítico').sum())} SKU", f"Queda ≤{umbral_crit}% o WOS < 2", icon="pulse", accent="gold")
        kpi_card_exec(k[3], "Sin Movimiento", f"{int(sin_mov.sum())} SKU", f"Sin venta en {dias_mov} días", icon="box", accent="cyan")
        kpi_card_exec(k[4], "Sell-Through", f"{st_prom:.1f}%", "Rotación global inicial", icon="gauge", accent="cyan", mini_gauge=f"{st_prom:.0f}%")
        st.write("")

        st.markdown('<div class="ardp-section">Monitoreo de quiebre de stock</div>', unsafe_allow_html=True)
        qa = st.columns(3)
        kpi(qa[0], "SKUs en quiebre (stock 0)", n_quiebre)
        kpi(qa[1], "SKUs en riesgo (WOS < 2 semanas)", n_riesgo)
        kpi(qa[2], "SKUs con stock activo", int((tabla_inv["stock_actual"] > 0).sum()))
        en_alerta = tabla_inv[quiebre | riesgo][["stock_actual", "vendido_28d", "semanas_de_stock"]].copy()
        en_alerta["situación"] = np.where(en_alerta["stock_actual"] <= 0, "🔴 Quiebre", "🟡 Riesgo de quiebre")
        if len(en_alerta):
            with st.expander(f"Ver {len(en_alerta):,} SKU en quiebre/riesgo", expanded=False):
                st.dataframe(
                    en_alerta.sort_values("semanas_de_stock").style.format(
                        {"semanas_de_stock": "{:.1f}"}, na_rep="-"),
                    width="stretch", height=260
                )
        else:
            st.success("Ningún SKU está en quiebre ni en riesgo de quiebre.")

        tabla_inv_vista = tabla_inv[[
            "stock_actual", "vendido_total", "inventario_restante_%", "sell_through_%",
            "semanas_de_stock", "dias_en_inventario", "estado", "alerta_movimiento"
        ]].sort_values("inventario_restante_%")
        with st.expander(f"Ver detalle completo de inventario · {len(tabla_inv_vista):,} SKU", expanded=False):
            st.dataframe(
                tabla_inv_vista.style.format({
                    "inventario_restante_%": "{:.0f}%", "sell_through_%": "{:.0f}%",
                    "semanas_de_stock": "{:.1f}", "dias_en_inventario": "{:.0f}"
                }, na_rep="-"),
                column_config={"dias_en_inventario": st.column_config.NumberColumn(
                    "Días en inventario",
                    help="Días desde la salida al mercado (28 de septiembre de 2026).")},
                width="stretch", height=330
            )

        st.markdown("**Inventario restante**")
        st.caption("Ordenado de menor a mayor cobertura del inventario inicial. El color identifica el estado.")
        ch = tabla_inv.rename_axis("sku").reset_index()
        ch = pd.DataFrame({
            "sku": ch["sku"].astype(str),
            "restante": ch["inventario_restante_%"].astype(float),
            "nivel": ch["estado"].map({"🔴 Crítico": "Crítico", "🟡 Atención requerida": "Atención requerida",
                                       "🟢 OK": "OK"}),
        })
        ch["producto"] = ch["sku"].map(nombre_producto)
        ch["producto_corto"] = ch["producto"].apply(lambda x: x if len(x) <= 38 else x[:35] + "…")
        if len(ch) > 40:
            ch = ch.nsmallest(40, "restante")
        orden_i = list(ch.sort_values("restante")["producto_corto"])
        barras_i = alt.Chart(ch).mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3).encode(
            y=alt.Y("producto_corto:N", sort=orden_i, title=None),
            x=alt.X("restante:Q", title="% de inventario restante", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("nivel:N", legend=alt.Legend(title=None, orient="bottom", labelColor=COLOR_TEXTO_SEC),
                            scale=alt.Scale(domain=["Crítico", "Atención requerida", "OK"],
                                            range=[COLOR_CORAL, COLOR_AMBAR, COLOR_JADE])),
            tooltip=["sku", "producto", alt.Tooltip("restante:Q", format=".0f", title="Restante %"), "nivel"]
        ).properties(height=max(260, min(520, 32 * len(ch))))
        lineas_i = alt.Chart(pd.DataFrame({"umbral": [umbral_crit, umbral_aten]})).mark_rule(
            strokeDash=[6, 4], color=COLOR_AZUL_HIELO).encode(x="umbral:Q")
        mostrar(barras_i + lineas_i)
    else:
        st.info("Aún no has subido ningún archivo de stock.")

# --- Rankings de productos (se arma al final: usa ventas e inventario) ---
with rank_box:
    st.markdown('<div class="ardp-section">Lectura rápida del portafolio</div>', unsafe_allow_html=True)
    st.caption("Los gráficos priorizan la lectura; el detalle completo queda disponible en desplegables.")
    etiqueta = lambda s: etiquetas_sku.get(str(s), str(s))
    vp_r = df_per[~df_per["estado"].str.lower().isin(EXCLUIDOS)]
    base_r = vp_r.groupby("sku").agg(unidades=("order_id", "count"), ingreso=("precio_pagado", "sum"))
    base_r = base_r[base_r.index != "(sin SKU)"]
    base_r["ingreso_usd"] = base_r["ingreso"] / 1.19 / fx
    r1, r2 = st.columns(2, gap="medium")
    with r1:
        st.markdown(f"""
        <div class="ardp-panel">
          <div class="ardp-panel-header">
            <div>
              <div class="ardp-panel-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>
                Best sellers · Top 5 por unidades
              </div>
              <div class="ardp-panel-sub">Productos líderes en rotación comercial</div>
            </div>
            <div style="font-size:11px;color:{COLOR_TEXTO_SEC};background:rgba(255,255,255,0.05);padding:4px 10px;border-radius:6px;border:1px solid rgba(255,255,255,0.08);">
              Top Rotación
            </div>
          </div>
        """, unsafe_allow_html=True)
        top5 = base_r.sort_values(["unidades", "ingreso_usd"], ascending=False).head(5).rename_axis("sku").reset_index()
        if len(top5):
            top5["producto"] = top5["sku"].map(nombre_producto)
            top5["producto_corto"] = top5["sku"].map(lambda x: etiqueta_producto(x, 32))
            top5_base = alt.Chart(top5).encode(
                y=alt.Y("producto_corto:N", sort="-x", title=None, axis=alt.Axis(labelColor=COLOR_TEXTO_SEC, labelFontSize=11))
            )
            top5_bars = top5_base.mark_bar(
                color=COLOR_JADE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=18
            ).encode(
                x=alt.X("unidades:Q", title="Unidades", axis=alt.Axis(gridColor="rgba(141,200,240,0.08)", labelColor=COLOR_TEXTO_SEC)),
                tooltip=["sku", "producto", "unidades", alt.Tooltip("ingreso_usd:Q", format=",.0f", title="Ingreso sin IVA US$")]
            )
            top5_txt = top5_base.mark_text(
                align="left", baseline="middle", dx=6, color=COLOR_JADE, fontWeight="bold", fontSize=11
            ).encode(
                x="unidades:Q",
                text=alt.Text("unidades:Q", format=",d")
            )
            mostrar((top5_bars + top5_txt).properties(height=230))
            st.markdown('</div>', unsafe_allow_html=True)
            with st.expander("Ver detalle best sellers", expanded=False):
                st.dataframe(top5[["producto", "sku", "unidades", "ingreso_usd"]].rename(columns={"producto":"Producto","sku":"SKU","unidades":"Unidades","ingreso_usd":"Ingreso sin IVA"})
                             .style.format({"Ingreso sin IVA":"US$ {:,.0f}"}), width="stretch", hide_index=True)
        else:
            st.info("Todavía no hay ventas en este período.")
            st.markdown('</div>', unsafe_allow_html=True)

    with r2:
        st.markdown(f"""
        <div class="ardp-panel">
          <div class="ardp-panel-header">
            <div>
              <div class="ardp-panel-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_AMBAR}" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                Slow movers · Stock alto con baja venta
              </div>
              <div class="ardp-panel-sub">SKUs que requieren impulso promocional</div>
            </div>
            <div style="font-size:11px;color:{COLOR_TEXTO_SEC};background:rgba(255,255,255,0.05);padding:4px 10px;border-radius:6px;border:1px solid rgba(255,255,255,0.08);">
              Atención Stock
            </div>
          </div>
        """, unsafe_allow_html=True)
        if tabla_inv is not None and len(tabla_inv):
            con_stock = (tabla_inv[tabla_inv["stock_actual"] > 0][["stock_actual", "dias_en_inventario"]]
                         .join(base_r[["unidades"]]).fillna({"unidades": 0}))
            sm = con_stock.sort_values(["unidades", "stock_actual"], ascending=[True, False]).head(5).rename_axis("sku").reset_index()
            sm["producto"] = sm["sku"].map(nombre_producto)
            sm["producto_corto"] = sm["sku"].map(lambda x: etiqueta_producto(x, 32))
            sm_base = alt.Chart(sm).encode(
                y=alt.Y("producto_corto:N", sort="-x", title=None, axis=alt.Axis(labelColor=COLOR_TEXTO_SEC, labelFontSize=11))
            )
            sm_bars = sm_base.mark_bar(
                color=COLOR_AMBAR, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=18
            ).encode(
                x=alt.X("stock_actual:Q", title="Stock actual", axis=alt.Axis(gridColor="rgba(141,200,240,0.08)", labelColor=COLOR_TEXTO_SEC)),
                tooltip=["sku", "producto", "unidades", "stock_actual", "dias_en_inventario"]
            )
            sm_txt = sm_base.mark_text(
                align="left", baseline="middle", dx=6, color=COLOR_AMBAR, fontWeight="bold", fontSize=11
            ).encode(
                x="stock_actual:Q",
                text=alt.Text("stock_actual:Q", format=",d")
            )
            mostrar((sm_bars + sm_txt).properties(height=230))
            st.markdown('</div>', unsafe_allow_html=True)
            with st.expander("Ver detalle slow movers", expanded=False):
                st.dataframe(sm[["producto", "sku", "unidades", "stock_actual", "dias_en_inventario"]].rename(columns={
                    "producto":"Producto", "sku":"SKU", "unidades":"Unidades vendidas", "stock_actual":"Stock", "dias_en_inventario":"Días en inventario"}),
                    width="stretch", hide_index=True)
        else:
            st.info("Sube el inventario para ver los slow movers.")
            st.markdown('</div>', unsafe_allow_html=True)

    universo = set(tabla_inv.index) if (tabla_inv is not None and len(tabla_inv)) else set(etiquetas_sku)
    if sel_skus_prod:
        universo &= set(sel_skus_prod)
    sin_venta = sorted(universo - set(base_r.index))
    n_sin_venta = len(sin_venta)
    st.markdown("**Productos sin venta en el período**")
    kv = st.columns(2)
    kpi(kv[0], "Productos sin ninguna venta", n_sin_venta)
    kpi(kv[1], "Productos analizados", len(universo))
    if sin_venta:
        filas_cero = []
        for s in sin_venta:
            fila_c = {"sku": str(s), "producto": etiqueta(s), "stock": 0, "dias": 0}
            if tabla_inv is not None and s in tabla_inv.index:
                fila_c["stock"] = tabla_inv.at[s, "stock_actual"]
                fila_c["dias"] = tabla_inv.at[s, "dias_en_inventario"]
            filas_cero.append(fila_c)
        cero = pd.DataFrame(filas_cero)
        cero["producto_corto"] = cero["sku"].map(lambda x: etiqueta_producto(x, 38))
        mostrar(alt.Chart(cero).mark_bar(color=VERDE_4).encode(
            y=alt.Y("producto_corto:N", sort="-x", title=None),
            x=alt.X("stock:Q", title="Stock actual"),
            tooltip=["sku", "producto", "stock", "dias"]
        ).properties(height=max(220, min(420, 32 * len(cero)))))
        with st.expander("Ver detalle de productos sin venta", expanded=False):
            st.dataframe(cero[["producto", "sku", "stock", "dias"]].rename(columns={
                "producto":"Producto", "sku":"SKU", "stock":"Stock", "dias":"Días en inventario"}), width="stretch", hide_index=True)


# --- Cancelaciones y devoluciones (pedidos que no cuentan como venta, pero se miden aparte) ---
with tab_ventas:
    st.divider()
    st.markdown('<div class="ardp-section">Cancelaciones y devoluciones</div>', unsafe_allow_html=True)
    estado_min = df_per["estado"].fillna("").str.lower()
    excl = df_per[estado_min.isin(EXCLUIDOS)]
    pedidos_total = df_per["order_id"].nunique()
    n_cancel = excl["order_id"].nunique()
    tasa_cancel = n_cancel / pedidos_total * 100 if pedidos_total else None
    cc = st.columns(4)
    cc[0].metric("Pedidos cancelados o devueltos", n_cancel)
    cc[1].metric("Tasa de cancelación", f"{tasa_cancel:.1f}%" if tasa_cancel is not None else "-",
                 help="Pedidos cancelados, fallidos o devueltos ÷ pedidos totales del período.")
    cc[2].metric("Valor no vendido", usd_corto(excl["precio_pagado"].sum() / fx),
                 help="Valor de esos pedidos, con IVA, convertido a dólares.")
    cc[3].metric("Pedidos totales", pedidos_total)
    with st.expander("Estados de pedido detectados en las ventas"):
        estados_det = (df_per.assign(estado=df_per["estado"].fillna("(sin estado)").str.lower())
                       .groupby("estado").agg(pedidos=("order_id", "nunique")))
        estados_det["¿Cuenta como venta?"] = np.where(estados_det.index.isin(EXCLUIDOS), "No", "Sí")
        estados_det.index.name = "Estado"
        st.dataframe(estados_det.rename(columns={"pedidos": "Pedidos"}), width="stretch")
    if len(excl):
        por_estado = (excl.assign(estado=excl["estado"].str.lower()).groupby("estado")
                      .agg(pedidos=("order_id", "nunique"), valor=("precio_pagado", "sum")))
        por_estado["valor_usd"] = por_estado["valor"] / fx
        por_estado.index.name = "Estado"
        g_c1, g_c2 = st.columns(2)
        with g_c1:
            st.markdown("**Por estado**")
            st.dataframe(por_estado[["pedidos", "valor_usd"]].rename(
                columns={"pedidos": "Pedidos", "valor_usd": "Valor US$"})
                .style.format({"Valor US$": "US$ {:,.0f}"}), width="stretch")
            top_c = (excl[excl["sku"] != "(sin SKU)"].groupby("sku")["order_id"].nunique()
                     .sort_values(ascending=False).head(5))
            if len(top_c):
                st.markdown("**Productos con más cancelaciones (top 5)**")
                st.dataframe(pd.DataFrame({"Producto": [etiquetas_sku.get(s, s) for s in top_c.index],
                                           "Pedidos": top_c.values}), width="stretch", hide_index=True)
        with g_c2:
            st.markdown("**Tasa de cancelación por mes (%)**")
            mes_todos = pd.to_datetime(df_per["created_at"]).dt.to_period("M").astype(str)
            mes_excl = pd.to_datetime(excl["created_at"]).dt.to_period("M").astype(str)
            tot_m = df_per.groupby(mes_todos)["order_id"].nunique()
            can_m = excl.groupby(mes_excl)["order_id"].nunique()
            tasa_m = can_m.reindex(tot_m.index).fillna(0) / tot_m * 100
            tasa_m.index.name = "Año/Mes"
            tasa_df = tasa_m.rename("Tasa").reset_index().rename(columns={tasa_m.index.name or "index":"Año/Mes"})
            mostrar(alt.Chart(tasa_df).mark_bar(color=VERDE_2).encode(
                x=alt.X("Año/Mes:N", title=None, axis=alt.Axis(labelAngle=-35)),
                y=alt.Y("Tasa:Q", title="%"),
                tooltip=["Año/Mes", alt.Tooltip("Tasa:Q", format=".1f", title="Tasa de cancelación (%)")]
            ).properties(height=300))
    else:
        st.markdown("No hay pedidos cancelados ni devueltos en este período.")


# --- Resumen ejecutivo FINART: jerarquía visual, indicadores y gráficas sin alterar cálculos
with tab_res:
    corte_txt = mes_cur["periodo"] if mes_cur is not None else "Sin corte disponible"
    estado_mes = mes_cur["semaforo"] if mes_cur is not None else "⚪ Sin meta"
    estado_trim = semaforo(q_cur_datos["real"], q_cur_datos["esperado"], q_cur_datos["meta"]) if q_cur_datos is not None else "⚪ Sin meta"
    estado_plan = semaforo(real_total, esperado_total, meta_total) if meta_total else "⚪ Sin meta"

    page_header("FINART · ARDP · FALABELLA COLOMBIA", "Resumen Ejecutivo", f"Desempeño comercial, avance frente al presupuesto y alertas operativas · Corte {corte_txt}")

    if meses is not None and mes_cur is not None:
        cumplimiento_mes = (mes_cur["real"] / mes_cur["meta"] * 100) if mes_cur["meta"] else None
        cards = st.columns(4, gap="medium")
        
        kpi_card_exec(cards[0], f"META · {periodo_mostrar(mes_cur['periodo'])}", usd_corto(mes_cur["meta"]), "Presupuesto del mes", icon="target", accent="blue")
        kpi_card_exec(cards[1], "VENTA REAL", usd_corto(mes_cur["real"]), "Venta confirmada del mes", icon="bars", accent="green")
        cumpl_txt = f"{cumplimiento_mes:.1f}%" if cumplimiento_mes is not None else "-"
        kpi_card_exec(cards[2], "CUMPLIMIENTO", cumpl_txt, "Venta real / meta mensual", icon="gauge", accent="cyan", mini_gauge=cumpl_txt)
        estado_mes_limpio = estado_mes.replace("🔴 ", "").replace("🟡 ", "").replace("🟢 ", "").replace("⚪ ", "")
        kpi_card_exec(cards[3], "ESTADO DEL MES", estado_mes_limpio, "Ritmo frente al plan", icon="pulse", accent="gold")

        st.markdown('<div class="ardp-divider"></div>', unsafe_allow_html=True)
        # Visualización principal de referencia: curva de ventas vs ruta del presupuesto
        left, right = st.columns([1.9, 1.1], gap="medium")
        with left:
            st.markdown(f"""
            <div class="ardp-panel">
              <div class="ardp-panel-header">
                <div>
                  <div class="ardp-panel-title">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
                    Avance acumulado vs. ruta presupuestada
                  </div>
                  <div class="ardp-panel-sub">Evolución real acumulada (Esmeralda) frente a la meta (Azul Zafiro)</div>
                </div>
                <div style="font-size:11px;color:{COLOR_TEXTO_SEC};background:rgba(50,124,193,0.15);padding:4px 10px;border-radius:6px;border:1px solid rgba(141,200,240,0.25);">
                  Área y Línea ejecutiva
                </div>
              </div>
            """, unsafe_allow_html=True)
            if grafico_ruta is not None and len(grafico_ruta):
                # Gráfica moderna de área y línea
                df_acum = grafico_ruta.copy().reset_index()
                df_acum = df_acum.rename(columns={df_acum.columns[0]: "Fecha"})
                df_acum["Fecha"] = pd.to_datetime(df_acum["Fecha"], errors="coerce")
                for col in ["Acumulado real", "Ruta del presupuesto"]:
                    df_acum[col] = pd.to_numeric(df_acum[col], errors="coerce")
                df_acum = df_acum.dropna(subset=["Fecha"])
                df_acum["Mes"] = df_acum["Fecha"].dt.to_period("M")
                mensual_acum = df_acum.groupby("Mes", sort=True).tail(1).copy()
                mensual_acum["Periodo"] = mensual_acum["Fecha"].dt.strftime("%b-%y")
                mensual_acum["Acumulado real"] = mensual_acum["Acumulado real"].where(mensual_acum["Fecha"] <= pd.Timestamp.today().normalize())
                
                base_c = alt.Chart(mensual_acum).encode(
                    x=alt.X("Periodo:N", sort=mensual_acum["Periodo"].tolist(), title=None,
                            axis=alt.Axis(labelAngle=0, labelColor=COLOR_TEXTO_SEC, labelLimit=75))
                )
                area_meta = base_c.mark_area(
                    color=COLOR_META_AZUL, opacity=0.18, line=alt.OverlayMarkDef(color=COLOR_AZUL_HIELO, strokeWidth=1.8, strokeDash=[4, 3])
                ).encode(
                    y=alt.Y("Ruta del presupuesto:Q", title="US$", axis=alt.Axis(format=",.0f", gridColor="rgba(141,200,240,0.08)", labelColor=COLOR_TEXTO_SEC)),
                    tooltip=["Periodo", alt.Tooltip("Ruta del presupuesto:Q", title="Ruta acumulada (US$)", format=",.0f")]
                )
                linea_real = base_c.mark_line(
                    color=COLOR_JADE, strokeWidth=3.5, point=alt.OverlayMarkDef(color=COLOR_JADE, size=65, fill="#071729", strokeWidth=2.5)
                ).encode(
                    y=alt.Y("Acumulado real:Q", title="US$", axis=alt.Axis(format=",.0f")),
                    tooltip=["Periodo", alt.Tooltip("Acumulado real:Q", title="Venta acumulada (US$)", format=",.0f")]
                )
                chart_acum_res = (area_meta + linea_real).resolve_scale(y="shared").properties(
                    height=240, background="transparent"
                ).configure_view(stroke="transparent")
                mostrar(chart_acum_res)
                
                st.markdown(f"""
                  <div class="ardp-chart-legend" style="justify-content:center;margin-top:6px;">
                    <span><span class="legend-swatch" style="background:{COLOR_META_AZUL};"></span> Ruta del presupuesto (área)</span>
                    <span><span class="legend-swatch" style="background:{COLOR_JADE};"></span> Venta real acumulada (línea)</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("No hay datos suficientes para construir la evolución acumulada.")
                st.markdown('</div>', unsafe_allow_html=True)
                
        with right:
            st.markdown(f"""
            <div class="ardp-panel" style="display:flex;flex-direction:column;justify-content:space-between;height:100%;">
              <div>
                <div class="ardp-panel-title">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
                  Estado del plan de ventas
                </div>
                <div class="ardp-panel-sub">Lectura ejecutiva del año de proyecto vigente</div>
            """, unsafe_allow_html=True)
            if estado_plan.startswith("🔴"):
                dot = "red"
            elif estado_plan.startswith("🟡"):
                dot = "yellow"
            elif estado_plan.startswith("🟢"):
                dot = "green"
            else:
                dot = "yellow"
            st.markdown(f'<div class="ardp-status"><span class="ardp-dot {dot}"></span>{estado_plan.replace("🔴 ","").replace("🟡 ","").replace("🟢 ","").replace("⚪ ","")}</div>', unsafe_allow_html=True)
            avance = real_total / meta_total * 100 if meta_total else 0
            st.markdown(f'<div class="ardp-statline"><span class="name">Meta oficial · Año {proyecto_anio}</span><span class="num">{usd_corto(meta_total)}</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ardp-statline"><span class="name">Venta acumulada</span><span class="num">{usd_corto(real_total)}</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ardp-statline"><span class="name">Avance de la meta</span><span class="num" style="color:{COLOR_JADE};">{avance:.3f}%</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ardp-statline"><span class="name">Saldo pendiente</span><span class="num">{usd_corto(max(meta_total-real_total, 0))}</span></div>', unsafe_allow_html=True)
            st.markdown('</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="ardp-divider"></div>', unsafe_allow_html=True)
        # Dos visualizaciones complementarias de segundo nivel
        c1, c2 = st.columns([1.2, 1], gap="medium")
        with c1:
            st.markdown(f"""
            <div class="ardp-panel">
              <div class="ardp-panel-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                Meta vs. venta real por trimestre
              </div>
              <div class="ardp-panel-sub">Comparación de valores trimestrales del presupuesto</div>
            """, unsafe_allow_html=True)
            _resumen_trim = (meses.groupby("trimestre", sort=False, as_index=False)
                             .agg(Meta=("meta", "sum"), Real=("real", "sum")))
            _resumen_trim["Trim_Label"] = _resumen_trim["trimestre"].map(lambda t: str(t).split()[0] if str(t).split() else str(t))
            _chart_trim_res = grafico_meta_real_agrupado(_resumen_trim, x_col="Trim_Label", meta_col="Meta", real_col="Real", alto=210)
            mostrar(_chart_trim_res)
            st.markdown(f"""
              <div class="ardp-chart-legend" style="justify-content:center;margin-top:6px;">
                <span><span class="legend-swatch" style="background:{COLOR_META_AZUL};"></span> Meta trimestral</span>
                <span><span class="legend-swatch" style="background:{COLOR_JADE};"></span> Real</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
            <div class="ardp-panel">
              <div class="ardp-panel-header">
                <div>
                  <div class="ardp-panel-title">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{COLOR_JADE}" stroke-width="2.2"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>
                    Distribución del presupuesto anual
                  </div>
                  <div class="ardp-panel-sub">Ponderación de cada trimestre en el plan</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            dona_res = grafico_dona_distribucion(
                _resumen_trim, cat_col="Trim_Label", val_col="Meta",
                titulo_centro=usd_corto(meta_total), subtitulo_centro="Total Anual", alto=165
            )
            mostrar(dona_res)


        st.markdown('<div class="ardp-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="ardp-section">Indicadores comerciales y de operación</div>', unsafe_allow_html=True)
        ec = st.columns(4, gap="medium")
        trim_cum = (q_cur_datos["real"] / q_cur_datos["meta"] * 100) if q_cur_datos is not None and q_cur_datos["meta"] else None
        
        kpi(ec[0], "VENTA DEL TRIMESTRE", usd_corto(q_cur_datos["real"]) if q_cur_datos is not None else "-")
        kpi(ec[1], "CUMPLIMIENTO TRIMESTRAL", f"{trim_cum:.1f}%" if trim_cum is not None else "-")
        kpi(ec[2], "VENTAS HOY", fmt(v_hoy, fx))
        kpi(ec[3], "ÚLTIMOS 7 DÍAS", fmt(sem, fx))

        st.write("")
        op = st.columns(4, gap="medium")
        kpi(op[0], "MARGEN REAL ACUMULADO", f"{margen_acum:.0f}%" if margen_acum is not None else "-")
        kpi(op[1], "SKUS CRÍTICOS", n_criticos if n_criticos is not None else "-")
        kpi(op[2], f"SKUS SIN VENTA · {DIAS_SIN_VENTAS}D", n_sin_mov if n_sin_mov is not None else "-")
        kpi(op[3], "TASA DE CANCELACIÓN", f"{tasa_cancel:.1f}%" if tasa_cancel is not None else "-")

        st.write("")
        al = st.columns(3, gap="medium")
        kpi(al[0], "QUIEBRE DE STOCK", n_quiebre if n_quiebre is not None else "-")
        kpi(al[1], "RIESGO DE QUIEBRE", n_riesgo if n_riesgo is not None else "-")
        kpi(al[2], "PRODUCTOS SIN VENTA", n_sin_venta if n_sin_venta is not None else "-")
    else:
        st.info("No hay presupuesto disponible para construir el resumen ejecutivo.")
