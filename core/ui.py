"""Componentes de interfaz de usuario de alta gama, accesibles y responsivos."""
import io
import textwrap
import pandas as pd
import streamlit as st
from core.config import FINART_PALETTE


def kpi_card(contenedor, titulo, valor, delta=None, delta_positivo=True, help_text=None, fs="clamp(1.15rem, 1.8vw, 1.85rem)"):
    """Renderiza una tarjeta KPI premium accesible que nunca se corta ni desborda."""
    v_clean = str(valor).replace("$", "&#36;")
    t_clean = str(titulo).replace("$", "&#36;")
    
    delta_html = ""
    if delta is not None and str(delta).strip():
        color_delta = "#10B981" if delta_positivo else "#EF4444"
        d_clean = str(delta).replace("$", "&#36;")
        delta_html = f"<div style='font-size: 0.8rem; font-weight: 500; color: {color_delta}; margin-top: 4px;'>{d_clean}</div>"

    help_attr = f"title='{help_text}'" if help_text else ""
    help_icon = f"<span style='cursor:help; opacity:0.6; font-size:0.75rem; margin-left:4px;' title='{help_text}'>ℹ️</span>" if help_text else ""

    html = (
        f'<div class="finart-kpi-card" {help_attr} style="'
        f'background: #FFFFFF; border: 1px solid {FINART_PALETTE["border_subtle"]}; '
        f'border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05); '
        f'display: flex; flex-direction: column; justify-content: space-between; min-height: 95px; margin-bottom: 8px;">'
        f'<div style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: {FINART_PALETTE["text_muted"]}; display: flex; align-items: center; justify-content: space-between;">'
        f'<span>{t_clean}</span>{help_icon}</div>'
        f'<div style="font-size: {fs}; font-weight: 700; color: {FINART_PALETTE["navy_primary"]}; line-height: 1.2; word-break: break-word; white-space: normal; margin-top: 6px;">'
        f'{v_clean}</div>'
        f'{delta_html}'
        f'</div>'
    )
    contenedor.markdown(html, unsafe_allow_html=True)


def semaforo_badge(real, esperado, meta):
    """Genera etiqueta accesible de semáforo (color + icono + texto explicativo)."""
    if not meta or meta <= 0:
        return "⚪ Sin meta"
    if not esperado or esperado <= 0:
        return "⚪ Por iniciar"
    ratio = (real / esperado) * 100.0
    if ratio >= 100.0:
        return "🟢 En ritmo (≥100%)"
    if ratio >= 80.0:
        return "🟡 Atención requerida (80%-99%)"
    return "🔴 Atrasado (<80%)"


def semaforo_texto_puro(real, esperado, meta):
    """Mantiene compatibilidad con el formato original."""
    if not meta or meta <= 0:
        return "⚪ Sin meta"
    if not esperado or esperado <= 0:
        return "⚪ Por iniciar"
    ratio = (real / esperado) * 100.0
    if ratio >= 100.0:
        return "🟢 En ritmo"
    if ratio >= 80.0:
        return "🟡 Atención requerida"
    return "🔴 Atrasado"


def tarjeta_inventario(col, color, titulo, valor, help_text=None):
    """Tarjeta específica para el resumen visual de inventario."""
    t_clean = str(titulo).replace("$", "&#36;")
    v_clean = str(valor).replace("$", "&#36;")
    help_attr = f"title='{help_text}'" if help_text else ""

    html = textwrap.dedent(f"""
<div {help_attr} style="
background: #FFFFFF;
border: 1px solid {FINART_PALETTE['border_subtle']};
border-radius: 12px;
padding: 14px 16px;
box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
min-height: 110px;
display: flex;
flex-direction: column;
justify-content: space-between;
">
<div style="display:flex; align-items:center; gap: 8px;">
    <div style="width: 12px; height: 12px; border-radius: 50%; background: {color}; flex-shrink: 0;"></div>
    <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: {FINART_PALETTE['text_muted']};">
        {t_clean}
    </div>
</div>
<div style="font-size: 1.8rem; font-weight: 700; color: {FINART_PALETTE['navy_primary']}; margin-top: 8px;">
    {v_clean}
</div>
</div>
""").strip()
    col.markdown(html, unsafe_allow_html=True)


def descargar_dataframe(df, nombre_base, label="Descargar datos"):
    """Ofrece botones para descargar el DataFrame tanto en CSV como en Excel (.xlsx)."""
    c1, c2 = st.columns(2)
    # CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    c1.download_button(
        label=f"📥 {label} (.csv)",
        data=csv_bytes,
        file_name=f"{nombre_base}.csv",
        mime="text/csv",
        key=f"dl_csv_{nombre_base}",
        use_container_width=True,
    )
    # Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")
    excel_bytes = output.getvalue()
    c2.download_button(
        label=f"📊 {label} (.xlsx)",
        data=excel_bytes,
        file_name=f"{nombre_base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_xlsx_{nombre_base}",
        use_container_width=True,
    )


def empty_state(titulo, mensaje, icono="ℹ️"):
    """Renderiza un estado vacío limpio y orientativo."""
    html = textwrap.dedent(f"""
<div style="
text-align: center;
padding: 2.5rem 1.5rem;
background: #FFFFFF;
border: 1px dashed {FINART_PALETTE['border_subtle']};
border-radius: 12px;
margin: 1rem 0;
">
<div style="font-size: 2.2rem; margin-bottom: 0.5rem;">{icono}</div>
<div style="font-size: 1.05rem; font-weight: 600; color: {FINART_PALETTE['navy_primary']};">{titulo}</div>
<div style="font-size: 0.88rem; color: {FINART_PALETTE['text_muted']}; max-width: 500px; margin: 0.4rem auto 0;">{mensaje}</div>
</div>
""").strip()
    st.markdown(html, unsafe_allow_html=True)
