"""
Importación de productos desde un reporte de inventario de otro sistema (Eleventa).

El reporte es texto separado por tabuladores (Latin-1) con extensión .xls, o un Excel real.
Columnas: Codigo, Descripcion, Precio Costo, Precio Venta, Precio Mayoreo, Inventario,
Inv. Minimo, Departamento.
"""
import csv
import io
import json
import math
import re
import unicodedata
from decimal import Decimal

import pandas as pd

SUCCESS_STATUS = "Exitoso"
MAX_ROWS = 10000
MAX_CODE_LENGTH = 50
MAX_NAME_LENGTH = 100
MAX_BRAND_LENGTH = 100
NO_DEPARTMENT_LABEL = "- Sin Departamento -"
HEADER_SEARCH_ROWS = 10

REQUIRED_HEADERS = {
    "code": "codigo",
    "name": "descripcion",
    "cost": "precio costo",
    "unit_price": "precio venta",
}
OPTIONAL_HEADERS = {
    "wholesale_price": "precio mayoreo",
    "quantity": "inventario",
    "department": "departamento",
}
HEADER_LABELS = {
    "codigo": "Codigo",
    "descripcion": "Descripcion",
    "precio costo": "Precio Costo",
    "precio venta": "Precio Venta",
}

XLSX_SIGNATURE = b"PK"
XLS_SIGNATURE = b"\xd0\xcf\x11\xe0"
UTF8_BOM = b"\xef\xbb\xbf"
DELIMITERS = ("\t", ",", ";")

NUMERIC_EDIT_FIELDS = ("cost", "unit_price", "wholesale_price")
TEXT_EDIT_FIELDS = ("code",)
EDITABLE_FIELDS = NUMERIC_EDIT_FIELDS + TEXT_EDIT_FIELDS
WHOLESALE_MODE_QUANTITY = "quantity"
WHOLESALE_MODE_IGNORE = "ignore"
WHOLESALE_MODES = (WHOLESALE_MODE_QUANTITY, WHOLESALE_MODE_IGNORE)
MIN_WHOLESALE_QUANTITY = 2


def normalize_header(value):
    """Minúsculas, sin acentos, sin puntos y con espacios colapsados"""
    text = unicodedata.normalize("NFD", str(value if value is not None else ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.replace(".", "")).strip().lower()


def parse_money(value):
    """'$1,234.00' → 1234.0; vacío → None; texto no numérico → NaN"""
    text = re.sub(r"[$,\s]", "", str(value if value is not None else ""))
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return math.nan


def _clean_text(value):
    return str(value if value is not None else "").strip().replace("�", "ñ")


def _decode_text(raw):
    if raw.startswith(UTF8_BOM):
        return raw[len(UTF8_BOM):].decode("utf-8", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _matrix_from_excel(file_obj, engine):
    file_obj.seek(0)
    frame = pd.read_excel(file_obj, header=None, dtype=str, engine=engine).fillna("")
    return frame.values.tolist()


def read_matrix(file_obj):
    """Devuelve el contenido del archivo como lista de filas (listas de celdas)"""
    file_obj.seek(0)
    raw = file_obj.read()
    if raw.startswith(XLSX_SIGNATURE):
        return _matrix_from_excel(file_obj, "openpyxl")
    if raw.startswith(XLS_SIGNATURE):
        return _matrix_from_excel(file_obj, "xlrd")
    return _split_text(_decode_text(raw))


def _split_text(text):
    """Separa texto delimitado; el delimitador (tabulador, coma o punto y coma) se detecta en el encabezado"""
    lines = text.splitlines()
    header = next((line for line in lines if line.strip()), "")
    delimiter = max(DELIMITERS, key=header.count)
    if delimiter == "\t":
        # Se separa a mano: las descripciones pueden traer comillas (12")
        return [line.split(delimiter) for line in lines]
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def _find_header_row(matrix):
    for index, cells in enumerate(matrix[:HEADER_SEARCH_ROWS]):
        headers = [normalize_header(cell) for cell in cells]
        if "codigo" in headers and "descripcion" in headers:
            return index
    return None


def _build_row(cells, index, columns):
    def get(field):
        position = columns.get(field)
        return cells[position] if position is not None and position < len(cells) else ""

    department = _clean_text(get("department"))
    return {
        "excel_row": index + 1,
        "code": _clean_text(get("code")),
        "name": _clean_text(get("name")),
        "cost": parse_money(get("cost")),
        "unit_price": parse_money(get("unit_price")),
        "wholesale_price": parse_money(get("wholesale_price")),
        "quantity": parse_money(get("quantity")),
        "department": None if department in ("", NO_DEPARTMENT_LABEL) else department,
    }


def parse_eleventa_file(file_obj):
    """
    Lee el reporte y devuelve las filas normalizadas.

    Raises:
        ValueError: Si faltan encabezados o columnas, el archivo está vacío o excede MAX_ROWS
    """
    matrix = read_matrix(file_obj)
    header_index = _find_header_row(matrix)
    if header_index is None:
        raise ValueError("No se encontraron los encabezados del reporte")

    headers = [normalize_header(cell) for cell in matrix[header_index]]
    columns = {
        field: headers.index(header)
        for field, header in {**REQUIRED_HEADERS, **OPTIONAL_HEADERS}.items()
        if header in headers
    }
    missing = [
        HEADER_LABELS[header] for field, header in REQUIRED_HEADERS.items() if field not in columns
    ]
    if missing:
        raise ValueError(f"Faltan columnas: {', '.join(missing)}")

    rows = [
        _build_row(cells, index, columns)
        for index, cells in enumerate(matrix)
        if index > header_index and any(str(cell).strip() for cell in cells)
    ]
    if not rows:
        raise ValueError("El archivo está vacío")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"Demasiadas filas. Máximo: {MAX_ROWS}")
    return rows


def _is_positive(value):
    return value is not None and not math.isnan(value) and value > 0


def _row_error(row, first_row_by_code):
    """Primer error de la fila, o None si es válida"""
    if not row["code"]:
        return "Sin código"
    if len(row["code"]) > MAX_CODE_LENGTH:
        return f"Código demasiado largo (máximo {MAX_CODE_LENGTH} caracteres)"
    if not row["name"]:
        return "Sin nombre"
    first_row = first_row_by_code[row["code"]]
    if first_row != row["excel_row"]:
        return f"Código existente en la fila {first_row}"
    if not _is_positive(row["cost"]):
        return "Costo debe ser mayor a 0"
    if not _is_positive(row["unit_price"]):
        return "Precio de venta debe ser mayor a 0"
    if row["cost"] >= row["unit_price"]:
        return "Costo debe ser menor que precio de venta"
    wholesale = row["wholesale_price"]
    if wholesale is not None:
        if math.isnan(wholesale):
            return "Precio mayoreo inválido"
        if wholesale > row["unit_price"]:
            return "Mayoreo mayor al precio de venta"
        if wholesale < row["cost"]:
            return "Mayoreo menor que el costo"
    quantity = row["quantity"]
    if quantity is not None and not quantity >= 0:
        return "Inventario debe ser un número mayor o igual a 0"
    return None


def _load_json(value, label):
    if value in (None, ""):
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} debe ser JSON válido")


