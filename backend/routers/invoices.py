import os
import json
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import SessionLocal
import models, schemas
from services.wsfe_client import create_wsfe_client, create_wsaa_client
from services.afip_service import create_afip_service
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_afip_config(db: Session):
    """Obtiene configuración de AFIP"""
    return db.query(models.ElectronicInvoiceConfig).first()


def get_next_invoice_number(db: Session, punto_venta: int, tipo_factura: int):
    last = db.query(models.Invoice).filter(
        models.Invoice.punto_venta == punto_venta,
        models.Invoice.tipo_factura == tipo_factura
    ).order_by(models.Invoice.numero.desc()).first()
    
    if last:
        return last.numero + 1
    return 1


def get_client_tipo_doc(cliente_cuit: str) -> tuple:
    """Determina el tipo de documento según el CUIT del cliente"""
    if not cliente_cuit or cliente_cuit == "0":
        return 99, "0"
    
    if len(cliente_cuit) == 11 and cliente_cuit.isdigit():
        prefix = cliente_cuit[:2]
        if prefix in ["20", "23", "24", "27", "30", "33"]:
            return 80, cliente_cuit
    
    return 96, cliente_cuit


def is_mock_mode() -> bool:
    """Check if running in mock mode"""
    return settings.is_afip_mock_mode


def request_cae_real(db: Session, invoice_data: dict) -> dict:
    """Solicita CAE real a ARCA usando WSFE"""
    config = get_afip_config(db)
    
    if not config or not config.enabled:
        return {
            "success": False,
            "error": "Sistema no habilitado para facturación electrónica"
        }
    
    wsfe_client = create_wsfe_client({
        "cert_path": config.cert_path,
        "key_path": config.key_path,
        "CUIT": config.CUIT,
        "ambiente": config.ambiente
    })
    
    if not wsfe_client:
        return {
            "success": False,
            "error": "No se pudo crear cliente WSFE"
        }
    
    doc_tipo, doc_nro = get_client_tipo_doc(invoice_data.get("cliente_cuit", ""))
    
    wsfe_invoice_data = {
        "punto_venta": invoice_data.get("punto_venta", config.punto_venta),
        "tipo_comprobante": invoice_data.get("tipo_comprobante", 6),
        "cliente_cuit": doc_nro,
        "cliente_tipo_doc": doc_tipo,
        "cbte_desde": invoice_data.get("numero", 1),
        "cbte_hasta": invoice_data.get("numero", 1),
        "subtotal": invoice_data.get("subtotal", 0),
        "iva": invoice_data.get("iva", 0),
        "iva_tipo": invoice_data.get("iva_tipo", 5)
    }
    
    return wsfe_client.request_cae(wsfe_invoice_data)


def generate_mock_cae(invoice_data: dict, force_result: str = None) -> dict:
    """Generate mock CAE with realistic behavior"""
    import random
    
    # Check force_result parameter or simulate occasional failures
    simulate_failure = random.random() < 0.1
    
    if force_result == "success" or (not simulate_failure and force_result != "failure"):
        prefix = random.choice([61, 62, 63])
        cae_number = f"{prefix}{random.randint(1000000000, 9999999999)}"
        vencimiento = datetime.now() + timedelta(days=10)
        
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
    else:
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


