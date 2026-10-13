"""Configuración general, constantes de negocio y rutas para Finart Dashboards."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Rutas base
BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = Path(os.getenv("DATOS_DIR", str(BASE_DIR / "datos")))
DATOS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Archivos de datos oficiales
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "ventas.db")))
FILE_PPTO = DATOS_DIR / "presupuesto.xlsx"
FILE_COSTOS = DATOS_DIR / "costos.xlsx"
FILE_INGRESOS = DATOS_DIR / "ingresos.xlsx"  # Enchufe para fecha de salida al mercado

# Reglas de negocio - Umbrales de inventario (% restante) y ventana de alerta
UMBRAL_CRITICO = 50.0
UMBRAL_ATENCION = 65.0
DIAS_SIN_VENTAS = 28

# Reglas de negocio - Semáforo de cumplimiento de presupuesto (% de lo esperado a hoy)
SEMAFORO_VERDE = 100.0
SEMAFORO_AMARILLO = 80.0

# Reglas de negocio - IVA y pedidos
IVA_FACTOR = 1.19
EXCLUIDOS = {
    e.strip().lower()
    for e in os.getenv("ESTADOS_EXCLUIDOS", "canceled,cancelled,failed,returned").split(",")
    if e.strip()
}

# Tasa de cambio de respaldo
DEFAULT_FX_USD_COP = float(os.getenv("FX_USD_COP", "3100.0"))

# Enchufe de comisión real (si se define en .env, ej: 0.15 para 15%)
COMISION_REAL_NEGOCIADA = os.getenv("COMISION_REAL_NEGOCIADA", None)

# Paleta de colores institucional Finart S.A.S. (Joyas / Bisutería Fina)
FINART_PALETTE = {
    "navy_dark": "#0B0F17",
    "navy_primary": "#0F172A",
    "navy_card": "#1E293B",
    "gold_primary": "#C5A059",
    "gold_accent": "#D4AF37",
    "gold_dark": "#99732B",
    "gold_light": "#F5E9CE",
    "bg_canvas": "#F8FAFC",
    "text_main": "#0F172A",
    "text_muted": "#64748B",
    "border_subtle": "#E2E8F0",
    "semantic_green": "#10B981",
    "semantic_amber": "#F59E0B",
    "semantic_red": "#EF4444",
    "semantic_gray": "#94A3B8",
}
