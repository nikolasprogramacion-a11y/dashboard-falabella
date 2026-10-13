"""Cliente mínimo (solo lectura) para la API del Seller Center de Falabella.

Firma: HMAC-SHA256 (hex) de los parámetros ordenados por nombre y codificados
en URL, usando la API Key como llave. Docs: https://developers.falabella.com/
"""
import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests

BASE_URL = os.getenv("FALABELLA_BASE_URL", "https://sellercenter-api.falabella.com/")


class FalabellaError(Exception):
    pass


def _lista(x):
    """La API devuelve un dict cuando hay 1 elemento y una lista cuando hay varios."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _iso(v):
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.replace(microsecond=0).isoformat()
    return str(v)


def _num(x):
    """Convierte a número. Falabella manda precios como texto con comas de
    miles, ej. '109,900.00' -> 109900.0."""
    if x is None:
        return None
    if isinstance(x, str):
        x = x.replace(",", "").strip()
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _estado_orden(orden):
    """El estado viene anidado: Statuses -> {'Status': 'pending'} (o una lista
    si la orden tiene varios ítems en distinto estado)."""
    st = (orden or {}).get("Statuses")
    if isinstance(st, dict):
        st = st.get("Status")
    if isinstance(st, list):
        st = st[-1] if st else None  # el más reciente
    return (st or "").lower()


class FalabellaClient:
    def __init__(self, user_id, api_key, base_url=BASE_URL, pausa=0.3):
        self.user_id = user_id
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") + "/"
        self.pausa = pausa  # segundos entre llamadas, para no saturar la API
        self.sesion = requests.Session()
        self.sesion.headers["User-Agent"] = "dashboard-ventas/0.1"

    def _firmar(self, params):
        qs = "&".join(
            f"{quote(k, safe='')}={quote(str(v), safe='')}" for k, v in sorted(params.items())
        )
        firma = hmac.new(self.api_key.encode(), qs.encode(), hashlib.sha256).hexdigest()
        return qs, firma

    def _llamar(self, action, **extra):
        params = {
            "Action": action,
            "Format": "JSON",
            "Timestamp": _iso(datetime.now(timezone.utc)),
            "UserID": self.user_id,
            "Version": "1.0",
            **extra,
        }
        qs, firma = self._firmar(params)
        r = self.sesion.get(f"{self.base_url}?{qs}&Signature={firma}", timeout=60)
        time.sleep(self.pausa)
        try:
            data = r.json()
        except ValueError:
            raise FalabellaError(f"Respuesta no JSON (HTTP {r.status_code}): {r.text[:300]}")
        if "ErrorResponse" in data:
            head = data["ErrorResponse"].get("Head", {})
            raise FalabellaError(f"{head.get('ErrorCode')}: {head.get('ErrorMessage')}")
        return data.get("SuccessResponse", data)

    def get_orders(self, *, created_after=None, created_before=None,
                   updated_after=None, updated_before=None, status=None, limit=100):
        """Trae todas las órdenes que cumplan el filtro (pagina automáticamente)."""
        filtros = {
            "CreatedAfter": created_after, "CreatedBefore": created_before,
            "UpdatedAfter": updated_after, "UpdatedBefore": updated_before,
        }
        filtros = {k: _iso(v) for k, v in filtros.items() if v}
        if status:
            filtros["Status"] = status
        ordenes, offset = [], 0
        while True:
            resp = self._llamar("GetOrders", Limit=limit, Offset=offset, **filtros)
            lote = _lista((resp.get("Body", {}).get("Orders") or {}).get("Order"))
            ordenes += lote
            if len(lote) < limit:
                return ordenes
            offset += limit

    def get_order_items(self, order_id):
        resp = self._llamar("GetOrderItems", OrderId=order_id)
        return _lista((resp.get("Body", {}).get("OrderItems") or {}).get("OrderItem"))

    def get_products(self, limit=100):
        """Trae todos los productos con su stock actual (pagina automáticamente)."""
        productos, offset = [], 0
        while True:
            resp = self._llamar("GetProducts", Limit=limit, Offset=offset)
            lote = _lista((resp.get("Body", {}).get("Products") or {}).get("Product"))
            productos += lote
            if len(lote) < limit:
                return productos
            offset += limit


def normalizar_producto(p):
    """Deja SKU, nombre y stock actual. La API anida stock/precio en
    BusinessUnits -> BusinessUnit (puede ser dict o lista si hay varias tiendas)."""
    bu = _lista((p.get("BusinessUnits") or {}).get("BusinessUnit"))
    bu = bu[0] if bu else {}
    return {
        "sku": p.get("SellerSku") or p.get("ShopSku"),
        "producto": p.get("Name"),
        "stock": int(_num(bu.get("Stock")) or 0),
        "precio": _num(bu.get("Price")),
    }


def normalizar_item(item, orden=None):
    """Deja solo columnas de ventas. NO guarda datos personales del cliente."""
    orden = orden or {}
    return {
        "order_item_id": str(item.get("OrderItemId")),
        "order_id": str(item.get("OrderId") or orden.get("OrderId")),
        "created_at": item.get("CreatedAt") or orden.get("CreatedAt"),
        "updated_at": item.get("UpdatedAt") or orden.get("UpdatedAt"),
        "sku": item.get("Sku") or item.get("ShopSku"),
        "producto": item.get("Name"),
        "estado": (item.get("Status") or "").lower() or _estado_orden(orden),
        "precio_pagado": _num(item.get("PaidPrice")) or _num(orden.get("GrandTotal")),
        "precio_item": _num(item.get("ItemPrice")) or _num(orden.get("ProductTotal")),
        "envio": _num(item.get("ShippingAmount")),
        "moneda": item.get("Currency"),
    }