@router.post("/invoices")
def create_invoice(data: schemas.InvoiceCreate, request: Request, db: Session = Depends(get_db)):
    """Crea una nueva factura con CAE"""
    client = db.query(models.Client).filter(models.Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    config = get_afip_config(db)
    punto_venta = config.punto_venta if config else 1
    tipo_factura = data.tipo_factura
    
    numero = get_next_invoice_number(db, punto_venta, tipo_factura)
    
    subtotal = 0
    items_data = []
    
    for item in data.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto {item.product_id} no encontrado")
        
        item_subtotal = item.unit_price * item.quantity
        subtotal += item_subtotal
        items_data.append({
            "product": product,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item_subtotal
        })
    
    iva = subtotal * 0.21
    total = subtotal + iva
    
    # Determine mode: mock (default) or real (if configured)
    use_mock = is_mock_mode() or not (config and config.enabled and config.cert_path and os.path.exists(config.cert_path))
    
    if not use_mock:
        logger.info("Solicitando CAE real a ARCA...")
        
        invoice_for_wsfe = {
            "punto_venta": punto_venta,
            "tipo_comprobante": tipo_factura,
            "numero": numero,
            "subtotal": subtotal,
            "iva": iva,
            "iva_tipo": 5,
            "cliente_cuit": client.tax_id or ""
        }
        
        cae_result = request_cae_real(db, invoice_for_wsfe)
        
        if cae_result.get("success"):
            cae = cae_result["CAE"]
            cae_vto = datetime.strptime(cae_result["CAE_vto"], "%Y-%m-%dT%H:%M:%S.%f")
            estado = "issued"
            logger.info(f"CAE obtenido exitosamente: {cae}")
        else:
            logger.error(f"Error obteniendo CAE: {cae_result.get('error')}")
            cae = None
            cae_vto = None
            estado = "error"
    else:
        logger.info("Usando CAE simulado (modo mock - sin certificado ARCA)")
        force_result = getattr(data, 'force_result', None) if hasattr(data, 'force_result') else None
        cae_result = generate_mock_cae({"numero": numero}, force_result)
        cae = cae_result.get("CAE") if cae_result.get("success") else None
        cae_vto = datetime.fromisoformat(cae_result["CAE_vto"]) if cae_result.get("CAE_vto") else None
        estado = "issued" if cae_result.get("success") else "error"
    
    invoice = models.Invoice(
        sale_id=data.sale_id,
        client_id=data.client_id,
        cae=cae,
        cae_vto=cae_vto,
        punto_venta=punto_venta,
        numero=numero,
        tipo_factura=tipo_factura,
        subtotal=subtotal,
        iva=iva,
        total=total,
        estado=estado,
        afip_response=json.dumps(cae_result) if not use_mock else json.dumps(cae_result)
    )
    
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    return {
        "id": invoice.id,
        "numero": f"{punto_venta:05d}-{numero:08d}",
        "cae": cae,
        "cae_vto": cae_vto.isoformat() if cae_vto else None,
        "tipo_factura": tipo_factura,
        "subtotal": subtotal,
        "iva": iva,
        "total": total,
        "estado": estado,
        "modo": "real" if not use_mock else "mock"
    }


@router.get("/invoices")
def list_invoices(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    invoices = db.query(models.Invoice).order_by(models.Invoice.fecha.desc()).offset(skip).limit(limit).all()
    
    result = []
    for inv in invoices:
        client = db.query(models.Client).filter(models.Client.id == inv.client_id).first()
        result.append({
            "id": inv.id,
            "numero": f"{inv.punto_venta:05d}-{inv.numero:08d}",
            "cliente": client.name if client else "N/A",
            "cae": inv.cae,
            "cae_vto": inv.cae_vto.isoformat() if inv.cae_vto else None,
            "tipo_factura": inv.tipo_factura,
            "total": inv.total,
            "estado": inv.estado,
            "fecha": inv.fecha.isoformat()
        })
    
    return result


@router.get("/invoices/count")
def count_invoices(db: Session = Depends(get_db)):
    count = db.query(models.Invoice).count()
    return {"count": count}


@router.get("/invoices/{id}")
def get_invoice(id: int, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    client = db.query(models.Client).filter(models.Client.id == invoice.client_id).first()
    
    items = []
    if invoice.sale_id:
        sale_items = db.query(models.SaleItem).filter(models.SaleItem.sale_id == invoice.sale_id).all()
        for si in sale_items:
            product = db.query(models.Product).filter(models.Product.id == si.product_id).first()
            items.append({
                "producto": product.name if product else "N/A",
                "cantidad": si.quantity,
                "precio": si.price,
                "subtotal": si.quantity * si.price
            })
    
    return {
        "id": invoice.id,
        "numero": f"{invoice.punto_venta:05d}-{invoice.numero:08d}",
        "cliente": {
            "nombre": client.name if client else "N/A",
            "direccion": client.address if client and client.address else "",
            "cuit": client.tax_id if client and client.tax_id else ""
        },
        "cae": invoice.cae,
        "cae_vto": invoice.cae_vto.isoformat() if invoice.cae_vto else None,
        "tipo_factura": invoice.tipo_factura,
        "subtotal": invoice.subtotal,
        "iva": invoice.iva,
        "total": invoice.total,
        "estado": invoice.estado,
        "fecha": invoice.fecha.isoformat(),
        "items": items
    }


@router.delete("/invoices/{id}")
def delete_invoice(id: int, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    db.delete(invoice)
    db.commit()
    
    return {"ok": True}


@router.get("/invoices/mode")
def get_invoice_mode(db: Session = Depends(get_db)):
    """Get current invoice mode status (mock or real)"""
    config = get_afip_config(db)
    is_mock = is_mock_mode()
    
    return {
        "mode": "mock" if is_mock else "real",
        "mock_mode": is_mock,
        "configured": bool(config and config.enabled and config.cert_path),
        "message": "Modo simulación (sin certificado ARCA)" if is_mock else "Modo real (con certificado ARCA)"
    }
