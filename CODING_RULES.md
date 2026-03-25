# Reglas de Código — SmartVenta

## Idioma
- Código (variables, funciones, clases, campos) en **inglés**
- Comentarios y mensajes de error al usuario en **español**
- Commits en inglés con formato: `tipo(módulo): descripción`
  - Tipos: `feat`, `fix`, `refactor`, `chore`

## Imports (PEP 8)
Orden estricto separado por línea en blanco:
1. Stdlib (`datetime`, `collections`, `json`)
2. Terceros (`pandas`, `numpy`, `rest_framework`, `django`)
3. Django internos (`django.db`, `django.contrib`)
4. Apps del proyecto (`core`, `logs`, `notifications`, `products`, `sales`)
5. Imports relativos (`from .models import ...`, `from .decorators import ...`)

Dentro de cada grupo, ordenar alfabéticamente.

## Modelos
- Heredar de `CreatedAtModel` (definido en `tenants/models`) para tener `created_at` automático
- Usar `Base` (name + ordering) para modelos con campo `name`
- Choices como constantes de clase o en `core/constants.py` usando `models.TextChoices`
- Siempre definir `__str__`
- Agregar `indexes` en `Meta` para campos usados en filtros frecuentes
- Usar `CheckConstraint` a nivel de BD para validaciones críticas (ej: stock negativo)
- ForeignKey siempre con `related_name` explícito cuando se necesite acceso inverso
- `select_for_update()` en operaciones que modifican stock

## Views
- CRUD estándar → `viewsets.ModelViewSet`
- Operaciones custom → `APIView`
- Decorar con `@method_decorator(get_store(), name="dispatch")` las views que necesiten `request.store`
- Operaciones de stock siempre dentro de `transaction.atomic`
- Crear logs (`StoreProductLog`) en cada movimiento de inventario
- Usar `bulk_create` / `bulk_update` cuando se procesan múltiples registros
- Notificar vía `notify_store(store, tenant_id, data)` en eventos relevantes
- Validaciones de negocio en `perform_create` / `perform_update`, no en el serializer

## Serializers
- Campos de solo lectura en `read_only_fields`
- Preferir `source=` sobre `SerializerMethodField` siempre que sea posible:
  - `serializers.CharField(source='brand.name', read_only=True)` en vez de `get_brand_name`
  - `serializers.CharField(source='get_full_name', read_only=True)` para métodos del modelo sin args
  - `serializers.CharField(source='get_store_type_display', read_only=True)` para display de choices
- Usar `SerializerMethodField` solo cuando hay lógica (condicionales, cálculos, contexto)
- Optimizar querysets con `select_related` / `prefetch_related` en el viewset, no en el serializer
- Usar `only()` en listados para limitar campos traídos de BD

## Querysets
- `select_related` para FK y OneToOne
- `prefetch_related` para relaciones inversas y M2M
- `only()` en action `list` para reducir carga
- Annotaciones con `Subquery` / `OuterRef` cuando se necesiten datos de tablas relacionadas
- Filtros complejos con `Q` objects

## Notificaciones WebSocket
- Usar `notify_store(store_instance, tenant_id, data)` — siempre pasar la instancia de Store
- El payload siempre incluye `event`, `message`, `store_id`, `store_name`
- Eventos: `transfer_created`, `transfer_confirmed`, `distribution_created`, `distribution_confirmed`, `stock_request_created`, `stock_request_approved`, `reservation_created`

## Logs de inventario
- Cada movimiento de stock debe crear un `StoreProductLog` con:
  - `store_product`, `user`, `previous_stock`, `updated_stock`
  - `action` (E/S/A/N) y `movement` (MA/IM/DI/TR/DE/VE/AP) de `core/constants.py`
  - `store_related` cuando aplique (transferencias, distribuciones)

## Respuestas de error
- Validaciones de negocio: `raise ValidationError({"error": "mensaje"})` o `Response({"error": "..."}, status=400)`
- Recursos no encontrados: `Response({"status": "..."}, status=404)`

## General
- No dejar prints en código productivo
- No hardcodear IDs ni valores mágicos
- Constantes en `core/constants.py`
- Tareas pesadas (auditorías, reportes) van a Celery tasks
- Header `store-id` siempre es un ID numérico

## Commits
- Formato: `tipo(módulo): descripción en inglés`
- Tipos: `feat`, `fix`, `refactor`, `perf`, `chore`, `docs`
- Al generar un mensaje de commit, actualizar automáticamente `CHANGELOG.md` con la entrada correspondiente en la fecha actual
