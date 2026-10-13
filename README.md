# Dashboard Ejecutivo · ARDP Falabella
### Finart S.A.S. — Joyería, Bisutería, Relojería y Accesorios

Sistema de inteligencia de negocio y analítica ejecutiva para el seguimiento de ventas en Falabella Seller Center, control presupuestal 2026–2028, márgenes comerciales y gestión predictiva de inventarios.

---

## 📋 Tabla de Contenidos
1. [Visión General](#visión-general)
2. [Manual del Usuario para Gerentes](#manual-del-usuario-para-gerentes)
   - [Interpretación de Indicadores Clave (KPI)](#interpretación-de-indicadores-clave-kpi)
   - [Navegación por Pestañas](#navegación-por-pestañas)
   - [Actualización de Archivos de Datos](#actualización-de-archivos-de-datos)
   - [Enchufes para Datos Futuros](#enchufes-para-datos-futuros)
3. [Guía de Arquitectura y Desarrollo](#guía-de-arquitectura-y-desarrollo)
   - [Estructura del Proyecto (Multi-Dashboard)](#estructura-del-proyecto-multi-dashboard)
   - [Red de Pruebas Automatizadas](#red-de-pruebas-automatizadas)
4. [Guía de Despliegue y DevOps](#guía-de-despliegue-y-devops)
   - [Requisitos Previos y Variables de Entorno](#requisitos-previos-y-variables-de-entorno)
   - [Arranque Local (Windows / Linux)](#arranque-local-windows--linux)
   - [Despliegue con Docker y Docker Compose](#despliegue-con-docker-y-docker-compose)
   - [Sincronización Automática con Seller Center](#sincronización-automática-con-seller-center)
   - [Sistema de Respaldos Diarios](#sistema-de-respaldos-diarios)
   - [Diagnóstico y Chequeo de Salud (Healthcheck)](#diagnóstico-y-chequeo-de-salud-healthcheck)
5. [Recomendación de Seguridad y Despliegue en Producción](#recomendación-de-seguridad-y-despliegue-en-producción)

---

## 1. Visión General

El dashboard **ARDP · Falabella** centraliza la operación comercial de Finart S.A.S. en el marketplace de Falabella. Diseñado para ofrecer una respuesta ejecutiva en menos de 5 segundos bajo la pregunta *"¿Cómo vamos?"*, permite:
- Contrastar en tiempo real las ventas netas en dólares contra la meta presupuestal 2026–2028.
- Monitorear el pulso diario y semanal de ventas y cancelaciones.
- Auditar la rentabilidad real de cada SKU frente a la matriz de costos aprobada.
- Prevenir quiebres de inventario mediante análisis de rotación a 28 días y semanas de cobertura.

---

## 2. Manual del Usuario para Gerentes

### Interpretación de Indicadores Clave (KPI)

1. **Venta Neta (US$ y COP):**
   - Corresponde a los pedidos efectivos cuyo estado **no** es cancelado, fallido o devuelto (`canceled`, `cancelled`, `failed`, `returned`).
   - El precio de catálogo en Colombia ya incluye el 19% de IVA, por lo que la venta neta se calcula como: `Precio Pagado / 1.19`.
   - La conversión a dólares divide la venta neta en COP entre la TRM oficial del día (suministrada en tiempo real por el Banco de la República vía datos.gov.co).

2. **Cumplimiento Presupuestal y Semáforo:**
   - **Verde (🟢 En Meta):** Cumplimiento $\ge 100\%$ de la meta acumulada a la fecha.
   - **Amarillo (🟡 En Riesgo):** Cumplimiento entre $80\%$ y $99.9\%$.
   - **Rojo (🔴 Crítico):** Cumplimiento $< 80\%$.
   - *Nota de cálculo:* Cada mes presupuestado reparte su meta linealmente entre sus días. El semáforo compara lo vendido hasta el día actual del mes contra la meta esperada proporcional a ese mismo día.

3. **Margen Real de Venta vs. RENT de Matriz:**
   - **RENT Catálogo (Excel):** $1 - \frac{\text{Costo con Factor}}{\text{Precio Venta} / 1.19}$. Refleja el margen objetivo de lista (el catálogo estándar contiene 54 SKU con RENT entre 13.4% y 68.3%).
   - **Margen Real:** $\frac{(\text{Precio Pagado} / 1.19) - (\text{Costo} \times \text{Unidades})}{\text{Precio Pagado} / 1.19}$. Refleja el margen efectivo tras descuentos y promociones.
   - *Importante:* No se aplican deducciones de comisiones estimadas ni fórmulas no auditadas.

4. **Salud del Inventario:**
   - **% Restante:** $\frac{\text{Stock Actual}}{\text{Stock Actual} + \text{Unidades Vendidas Históricas}}$.
   - **Semanas de Stock:** $\frac{\text{Stock Actual}}{\text{Ventas últimos 28 días} / 4}$.
   - **Alertas de Inventario:**
     - 🔴 **Quiebre de Stock:** Stock igual a 0 unidades.
     - 🔴 **Riesgo Crítico:** Menos de 2 semanas de cobertura o $\%$ restante $\le 50\%$.
     - 🟡 **Atención:** $\%$ restante entre $50\%$ y $65\%$.
     - ⚪ **Sin Ventas:** SKUs con stock disponible pero sin ventas en los últimos 28 días.

---

### Navegación por Pestañas

- **Resumen:** Tablero principal con los 4 indicadores estratégicos, barra de progreso del mes, semáforo del trimestre y alertas críticas de stock y devoluciones.
- **Presupuesto:** Comparativo detallado contra la meta 2026–2028 por mes y trimestre (Q4 2026 a Q3 2028). Incluye desglose numérico exportable.
- **Ventas:** Análisis de tendencia diaria, mensual y distribución de pedidos. Módulo especializado de **Cancelaciones y Devoluciones** (tasa de pérdida, valor no vendido y top productos afectados).
- **Productos:** Matriz de rentabilidad por SKU, dispersión de margen vs. volumen, ranking de los productos más vendidos y auditoría de precios.
- **Inventario:** Monitoreo de existencias, semanas de rotación, clasificación de criticidad y módulo de carga rápida de stock.

---

### Actualización de Archivos de Datos

Los archivos maestros se encuentran en la carpeta `datos/`:

#### 1. `datos/presupuesto.xlsx`
- **Hoja obligatoria:** `PRESUPUESTO`
- **Fila clave:** `Ingresos netos / Venta Mayorista`
- **Período soportado:** 24 meses desde septiembre de 2026 hasta agosto de 2028.
- **Estructura trimestral:** Respeta celdas combinadas para trimestres con año (ejemplo: `Q4 2026`, que contiene 4 meses: sep, oct, nov, dic).
- **Totales de control:** Meta total de aprox. US$ 11.011.015. Al actualizar metas, mantenga la misma fila de ingresos netos.

#### 2. `datos/costos.xlsx`
- **Hoja obligatoria:** `MATRIZ`
- **Columnas requeridas:**
  - `SKU`: Código de producto de Finart (ej. `210114094`).
  - `PV`: Precio de venta sugerido al público con IVA.
  - `COSTO CON FACTOR`: Costo unitario cargado con factor de importación/manufactura.
  - `RENT`: Margen porcentual objetivo.
- Los nuevos SKUs agregados a esta hoja se integrarán automáticamente en el cálculo de margen del dashboard.

#### 3. Carga Manual de Inventario
- Puede cargar un archivo Excel o CSV directamente desde la pestaña **Inventario** del dashboard con las columnas `SKU` y `CANTIDAD` (o `STOCK`). El sistema guardará un snapshot fecheado en la base de datos `ventas.db`.

---

### Enchufes para Datos Futuros

El sistema incorpora tres "enchufes" arquitectónicos listos para operar cuando Finart disponga de la información, sin alterar la base de código:

1. **Fecha de Salida al Mercado (`datos/ingresos.xlsx`):**
   - Permite calcular la velocidad de venta real considerando los días exactos desde que cada SKU ingresó al catálogo.
   - Formato requerido: Columnas `SKU`, `FECHA_INGRESO` (o `FECHA_SALIDA`) y `UNIDADES_INICIALES`. Si el archivo no existe, el sistema muestra un estado informativo y asume la primera fecha de venta registrada.
2. **Comisión Real Negociada con Falabella:**
   - Configurable en el archivo `.env` mediante el parámetro `COMISION_FALABELLA_PCT` (ej. `0.15` para 15%).
   - Hasta que se defina oficialmente, permanece en `0.0` para respetar estrictamente la regla de no inventar márgenes estimados.
3. **TRM Histórica por Fecha:**
   - La arquitectura soporta consultar la TRM específica del día de cada orden en lugar de la TRM del día actual si se activa el parámetro `USAR_TRM_HISTORICA=true` en `.env`.

---

## 3. Guía de Arquitectura y Desarrollo

### Estructura del Proyecto (Multi-Dashboard)

El código ha sido modularizado para permitir la futura incorporación del dashboard de **"Tienda Física"** compartiendo componentes visuales, autenticación y lógica de datos:

```
dashboard-falabella/
├── app.py                         # Punto de entrada principal (autenticación y enrutamiento)
├── core/                          # Paquete común compartido
│   ├── config.py                  # Tokens de diseño, umbrales y rutas
│   ├── auth.py                    # Sistema de autenticación de usuarios
│   ├── currency.py                # Servicio TRM (datos.gov.co + fallback)
│   ├── ui.py                      # Componentes UI (KPI cards, badges, exportación)
│   ├── charts.py                  # Tema Altair unificado Finart y gráficas
│   └── data/                      # Conectores de base de datos y Excel
│       ├── db.py                  # Conexión SQLite e indexación
│       ├── budget_loader.py       # Lector del presupuesto 2026-2028
│       ├── margin_loader.py       # Lector de matriz de costos y RENT
│       └── stock_loader.py        # Lector y snapshot de inventarios
├── dashboards/                    # Módulos específicos por canal de venta
│   ├── falabella/                 # Dashboard ARDP · Falabella
│   │   ├── logic.py               # Lógica de negocio y métricas Falabella
│   │   ├── future_plugs.py        # Enchufes (ingresos.xlsx, comisiones, TRM histórica)
│   │   └── views/                 # Vistas del dashboard
│   │       ├── resumen.py         # Pestaña Resumen
│   │       ├── presupuesto.py     # Pestaña Presupuesto
│   │       ├── ventas.py          # Pestaña Ventas y Cancelaciones
│   │       ├── productos.py       # Pestaña Productos y Rentabilidad
│   │       └── inventario.py      # Pestaña Inventario y Quiebres
│   └── tienda/                    # Dashboard futuro: Tienda / Corner físico
│       └── README.md              # Especificación y guía de integración
├── assets/                        # Identidad visual corporativa
│   ├── finart-logo.png            # Logotipo oficial Finart
│   ├── favicon.ico                # Favicon institucional
│   └── estilos.css                # Sistema de diseño CSS Finart
├── datos/                         # Archivos maestros Excel (presupuesto, costos)
├── backups/                       # Copias de seguridad automáticas (.zip)
├── logs/                          # Registro de sincronizaciones y errores
├── scripts/                       # Herramientas de soporte y mantenimiento
│   ├── backup.py                  # Motor de respaldos con retención de 30 días
│   ├── healthcheck.py             # Diagnóstico de integridad de archivos y base de datos
│   ├── sincronizar_tarea.bat      # Script para Task Scheduler (Windows)
│   ├── sync_cron.sh               # Script para crontab (Linux)
│   └── capturar_pantallas.py      # Verificación visual automatizada (Playwright)
├── tests/                         # Suite de pruebas automatizadas (pytest)
├── Dockerfile                     # Construcción de contenedor seguro sin privilegios
├── docker-compose.yml             # Orquestación de contenedor y volúmenes
├── requirements.txt               # Dependencias Python con versiones fijadas
└── .env.example                   # Plantilla de variables de entorno
```

---

### Red de Pruebas Automatizadas

El proyecto cuenta con 22 pruebas automatizadas con `pytest` que verifican la integridad de las fórmulas antes de cualquier despliegue:

```bash
# Ejecutar la suite completa de pruebas
pytest tests/ -v
```

Las pruebas cubren:
- **`test_budget.py`:** Coincidencia exacta de metas presupuestales (US$ 11.011.015 total, trimestres y meses).
- **`test_margen.py`:** Cálculo de RENT de catálogo (SKU 210114094 = 47.43%) y márgenes reales sin inventar comisiones.
- **`test_stock.py`:** Detección de quiebres, semanas de inventario y regla de los 28 días.
- **`test_app_logic.py`:** Preparación de datos, estados excluidos y semáforos.
- **`test_edge_cases.py`:** Resistencia ante valores nulos, bases de datos vacías o registros atípicos.
- **`test_benchmark.py`:** Prueba de estrés con 40.000 pedidos (3 años y 500 SKUs) procesados en **< 0.3 segundos** (meta: < 2.0 s).

---

## 4. Guía de Despliegue y DevOps

### Requisitos Previos y Variables de Entorno

1. Instale Python 3.11 o superior.
2. Copie el archivo `.env.example` como `.env`:
   ```bash
   cp .env.example .env
   ```
3. Configure las variables en `.env`:
   ```ini
   # Autenticación
   DASHBOARD_PASSWORD=finart2026
   DASHBOARD_USERS={"gerencia": "finart2026", "comercial": "ventas2026"}

   # Credenciales Falabella Seller Center
   FALABELLA_USER=tu_usuario@finartsa.com
   FALABELLA_API_KEY=tu_api_key_seller_center

   # Tasa de cambio de respaldo (si falla la consulta en vivo)
   FX_USD_COP=4150.0
   ```

---

### Arranque Local

- **En Windows:**
  Haga doble clic en `iniciar_windows.bat` o ejecute desde la terminal:
  ```cmd
  iniciar_windows.bat
  ```

- **En Linux / macOS:**
  ```bash
  chmod +x iniciar_linux.sh
  ./iniciar_linux.sh
  ```

El dashboard se abrirá automáticamente en `http://localhost:8501`.

---

### Despliegue con Docker y Docker Compose

Para un entorno de producción aislado y estandarizado:

```bash
# Construir e iniciar el contenedor en segundo plano
docker compose up -d --build

# Ver los registros de ejecución
docker compose logs -f

# Detener el servicio
docker compose down
```

El archivo `docker-compose.yml` monta volúmenes persistentes para `ventas.db`, `datos/`, `backups/` y `logs/`, garantizando que la información se conserve intacta ante reinicios o actualizaciones.

---

### Sincronización Automática con Seller Center

Para que las órdenes de Falabella se sincronicen periódicamente a `ventas.db`:

#### En Windows (Programador de Tareas / Task Scheduler):
1. Abra el **Programador de tareas** (`taskschd.msc`).
2. Seleccione **Crear tarea básica...** y asígnele el nombre `Sincronizar Falabella Finart`.
3. Desencadenador: **Diariamente**, repetir cada 1 hora (o 3 horas).
4. Acción: **Iniciar un programa** $\rightarrow$ Seleccionar el archivo `scripts\sincronizar_tarea.bat`.
5. Los registros de sincronización quedarán almacenados en `logs\sync.log`.

#### En Linux (Cron):
Agregue la siguiente línea a su `crontab -e`:
```bash
0 */2 * * * /ruta/al/proyecto/scripts/sync_cron.sh
```

---

### Sistema de Respaldos Diarios

El script `scripts/backup.py` genera copias de seguridad comprimidas en formato `.zip` que incluyen la base de datos `ventas.db` y todos los archivos de `datos/`. Mantiene automáticamente una retención de 30 días, eliminando copias antiguas.

- **Ejecutar respaldo manual en Windows:**
  ```cmd
  scripts\hacer_respaldo.bat
  ```
- **Ejecutar desde terminal:**
  ```bash
  python scripts/backup.py
  ```

---

### Diagnóstico y Chequeo de Salud (Healthcheck)

Para verificar el estado integral del sistema (archivos maestros, base de datos SQLite, API de TRM y pruebas de regresión):

```bash
python scripts/healthcheck.py
```

Salida esperada:
```
============================================================
           FINART S.A.S. - DIAGNÓSTICO DE SALUD             
============================================================
[OK] Archivo presupuesto.xlsx encontrado
[OK] Hoja PRESUPUESTO y meta total validadas: US$ 11,011,015
[OK] Archivo costos.xlsx encontrado
[OK] Hoja MATRIZ y 54 SKUs de catálogo validados
[OK] Base de datos ventas.db encontrada
[OK] Tabla order_items presente con índices optimizados
[OK] Conexión y consulta a TRM oficial exitosa
------------------------------------------------------------
ESTADO GENERAL: SALUDABLE (SISTEMA OPERATIVO)
============================================================
```

---

## 5. Recomendación de Seguridad y Despliegue en Producción

> [!CAUTION]
> **Protección de Datos Estratégicos:** Por contener información comercial confidencial (márgenes reales, costos de fabricación, catálogo de clientes y ventas de Finart S.A.S.), **está estrictamente desaconsejado desplegar esta solución en servicios en la nube gratuitos o públicos** (como Streamlit Community Cloud público, Heroku free o HuggingFace Spaces públicos) donde el código o las variables puedan quedar expuestos.

### Arquitectura Recomendada para Finart S.A.S.:

```
                              [ Internet / VPN ]
                                      │
                                      ▼  HTTPS (Puerto 443 con Certificado SSL/TLS)
                       ┌─────────────────────────────┐
                       │   Reverse Proxy (Nginx /    │
                       │           Caddy)            │
                       └──────────────┬──────────────┘
                                      │  HTTP (Puerto 8501 en red interna Docker)
                                      ▼
                       ┌─────────────────────────────┐
                       │  Contenedor Docker Finart   │
                       │   (Usuario sin privilegios) │
                       │    Streamlit ARDP Falabella │
                       └──────────────┬──────────────┘
                                      │
                         Volúmenes Persistentes Cifrados
                         ├── ventas.db
                         ├── datos/ (presupuesto, costos)
                         └── backups/ (diario a NAS o Cloud privado)
```

1. **Infraestructura:** Servidor dedicado o Máquina Virtual interna (en la red corporativa de Finart) o VPS privada (AWS EC2 / Azure VM / Google Compute Engine) con firewall restringido.
2. **Acceso Seguro:** Acceso restringido exclusivamente mediante **VPN corporativa** de Finart o túnel privado (Cloudflare Zero Trust / WireGuard).
3. **Cifrado en Tránsito:** Reverse Proxy (Nginx o Caddy) con certificado SSL/TLS (HTTPS) forzoso.
4. **Cifrado en Reposo:** Disco del servidor cifrado con BitLocker (Windows Server) o LUKS (Linux).
5. **Autenticación en Capas:** Acceso protegido por credenciales de usuario configuradas en `.env` más autenticación básica en el servidor web.

---
© 2026 Finart S.A.S. — Todos los derechos reservados.
