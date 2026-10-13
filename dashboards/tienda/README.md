# Dashboard Tienda Física · Finart S.A.S. (Estructura Reservada)

Este directorio está preparado para alojar la segunda solución analítica de Finart S.A.S.:
**Ventas de Corner / Tienda Física, Control de Gastos Operativos y EBITDA**.

## Reutilización de Arquitectura Común
Al implementarse, este dashboard consumirá directamente los módulos compartidos de `core/`:
- `core.auth`: Mismo sistema de acceso y control de permisos de usuario.
- `core.ui`: Componentes KPI responsivos, tarjetas de estado y botones de exportación a Excel/CSV.
- `core.charts`: Tema institucional Finart en Altair, colores corporativos y formateo en español.
- `core.currency`: Consulta centralizada de TRM oficial del día e histórica.
- `assets/estilos.css` y `.streamlit/config.toml`: Identidad visual unificada.

## Estructura Proyectada
```text
dashboards/tienda/
├── __init__.py
├── views/
│   ├── ebitda.py            # Estado de resultados, ingresos tienda física vs gastos
│   ├── ventas_tienda.py     # Ventas en punto físico, ticket y tráfico
│   └── inventario_tienda.py # Stock en tienda vs bodega central
└── logic.py                 # Cálculos contables y operacionales de tienda
```
