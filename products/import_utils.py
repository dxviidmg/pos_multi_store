"""
Utilidades compartidas para importación de productos desde Excel
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from rest_framework.response import Response
from rest_framework import status
from django.core.files.uploadedfile import UploadedFile


def validate_excel_columns(df: pd.DataFrame, import_stock: str) -> None:
    """Valida que el Excel tenga las columnas esperadas
    
    Args:
        df: DataFrame de pandas con los datos del Excel
        import_stock: "Y" si se importa stock, "N" si no
        
    Raises:
        ValueError: Si faltan columnas requeridas
    """
    expected_columns = [
        "Código",
        "Marca",
        "Departamento",
        "Nombre",
        "Costo",
        "Precio unitario",
        "Precio mayoreo",
        "Cantidad minima mayoreo",
        "Precio Mayoreo en descuento de clientes",
    ]

    if import_stock == "Y":
        expected_columns += ["Cantidad"]

    from products.utils import is_list_in_another
    if not is_list_in_another(expected_columns, list(df.columns)):
        raise ValueError("Formato de excel incorrecto")


def rename_product_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas del Excel a nombres de modelo
    
    Args:
        df: DataFrame con columnas en español
        
    Returns:
        DataFrame con columnas renombradas
    """
    return df.rename(
        columns={
            "Código": "code",
            "Marca": "brand",
            "Departamento": "department",
            "Nombre": "name",
            "Costo": "cost",
            "Precio unitario": "unit_price",
            "Precio mayoreo": "wholesale_price",
            "Cantidad minima mayoreo": "min_wholesale_quantity",
            "Precio Mayoreo en descuento de clientes": "wholesale_price_on_client_discount",
            "Cantidad": "quantity",
            "Unidad": "unit",
        }
    )


def validate_store_product_columns(df: pd.DataFrame) -> None:
    """Valida columnas para importación de inventario
    
    Args:
        df: DataFrame de pandas
        
    Raises:
        ValueError: Si las columnas no coinciden
    """
    expected_columns = ["Código", "Cantidad", "Descripción"]
    if list(df.columns) != expected_columns:
        raise ValueError("Formato de excel incorrecto")


def rename_store_product_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas de inventario
    
    Args:
        df: DataFrame con columnas en español
        
    Returns:
        DataFrame con columnas renombradas
    """
    return df.rename(
        columns={
            "Código": "code",
            "Cantidad": "quantity",
            "Descripción": "description",
        }
    )


def validate_quantities(df: pd.DataFrame) -> None:
    """Valida que todas las cantidades sean números positivos
    
    Args:
        df: DataFrame con columna 'quantity'
        
    Raises:
        ValueError: Si hay valores no numéricos o negativos
    """
    def is_positive_number(x):
        try:
            return float(x) > 0
        except (TypeError, ValueError):
            return False

    all_valid = df["quantity"].apply(is_positive_number).all()
    if not all_valid:
        raise ValueError("No todos los datos en la columna Cantidad son números positivos")


def clean_row_data(row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Limpia espacios en blanco de los datos de una fila
    
    Args:
        row_data: Diccionario con datos de una fila
        
    Returns:
        Diccionario con strings limpios
    """
    return {
        key: value.strip() if isinstance(value, str) else value
        for key, value in row_data.items()
    }


VALID_UNITS = {"PZ", "KG", "CO"}
TRUTHY_VALUES = {"SI", "S", "1"}


def parse_unit(value) -> str:
    """Parsea el valor de unidad del Excel
    
    Args:
        value: Valor de la celda (puede ser str, None, etc.)
        
    Returns:
        Código de unidad válido ('PZ', 'KG', 'CO')
        
    Raises:
        ValueError: Si el valor no es una unidad válida
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "PZ"
    unit = str(value).strip().upper()
    if unit not in VALID_UNITS:
        raise ValueError(f"Unidad inválida: '{value}'. Valores válidos: PZ, KG, CO")
    return unit


def parse_sells_by_weight_to_unit(value) -> str | None:
    """Convierte el valor legacy 'Venta por peso' a unidad.

    Si el valor indica venta por peso, retorna 'KG'.
    Si no, retorna None (no sobreescribir la unidad).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "KG" if value else None
    if isinstance(value, (int, float)):
        return "KG" if value else None
    if str(value).strip().upper() in TRUTHY_VALUES:
        return "KG"
    return None
