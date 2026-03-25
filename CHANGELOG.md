# Changelog

Todos los cambios relevantes del proyecto están documentados aquí.

---

## 2026-03-25
- `feat(notifications)`: Notificaciones en tiempo real vía WebSocket con Django Channels
- `refactor(serializers)`: Optimizar serializers reemplazando `SerializerMethodField` por `source=`
- `fix(decorators)`: Proteger `get_store` contra header `store-id` no numérico
- `chore`: Reemplazar Gunicorn por Daphne en entrypoint para soporte ASGI/WebSocket
- `docs`: Crear `CODING_RULES.md` y `CHANGELOG.md`

## 2026-03-24
- `feat(stock-requests)`: Renombrar `updated_stock` a `requested_stock` y prevenir solicitudes duplicadas
- `fix(payments)`: Calcular total de pago usando conteo real de tiendas del tenant
- `feat(stores-cash-summary)`: Agregar dict de `manager`, flag `has_all_products` e info de impresora por tienda
- `feat(products)`: Ordenar brands y departments alfabéticamente
- `refactor`: Reordenar imports (PEP 8) y optimizar métodos de modelo con aggregates
- `perf(products)`: Optimizar búsqueda de store-product y listado de tiendas
- `perf(sales)`: Endpoint bulk `stores-cash-summary` (~7 queries en vez de ~70)

## 2026-03-23
- `feat(accounts)`: Agregar `store_count` en respuesta de login para owners
- `refactor(audit)`: Simplificar respuesta de auditoría de productos para exportación Excel

## 2026-03-21
- `feat(audit)`: Endpoints de auditoría de productos (códigos repetidos, costo cero, mayoreo inconsistente, faltantes)
- `refactor(audit)`: Renombrar audit1/audit2 a sales-logs-audit/stock-audit

## 2026-03-19
- `docs`: Agregar docstrings a scripts de mantenimiento

## 2026-03-15
- `feat(products)`: Filtro por código en ProductViewSet
- Mejorar tono de mensajes de notificación de pagos

## 2026-03-11
- `feat(sales)`: Filtro opcional por mes en dashboard de ventas

## 2026-03-10
- `feat(accounts)`: Agregar user.id en respuesta de login y ViewSet de usuarios
- `feat(accounts)`: Permitir a owners cambiar contraseña de managers

## 2026-03-09
- `refactor`: Optimizar TenantInfoView y cambiar notices a formato dict
- `feat(tenants)`: Endpoint CRUD de tenant

## 2026-03-07
- `refactor`: Centralizar action choices usando constantes LogAction

## 2026-03-06
- `feat(products)`: Endpoint para resetear stock de tienda
- `refactor`: Renombrar views a convenciones Django REST
- `refactor`: Mejorar naming de variables
- `refactor`: Reorganizar y estandarizar URLs en todas las apps

## 2026-03-05
- `feat(products)`: Endpoint de detalle de inversión con store ID requerido

## 2026-03-04
- `perf`: Optimizar queries con select_related, índices y aggregations
- `fix`: Prevenir race conditions en operaciones de stock con select_for_update
- `feat`: Validación triple de stock para prevenir inventario negativo
- `feat`: Validación y sanitización de archivos Excel
- `perf`: Optimizar calculate_reserved_stock con annotations de BD
- `perf`: Agregar only/defer, índices y connection pooling
- `refactor`: Extraer utilidades de importación, agregar enums, eliminar código muerto

## 2026-03-02
- `feat(sales)`: Filtrar ventas por año en dashboard
- `perf(sales)`: Optimizar get_sales_for_dashboard con values()

## 2026-02-28
- `fix(audit)`: Corregir manejo de errores en TaskResultView para tareas fallidas

## 2026-02-24
- Cambios generales

## 2026-01-02
- `feat`: Base de préstamos

## 2025-12-08
- `perf`: Optimizaciones generales
- `fix(products)`: Corregir distribución

## 2025-12-06
- `fix(products)`: Corregir transferencia

## 2025-11-24
- `fix(sales)`: Correcciones en ventas

## 2025-11-07
- `feat(products)`: Distribución v2

## 2025-11-05
- `feat`: Eliminar stock negativo

## 2025-11-03
- `perf`: Optimizaciones generales

## 2025-10-22
- `feat(sales)`: Dashboard de ventas (por semana, hora, método de pago)

## 2025-10-18
- `feat(audit)`: App de auditoría con detección de duplicados, inconsistencias y porcentajes

## 2025-10-17
- `feat(logs)`: Últimos 10 logs, ver duplicadas
- Celery worker en entrypoint

## 2025-10-08
- `feat(logs)`: Detección de duplicados y consistencia

## 2025-09-15
- `perf`: Optimización de queries, middleware keep-alive, índices de BD

## 2025-09-10
- `perf`: Optimización de store product y traspasos

## 2025-09-08
- `refactor`: Mejora de serializers

