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
- [Modelo de Negocio](#-modelo-de-negocio)
- [Licencia](#-licencia)

---

## ✨ Funcionalidades

| Módulo | Descripción |
|---|---|
| **Multi-sucursal** | Administra tiendas y almacenes de forma independiente o centralizada, cada una con su inventario, vendedores y caja |
| **Punto de venta** | Registro de ventas con pagos mixtos (efectivo, tarjeta, transferencia) y referencias de transacción |
| **Inventario en tiempo real** | Control de stock por sucursal con trazabilidad: entradas, salidas, ajustes, importaciones masivas y validación de stock negativo |
| **Transferencias** | Movimiento de mercancía entre sucursales/almacenes con seguimiento de estado |
| **Apartados** | Reservación de productos para clientes con bloqueo automático de stock |
| **Clientes y descuentos** | Registro de clientes con descuentos por porcentaje y precios de mayoreo por producto |
| **Corte de caja** | Resumen diario o por rango: ventas por método de pago, utilidad, flujo de caja y cancelaciones |
| **Roles y permisos** | Tres niveles: Propietario, Administrador de tienda y Vendedor |
| **Importación masiva** | Carga de productos e inventario desde Excel con plantillas y validación automática |
| **Impresión de tickets** | Configuración de impresoras térmicas por sucursal |
| **Auditoría** | Detección automática de ventas duplicadas, logs inconsistentes y discrepancias de stock (async) |
| **Bitácora** | Registro de cada movimiento de inventario: usuario, fecha, tipo, stock anterior/posterior |
| **Catálogo con imágenes** | Fotos de productos en AWS S3, organizados por marca y departamento |
| **Devoluciones** | Devoluciones parciales y cancelación de ventas con reversión automática de stock |

---

## 🛠 Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend / API | Python 3.10 · Django 5.1 · Django REST Framework 3.15 |
| Base de datos | PostgreSQL (producción) · SQLite (desarrollo) |
| Tareas asíncronas | Celery 5.5 · Redis |
| Tareas programadas | django-celery-beat |
| Almacenamiento | AWS S3 (django-storages + boto3) |
| Servidor web | Gunicorn |
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
│  Cliente     │────▶│  Gunicorn    │────▶│ PostgreSQL │
│  (Frontend)  │     │  Django API  │     └────────────┘
└─────────────┘     └──────┬───────┘
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
- Multi-tenant: cada negocio tiene su espacio aislado (Tenant)
- Header `store-id` identifica la sucursal activa en cada request
- 8 módulos Django: `tenants` · `accounts` · `products` · `clients` · `sales` · `logs` · `printers` · `audit`
- Tareas pesadas (auditorías, reportes) delegadas a Celery workers
- Índices optimizados en modelos críticos
- `CheckConstraint` a nivel de BD para prevenir stock negativo

---

## 📊 Modelos de Datos

```
Tenant (negocio)
├── Store (sucursal/almacén)
│   ├── StoreProduct (stock por sucursal)
│   ├── StoreWorker (vendedores)
│   ├── Sale → ProductSale + Payment
│   ├── CashFlow (entradas/salidas de caja)
│   └── StorePrinter
├── Brand / Department (clasificación)
├── Product (catálogo)
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

---

## 💻 Uso

La API expone los siguientes grupos de endpoints bajo `/api/`:

| Prefijo | Módulo | Descripción |
|---|---|---|
| `/api/` | accounts | Autenticación y gestión de usuarios |
| `/api/` | products | Productos, tiendas, marcas, departamentos, stock, transferencias, flujo de caja |
| `/api/` | sales | Ventas, corte de caja, importación de ventas |
| `/api/` | clients | Clientes y descuentos |
| `/api/` | tenants | Configuración del negocio y pagos de suscripción |
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

---

## 🌐 Despliegue

El proyecto está configurado para desplegarse en **Render** con la siguiente infraestructura:

| Servicio | Tipo | Descripción |
|---|---|---|
| `pos-web` | Web Service | API Django con Gunicorn (4 workers, 2 threads) |
| `pos-worker` | Worker | Celery worker para tareas asíncronas |
| `pos-db` | Database | PostgreSQL |
| `pos-redis` | Redis | Broker de mensajes para Celery |

El archivo `render.yaml` contiene la configuración completa de infraestructura como código.

---

## 💰 Modelo de Negocio

Suscripción mensual por sucursal: **$500 MXN/mes por tienda**, con facturación y control de vigencia integrados en el sistema.

---

## 📄 Licencia

Proyecto privado. Todos los derechos reservados.
