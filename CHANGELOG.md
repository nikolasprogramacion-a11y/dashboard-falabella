# Registro de Cambios (CHANGELOG)
### Dashboard Ejecutivo ARDP · Falabella — Finart S.A.S.

Todas las mejoras, refactorizaciones y adiciones al proyecto se documentan en este archivo.
El proyecto se rige por versionamiento semántico.

---

## [2.0.0] - 2026-10-05

### 🛡️ Red de Seguridad y Aseguramiento Numérico
- **Suite de Pruebas Automatizadas (`tests/`):**
  - Implementación de 22 pruebas unitarias y de integración con `pytest` que verifican al 100% las reglas de negocio antes y después de cualquier cambio.
  - Verificación matemática estricta de valores de control de presupuesto:
    - Meta total: US$ 11.011.015,38.
    - Q4 2026 (4 meses): US$ 296.584,62 (sep 0, oct 2.492, nov 74.769, dic 219.323).
    - Q1 2027: US$ 862.338,46.
    - Desde may-2027: US$ 595.661,54 por mes.
  - Verificación matemática estricta de márgenes de catálogo:
    - 54 SKUs con RENT entre 13,4% y 68,3%.
    - SKU 210114094: PV 109.900, Costo con factor 48.546, RENT 47,43%.
  - Pruebas de casos borde (`test_edge_cases.py`): validación contra DataFrames vacíos, valores nulos y sin historial previo.
  - Prueba de estrés y rendimiento (`test_benchmark.py`): procesamiento de 40.000 pedidos (3 años y 500 SKUs) en **0,299 segundos** (meta: < 2,0 segundos).

---

### 🎨 Identidad Visual Finart y Sistema de Diseño
- **Tokens de Marca e Identidad (`core/config.py` y `assets/estilos.css`):**
  - Paleta de color corporativa inspirada en la joyería fina y el sitio institucional de Finart:
    - Primario: Azul marino profundo (`#0F1E36`).
    - Acento: Oro joyero (`#C29B38` / `#D4AF37`).
    - Superficies: Blanco perla (`#F8F9FA`) y gris pizarra (`#E2E8F0`).
    - Éxito / Alerta / Peligro: Esmeralda (`#10B981`), Ámbar (`#F59E0B`), Rubí (`#EF4444`).
- **Componentes UI Responsivos (`core/ui.py`):**
  - Tarjetas de KPI ejecutivas con tipografía escalable (`clamp()`) que garantizan que ninguna cifra se corte ni se monte en resoluciones de 1440px (Desktop), 1024px (Tablet) y 390px (Móvil).
  - Semáforos accesibles con doble codificación: color + icono + texto descriptivo para usuarios con daltonismo.
  - Botones de exportación rápida a Excel y CSV en todas las tablas de análisis.
  - Estados vacíos amables con recomendaciones de acción para el usuario.
- **Gráficas Unificadas Altair (`core/charts.py`):**
  - Tema Finart personalizado con tipografía Inter/Segoe UI, fondo transparente, rejillas sutiles y tooltips enriquecidos.
  - Formateo numérico en español (`US$ 1.234`, porcentajes con coma decimal).
  - Límites de legibilidad configurados a un máximo de 40 barras para prevenir saturación visual.

---

### 🏛️ Arquitectura Multi-Dashboard
- **Modularización del Paquete Común (`core/`):**
  - `core.config`: Umbrales de stock (crítico $\le 50\%$, atención $\le 65\%$, quiebre 0), colores y rutas.
  - `core.auth`: Módulo de autenticación seguro por contraseña o multiusuario (`DASHBOARD_USERS`).
  - `core.currency`: Consulta robusta de la TRM oficial colombiana vía `datos.gov.co` (dataset `32sa-8pi3`) con respaldo en `open.er-api.com` y fallback configurable.
  - `core.data`: Conectores desacoplados y eficientes para base de datos SQLite (`db.py`), presupuesto (`budget_loader.py`), costos (`margin_loader.py`) e inventario (`stock_loader.py`).
- **Aislamiento del Canal Falabella (`dashboards/falabella/`):**
  - Lógica pura de cálculo (`logic.py`) separada de la capa visual (`views/`).
  - Vistas divididas por pestañas: `resumen.py`, `presupuesto.py`, `ventas.py`, `productos.py` e `inventario.py`.
- **Preparación para Tienda Física (`dashboards/tienda/`):**
  - Estructura y documentación arquitectónica (`README.md`) lista para incorporar el seguimiento de ventas físicas y EBITDA compartiendo el mismo sistema de diseño, autenticación y componentes sin duplicar código.
- **Envolturas de Compatibilidad Hacia Atrás:**
  - `budget.py`, `margen.py` y `stock.py` en la raíz se mantienen como wrappers transparentes para no romper scripts heredados.

---

### 🔌 Enchufes para Datos Futuros (Sin Invención de Datos)
- **Fecha de Entrada al Mercado:**
  - Soporte para `datos/ingresos.xlsx` con visualización clara de estado vacío si aún no está disponible.
- **Comisión Real Negociada:**
  - Parámetro de configuración `COMISION_FALABELLA_PCT` en `.env`. Permanece en 0,0% por defecto para evitar estimaciones no sustentadas.
- **TRM Histórica por Fecha de Pedido:**
  - Enchufe arquitectónico conmutable mediante la variable `USAR_TRM_HISTORICA`.

---

### ⚡ Rendimiento y Base de Datos
- **Optimización SQLite:**
  - Creación de índices compuestos para acelerar consultas críticas:
    - `idx_order_items_sku` sobre `order_items(sku)`.
    - `idx_order_items_created_at` sobre `order_items(created_at)`.
    - `idx_order_items_estado` sobre `order_items(estado)`.
    - `idx_stock_snapshots_fecha` sobre `stock_snapshots(fecha)`.
- **Caché Inteligente con Streamlit:**
  - Decoradores `@st.cache_data(ttl=3600)` para lectura de archivos Excel e índices de base de datos, evitando recargas innecesarias en cada interacción.

---

### 🚀 Infraestructura, DevOps y Seguridad
- **Contenedor Docker Seguro (`Dockerfile` & `docker-compose.yml`):**
  - Imagen base `python:3.11-slim` multi-etapa.
  - Ejecución bajo usuario sin privilegios (`finartuser`) para mitigar vulnerabilidades de seguridad.
  - Persistencia de volúmenes para base de datos, archivos de datos, logs y backups.
- **Scripts de Operación y Automatización:**
  - `iniciar_windows.bat` y `iniciar_linux.sh` para arranque local con un solo clic.
  - `scripts/backup.py` y `scripts/hacer_respaldo.bat`: Motor de respaldo automático a archivos `.zip` con política de retención de 30 días.
  - `scripts/sincronizar_tarea.bat` y `scripts/sync_cron.sh`: Automatización para el Programador de Tareas (Windows) y cron (Linux) con bitácora en `logs/sync.log`.
  - `scripts/healthcheck.py`: Chequeo de salud integral del sistema.
- **Herramientas de Calidad de Código:**
  - Configuración de `ruff.toml` para análisis estático ultrarrápido y formateo de código.
  - `.gitignore` robusto para evitar fuga de credenciales o bases de datos a repositorios.

---
