"""
Importación de productos desde la plantilla (modo Tradicional).

Lectura de filas, correcciones del usuario y validación pura (sin ORM): la vista consulta los códigos,
marcas y departamentos existentes y los pasa en `lookups`.
"""
import math

import pandas as pd

from .import_corrections import SUCCESS_STATUS, apply_edits, clean_text, parse_edits, parse_money
from .import_utils import parse_unit, is_fraction_unit, rename_product_columns, validate_excel_columns
from .utils import is_non_negative_number

MAX_ROWS = 10000
MAX_NAME_LENGTH = 100
MIN_WHOLESALE_QUANTITY = 2
TRUE_VALUES = {"true", "1", "si", "sí", "s"}

EDITABLE_FIELDS = (
    "code",
    "brand",
    "department",
    "name",
    "cost",
    "unit_price",
    "wholesale_price",
    "min_wholesale_quantity",
    "wholesale_price_on_client_discount",
    "unit",
    "quantity",
)


def normalize_text(value):
    """Texto sin espacios; un número entero leído como decimal (123.0) vuelve a ser 123"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return clean_text(value)


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value if value is not None else "").strip().lower() in TRUE_VALUES


def _parse_department(value):
    return normalize_text(value) or None


def _parse_unit(value):
    return normalize_text(value).upper() or None


EDIT_CONVERTERS = {
    "code": normalize_text,
    "brand": normalize_text,
    "department": _parse_department,
    "name": normalize_text,
    "cost": parse_money,
    "unit_price": parse_money,
    "wholesale_price": parse_money,
    "min_wholesale_quantity": parse_money,
    "wholesale_price_on_client_discount": _parse_bool,
    "unit": _parse_unit,
    "quantity": parse_money,
}


def read_template_rows(file_obj, import_stock):
    """
    Lee la plantilla en filas normalizadas (`excel_row` es el número de fila del archivo).

    Raises:
        ValueError: Si el formato es incorrecto, está vacío o excede MAX_ROWS
    """
    df = pd.read_excel(file_obj, nrows=MAX_ROWS + 1)
    df = df.astype(object).where(pd.notna(df), None)
    if len(df) > MAX_ROWS:
        raise ValueError(f"Demasiadas filas. Máximo: {MAX_ROWS}")
    validate_excel_columns(df, import_stock)
    df = rename_product_columns(df)
    if df.empty:
        raise ValueError("El excel esta vacio")

    return [
        {
            "excel_row": index + 2,
            "code": normalize_text(record["code"]),
            "brand": normalize_text(record["brand"]),
            "department": _parse_department(record["department"]),
            "name": normalize_text(record["name"]),
            "cost": parse_money(record["cost"]),
            "unit_price": parse_money(record["unit_price"]),
            "wholesale_price": parse_money(record["wholesale_price"]),
            "min_wholesale_quantity": parse_money(record["min_wholesale_quantity"]),
            "wholesale_price_on_client_discount": bool(record["wholesale_price_on_client_discount"]),
            "unit": _parse_unit(record["unit"]),
            "quantity": parse_money(record.get("quantity")),
        }
        for index, record in enumerate(df.to_dict(orient="records"))
    ]


def parse_template_edits(value):
    """Lee `edits` de la importación Tradicional (campos de EDITABLE_FIELDS)"""
    return parse_edits(value, EDITABLE_FIELDS)


def apply_template_edits(rows, edits, removed_rows):
    """Quita las filas descartadas y aplica las correcciones del usuario"""
    return apply_edits(rows, edits, removed_rows, EDIT_CONVERTERS)


def _price_status(row):
    """Estado por precios y mayoreo (la última regla que falla gana, como siempre); None si está bien"""
    wholesale, min_quantity = row["wholesale_price"], row["min_wholesale_quantity"]
    if (wholesale is None) ^ (min_quantity is None):
        return "Si existe mayoreo debe ingresar el precio mayoreo y la cantidad mínima"

    prices = [row["cost"], row["unit_price"]]
    if wholesale is not None:
        prices.append(wholesale)
    if prices[0] is None or prices[1] is None:
        return "Costo y precio(s) deben ser mayores a 0"
    if any(math.isnan(price) for price in prices):
        return "Precios o costos inválidos"

    status = None
    if not all(price > 0 for price in prices):
        status = "Costo y precio(s) deben ser mayores a 0"
    if len(prices) == 3 and prices[2] > prices[1]:
        status = "Precio mayoreo es mas grande que precio unitario"
    if len(prices) == 3 and prices[0] > prices[2]:
        status = "Precio mayoreo es mas chico que costo"
    if prices[0] >= prices[1]:
        status = "Costo debe ser menor que precio unitario"
    if min_quantity is not None:
        try:
            if int(min_quantity) < MIN_WHOLESALE_QUANTITY:
                status = "Cantidad minima mayoreo debe ser entero minimo 2"
        except (ValueError, OverflowError):
            status = "Cantidad minima mayoreo debe ser un numero entero"
    return status


def _row_status(row, first_row_by_code, lookups, options):
    if not row["code"]:
        return "Sin código"
    if not row["brand"]:
        return "Sin marca"
    if row["code"] in lookups["existing_codes"]:
        return "Código existente en el sistema"
    first_row = first_row_by_code[row["code"]]
    if first_row != row["excel_row"]:
        return f"Código existente en la fila {first_row}"

    status = _price_status(row)
    if options["create_brands"] == "N" and row["brand"] not in lookups["brands"]:
        status = "Marca inexistente"
    if (
        options["create_departments"] == "N"
        and options["departments_mandatory"] == "Y"
        and row["department"] not in lookups["departments"]
    ):
        status = "Departamento inexistente"
    if options["import_stock"] == "Y" and not is_non_negative_number(row["quantity"]):
        status = "Inventario debe ser un número positivo"

    unit = None
    try:
        unit = parse_unit(row["unit"])
    except ValueError as error:
        status = str(error)
    if is_fraction_unit(unit) and row["wholesale_price"] is not None:
        status = "Productos a granel no pueden tener precio de mayoreo"
    return status


def validate_product_rows(rows, lookups, options):
    """
    Agrega `status` a cada fila: 'Exitoso' o el motivo del error.

    Args:
        lookups: `existing_codes`, `brands` y `departments` (conjuntos de nombres del tenant)
        options: `create_brands`, `create_departments`, `departments_mandatory` e `import_stock` ('Y'/'N')
    """
    first_row_by_code = {}
    for row in rows:
        if row["code"] and row["brand"] and row["code"] not in lookups["existing_codes"]:
            first_row_by_code.setdefault(row["code"], row["excel_row"])
    return [
        {**row, "status": _row_status(row, first_row_by_code, lookups, options) or SUCCESS_STATUS}
        for row in rows
    ]
