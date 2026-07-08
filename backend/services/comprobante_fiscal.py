import random
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def get_client_tipo_doc(cliente_cuit: str) -> tuple:
    """Determina el tipo de documento AFIP según el CUIT del cliente.

    Args:
        cliente_cuit: CUIT del cliente (11 dígitos o vacío).

    Returns:
        Tupla (tipo_documento, numero_documento):
        - (80, CUIT) para CUIT de personas jurídicas
        - (96, CUIT) para CUIT de personas físicas o no reconocidos
        - (99, "0") para consumidor final
    """
    if not cliente_cuit or cliente_cuit == "0":
        return 99, "0"

    if len(cliente_cuit) == 11 and cliente_cuit.isdigit():
        prefix = cliente_cuit[:2]
        if prefix in ["20", "23", "24", "27", "30", "33"]:
            return 80, cliente_cuit

    return 96, cliente_cuit


def get_tipo_afip_from_tipo(tipo: str) -> Optional[int]:
    """Map internal tipo string to ARCA código de comprobante.

    Args:
        tipo: Tipo string (e.g. 'FACTURA_A', 'NOTA_CREDITO_B').

    Returns:
        ARCA integer code (1, 2, 3, 6, 7, 8, 11, 12, 13, 19, 81) or None.
    """
    mapping = {
        "FACTURA_A": 1, "FACTURA_B": 6, "FACTURA_C": 11,
        "FACTURA_M": 81, "FACTURA_E": 19,
        "NOTA_DEBITO_A": 2, "NOTA_DEBITO_B": 7, "NOTA_DEBITO_C": 12,
        "NOTA_CREDITO_A": 3, "NOTA_CREDITO_B": 8, "NOTA_CREDITO_C": 13,
    }
    return mapping.get(tipo.upper())


def generate_mock_cae(invoice_data: dict, force_result: Optional[str] = None) -> dict:
    """Genera un CAE simulado (mock) para testing sin conexión ARCA/AFIP.

    Funciona para cualquier tipo de comprobante fiscal.
    Simula éxito (~90% de las veces) o errores realistas de AFIP (~10%).

    Args:
        invoice_data: Diccionario con datos de la factura (al menos 'numero').
        force_result: Forzar resultado específico ('success', 'failure', o None).

    Returns:
        Diccionario con estructura similar a la respuesta real de WSFE:
        - success: bool
        - CAE: str o None
        - CAE_vto: str ISO format o None
        - modo: "mock"
        - resultado: "A" (aprobado) o "R" (rechazado)
        - message: str
        - error_code: str (solo si falla)
        - observaciones: list
        - numero_comprobante: int
    """
    simulate_failure = random.random() < 0.1

    if force_result == "success" or (not simulate_failure and force_result != "failure"):
        prefix = random.choice([61, 62, 63])
        cae_number = f"{prefix}{random.randint(1000000000, 9999999999)}"
        vencimiento = datetime.now() + timedelta(days=10)

        # Log CbtesAsoc when present (NC/ND audit trail)
        cbtes_asoc = invoice_data.get("CbtesAsoc")
        if cbtes_asoc:
            for entry in cbtes_asoc:
                logger.info(
                    f"Mock CAE for NC/ND with CbtesAsoc: "
                    f"Tipo={entry.get('Tipo')} PtoVta={entry.get('PtoVta')} Nro={entry.get('Nro')}"
                )

        # Log AlicIva groupings for audit parity
        items_raw = invoice_data.get("items_raw", [])
        if items_raw:
            iva_groups: dict[float, dict] = {}
            for item in items_raw:
                rate = round(item.get("iva_alicuota", 0), 2)
                if rate not in iva_groups:
                    iva_groups[rate] = {"BaseImp": 0.0, "Importe": 0.0}
                iva_groups[rate]["BaseImp"] += item.get("subtotal", 0)
                iva_groups[rate]["Importe"] += item.get("iva_importe", 0)
            for rate, amounts in sorted(iva_groups.items()):
                logger.info(
                    f"Mock AlicIva: tasa={rate}% "
                    f"BaseImp={round(amounts['BaseImp'], 2)} "
                    f"Importe={round(amounts['Importe'], 2)}"
                )

        # Log CondicionIVAReceptorId for audit parity
        cond_id = invoice_data.get("condicion_iva_receptor_id")
        if cond_id is not None:
            logger.info(f"Mock CondicionIVAReceptorId={cond_id}")

        logger.info(f"Mock CAE generated successfully: {cae_number}")

        return {
            "success": True,
            "CAE": cae_number,
            "CAE_vto": vencimiento.isoformat(),
            "modo": "mock",
            "resultado": "A",
            "message": "CAE generado en modo simulación (sin certificado ARCA)",
            "observaciones": [],
            "numero_comprobante": invoice_data.get("numero", 1)
        }

    # Simulate failure
    error_codes = [
        ("10001", "Error de autenticación - Token expirado"),
        ("10002", "Error de validación - Falta dato obligatorio"),
        ("10003", "Error de certificación - Certificado vencido"),
        ("10004", "Error de conexión - Servicio no disponible"),
        ("10005", "Error de validación - CUIT del emisor inválido"),
    ]

    error_code, error_msg = random.choice(error_codes)

    logger.warning(f"Mock CAE failed with code {error_code}: {error_msg}")

    return {
        "success": False,
        "CAE": None,
        "CAE_vto": None,
        "modo": "mock",
        "resultado": "R",
        "message": error_msg,
        "error_code": error_code,
        "observaciones": [error_msg]
    }
