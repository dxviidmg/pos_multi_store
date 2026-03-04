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
    """Valida que todas las cantidades sean números enteros
    
    Args:
        df: DataFrame con columna 'quantity'
        
    Raises:
        ValueError: Si hay valores no enteros
    """
    all_integers = df["quantity"].apply(lambda x: isinstance(x, int)).all()
    if not all_integers:
        raise ValueError("No todos los datos en la columna Cantidad son números")


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
