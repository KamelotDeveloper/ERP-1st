import logging
from sqlalchemy.orm import Session
from models import Comprobante

logger = logging.getLogger(__name__)


def get_next_numero(db: Session, punto_venta: int, tipo: str) -> int:
    """Obtiene el próximo número de comprobante para un punto de venta y tipo dado.

    Args:
        db: Sesión de base de datos.
        punto_venta: Número de punto de venta.
        tipo: Tipo de comprobante (ej: 'factura_a', 'remito', etc.).

    Returns:
        El próximo número correlativo (último + 1) o 1 si no hay comprobantes.
    """
    last = db.query(Comprobante).filter(
        Comprobante.punto_venta == punto_venta,
        Comprobante.tipo == tipo
    ).order_by(Comprobante.numero.desc()).first()

    if last:
        next_numero = last.numero + 1
        logger.debug(f"Next numero for PV={punto_venta}, tipo={tipo}: {next_numero}")
        return next_numero

    logger.debug(f"First numero for PV={punto_venta}, tipo={tipo}: 1")
    return 1
