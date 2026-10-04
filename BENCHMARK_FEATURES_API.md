# 📊 SmartVenta — Benchmark Mercadológico de Features

**Fecha de generación:** 27 de agosto de 2026  
**Última actualización:** 4 de octubre de 2026  
**Versión del sistema:** Producción activa  
**Tipo de producto:** Sistema POS (Punto de Venta) Multi-Sucursal SaaS en la Nube

---

## 📌 Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Gestión Multi-Sucursal](#2-gestión-multi-sucursal)
3. [Punto de Venta (POS)](#3-punto-de-venta-pos)
4. [Inventario](#4-inventario)
5. [Transferencias y Distribuciones](#5-transferencias-y-distribuciones)
6. [Apartados (Reservaciones)](#6-apartados-reservaciones)
7. [Clientes y Descuentos](#7-clientes-y-descuentos)
8. [Corte de Caja y Reportes Financieros](#8-corte-de-caja-y-reportes-financieros)
9. [Devoluciones y Cancelaciones](#9-devoluciones-y-cancelaciones)
10. [Catálogo de Productos](#10-catálogo-de-productos)
11. [Importación y Exportación Masiva](#11-importación-y-exportación-masiva)
12. [Auditoría e Integridad de Datos](#12-auditoría-e-integridad-de-datos)
13. [Bitácora de Movimientos](#13-bitácora-de-movimientos)
14. [Roles y Permisos](#14-roles-y-permisos)
15. [Impresión de Tickets](#15-impresión-de-tickets)
16. [Notificaciones en Tiempo Real](#16-notificaciones-en-tiempo-real)
17. [Dashboards y Analítica](#17-dashboards-y-analítica)
18. [Facturación y Suscripciones](#18-facturación-y-suscripciones)
19. [Infraestructura y Rendimiento](#19-infraestructura-y-rendimiento)
20. [Seguridad](#20-seguridad)
21. [Conversión de Unidades](#21-conversión-de-unidades)
22. [Correo Electrónico](#22-correo-electrónico)
23. [Tabla Resumen para Benchmark](#23-tabla-resumen-para-benchmark)

---

## 1. Resumen Ejecutivo

SmartVenta es un sistema POS en la nube diseñado para negocios minoristas con múltiples sucursales (tiendas y almacenes). Permite gestionar de forma centralizada inventario, ventas, clientes, personal y finanzas desde una sola plataforma web accesible desde cualquier dispositivo con navegador.

**Mercado objetivo:** Negocios minoristas con 1 a N sucursales en México.  
**Modelo de negocio:** SaaS con suscripción mensual por tienda. Cobro automatizado vía Mercado Pago. Los precios viven en los planes (`GET /api/plans/`), no en este documento.  
**Arquitectura:** API REST stateless, multi-tenant (cada negocio es un "Tenant" aislado).

---

## 2. Gestión Multi-Sucursal

### 2.1 Tipos de Ubicaciones
- **Tiendas ("T"):** Puntos de venta activos donde se realizan ventas al público. Cada tienda tiene su propia caja, vendedores, stock independiente e impresora de tickets.
- **Almacenes ("A"):** Ubicaciones de almacenamiento de mercancía. No realizan ventas directas, pero participan en el flujo de distribución y transferencias hacia tiendas.

### 2.2 Administración Centralizada
- El propietario (owner) del negocio puede ver y gestionar todas las sucursales desde un solo punto.
- Cada sucursal tiene un administrador (manager) asignado como usuario único, con credenciales generadas automáticamente al crear la tienda.
- Formato de credenciales automáticas: `{nombre_corto_negocio}.{tipo_tienda}.{nombre_tienda}`.
- Cada tienda tiene datos de contacto (dirección, teléfono).

### 2.3 Creación de Sucursales
- Al crear una nueva tienda, el sistema automáticamente:
  - Crea un usuario manager con credenciales basadas en el nombre del negocio y tienda.
  - Registra todos los productos existentes del catálogo del negocio en esa tienda (con stock en 0), para que el catálogo esté completo desde el primer día.
- Al crear un nuevo producto, automáticamente se registra en todas las tiendas del negocio (stock en 0).

### 2.4 Límite de Sucursales por Plan
- El plan contratado define cuántas sucursales puede tener el negocio. El sistema valida si se puede crear una nueva tienda antes de permitir la creación.

### 2.5 Visibilidad de Stock de Almacenes
- Configuración por negocio: el owner puede decidir si los vendedores ven o no el stock disponible en almacenes. Esto se controla con la opción `displays_stock_in_storages`.

---

## 3. Punto de Venta (POS)

### 3.1 Registro de Ventas
- Venta de múltiples productos en una sola transacción.
- Cada línea de venta registra: producto, cantidad y precio unitario aplicado.
- Soporte para productos vendidos por pieza (PZ), kilogramo (KG), litro (LT), bote (BO) o costal (CO).
- Cantidades decimales (hasta 3) para productos que se venden por fracción: kilogramo y litro. El producto y cada línea de venta indican si se vende por fracción (`sells_by_fraction`).
- Cálculo automático del total de la venta.

### 3.2 Métodos de Pago
- Tres métodos de pago soportados: **Efectivo**, **Tarjeta** y **Transferencia bancaria**.
- **Pagos mixtos:** una sola venta puede recibir pagos en múltiples métodos simultáneamente (ej. parte efectivo y parte tarjeta).
- Campo de referencia de transacción para pagos que no son efectivo (número de autorización, referencia de transferencia, etc.).

### 3.3 Búsqueda de Productos en POS
- Búsqueda por nombre, marca o código de barras.
- Filtrado por marca y departamento.
- Búsqueda directa por código exacto (para lectura de código de barras con escáner).
- Resultado limitado a 200 productos por defecto para evitar sobrecargar la interfaz. El límite es configurable con el parámetro `limit`.

### 3.4 Validación de Stock en Venta
- Antes de confirmar la venta, valida que haya stock disponible suficiente.
- El stock disponible se calcula como: `stock actual - stock reservado en traspasos pendientes - stock reservado en apartados`.
- Si el stock disponible es insuficiente, la venta se rechaza con mensaje claro indicando el producto, la cantidad disponible y la solicitada.

### 3.5 Descuento de Inventario Automático
- Al confirmar la venta, el stock de cada producto se descuenta automáticamente de la sucursal.
- Se genera un registro de log (bitácora) por cada producto vendido con: stock anterior, stock nuevo, usuario, tipo de movimiento.

### 3.6 Asignación de Vendedor
- Cada venta queda asociada al usuario que la registró (vendedor o administrador).
- Los vendedores solo ven sus propias ventas. Los administradores y propietarios ven todas.

### 3.7 Asignación de Cliente
- Opcionalmente se puede asociar un cliente a la venta, lo que permite aplicar descuentos y llevar historial de compras.

### 3.8 Prevención y Detección de Ventas Duplicadas
- **Bloqueo por doble envío:** si el mismo vendedor registra en la misma tienda otra venta con la misma cantidad total de productos en menos de 2 segundos, la venta se rechaza con HTTP 409 (evita duplicados por doble clic o reintentos de red).
- Además, el sistema detecta automáticamente posibles ventas duplicadas: si dos ventas consecutivas en la misma tienda tienen el mismo total y ocurren en menos de 1 segundo, se marca como potencial duplicado.
- Se envía notificación en tiempo real al registrar una venta potencialmente duplicada.
- Funcionalidad para revertir stock y eliminar ventas duplicadas.

### 3.9 Venta desde Archivo Excel (Importación de Ventas)
- Permite registrar ventas masivamente desde un archivo Excel.
- Flujo en dos pasos: primero validación (revisa códigos, stock disponible), luego importación.
- Cada fila del Excel genera una venta individual con pago en efectivo.

### 3.10 Utilidad por Venta
- Cada venta almacena su utilidad: suma de (precio de venta − costo) × cantidad de cada producto.
- Se recalcula automáticamente al agregar, modificar o eliminar productos de la venta (por ejemplo, en devoluciones parciales).
- La utilidad guardada alimenta el corte de caja multi-sucursal y el dashboard de ventas sin recalcular en cada consulta.

---

## 4. Inventario

### 4.1 Stock por Sucursal
- Cada producto tiene un registro de stock independiente por cada sucursal/almacén.
- El stock se representa con hasta 3 decimales (para productos que se venden por peso).
- Consulta de stock total consolidado de un producto en todas las sucursales.

### 4.2 Consulta de Stock en Otras Tiendas
- Desde cualquier tienda se puede consultar el stock disponible de un producto en las demás ubicaciones. Se muestra el stock disponible (descontando reservados).

### 4.3 Entradas Manuales de Stock
- Se pueden registrar entradas de stock (mercancía recibida) de múltiples productos a la vez.
- Cada entrada genera un log de bitácora con acción "Entrada".

### 4.4 Ajustes de Stock
- Modificación directa del stock de un producto cuando hay discrepancias con conteo físico.
- Solo se genera log si el stock realmente cambia.
- Si el producto tenía la bandera `requires_stock_verification`, se limpia automáticamente al hacer el ajuste.

### 4.5 Solicitud de Ajuste de Stock
- Un vendedor puede solicitar un ajuste de stock (no aplicarlo directamente). Esto genera una "solicitud de ajuste".
- El administrador puede aprobar o rechazar la solicitud.
- Al aprobar, se aplica el nuevo stock, se genera el log correspondiente y se limpia la bandera de verificación.
- Solo puede haber una solicitud pendiente por producto-tienda a la vez.
- Se envía notificación en tiempo real cuando se crea o aprueba una solicitud.

### 4.6 Reinicio de Stock
- Funcionalidad para poner todo el stock de una tienda en 0 (operación administrativa para inventarios iniciales o mudanzas).

### 4.7 Inversión en Inventario
- Cálculo automático de la inversión total en inventario de una tienda: suma de (stock × costo) de todos los productos con stock > 0.

### 4.8 Validación de Stock Negativo
- **Constraint a nivel de base de datos** (`CheckConstraint`): impide que el stock sea menor a 0 en cualquier circunstancia.
- Validación adicional a nivel de aplicación (método `clean()` en el modelo).
- Esto garantiza integridad incluso ante condiciones de carrera (race conditions).

### 4.9 Stock Reservado
- El stock reservado se calcula dinámicamente y consiste en:
  - Stock comprometido en transferencias pendientes (no confirmadas).
  - Stock comprometido en apartados en progreso.
- El stock "disponible para venta" = stock real - stock reservado.

### 4.10 Verificación de Stock (Auditoría)
- Bandera `requires_stock_verification` por producto-tienda que indica discrepancia entre stock del sistema y el último log.
- Dashboard asíncrono que detecta todas las discrepancias en las tiendas del negocio.

---

## 5. Transferencias y Distribuciones

### 5.1 Transferencias Individuales
- Movimiento de un producto específico de una sucursal (origen) a otra (destino).
- Se registra: producto, cantidad, tienda origen, tienda destino.
- La transferencia queda "pendiente" hasta que se confirma la recepción.
- Al confirmar: se descuenta stock de origen, se suma stock en destino, se generan logs en ambas tiendas.
- Validación de stock suficiente en tienda origen antes de confirmar.
- Notificación en tiempo real a la tienda destino cuando se crea un traspaso.

### 5.2 Distribuciones (Transferencias Masivas)
- Una "distribución" agrupa múltiples transferencias de una misma tienda origen a una misma tienda destino.
- Útil para envíos grandes de mercancía (ej. del almacén central a una tienda).
- Se confirma toda la distribución de una sola vez.
- Si la tienda origen no tiene stock suficiente al momento de confirmar, se hace un ajuste automático para permitir la operación (con log de ajuste).
- Notificación en tiempo real a la tienda destino al crear y confirmar distribuciones.
- **Protección contra doble confirmación:** si la distribución ya fue confirmada, o se intenta confirmar de nuevo en menos de 2 segundos, se rechaza con HTTP 409.

### 5.3 Filtrado de Transferencias
- Filtrado por estado: pendientes o aplicadas (confirmadas hoy).
- Listado de movimientos pendientes agrupado por pares de tiendas (origen → destino) con conteo de distribuciones y traspasos.
- Las cantidades se devuelven como enteros cuando no tienen decimales (ej. `5` en vez de `5.000`).

### 5.4 Dashboard de Traspasos Pendientes
- Vista asíncrona (Celery task) que muestra todos los traspasos pendientes de todas las tiendas del negocio, con detalle de producto, marca, cantidad, fechas y tiendas involucradas.

---

## 6. Apartados (Reservaciones)

### 6.1 Creación de Apartados
- Un apartado es una venta marcada como "en progreso" (`reservation_in_progress = True`).
- Al crear un apartado, el stock **NO se descuenta** de la tienda. En su lugar, el stock queda "reservado" y se resta del stock disponible para otras ventas.
- El apartado se puede asociar a un cliente.

### 6.2 Abonos a Apartados
- El cliente puede ir abonando al apartado con pagos parciales.
- Cada abono se registra como un nuevo `Payment` asociado a la venta.
- Se soportan pagos mixtos en los abonos (efectivo, tarjeta, transferencia).

### 6.3 Liquidación de Apartados
- Cuando el cliente completa el pago, el apartado se "liquida" (cambia a `reservation_in_progress = False`).
- En ese momento se descuenta el stock de la tienda y se generan los logs de salida.

### 6.4 Cancelación de Apartados
- Si el cliente cancela, se maneja la devolución del dinero:
  - Los abonos hechos en días anteriores (ya reflejados en cortes de caja pasados) generan un registro de flujo de caja tipo "Salida" para cuadrar los números.
  - Se calcula el total a devolver al cliente.
- El apartado se marca como cancelado con su motivo.

### 6.5 Notificaciones de Apartados
- Se notifica en tiempo real cuando se crea un nuevo apartado.

---

## 7. Clientes y Descuentos

### 7.1 Registro de Clientes
- Datos: nombre, apellido, teléfono (10 dígitos).
- Cada cliente está asociado a un nivel de descuento.

### 7.2 Niveles de Descuento
- Los descuentos se definen como porcentajes (0-100%) a nivel de negocio (tenant).
- Cada negocio puede crear múltiples niveles de descuento (ej. 5%, 10%, 15%, 20%).
- Restricción de unicidad: no puede haber dos descuentos con el mismo porcentaje en el mismo negocio.
- El descuento se aplica como complemento porcentual: si el descuento es 10%, el cliente paga el 90%.

### 7.3 Historial de Compras por Cliente
- Se puede consultar el total de ventas de un cliente en un rango de fechas.
- Búsqueda de ventas por nombre o apellido del cliente.

### 7.4 Búsqueda de Clientes
- Búsqueda por nombre completo (nombre + apellido) o por número de teléfono.

### 7.5 Precio de Mayoreo por Producto
- Cada producto puede tener un precio de mayoreo definido, con una cantidad mínima para que aplique.
- Si el cliente tiene un descuento asignado Y el producto tiene la opción `wholesale_price_on_client_discount`, se aplica el precio de mayoreo cuando se usa el descuento del cliente.

---

## 8. Corte de Caja y Reportes Financieros

### 8.1 Corte de Caja Individual (por Tienda)
- Resumen financiero de una tienda para un día o rango de fechas.
- Incluye:
  - Desglose por método de pago (efectivo, tarjeta, transferencia).
  - Total vendido (ventas normales).
  - Total apartado (abonos a apartados).
  - Total del día (vendido + apartado).
  - Entradas de caja (inyecciones de efectivo, cambio, etc.).
  - Salidas de caja (gastos, retiros, etc.).
  - Total de entradas/salidas (neto del flujo de caja).
  - Total en caja (efectivo + neto de flujo de caja).
  - Total de ganancias (utilidad: (precio de venta − costo) × cantidad, para todas las ventas).
  - Número de ventas realizadas.
  - Apartados realizados en el periodo.
  - Ventas canceladas.
  - Distribuciones pendientes.
  - Traspasos pendientes.

### 8.2 Corte de Caja Bulk (Multi-Sucursal)
- Vista consolidada de todas las tiendas en un rango de fechas.
- Muestra el resumen de cada tienda con los mismos campos y además:
  - Nombre del administrador de cada tienda.
  - Si la tienda tiene todos los productos del catálogo.
  - Información de la impresora asignada (marca y modelo).
- Totales consolidados de todas las tiendas (suma de efectivo, tarjeta, transferencia, ventas, ganancias, etc.).
- La ganancia por tienda se obtiene sumando la utilidad guardada en cada venta.
- Optimizado con ~5 queries para manejar muchas tiendas sin degradar rendimiento.

### 8.3 Corte por Departamento
- Filtrar el corte de caja por departamento de producto.
- Muestra solo las ventas cuyos productos pertenecen al departamento seleccionado.

### 8.4 Flujo de Caja (Cash Flow)
- Registro de movimientos de efectivo independientes de las ventas:
  - **Entradas:** inyecciones de efectivo, cambio recibido, cobros externos.
  - **Salidas:** gastos operativos, retiros de efectivo, pagos a proveedores.
- Cada movimiento registra: concepto (texto libre hasta 50 caracteres), monto, tipo (entrada/salida), usuario que lo registra, tienda.
- Filtrado por rango de fechas.

### 8.5 Ventas Totales por Vendedor
- Consulta del total de ventas de un vendedor específico en un rango de fechas.

---

## 9. Devoluciones y Cancelaciones

### 9.1 Cancelación Completa de Venta
- Se puede cancelar una venta si:
  - No es un apartado en progreso.
  - El pago fue únicamente en efectivo.
  - No ha sido previamente cancelada ni tiene devoluciones.
- Al cancelar:
  - Se devuelve el stock de todos los productos al inventario de la tienda.
  - Se genera log de entrada por devolución para cada producto.
  - Se eliminan los registros de productos de la venta.
  - Se marca la venta como cancelada con un motivo opcional.
  - Se calcula el monto a devolver al cliente.

### 9.2 Devolución Parcial
- Se pueden devolver productos individuales de una venta sin cancelarla por completo.
- Se indica qué productos devolver y en qué cantidad.
- El stock del producto devuelto se regresa al inventario.
- Se recalcula el total de la venta descontando los productos devueltos.
- Se actualiza el monto del pago al nuevo total.
- Se marca la venta con `has_return = True` y un motivo de devolución.
- Se calcula el monto a devolver al cliente (diferencia entre total original y nuevo total).

### 9.3 Cancelación de Apartado
- Si un apartado se cancela:
  - No es necesario revertir stock (nunca se descontó).
  - Los pagos de días anteriores que ya se reflejaron en cortes pasados generan un flujo de caja de salida para cuadrar números.
  - Se calcula el total pagado para devolver al cliente.

---

## 10. Catálogo de Productos

### 10.1 Datos del Producto
- **Código:** Identificador único dentro del negocio. Hasta 50 caracteres. Se usa para lectura de código de barras.
- **Nombre:** Hasta 100 caracteres.
- **Marca:** Obligatoria. Clasificación primaria del producto.
- **Departamento:** Opcional. Clasificación secundaria (ej. "Electrónica", "Ropa", "Abarrotes").
- **Costo:** Precio de compra al proveedor. Hasta 10 dígitos con 2 decimales.
- **Precio unitario (menudeo):** Precio de venta normal. Hasta 10 dígitos con 2 decimales.
- **Precio de mayoreo:** Opcional. Precio especial para compras en volumen.
- **Cantidad mínima para mayoreo:** Opcional. Número de piezas mínimas para que aplique el precio de mayoreo.
- **Precio mayoreo aplica con descuento de cliente:** Boolean. Define si el precio de mayoreo se activa cuando el cliente tiene descuento asignado.
- **Imagen:** Foto del producto almacenada en AWS S3, organizada por negocio.
- **Unidad de medida:** Pieza (PZ), Kilogramo (KG), Litro (LT), Bote (BO) o Costal (CO).

### 10.2 Validaciones del Catálogo
- El código de producto es único dentro de un negocio (tenant). No pueden existir dos productos con el mismo código en el mismo negocio.
- Reglas de precio (se exigen en la importación desde Excel y se detectan en la auditoría de catálogo; ver 11.1 y 12.1):
  - Productos por fracción (KG, LT) no pueden tener precio de mayoreo.
  - Si tiene precio de mayoreo, debe tener cantidad mínima y viceversa.
  - Costo < precio mayoreo < precio unitario.

### 10.3 Búsqueda en Catálogo
- Filtros del listado de productos: nombre (`q`, búsqueda parcial), código, marca, departamento y stock máximo.

### 10.4 Marcas y Departamentos
- Las marcas y departamentos son entidades independientes creadas por el negocio.
- Se pueden crear, editar y eliminar.
- Conteo de productos por marca y por departamento.
- Funcionalidad para "reasignar" productos de una marca/departamento a otra y opcionalmente eliminar la original.

### 10.5 Estandarización de Códigos
- Funcionalidad para convertir todos los códigos a mayúsculas y reemplazar apóstrofes por guiones (limpieza masiva).

### 10.6 Actualización Masiva de Precios
- Actualizar costo, precio unitario, precio mayoreo y cantidad mínima mayoreo de múltiples productos a la vez.
- Se genera log de cambio de precio para cada producto modificado, registrando: campo, valor anterior, valor nuevo, usuario que hizo el cambio.

### 10.7 Eliminación Masiva de Productos
- Eliminar múltiples productos por sus IDs en una sola operación.

### 10.8 Historial de Cambios de Precio
- Cada vez que se modifica el costo, precio unitario, precio mayoreo o cantidad mínima de mayoreo de un producto, se registra un log con: producto, usuario, campo modificado, valor anterior, valor nuevo, fecha.
- Consulta del historial de precios de un producto específico o del negocio completo.

---

## 11. Importación y Exportación Masiva

### 11.1 Importación de Productos desde Excel
- Carga masiva de catálogo de productos desde archivos Excel (.xlsx, .xls).
- **Flujo en dos pasos:**
  1. **Validación:** Se sube el archivo y el sistema devuelve un reporte fila por fila indicando si cada producto se puede importar o tiene algún problema.
  2. **Importación:** Si la validación es aceptable, se confirma la importación.
- Validaciones que se realizan:
  - Código no vacío.
  - Marca no vacía.
  - Código no existente previamente en el sistema.
  - Código no duplicado dentro del mismo archivo.
  - Precios y costos son números positivos.
  - Costo menor que precio unitario.
  - Si hay precio mayoreo: costo < precio mayoreo < precio unitario.
  - Si hay mayoreo, ambos campos (precio y cantidad mínima) deben estar presentes.
  - Cantidad mínima de mayoreo es un número entero de al menos 2.
  - Marcas existen (configurable: se pueden crear automáticamente).
  - Departamentos existen (configurable: se pueden crear automáticamente).
  - Unidad válida en la columna "Unidad" (PZ, KG, LT, BO, CO). Si está vacía, se usa PZ.
  - Productos por fracción (KG, LT) no pueden tener precio de mayoreo.
  - Cantidad de stock no negativa (si se importa stock). Una cantidad en 0 o vacía deja el stock sin cambios.
  - Nombres de marca y departamento se limpian de espacios al inicio y al final.
- Opciones configurables:
  - Crear marcas automáticamente si no existen.
  - Crear departamentos automáticamente si no existen.
  - Si los departamentos son obligatorios.
  - Si importar stock inicial junto con los productos.
- Límites de seguridad: máximo 10,000 filas, máximo 10MB por archivo.

### 11.2 Importación de Stock desde Excel
- Carga masiva de stock para productos existentes.
- **Flujo en dos pasos:** validación + importación.
- Dos modos:
  - **Ajuste ("A"):** Pone el stock en la cantidad indicada.
  - **Entrada ("E"):** Suma la cantidad indicada al stock existente.
- Validaciones: código existente en el sistema, producto registrado en la tienda seleccionada, código no duplicado en el archivo, cantidades positivas.
- Genera log de bitácora con movimiento tipo "Importación" para cada producto.

### 11.3 Importación de Ventas desde Excel
- Permite registrar ventas en lote desde un archivo Excel (ej. para migrar datos de otro sistema).
- Validación previa de stock disponible.
- Cada fila genera una venta independiente con pago en efectivo.

### 11.4 Validaciones de Archivo
- Tamaño máximo: 10 MB.
- Extensiones permitidas: .xlsx, .xls.
- Tipos MIME válidos verificados.
- Máximo 10,000 filas por archivo.

---

## 12. Auditoría e Integridad de Datos

### 12.1 Auditoría de Catálogo de Productos
- **Códigos de barras duplicados:** Detecta productos con el mismo código dentro del negocio, mostrando código, marca, departamento y nombre de cada duplicado.
- **Problemas de costo:** Lista productos con costo, precio unitario y precio de mayoreo, y el motivo (puede haber varios por producto):
  - Costo en cero o nulo (posible error de carga).
  - Costo mayor o igual al precio unitario.
  - Costo mayor o igual al precio de mayoreo.
- **Precios de mayoreo inconsistentes:** Detecta:
  - Precio de mayoreo >= precio unitario.
  - Precio de mayoreo <= costo.
  - Precio de mayoreo sin cantidad mínima.
  - Cantidad mínima sin precio de mayoreo.
  - Cantidad mínima de mayoreo menor a 2.
- **Productos faltantes en tiendas:** Detecta productos que no están registrados en todas las tiendas del negocio e indica en cuáles faltan. Resuelto con consultas agrupadas (sin N+1).

### 12.2 Auditoría de Ventas (Duplicados)
- Tarea asíncrona (Celery) que recorre todas las ventas en un rango de fechas y detecta ventas duplicadas (mismo total, misma tienda, en menos de 1 segundo).
- Incluye barra de progreso en tiempo real.
- Serializa las ventas duplicadas con detalle para revisión.

### 12.3 Auditoría de Logs (Inconsistencias)
- Tarea asíncrona que recorre todos los logs de inventario en un rango de fechas y detecta:
  - **Logs duplicados:** Dos logs con misma acción, mismo movimiento, mismo producto en menos de 1 segundo.
  - **Logs inconsistentes:** El `previous_stock` de un log no coincide con el `updated_stock` del log anterior (hubo un movimiento no registrado).
  - **Logs con negativos:** Registros donde el stock anterior o posterior es negativo (indicador de problemas históricos).
- Incluye barra de progreso en tiempo real.

### 12.4 Auditoría de Stock (Discrepancias)
- Tarea asíncrona que compara el stock actual de cada producto-tienda con el `updated_stock` del último log registrado.
- Si no coinciden, marca el producto como `requires_stock_verification = True`.
- Permite al equipo corregir discrepancias con conteo físico.

### 12.5 Productos sin Actividad
- Tarea asíncrona que identifica productos que nunca han tenido: ventas, transferencias ni movimientos de inventario.
- Útil para limpiar catálogos de productos que se dieron de alta pero nunca se compraron/vendieron.

### 12.6 Detección en Tiempo Real de Ventas Duplicadas
- Endpoint que detecta ventas duplicadas del día en curso, agrupadas por tienda, para mostrar alertas al propietario.

---

## 13. Bitácora de Movimientos

### 13.1 Registro Automático
- Cada movimiento de inventario genera un registro en la bitácora con:
  - **Producto-tienda afectado.**
  - **Usuario responsable.**
  - **Stock anterior y stock posterior.**
  - **Acción:** Entrada (E), Salida (S), Ajuste (A), NA (N).
  - **Tipo de movimiento:** Manual, Importación, Distribución, Transferencia, Devolución, Venta, Apartado, Conversión.
  - **Tienda relacionada** (en transferencias y distribuciones: tienda origen o destino).
  - **Fecha y hora** automática.

### 13.2 Consulta de Bitácora
- Filtros disponibles: producto específico, fecha, marca, acción, tienda relacionada.
- Para producto específico: filtro por meses (últimos N meses).
- Se muestra: descripción del movimiento, diferencia de stock, usuario, fecha.

### 13.3 Descripción Legible
- El sistema genera automáticamente una descripción legible del movimiento, por ejemplo: "Salida Transferencia Destino: Sucursal Centro (Tienda)", "Entrada Devolución", "Ajuste Manual".

### 13.4 Cálculo de Diferencia
- Cada log calcula la diferencia (updated_stock - previous_stock) y la presenta con signo: "+5" o "-3".

---

## 14. Roles y Permisos

### 14.1 Propietario (Owner)
- Acceso total al negocio.
- Ve todas las sucursales.
- Puede crear tiendas, almacenes, productos, marcas, departamentos.
- Puede gestionar suscripción y pagos.
- Puede cambiar contraseñas de administradores de tienda y vendedores.
- Puede cancelar la suscripción del negocio.
- Recibe notificaciones de todas las tiendas (vía WebSocket).
- Ve reportes consolidados multi-sucursal.
- Puede ejecutar auditorías.
- Puede redeploy de la aplicación (acceso técnico).

### 14.2 Administrador de Tienda (Manager)
- Acceso limitado a su tienda asignada.
- Puede gestionar inventario de su tienda.
- Puede confirmar transferencias recibidas.
- Puede realizar ventas.
- Puede hacer corte de caja de su tienda.
- Puede crear vendedores en su tienda.
- Ve todas las ventas de su tienda (de todos los vendedores).

### 14.3 Vendedor (Seller)
- Acceso más limitado.
- Solo puede realizar ventas.
- Solo ve sus propias ventas.
- Puede solicitar ajustes de stock (no aplicarlos directamente).
- Asociado a una tienda específica.

### 14.4 Gestión de Trabajadores
- CRUD completo de vendedores por tienda.
- Al crear un vendedor, se genera un usuario con contraseña igual al username.
- Cada vendedor está asociado a una tienda y tiene un rol (Administrador o Vendedor).
- La respuesta de creación devuelve el mismo formato que el listado.

### 14.5 Cambio de Contraseña
- Un usuario puede cambiar su propia contraseña (requiere contraseña actual).
- El propietario puede cambiar la contraseña de los administradores y vendedores de sus tiendas (requiere contraseña del propietario).

---

## 15. Impresión de Tickets

### 15.1 Configuración de Impresoras
- Catálogo de impresoras térmicas con: marca, modelo y altura de fuente.
- Asignación de impresora a cada tienda (relación `StorePrinter`).
- Cada tienda puede tener una impresora asignada.
- Información de impresora visible en el login y en reportes.

### 15.2 Soporte Técnico
- El sistema soporta impresoras térmicas vía la librería `python-escpos`.
- Configuración de altura de fuente personalizable por impresora.

---

## 16. Notificaciones en Tiempo Real

### 16.1 Tecnología
- **WebSocket** mediante Django Channels.
- Canal Redis como backend de mensajería.
- Autenticación por token en la conexión WebSocket.

### 16.2 Grupos de Notificación
- **Grupo por tienda** (`store_{id}`): recibe notificaciones de eventos de esa tienda.
- **Grupo por negocio** (`tenant_{id}`): el propietario fuera de una tienda recibe notificaciones de todas las tiendas.
- El propietario dentro de una tienda solo recibe notificaciones de esa tienda.
- Managers y vendedores solo reciben de su tienda.

### 16.3 Eventos Notificados
- **transfer_created:** Se creó un nuevo traspaso hacia la tienda.
- **transfer_confirmed:** Se confirmó un traspaso.
- **distribution_created:** Se creó una nueva distribución.
- **distribution_confirmed:** Se confirmó una distribución.
- **reservation_created:** Se creó un nuevo apartado.
- **duplicate_sale:** Se detectó una posible venta duplicada.
- **stock_request_created:** Se creó una solicitud de ajuste de stock.
- **stock_request_approved:** Se aprobó una solicitud de ajuste de stock.

### 16.4 Tolerancia a Fallos
- Si Redis no está disponible, las notificaciones fallan silenciosamente sin interrumpir la operación principal (venta, transferencia, etc.).

---

## 17. Dashboards y Analítica

### 17.1 Dashboard de Ventas
- Tarea asíncrona que obtiene todas las ventas de las tiendas del negocio filtradas por año y opcionalmente por mes.
- Datos para graficar: total por día, por tienda, tendencias.
- Se entregan datos crudos (fecha, tienda, total, utilidad) para que el frontend los grafique como desee.

### 17.2 Dashboard de Cancelaciones y Devoluciones
- Lista de ventas canceladas y con devolución en un periodo.
- Incluye: total de ventas normales del periodo (para calcular tasa de cancelación).
- Datos por venta: total, fecha, tienda, si fue cancelación o devolución, motivo.

### 17.3 Dashboard de Productos
- **Top 10 productos más vendidos:** con porcentaje sobre el total de unidades vendidas.
- **Top 10 marcas más vendidas:** con porcentaje y número de productos distintos vendidos.
- **10 productos menos vendidos** (que sí tuvieron al menos una venta).
- **Resumen:** total de productos, total de marcas, productos sin ventas en el periodo.
- Filtro por año, mes y tienda.

### 17.4 Dashboard de Verificación de Stock
- Lista de todos los productos marcados con `requires_stock_verification` en todas las tiendas.
- Agrupado por tienda.
- Incluye total de productos-tienda para contexto.

### 17.5 Dashboard de Traspasos Pendientes
- Todos los traspasos no confirmados dirigidos a tiendas del negocio.
- Detalle: producto, marca, cantidad, tienda origen, tienda destino, fecha de creación.

### 17.6 Todas las Tareas Asíncronas con Progreso
- Todos los dashboards pesados se ejecutan como tareas de Celery con:
  - Barra de progreso consultable vía endpoint.
  - Estado: PENDING, PROGRESS (con porcentaje), SUCCESS (con resultado), FAILURE (con error).
  - Endpoint genérico para consultar el resultado de cualquier tarea por su ID.

---

## 18. Facturación y Suscripciones

### 18.1 Planes
- Definidos por: nombre, precio, número de tiendas permitidas, tipo de facturación (Suscripción automática o Manual).
- Planes públicos visibles sin autenticación (para landing page).
- Cada plan puede estar vinculado a un plan en Mercado Pago (preapproval_plan).

### 18.2 Pagos Manuales
- Registro de pagos con: meses pagados, total calculado automáticamente (precio del plan × meses).
- Cálculo automático del periodo de vigencia: inicio = día siguiente al último pago (o fecha de creación del tenant), fin = inicio + meses - 1 día.
- Se puede generar una preferencia de pago en Mercado Pago para que el cliente pague online.
- Detección automática de meses adeudados.

### 18.3 Suscripciones Recurrentes (Mercado Pago)
- Creación de suscripciones recurrentes vía Preapproval de Mercado Pago.
- El cobro se realiza automáticamente cada mes.
- Al crear una suscripción nueva, se cancelan las anteriores del mismo negocio.
- Estados de suscripción alineados a Mercado Pago: pendiente, autorizada, pausada, cancelada.
- Estado del negocio derivado: **activo**, **cancelado** (lo canceló el propietario) o **expirado** (Mercado Pago pausó o canceló la suscripción por fallo de cobro).
- Webhook para recibir notificaciones de Mercado Pago:
  - **Pagos aprobados:** Se registra automáticamente un Payment con 1 mes de vigencia y se envía recibo al cliente.
  - **Pagos rechazados:** Se avisa al cliente (pago rechazado o tarjeta vencida, con enlace para actualizarla) y a soporte.
  - **Cambios de estado en suscripción:** Se guarda el estado de Mercado Pago. Una cancelación de Mercado Pago no se trata como cancelación del negocio, porque también ocurre por tarjeta vencida.
- Detección de duplicados en pagos (por external_reference).

### 18.4 Cambio de Tarjeta e Historial
- El propietario puede actualizar la tarjeta de su suscripción sin cancelarla (cambio preventivo), incluso con la cuenta vencida.
- Historial de tarjetas por suscripción: marca, últimos 4 dígitos y vencimiento (MM/AA).
- Solo se guardan datos no sensibles de la tarjeta (sin número completo ni CVV).
- La consulta del plan actual muestra el estado de la suscripción y la tarjeta vigente.

### 18.5 Cancelación de Suscripción
- El propietario cancela desde la app: se cancela la suscripción en Mercado Pago y el negocio queda inactivo, en una transacción atómica.
- Corte inmediato: se invalidan las sesiones de todos los usuarios del negocio (propietario, administradores y vendedores).
- El login de un negocio cancelado responde 403 con código `tenant_inactive`. La reactivación se gestiona con soporte.

### 18.6 Control de Acceso por Vigencia
- Acceso completo hasta el fin de la vigencia pagada más **7 días de gracia** (hora local de México).
- Pasada la gracia:
  - El propietario entra en "modo pago" y solo puede usar los endpoints de pago y suscripción.
  - Administradores y vendedores quedan bloqueados (403, código `subscription_expired`).
- Planes con facturación manual no se bloquean.
- Negocio nuevo sin pago registrado: acceso durante 24 horas mientras se confirma el primer cobro.

### 18.7 Registro Público de Nuevos Negocios
- Endpoint público (protegido por API Key) que permite:
  - Crear un negocio nuevo (Tenant).
  - Crear su usuario propietario.
  - Procesar el primer pago de suscripción en Mercado Pago.
  - Todo en una sola transacción atómica.
- Validaciones: nombre corto único, email no duplicado, plan válido.

### 18.8 Avisos de Vigencia
- El sistema muestra avisos al propietario dependiendo de su situación:
  - **Cuenta sandbox:** Aviso informativo + modal de pago si está por vencer.
  - **Con suscripción activa:** Aviso preventivo de cobro próximo.
  - **Sin suscripción (pago manual):** Avisos de vencimiento (5 días antes, hoy, vencido).
- Variantes de aviso: success, warning, error.

### 18.9 Fechas Clave del Negocio
- Consulta de: fecha de creación del negocio, fecha de activación de suscripción, fecha del primer pago.

### 18.10 Verificación de Disponibilidad de Nombre
- Endpoint público para verificar si un nombre corto (short_name) ya está en uso antes de registrarse.

---

## 19. Infraestructura y Rendimiento

### 19.1 Arquitectura Cloud
- **Hosting:** Render (Web Service + Worker + PostgreSQL + Redis).
- **API:** Django REST Framework servido por Daphne (ASGI), que atiende HTTP y WebSocket en el mismo proceso.
- **Archivos estáticos:** WhiteNoise para servir assets sin CDN adicional.
- **Almacenamiento de imágenes:** AWS S3 con django-storages.
- **Tareas asíncronas:** Celery con Redis como broker.
- **WebSockets:** Django Channels con Redis como canal de mensajería.

### 19.2 Optimizaciones de Base de Datos
- **Índices compuestos** en modelos críticos: StoreProduct, Sale, Transfer, StoreProductLog, Product, Brand, Department.
- **select_related / prefetch_related** en todas las consultas que requieren relaciones.
- **Subqueries y anotaciones** en lugar de consultas N+1 (ej. stock reservado).
- **bulk_create** para inserción masiva de logs.
- **bulk_update** para actualización masiva de stock en ventas.
- **select_for_update** para bloqueo de registros en operaciones concurrentes.
- **Transacciones atómicas** (`@transaction.atomic`) en todas las operaciones que modifican múltiples registros.
- **iterator()** con chunk_size para recorrer grandes cantidades de registros sin consumir memoria.
- **only()** y **values()** para limitar campos traídos de BD cuando no se necesitan todos.
- **CheckConstraint** a nivel BD para stock no negativo (integridad garantizada por el motor de BD).

### 19.3 Procesamiento Asíncrono
- Las operaciones pesadas se delegan a Celery workers:
  - Auditorías de ventas duplicadas.
  - Auditorías de logs inconsistentes.
  - Auditorías de stock.
  - Dashboards de ventas, cancelaciones, productos.
  - Dashboard de verificación de stock.
  - Dashboard de traspasos pendientes.
  - Búsqueda de productos sin actividad.
- Progreso consultable en tiempo real.

### 19.4 Contratos de API
- Especificación OpenAPI 3.0 de los 8 módulos en `specs/`, base para desarrollo guiado por contrato, generación de tipos y documentación interactiva.

### 19.5 Redeploy
- Endpoint para disparar un redeploy del servicio en Render vía API key (para aplicar cambios sin acceder manualmente al dashboard de Render).

### 19.6 Middleware Keep-Alive
- Middleware personalizado para mantener conexiones activas y evitar timeouts en servidores de hosting.

---

## 20. Seguridad

### 20.1 Autenticación
- Token Authentication de DRF: cada usuario tiene un token único.
- El token se envía en cada request vía header `Authorization: Token <token>`.
- Login devuelve el token junto con metadata del usuario (rol, tienda, tenant, si el negocio tiene varias tiendas (`multistore`), etc.).

### 20.2 Multi-Tenancy
- Aislamiento total entre negocios: un usuario solo puede acceder a datos de su propio tenant.
- Header `store-id` identifica la sucursal activa del request.
- Todas las queries filtran por tenant del usuario autenticado.

### 20.3 API Key para Endpoints Públicos
- Los endpoints públicos (registro, verificación de nombre, planes) están protegidos con una API Key estática. No requieren autenticación de usuario pero sí la API Key para evitar abuso.

### 20.4 Validación de Archivos
- Los archivos Excel subidos se validan por: tamaño máximo, extensión permitida, tipo MIME.
- Límite de filas para evitar ataques de denegación de servicio.

### 20.5 Protección contra Concurrencia
- `select_for_update()` en operaciones de stock para evitar condiciones de carrera.
- Transacciones atómicas para garantizar consistencia.
- CheckConstraint a nivel BD como última línea de defensa contra stock negativo.

### 20.6 Control de Acceso por Suscripción
- Permiso global que bloquea el acceso según la vigencia de la suscripción (ver 18.6).
- Al cancelar el negocio se borran los tokens de todos sus usuarios: cualquier sesión abierta responde 401.
- Datos de tarjeta limitados a marca, últimos 4 dígitos y vencimiento.

### 20.7 Generación Segura de Contraseñas
- Las contraseñas se almacenan con hash seguro (Django `make_password`).
- Los tokens de autenticación son valores aleatorios no predecibles.

---

## 21. Conversión de Unidades

### 21.1 Reglas de Conversión
- Se pueden definir reglas de conversión entre productos: "1 unidad del producto A = N unidades del producto B".
- Ejemplo: 1 costal de maíz = 10 kg de maíz.
- Factor de conversión configurable por par de productos.

### 21.2 Aplicación de Conversión
- Al aplicar una conversión en una tienda:
  - Se descuenta 1 unidad del producto origen.
  - Se suman N unidades al producto destino.
  - Se generan logs de salida (origen) y entrada (destino) con movimiento tipo "Conversión".
  - Validación de stock suficiente en el producto origen.
- Operación atómica con bloqueo de registros.

---

## 22. Correo Electrónico

### 22.1 Servicio de Email
- Arquitectura con patrón Strategy: backend intercambiable (actualmente SMTP).
- Templates HTML por tipo de mensaje.

### 22.2 Correos al Cliente
- Bienvenida con credenciales de acceso y botón para iniciar sesión, al crear la suscripción.
- Recibo de cada cobro aprobado.
- Aviso de pago rechazado o tarjeta vencida, con enlace para actualizar la tarjeta.

### 22.3 Avisos Internos a Soporte
- Nuevo negocio registrado.
- Primer pago recibido.
- Pago rechazado.
- Negocio sin pago tras 24 horas (tarea lista, programación pendiente de activar).

---

## 23. Tabla Resumen para Benchmark

| # | Categoría | Feature | Detalle |
|---|---|---|---|
| 1 | Multi-Sucursal | Tiendas + Almacenes | Dos tipos de ubicación con roles diferentes |
| 2 | Multi-Sucursal | Catálogo compartido | Producto se crea en todas las tiendas automáticamente |
| 3 | Multi-Sucursal | Límite por plan | Número de tiendas según plan contratado |
| 4 | Multi-Sucursal | Vista consolidada | Owner ve todas las tiendas desde un punto |
| 5 | POS | Pagos mixtos | Efectivo + Tarjeta + Transferencia en una venta |
| 6 | POS | Referencia de pago | Número de autorización/referencia en pagos no-efectivo |
| 7 | POS | Búsqueda por código/nombre/marca | Escáner de código de barras y búsqueda textual |
| 8 | POS | Validación de stock disponible | Stock real - reservado = disponible |
| 9 | POS | Detección de duplicados | Alerta automática en ventas repetidas en <1 segundo |
| 10 | POS | Venta por peso (kg) | Cantidades decimales para productos a granel |
| 11 | POS | Descuento por cliente | Porcentaje de descuento automático por nivel de cliente |
| 12 | POS | Precio de mayoreo | Precio especial al superar cantidad mínima |
| 13 | Inventario | Stock por sucursal | Control independiente por ubicación |
| 14 | Inventario | Stock en otras tiendas | Consultar disponibilidad en otras ubicaciones |
| 15 | Inventario | Solicitud de ajuste | Vendedor propone, admin aprueba |
| 16 | Inventario | Stock negativo imposible | Constraint de BD + validación de app |
| 17 | Inventario | Inversión en inventario | Cálculo de valor total del stock |
| 18 | Inventario | Verificación de stock | Marcado automático de discrepancias |
| 19 | Transferencias | Traspasos individuales | Producto a producto entre tiendas |
| 20 | Transferencias | Distribuciones masivas | Múltiples productos en un envío |
| 21 | Transferencias | Confirmación de recepción | Flujo pendiente → confirmado |
| 22 | Transferencias | Notificación en tiempo real | WebSocket al crear y confirmar |
| 23 | Apartados | Reserva sin descontar stock | Stock reservado pero no descontado |
| 24 | Apartados | Abonos parciales | Pagos parciales hasta liquidar |
| 25 | Apartados | Cancelación con devolución | Cálculo de monto a devolver |
| 26 | Clientes | Niveles de descuento | Porcentajes personalizados por negocio |
| 27 | Clientes | Historial de compras | Total de compras por rango de fechas |
| 28 | Corte de Caja | Individual por tienda | Desglose completo por día/rango |
| 29 | Corte de Caja | Bulk multi-sucursal | Todas las tiendas en una vista |
| 30 | Corte de Caja | Por departamento | Filtro por categoría de producto |
| 31 | Corte de Caja | Flujo de caja | Entradas y salidas independientes de ventas |
| 32 | Devoluciones | Cancelación completa | Reversión total de stock + cancelación |
| 33 | Devoluciones | Devolución parcial | Devolver productos individuales |
| 34 | Catálogo | Imagen por producto | Fotos en AWS S3 |
| 35 | Catálogo | Marcas + Departamentos | Clasificación dual |
| 36 | Catálogo | Historial de precios | Log de cada cambio de precio |
| 37 | Catálogo | Actualización masiva de precios | Cambiar precios de múltiples productos |
| 38 | Catálogo | Unidades de medida | Pieza, Kilogramo, Litro, Bote, Costal |
| 39 | Importación | Productos desde Excel | Carga masiva con validación previa |
| 40 | Importación | Stock desde Excel | Ajuste o entrada masiva |
| 41 | Importación | Ventas desde Excel | Migración de datos históricos |
| 42 | Auditoría | Códigos duplicados | Detección automática |
| 43 | Auditoría | Problemas de costo | Costo en cero o mayor que precio unitario/mayoreo |
| 44 | Auditoría | Mayoreo inconsistente | Validación de reglas de precio |
| 45 | Auditoría | Productos faltantes en tiendas | Catálogo incompleto |
| 46 | Auditoría | Logs duplicados/inconsistentes | Integridad de bitácora |
| 47 | Auditoría | Stock vs último log | Discrepancias de inventario |
| 48 | Auditoría | Productos sin actividad | Limpieza de catálogo |
| 49 | Bitácora | Registro automático completo | Cada movimiento queda documentado |
| 50 | Bitácora | Trazabilidad por movimiento | Tipo, acción, usuario, tienda |
| 51 | Roles | 3 niveles (Owner/Manager/Seller) | Acceso diferenciado |
| 52 | Roles | Creación automática de usuarios | Credenciales generadas al crear tienda |
| 53 | Impresoras | Configuración térmica | Marca, modelo, fuente por tienda |
| 54 | Notificaciones | WebSocket en tiempo real | Push instantáneo de eventos |
| 55 | Notificaciones | Grupos por tienda/tenant | Segmentación de audiencia |
| 56 | Dashboards | Ventas por periodo | Análisis temporal |
| 57 | Dashboards | Cancelaciones y devoluciones | Tasa de cancelación |
| 58 | Dashboards | Top/bottom productos y marcas | Ranking de ventas |
| 59 | Dashboards | Procesamiento asíncrono | No bloquea la interfaz |
| 60 | Facturación | Suscripción recurrente | Cobro automático Mercado Pago |
| 61 | Facturación | Pago manual | Preferencias de pago MP |
| 62 | Facturación | Registro público (self-service) | Alta de negocio sin intervención |
| 63 | Facturación | Avisos de vencimiento | Alertas proactivas |
| 64 | Facturación | Webhook de pagos | Registro automático de cobros |
| 65 | Seguridad | Token Auth | Autenticación stateless |
| 66 | Seguridad | Multi-tenancy aislado | Datos separados por negocio |
| 67 | Seguridad | Protección de concurrencia | select_for_update + constraints |
| 68 | Infraestructura | Cloud nativa (Render) | Escalable sin servidor propio |
| 69 | Infraestructura | Celery workers | Procesamiento paralelo |
| 70 | Infraestructura | Índices optimizados | Performance en queries críticas |
| 71 | Conversión | Reglas de conversión | 1 unidad A = N unidades B |
| 72 | Email | Bienvenida automatizada | Onboarding con credenciales |
| 73 | POS | Bloqueo de doble envío | Ventas y distribuciones duplicadas rechazadas (409) |
| 74 | POS | Utilidad por venta | Ganancia guardada y recalculada automáticamente |
| 75 | Catálogo | Venta por fracción | Kilogramo y litro con cantidades decimales |
| 76 | Facturación | Cambio de tarjeta | Actualización sin cancelar la suscripción |
| 77 | Facturación | Historial de tarjetas | Marca, últimos 4 dígitos y vencimiento |
| 78 | Facturación | Cancelación self-service | Corte inmediato de sesiones del negocio |
| 79 | Facturación | Periodo de gracia | 7 días de acceso completo tras el vencimiento |
| 80 | Email | Recibos y avisos de pago | Cobro exitoso, rechazo y tarjeta vencida |
| 81 | Email | Avisos a soporte | Nuevos negocios, primer pago y rechazos |
| 82 | Infraestructura | Contratos OpenAPI | Especificación de los 8 módulos |

---

## 📝 Notas para el Benchmark

**Fortalezas clave para diferenciación:**
- Multi-sucursal real con inventario independiente por ubicación.
- Apartados con bloqueo de stock sin descuento físico.
- Auditoría automatizada de integridad de datos.
- Notificaciones WebSocket en tiempo real.
- Procesamiento asíncrono para operaciones pesadas con barra de progreso.
- Self-service: el cliente se registra y paga sin intervención humana.
- Constraint de BD para stock negativo (imposible incluso con bugs).

**Áreas a evaluar vs competencia:**
- E-commerce integrado (actualmente solo POS físico).
- App móvil nativa vs web-only.
- Reportes exportables (PDF/Excel).
- Integración fiscal (CFDI/facturación electrónica SAT).
- Programa de lealtad / puntos.
- Gestión de proveedores y órdenes de compra.
- Pronóstico de demanda / reordenamiento automático.
- Multi-moneda / multi-idioma.
- Modo offline para ventas sin internet.
- Integración con marketplaces (MercadoLibre, Amazon).
