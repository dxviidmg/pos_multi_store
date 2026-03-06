"""
Constantes y enums para el proyecto
"""
from django.db import models


class LogAction(models.TextChoices):
    """Acciones de log de inventario"""
    ENTRADA = "E", "Entrada"
    SALIDA = "S", "Salida"
    AJUSTE = "A", "Ajuste"
    NA = "N", "NA"


class LogMovement(models.TextChoices):
    """Tipos de movimiento de inventario"""
    MANUAL = "MA", "Manual"
    IMPORTACION = "IM", "Importación"
    DISTRIBUCION = "DI", "Distribución"
    TRANSFERENCIA = "TR", "Transferencia"
    DEVOLUCION = "DE", "Devolución"
    VENTA = "VE", "Venta"
    APARTADO = "AP", "Apartado"


class PaymentMethod(models.TextChoices):
    """Métodos de pago"""
    EFECTIVO = "EF", "Efectivo"
    TARJETA = "TC", "Tarjeta"
    TRANSFERENCIA = "TR", "Transferencia"


class StoreType(models.TextChoices):
    """Tipos de tienda"""
    ALMACEN = "A", "Almacen"
    TIENDA = "T", "Tienda"


class CashFlowType(models.TextChoices):
    """Tipos de flujo de caja"""
    ENTRADA = "E", "Entrada"
    SALIDA = "S", "Salida"


class WorkerRole(models.TextChoices):
    """Roles de trabajadores"""
    ADMIN = "A", "Administrador"
    VENDEDOR = "V", "Vendedor"