def parse_edits(value):
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
        unknown = set(changes) - set(EDITABLE_FIELDS)
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


def _apply_edit(field, value):
    if field in NUMERIC_EDIT_FIELDS:
        return parse_money(value)
    return _clean_text(value)


def apply_edits(rows, edits, removed_rows):
    """Quita las filas descartadas y aplica las correcciones; `excel_row` no cambia"""
    return [
        {**row, **{field: _apply_edit(field, value) for field, value in edits.get(row["excel_row"], {}).items()}}
        for row in rows
        if row["excel_row"] not in removed_rows
    ]


def parse_wholesale_options(mode, min_quantity):
    """
    Valida las opciones de mayoreo (el reporte no trae cantidad mínima).

    Returns:
        (mode, min_quantity): min_quantity es None si el modo es ignorar el mayoreo
    Raises:
        ValueError: Si el modo no es válido o la cantidad mínima no es un entero de al menos 2
    """
    if mode not in WHOLESALE_MODES:
        raise ValueError("Elige qué hacer con el precio mayoreo")
    if mode == WHOLESALE_MODE_IGNORE:
        return mode, None
    try:
        quantity = int(str(min_quantity).strip())
    except (TypeError, ValueError):
        quantity = 0
    if quantity < MIN_WHOLESALE_QUANTITY:
        raise ValueError(f"La cantidad mínima de mayoreo debe ser un entero de al menos {MIN_WHOLESALE_QUANTITY}")
    return mode, quantity


def apply_wholesale_options(rows, min_quantity):
    """
    Con cantidad mínima: los precios mayoreo mayores a 0 la reciben y los demás quedan sin mayoreo.
    Sin cantidad mínima (None): el precio mayoreo se ignora y solo queda el de menudeo.
    """
    result = []
    for row in rows:
        wholesale = row["wholesale_price"]
        has_wholesale = (
            min_quantity is not None
            and wholesale is not None
            and (math.isnan(wholesale) or wholesale > 0)
        )
        result.append(
            {
                **row,
                "wholesale_price": wholesale if has_wholesale else None,
                "min_wholesale_quantity": min_quantity if has_wholesale else None,
            }
        )
    return result


def validate_eleventa_rows(rows):
    """Agrega `status` a cada fila: 'Exitoso' o el motivo del error"""
    first_row_by_code = {}
    for row in rows:
        first_row_by_code.setdefault(row["code"], row["excel_row"])
    return [
        {**row, "status": _row_error(row, first_row_by_code) or SUCCESS_STATUS} for row in rows
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


def parse_excluded_codes(value):
    """Lee `excluded_codes` (texto JSON con una lista de códigos) en un set"""
    if value in (None, ""):
        return set()
    try:
        codes = json.loads(value)
    except (TypeError, ValueError):
        raise ValueError("excluded_codes debe ser una lista JSON de códigos")
    if not isinstance(codes, list):
        raise ValueError("excluded_codes debe ser una lista JSON de códigos")
    return {str(code).strip() for code in codes}


def to_decimal(value):
    return Decimal(str(value))
