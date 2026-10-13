"""Módulo wrapper de compatibilidad para margen.py.
La implementación central reside en core.data.margin_loader.
"""
from core.data.margin_loader import (
    leer_margenes,
    cargar_margenes_cache,
    _sku_texto,
    _norm,
    _COLS,
    _REQUERIDAS,
)

__all__ = ["leer_margenes", "cargar_margenes_cache", "_sku_texto", "_norm", "_COLS", "_REQUERIDAS"]

