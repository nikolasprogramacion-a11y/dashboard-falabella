"""Script de aplicación del rediseño visual para app.py."""
import re
import os
import shutil

backup_file = "app_pre_redesign.py"
if not os.path.exists(backup_file):
    shutil.copy("app.py", backup_file)
    print(f"Copia de seguridad guardada en {backup_file}")

with open("app.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

# 1. Reemplazar la cabecera CSS inicial (desde st.set_page_config hasta antes de def page_header)
inicio_css = content.find('st.set_page_config(page_title="Dashboard ARDP - Falabella", layout="wide")')
fin_css = content.find('def page_header(eyebrow, title, subtitle):')

if inicio_css != -1 and fin_css != -1:
    nueva_cabecera = '''# ===== CARGA DE ASSETS & CONFIGURACIÓN EJECUTIVA FINART =====
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
.ardp-header, .ardp-page {{
  background-image: linear-gradient(90deg, #070e17 0%, rgba(7, 14, 23, 0.98) 28%, rgba(7, 14, 23, 0.76) 55%, rgba(7, 14, 23, 0.28) 82%, rgba(7, 14, 23, 0.12) 100%), url("data:image/jpeg;base64,{FONDO_B64}") !important;
}}
.finart-sidebar-footer {{
  background-image: linear-gradient(0deg, #050d18 0%, rgba(5, 13, 24, 0.85) 50%, rgba(5, 13, 24, 0.15) 100%), url("data:image/jpeg;base64,{FONDO_B64}") !important;
}}
</style>
""", unsafe_allow_html=True)

'''
    content = content[:inicio_css] + nueva_cabecera + content[fin_css:]
    print("Cabecera CSS reemplazada exitosamente.")
else:
    print("No se encontraron los puntos de corte de la cabecera CSS.")

# 2. Reemplazar def page_header y añadir helpers visuales
inicio_header = content.find('def page_header(eyebrow, title, subtitle):')
fin_header = content.find('def fmt(cop_amount, fx):')

if inicio_header != -1 and fin_header != -1:
    nuevos_helpers = '''def page_header(eyebrow, title, subtitle, right_badge="2027"):
    badge_html = f\'\'\'<div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:6px 14px;color:#cbd5e1;font-size:12px;font-weight:600;display:flex;align-items:center;gap:6px;"><span>Año</span> <strong style="color:#ffffff;">{right_badge}</strong></div>\'\'\' if right_badge else ""
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
        "target": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00e599" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
        "bars": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00e599" stroke-width="2.2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
        "gauge": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.2"><path d="M12 2v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="M20 12h2"/><path d="M2 12h2"/><path d="m19.07 4.93-1.41 1.41"/><path d="M12 6a6 6 0 0 0-6 6v4a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-4a6 6 0 0 0-6-6Z"/><path d="m14 14-2-2"/></svg>',
        "coins": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e5b35a" stroke-width="2.2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>',
        "pulse": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2.2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
        "box": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.2"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>',
    }
    svg_icon = icons.get(icon, icons["target"])
    extra_badge = f\'<div class="mini-radial-badge">{mini_gauge}</div>\' if mini_gauge is not None else ""
    
    val_style = 'color: #ffffff;'
    if icon == "pulse":
        if "atrasado" in str(value).lower():
            val_style = 'color: #f87171;'
        elif "ritmo" in str(value).lower() or "ok" in str(value).lower():
            val_style = 'color: #34d399;'
        elif "atención" in str(value).lower() or "riesgo" in str(value).lower():
            val_style = 'color: #fbbf24;'

    col.markdown(
        f"""<div class="ardp-kpi">
          <div class="card-header-row">
            <div class="card-header-left">
              <div class="kpi-icon-badge {accent}">{svg_icon}</div>
              <div class="label">{label}</div>
            </div>
            {extra_badge}
          </div>
          <div class="value" style="{val_style}">{value}</div>
          <div class="note">{note}</div>
        </div>""",
        unsafe_allow_html=True
    )

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

    return f"""
    <div class="ardp-panel" style="display:flex;flex-direction:column;justify-content:space-between;height:100%;">
      <div>
        <div class="ardp-panel-title">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#00e599" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="m12 6 4 6h-8l4-6Z"/></svg>
          Cumplimiento trimestral
        </div>
        <div style="text-align:center;margin:10px 0 6px;">
          <svg viewBox="0 0 200 115" style="width:170px;max-width:100%;display:inline-block;">
            <path d="M 30 95 A 70 70 0 0 1 170 95" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="14" stroke-linecap="round"/>
            <path d="{arc_path}" fill="none" stroke="#00e599" stroke-width="14" stroke-linecap="round"/>
            <text x="100" y="78" text-anchor="middle" font-size="24" font-weight="700" fill="#ffffff" font-family="'Inter', sans-serif">{pct_val:.3f}%</text>
            <text x="100" y="94" text-anchor="middle" font-size="10.5" fill="#8fa4b8" font-family="'Inter', sans-serif">Avance del año</text>
          </svg>
        </div>
      </div>
      <div>
        <div class="ardp-statline">
          <span class="name">ℹ️ Venta acumulada:</span>
          <span class="num">{venta_acum}</span>
        </div>
        <div class="ardp-statline">
          <span class="name">Meta anual:</span>
          <span class="num">{meta_anual}</span>
        </div>
        <div class="ardp-statline">
          <span class="name">Falta por alcanzar:</span>
          <span class="num">{falta_alcanzar}</span>
        </div>
      </div>
    </div>
    """

'''
    content = content[:inicio_header] + nuevos_helpers + content[fin_header:]
    print("Helpers visuales y page_header actualizados.")

# 3. Actualizar sidebar brand para incluir el pie con foto
marca_sidebar_antigua = '''st.markdown("""
<div class="finart-sidebar-brand">
  <div class="brand-word">FINART</div>
  <div class="brand-by">by Agatha</div>
  <div class="brand-line"></div>
  <div class="brand-channel">SELLER CENTER<br><strong>Falabella · Colombia</strong></div>
</div>
""", unsafe_allow_html=True)'''

marca_sidebar_nueva = '''st.markdown("""
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
""", unsafe_allow_html=True)'''

if marca_sidebar_antigua in content:
    content = content.replace(marca_sidebar_antigua, marca_sidebar_nueva)
    print("Pie de menú lateral incorporado.")

# 4. Eliminar bloques de estilos obsoletos al final del archivo
pos_cierre_resumen = content.find('st.info("No hay presupuesto disponible para construir el resumen ejecutivo.")')
if pos_cierre_resumen != -1:
    fin_de_bloque = content.find('\n', pos_cierre_resumen)
    content = content[:fin_de_bloque] + "\n"
    print("Estilos obsoletos al final de app.py eliminados.")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Proceso inicial completado exitosamente.")
