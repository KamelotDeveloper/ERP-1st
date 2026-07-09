"""
import_service.py — Bulk import service for CSV/XLSX files.
Supports Client, Product, Material resources with validation and side effects.
"""
import csv
import io
import os
import re
from typing import List, Dict, Tuple

from fastapi import HTTPException, UploadFile
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

import schemas


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ROWS_PARSE = 10000
MAX_ROWS_PREVIEW = 5000

# Spanish/normalized header -> field name mapping
HEADER_MAP = {
    "clients": {
        "nombre": "name",
        "email": "email",
        "telefono": "phone",
        "direccion": "address",
        "cuit": "tax_id",
        "condicion_iva_receptor_id": "condicion_iva_receptor_id",
    },
    "products": {
        "sku": "sku",
        "nombre": "name",
        "precio": "price",
        "stock": "stock",
        "stock_minimo": "stock_minimo",
    },
    "materials": {
        "sku": "sku",
        "nombre": "name",
        "categoria": "category",
        "stock_actual": "current_stock",
        "costo_unitario": "unit_cost",
        "precio_unitario": "unit_price",
        "stock_minimo": "stock_minimo",
    },
}

# Accepted English field names (mapped to themselves)
VALID_FIELD_NAMES = {
    "clients": {"name", "email", "phone", "address", "tax_id", "condicion_iva_receptor_id"},
    "products": {"sku", "name", "price", "stock", "stock_minimo"},
    "materials": {"sku", "name", "category", "current_stock", "unit_cost", "unit_price", "stock_minimo"},
}

SCHEMA_MAP = {
    "clients": schemas.ClientCreate,
    "products": schemas.ProductCreate,
    "materials": schemas.MaterialCreate,
}

TEMPLATE_HEADERS = {
    "clients": ["nombre", "email", "telefono", "direccion", "cuit", "condicion_iva_receptor_id"],
    "products": ["sku", "nombre", "precio", "stock", "stock_minimo"],
    "materials": ["sku", "nombre", "categoria", "stock_actual", "costo_unitario", "precio_unitario", "stock_minimo"],
}

VALID_RESOURCES = {"clients", "products", "materials"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_header(header: str) -> str:
    h = header.strip().lower()
    h = h.replace(" ", "_").replace("-", "_")
    h = "".join(c for c in h if c.isalnum() or c == "_")
    return h


def _normalize_number(value: str) -> str:
    """Convert locale-formatted numbers (e.g. '4,5' -> '4.5')."""
    if isinstance(value, str):
        value = value.strip()
        if re.match(r'^-?\d+,\d+$', value):
            value = value.replace(",", ".")
    return value


def _detect_delimiter(sample: str) -> str:
    lines = sample.split("\n")
    if not lines:
        return ","
    first = lines[0]
    counts = {
        ",": first.count(","),
        ";": first.count(";"),
        "\t": first.count("\t"),
    }
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def _empty_to_none(value):
    """Convert empty/whitespace-only string to None."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_csv(content: bytes, warnings: List[str]) -> List[Dict]:
    """Parse CSV content -> list of dicts with original header keys."""
    raw = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            raw = content.decode(encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if raw is None:
        raise HTTPException(status_code=400, detail="No se pudo detectar la codificacion del archivo CSV")

    delimiter = _detect_delimiter(raw)
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)

    if not reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="No se detectaron headers. Verifique que la primera fila contenga los nombres de columna",
        )

    rows = []
    for row in reader:
        cleaned = {}
        for k, v in row.items():
            if k is None:
                continue
            cleaned[k] = _normalize_number(v) if isinstance(v, str) else v
        rows.append(cleaned)

    return rows


def _parse_xlsx(content: bytes, warnings: List[str]) -> List[Dict]:
    """Parse XLSX content (first sheet only) -> list of dicts with original header keys."""
    wb = None
    try:
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
    except InvalidFileException:
        raise HTTPException(status_code=400, detail="El archivo Excel no es valido o esta danado")
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "protected" in msg:
            raise HTTPException(
                status_code=400,
                detail="El archivo esta protegido con contrasena. Quite la proteccion e intente nuevamente",
            )
        raise HTTPException(status_code=400, detail=f"Error al leer archivo Excel: {str(e)}")

    sheet = wb.active
    if sheet is None:
        wb.close()
        raise HTTPException(status_code=400, detail="El archivo Excel no tiene hojas")

    header_row = next(sheet.iter_rows(values_only=True), None)
    if not header_row:
        wb.close()
        raise HTTPException(
            status_code=400,
            detail="No se detectaron headers. Verifique que la primera fila contenga los nombres de columna",
        )

    headers = []
    for h in header_row:
        h_str = str(h).strip() if h is not None else ""
        if h_str:
            headers.append(h_str)

    if not headers:
        wb.close()
        raise HTTPException(
            status_code=400,
            detail="No se detectaron headers. Verifique que la primera fila contenga los nombres de columna",
        )

    rows = []
    for row in sheet.iter_rows(values_only=True):
        if all(cell is None or (isinstance(cell, str) and cell.strip() == "") for cell in row):
            continue

        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(row):
                val = row[i]
                if isinstance(val, str):
                    val = val.strip()
                elif val is None:
                    val = ""
                row_dict[header] = val
        rows.append(row_dict)

    wb.close()
    return rows


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

def _build_column_mapping(headers: List[str], resource: str) -> Tuple[Dict[str, str], List[str]]:
    """Build (mapped: {original_header: field_name}, ignored: [original_headers])."""
    header_map = HEADER_MAP[resource]
    valid_fields = VALID_FIELD_NAMES[resource]

    mapped = {}
    ignored = []

    for header in headers:
        normalized = _normalize_header(header)
        if not normalized:
            continue
        if normalized in header_map:
            mapped[header] = header_map[normalized]
        elif normalized in valid_fields:
            mapped[header] = normalized
        else:
            ignored.append(header)

    return mapped, ignored


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(file: UploadFile) -> Tuple[List[Dict], List[str]]:
    """Parse uploaded file (CSV or XLSX).

    Returns (rows, warnings).
    Each row is a dict with original (un-normalized) header keys.
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in (".csv", ".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Use CSV o Excel (.xlsx)",
        )

    content = file.file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="El archivo excede el tamano maximo de 10MB",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="El archivo esta vacio")

    warnings = []

    if ext == ".csv":
        data_rows = _parse_csv(content, warnings)
    else:
        data_rows = _parse_xlsx(content, warnings)

    # Filter completely empty rows
    data_rows = [
        row
        for row in data_rows
        if any(
            isinstance(v, str) and v.strip() != "" or not isinstance(v, str)
            for v in row.values()
        )
    ]

    if not data_rows:
        raise HTTPException(status_code=400, detail="El archivo no contiene filas de datos")

    if len(data_rows) > MAX_ROWS_PARSE:
        warnings.append(
            f"El archivo tiene {len(data_rows)} filas. Procesando primeras {MAX_ROWS_PARSE}."
        )
        data_rows = data_rows[:MAX_ROWS_PARSE]

    return data_rows, warnings
