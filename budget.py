"""Módulo wrapper de compatibilidad para budget.py.
La implementación central reside en core.data.budget_loader.
"""
from core.data.budget_loader import (
    periodo_a_fechas,
    leer_presupuesto,
    trimestre_con_anio,
    cargar_presupuesto_cache,
    _MESES,
)

__all__ = ["periodo_a_fechas", "leer_presupuesto", "trimestre_con_anio", "cargar_presupuesto_cache", "_MESES"]

