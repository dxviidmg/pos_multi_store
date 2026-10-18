"""
Utilidades compartidas por las importaciones con correcciones en la tabla de errores.

El usuario puede corregir campos (`edits`), quitar filas (`removed_rows`) y omitir productos
(`excluded_codes`) sin volver a cargar el archivo; el backend los aplica sobre lo que leyó del archivo.
"""
import json
import math
import re
from decimal import Decimal

SUCCESS_STATUS = "Exitoso"


def clean_text(value):
    """Texto sin espacios en los extremos; un `�` (caracter de reemplazo) se lee como `ñ`"""
    return str(value if value is not None else "").strip().replace("�", "ñ")


def parse_money(value):
    """'$1,234.00' → 1234.0; vacío → None; texto no numérico → NaN"""
    text = re.sub(r"[$,\s]", "", str(value if value is not None else ""))
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return math.nan


def to_decimal(value):
    return Decimal(str(value))


def _load_json(value, label):
    if value in (None, ""):
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} debe ser JSON válido")


def parse_edits(value, editable_fields):
    """
    Lee `edits`: texto JSON `{"<excel_row>": {"<campo>": valor}}` con las correcciones del usuario.

    Raises:
        ValueError: Si no es JSON, no tiene esa forma o trae un campo que no se puede editar
    """
    data = _load_json(value, "edits")
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("edits debe ser un objeto JSON")
    edits = {}
    for excel_row, changes in data.items():
        if not isinstance(changes, dict):
            raise ValueError("edits debe ser un objeto JSON")
        unknown = set(changes) - set(editable_fields)
        if unknown:
            raise ValueError(f"Campo no editable: {', '.join(sorted(unknown))}")
        try:
            edits[int(excel_row)] = changes
        except ValueError:
            raise ValueError("edits debe usar números de fila")
    return edits


def parse_removed_rows(value):
    """Lee `removed_rows`: texto JSON con la lista de números de fila que el usuario quitó"""
    data = _load_json(value, "removed_rows")
    if data is None:
        return set()
    try:
        return {int(row) for row in data}
    except (TypeError, ValueError):
        raise ValueError("removed_rows debe ser una lista JSON de números de fila")


def parse_excluded_codes(value):
    """Lee `excluded_codes` (texto JSON con una lista de códigos) en un set"""
    data = _load_json(value, "excluded_codes")
    if data is None:
        return set()
    if not isinstance(data, list):
        raise ValueError("excluded_codes debe ser una lista JSON de códigos")
    return {str(code).strip() for code in data}


def apply_edits(rows, edits, removed_rows, converters):
    """
    Quita las filas descartadas y aplica las correcciones; `excel_row` no cambia.
    `converters` asigna a cada campo editable la función que convierte el valor recibido.
    """
    return [
        {
            **row,
            **{field: converters[field](value) for field, value in edits.get(row["excel_row"], {}).items()},
        }
        for row in rows
        if row["excel_row"] not in removed_rows
    ]


def serialize_rows(rows):
    """Filas listas para JSON (NaN no es JSON válido)"""
    return [
        {
            key: (None if isinstance(value, float) and math.isnan(value) else value)
            for key, value in row.items()
        }
        for row in rows
    ]
