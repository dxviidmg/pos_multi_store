# 🛒 SmartVenta

**Sistema de Punto de Venta Multi-Sucursal en la Nube**

SmartVenta es un POS diseñado para negocios minoristas con múltiples sucursales y almacenes. Gestiona de forma centralizada inventario, ventas, clientes y personal desde una sola plataforma.

---

## 📋 Tabla de Contenidos

- [Funcionalidades](#-funcionalidades)
- [Stack Tecnológico](#-stack-tecnológico)
- [Arquitectura](#-arquitectura)
- [Modelos de Datos](#-modelos-de-datos)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación](#-instalación)
- [Variables de Entorno](#-variables-de-entorno)
- [Uso](#-uso)
- [Despliegue](#-despliegue)
- [Licencia](#-licencia)

---

## ✨ Funcionalidades

| Módulo | Descripción |
|---|---|
| **Multi-sucursal** | Administra tiendas y almacenes de forma independiente o centralizada, cada una con su inventario, vendedores y caja |
| **Punto de venta** | Registro de ventas con pagos mixtos (efectivo, tarjeta, transferencia) y referencias de transacción. Bloqueo de ventas y distribuciones duplicadas por doble envío (HTTP 409) |
| **Venta a granel** | Unidades Pieza, Kilogramo, Litro, Bote y Costal. Stock y cantidades con hasta 3 decimales para productos por peso o volumen |
| **Inventario en tiempo real** | Control de stock por sucursal con trazabilidad: entradas, salidas, ajustes, importaciones masivas y validación de stock negativo |
| **Transferencias** | Movimiento de mercancía entre sucursales/almacenes con seguimiento de estado |
| **Apartados** | Reservación de productos para clientes con bloqueo automático de stock |
| **Clientes y descuentos** | Registro de clientes con descuentos por porcentaje y precios de mayoreo por producto |
| **Corte de caja** | Resumen diario o por rango: ventas por método de pago, utilidad, flujo de caja, cancelaciones. Vista bulk multi-sucursal con datos del administrador y validación de catálogo completo |
| **Utilidad por venta** | Cada venta guarda su utilidad (precio − costo × cantidad), recalculada al modificar o devolver productos. Alimenta el corte de caja y el dashboard de ventas |
| **Roles y permisos** | Tres niveles: Propietario, Administrador de tienda y Vendedor |
| **Importación masiva** | Carga de productos (con unidad de medida y stock inicial) e inventario desde Excel, con plantillas y validación fila por fila de precios, costos y mayoreo |
| **Impresión de tickets** | Configuración de impresoras térmicas por sucursal |
| **Auditoría** | Detección automática de ventas duplicadas, logs inconsistentes, discrepancias de stock, códigos de barras repetidos, problemas de costo (en cero, mayor o igual al precio unitario o al de mayoreo), precios de mayoreo inconsistentes, productos faltantes en tiendas y productos sin actividad |
| **Bitácora** | Registro de cada movimiento de inventario: usuario, fecha, tipo, stock anterior/posterior |
| **Catálogo con imágenes** | Fotos de productos en AWS S3, organizados por marca y departamento |
| **Devoluciones** | Devoluciones parciales y cancelación de ventas con reversión automática de stock |
| **Notificaciones en tiempo real** | Avisos vía WebSocket de traspasos, distribuciones, apartados, solicitudes de ajuste de stock y posibles ventas duplicadas |
| **Suscripción y facturación** | Cobro recurrente con Mercado Pago, cambio de tarjeta, historial de tarjetas, cancelación por el propietario y 7 días de gracia tras el vencimiento |
| **Correos automáticos** | Bienvenida con credenciales, recibo de cada cobro y aviso de pago rechazado o tarjeta vencida |

---

## 🛠 Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend / API | Python 3.10 · Django 5.1 · Django REST Framework 3.15 |
| Base de datos | PostgreSQL (producción) · SQLite (desarrollo) |
| Tareas asíncronas | Celery 5.5 · Redis |
| Tareas programadas | django-celery-beat |
| Almacenamiento | AWS S3 (django-storages + boto3) |
| Servidor web | Daphne (ASGI) |
| Tiempo real | Django Channels · channels-redis (WebSocket) |
| Pagos | Mercado Pago (suscripciones y webhooks) |
| Correo | SMTP (Gmail) |
| Archivos estáticos | WhiteNoise |
| Hosting | Render |
| Autenticación | Token Authentication (DRF) |
| Procesamiento de datos | Pandas · NumPy · OpenPyXL |
| Impresión | python-escpos |
| Códigos de barras | python-barcode · qrcode |

---

## 🏗 Arquitectura

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│  Cliente     │────▶│  Daphne      │────▶│ PostgreSQL │
│  (Frontend)  │◀ ─ ─│  Django API  │     └────────────┘
└─────────────┘  WS └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌────────────┐
                    │    Celery    │────▶│   Redis    │
                    │   Workers    │     └────────────┘
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   AWS S3     │
                    │  (imágenes)  │
                    └──────────────┘
```

- API REST stateless con autenticación por token
- WebSocket en `ws/notifications/` (Django Channels sobre Redis) para notificaciones en tiempo real
- Multi-tenant: cada negocio tiene su espacio aislado (Tenant)
- Header `store-id` identifica la sucursal activa en cada request
- 8 módulos Django: `tenants` · `accounts` · `products` · `clients` · `sales` · `logs` · `printers` · `audit`
- Paquetes de soporte: `notifications` (consumers WebSocket) · `core` (constantes y servicio de correo)
- Contratos OpenAPI 3.0 de cada módulo en [specs/](specs/)
- Acceso controlado por vigencia de suscripción (`TenantHasAccess`): propietario vencido solo accede a endpoints de pago
- Tareas pesadas (auditorías, reportes) delegadas a Celery workers
- Índices optimizados en modelos críticos
- `CheckConstraint` a nivel de BD para prevenir stock negativo

---

## 📊 Modelos de Datos

```
Tenant (negocio)
├── Plan · Payment · Subscription → SubscriptionPayment
├── Store (sucursal/almacén)
│   ├── StoreProduct (stock por sucursal) → StockUpdateRequest
│   ├── StoreWorker (vendedores)
│   ├── Sale (con utilidad) → ProductSale + Payment
│   ├── CashFlow (entradas/salidas de caja)
│   └── StorePrinter
├── Brand / Department (clasificación)
├── Product (catálogo) → ProductConversion · ProductPriceLog
├── Client → Discount
├── Transfer / Distribution (movimientos entre sucursales)
└── StoreProductLog (bitácora de inventario)
```

---

## 📌 Requisitos Previos

- Python 3.10+
- PostgreSQL (producción) o SQLite (desarrollo)
- Redis (para Celery)
- Cuenta AWS con bucket S3 configurado

---

## 🚀 Instalación

```bash
# Clonar el repositorio
git clone <url-del-repo>
cd pos_multi_store

# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Iniciar servidor de desarrollo
python manage.py runserver
```

Para tareas asíncronas, en otra terminal:

```bash
celery -A pos_multi_store worker -l info
```

---

## 🔐 Variables de Entorno

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | URL de conexión a PostgreSQL |
| `REDIS_URL` | URL de conexión a Redis |
| `AWS_ACCESS_KEY_ID` | Clave de acceso AWS |
| `AWS_SECRET_ACCESS_KEY` | Clave secreta AWS |
| `AWS_STORAGE_BUCKET_NAME` | Nombre del bucket S3 |
| `AWS_S3_REGION_NAME` | Región del bucket S3 |
| `RENDER_API_KEY` | API key de Render (para redeploy) |
| `RENDER_SERVICE_ID` | ID del servicio en Render |
| `MERCADO_PAGO_ACCESS_TOKEN` | Token de acceso de Mercado Pago |
| `MERCADO_PAGO_BACK_URL` | URL de retorno tras el pago; también se usa como URL del frontend en correos |
| `PUBLIC_API_KEY` | API key de los endpoints públicos (registro, planes, verificación de nombre) |
| `EMAIL_HOST_USER` | Cuenta SMTP para envío de correos |
| `EMAIL_HOST_PASSWORD` | Contraseña de la cuenta SMTP |
| `SUPPORT_EMAIL` | Correo que recibe avisos internos (nuevo negocio, primer pago, pago rechazado) |

---

## 💻 Uso

La API expone los siguientes grupos de endpoints bajo `/api/`:

| Prefijo | Módulo | Descripción |
|---|---|---|
| `/api/` | accounts | Autenticación y gestión de usuarios |
| `/api/` | products | Productos, tiendas, marcas, departamentos, stock, transferencias, flujo de caja |
| `/api/` | sales | Ventas, corte de caja, importación de ventas |
| `/api/` | clients | Clientes y descuentos |
| `/api/` | tenants | Configuración del negocio, planes, suscripción, cancelación, cambio de tarjeta y webhook de Mercado Pago |
| `/api/` | logs | Bitácora de movimientos de inventario |
| `/api/` | printers | Configuración de impresoras |
| `/api/` | audit | Auditorías asíncronas y consulta de resultados |

Autenticación requerida en todos los endpoints vía header:
```
Authorization: Token <tu-token>
```

Identificación de sucursal vía header:
```
store-id: <id-de-la-tienda>
```

Notificaciones en tiempo real vía WebSocket en `ws/notifications/`.

La especificación completa de cada endpoint está en [specs/](specs/) (OpenAPI 3.0).

---

## 🌐 Despliegue

El proyecto está configurado para desplegarse en **Render** con la siguiente infraestructura:

| Servicio | Tipo | Descripción |
|---|---|---|
| `pos-web` | Web Service | API Django con Daphne (HTTP + WebSocket) |
| `pos-worker` | Worker | Celery worker para tareas asíncronas |
| `pos-db` | Database | PostgreSQL |
| `pos-redis` | Redis | Broker de mensajes para Celery |

El archivo `render.yaml` contiene la configuración completa de infraestructura como código. `entrypoint.sh` aplica migraciones, inicia un worker de Celery en segundo plano y levanta Daphne.

---

## 📄 Licencia

Proyecto privado. Todos los derechos reservados.