## 2025-08-15
- `feat`: Tareas asíncronas con Celery
- `feat(sales)`: Códigos de barras en ventas

## 2025-08-12
- `fix(products)`: Corregir transferencias

## 2025-08-01
- `feat`: Integración de Celery y Redis
- `perf`: Optimizaciones de queries

## 2025-07-22
- `fix(sales)`: Filtrar ventas canceladas correctamente

## 2025-06-24
- `feat(sales)`: Aceptar intercambios/devoluciones

## 2025-06-17
- `feat(clients)`: Compras por cliente

## 2025-06-10
- `feat`: Nueva validación de datos

## 2025-05-27
- `feat(printers)`: Configuración de impresoras

## 2025-05-05
- `feat(sales)`: Sistema de apartados (reservaciones)

## 2025-04-24
- `feat(products)`: Códigos a mayúsculas automáticamente

## 2025-04-18
- `feat(sales)`: Devoluciones parciales

## 2025-04-07
- `feat(products)`: Reasignar productos entre marcas/departamentos

## 2025-04-05
- `fix`: Correcciones en distribución, cash summary, importación

## 2025-04-02
- `feat(sales)`: Mejora en cancelación de ventas

## 2025-03-26
- `feat(products)`: Importación masiva de stock desde Excel

## 2025-03-25
- `feat(sales)`: Ventas por departamento

## 2025-03-24
- `feat(accounts)`: Roles y permisos (owner, manager, seller)
- `feat(products)`: Departamentos

## 2025-03-20
- `feat(accounts)`: Sistema de vendedores (StoreWorker)

## 2025-03-19
- `feat(sales)`: Corte de caja por rango de fechas

## 2025-03-18
- `feat(products)`: Importación de productos mejorada
- `fix(products)`: Corregir traspasos
- `feat(sales)`: Referencia de pago

## 2025-03-17
- `feat(tenants)`: Info de tenant y conteo de productos

## 2025-03-15
- `feat(printers)`: Impresión de tickets

## 2025-03-10
- `feat(products)`: Imágenes de productos en AWS S3
- `feat(logs)`: Filtros en bitácora

## 2025-03-05
- `feat(sales)`: Corte de caja (cash summary)
- `feat(tenants)`: Sistema de pagos/suscripción

## 2025-03-01
- `feat(sales)`: Detección de ventas duplicadas

## 2025-02-28
- `feat(products)`: Mejora en listado de tiendas

## 2025-02-23
- `feat(printers)`: Impresoras térmicas (python-escpos)

## 2025-02-19
- `feat(products)`: Traspasos entre almacenes

## 2025-02-09
- `feat(sales)`: Corte de caja base

## 2025-02-06
- `feat(products)`: Flujo de caja (CashFlow)

## 2025-02-04
- `feat(printers)`: App de impresoras

## 2025-01-27
- `feat(products)`: Inversión por tienda

## 2025-01-25
- `feat(products)`: Importación de máquinas/stock y mejora de logs

## 2025-01-24
- `feat(logs)`: App de bitácora de inventario

## 2025-01-23
- `perf`: Optimización de queries en store-product-list

## 2025-01-22
- `chore`: Configuración de producción (decouple, migraciones)

## 2025-01-20
- `feat(sales)`: Vendedor obligatorio y cancelación de ventas

## 2025-01-19
- `refactor`: Decorador get_store para obtener tienda del header

## 2025-01-15
- `feat(sales)`: Importación de ventas desde Excel

## 2025-01-12
- `feat(tenants)`: Sistema multi-tenant

## 2025-01-07
- `refactor(accounts)`: Refactorizar usuarios y signals

## 2025-01-06
- Primera versión funcional completa

## 2024-12-12
- Desarrollo en progreso

## 2024-11-08
- `feat(products)`: Traspaso multi-producto

## 2024-11-06
- `chore`: Deploy inicial (Gunicorn, WhiteNoise, PostgreSQL, Render)
- `feat(products)`: Mejora en importación de datos

## 2024-11-04
- `feat`: Integridad de datos y validaciones

## 2024-11-01
- `feat(products)`: Sistema de traspasos entre sucursales

## 2024-10-27
- `feat(sales)`: Creación de ventas con descuento de stock

## 2024-10-24
- `feat(products)`: Importación masiva de datos desde Excel

## 2024-10-23
- `feat(sales)`: App de ventas
- `feat(clients)`: App de clientes con descuentos y mayoreo

## 2024-10-22
- `feat(clients)`: Sistema de descuentos

## 2024-10-18
- `feat(clients)`: API de clientes
- `feat(products)`: API de StoreProduct

## 2024-10-14
- `feat(accounts)`: Login y autenticación por token

## 2024-10-08
- `feat(products)`: Marca, categoría, precios y manager

## 2024-10-07
- `feat(products)`: Modelos de Product y Store

## 2024-10-04
- 🎉 Primer commit
