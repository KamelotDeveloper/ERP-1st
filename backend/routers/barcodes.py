"""Barcode generation and SKU lookup endpoints.

Uses reportlab (already a project dependency) for Code128 barcode rendering.
No additional packages required.
"""

import io
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics import renderPM
from sqlalchemy.orm import Session

from database import SessionLocal
import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/barcodes", tags=["Barcodes"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Barcode image generation (reportlab)
# ---------------------------------------------------------------------------

def _make_barcode_drawing(value: str):
    """Create a Code128 barcode drawing suitable for 50mm thermal labels.

    barWidth is the width of a single narrow bar (module unit).
    Total image width is determined by the number of bars in the encoding.
    """
    d = createBarcodeDrawing(
        "Code128",
        value=value,
        barWidth=1.8,              # ~1.8pt per module (~0.63mm) — total ~35-40mm
        barHeight=12 * 72 / 25.4,  # 12mm bar height in points
        humanReadable=True,
        fontSize=10,
        text=None,
    )
    return d


@router.get("/{value}.png")
def barcode_png(value: str) -> Response:
    """Generate a Code128 barcode as PNG image."""
    if not value or len(value) > 50:
        raise HTTPException(status_code=400, detail="Invalid barcode value")

    try:
        d = _make_barcode_drawing(value)
        buf = io.BytesIO()
        renderPM.drawToFile(d, buf, fmt="PNG", dpi=300)
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as e:
        logger.error(f"Error generating barcode PNG for '{value}': {e}")
        raise HTTPException(status_code=500, detail="Error generating barcode")


@router.get("/{value}.svg")
def barcode_svg(value: str) -> Response:
    """Generate a Code128 barcode as SVG string."""
    if not value or len(value) > 50:
        raise HTTPException(status_code=400, detail="Invalid barcode value")

    try:
        d = _make_barcode_drawing(value)
        svg_bytes = d.asSVG()
        return Response(content=svg_bytes, media_type="image/svg+xml")
    except Exception as e:
        logger.error(f"Error generating barcode SVG for '{value}': {e}")
        raise HTTPException(status_code=500, detail="Error generating barcode")


# ---------------------------------------------------------------------------
# SKU lookup (for barcode scanners)
# ---------------------------------------------------------------------------

@router.get("/search/{sku}")
def search_by_sku(sku: str, db: Session = Depends(get_db)):
    """Search for a product or material by SKU code.

    Returns the found item with a `type` field ('product' or 'material')
    so the frontend knows what it got.
    """
    if not sku or len(sku.strip()) == 0:
        raise HTTPException(status_code=400, detail="SKU is required")

    sku = sku.strip()

    # Search products first
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if product:
        return {
            "type": "product",
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "price": product.price,
            "stock": product.stock,
        }

    # Then materials
    material = db.query(models.Material).filter(models.Material.sku == sku).first()
    if material:
        return {
            "type": "material",
            "id": material.id,
            "sku": material.sku,
            "name": material.name,
            "price": material.unit_price or 0,
            "stock": material.current_stock,
        }

    raise HTTPException(status_code=404, detail=f"No product or material found with SKU: {sku}")
