"""Módulo wrapper de compatibilidad para stock.py.
La implementación central reside en core.data.stock_loader.
"""
from core.data.stock_loader import (
    POSIBLES_SKU,
    POSIBLES_QTY,
    SKU_NULOS,
    _col,
    _sku_str,
    sku_valido,
    leer_stock_manual,
    limpiar_stock,
)

__all__ = [
    "POSIBLES_SKU",
    "POSIBLES_QTY",
    "SKU_NULOS",
    "_col",
    "_sku_str",
    "sku_valido",
    "leer_stock_manual",
    "limpiar_stock",
]

