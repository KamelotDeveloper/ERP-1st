import os
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from typing import Optional
from database import SessionLocal
import models
from services.afip_service import create_afip_service
from services.wsfe_client import create_wsaa_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/electronic-invoicing", tags=["Facturación Electrónica"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy.orm import Session


def get_config(db: Session):
    config = db.query(models.ElectronicInvoiceConfig).first()
    if not config:
        config = models.ElectronicInvoiceConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def validate_cuit(cuit: str) -> bool:
    """Valida CUIT argentino con algoritmo de verificación (DV)"""
    if not cuit or len(cuit) != 11 or not cuit.isdigit():
        return False
    
    base = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    
    total = 0
    for i in range(10):
        total += int(cuit[i]) * base[i]
    
    remainder = total % 11
    verif_digit = 11 - remainder
    
    if verif_digit == 11:
        verif_digit = 0
    elif verif_digit == 10:
        verif_digit = 9
    
    return int(cuit[10]) == verif_digit


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    """Obtiene el estado actual de la habilitación"""
    config = get_config(db)
    
    afip_service = create_afip_service({
        "cert_path": config.cert_path,
        "key_path": config.key_path,
        "CUIT": config.CUIT,
        "ambiente": config.ambiente
    })
    
    cred_check = afip_service.check_credentials_exist()
    
    return {
        "habilitado": config.enabled,
        "ambiente": config.ambiente,
        "razon_social": config.razon_social,
        "CUIT": config.CUIT,
        "punto_venta": config.punto_venta,
        "estado_habilitacion": config.estado_habilitacion,
        "ultimo_check": config.ultimo_check.isoformat() if config.ultimo_check else None,
        "errores": config.errores,
        "credenciales": cred_check
    }


@router.post("/setup")
def setup_electronic_invoicing(
    razon_social: str = Body(...),
    CUIT: str = Body(...),
    punto_venta: int = Body(1),
    ambiente: str = Body("testing"),
    db: Session = Depends(get_db)
):
    """Paso 1: Configuración inicial con validación de CUIT"""
    if not validate_cuit(CUIT):
        raise HTTPException(status_code=400, detail="CUIT inválido (verifique el número)")
    
    config = get_config(db)
    config.razon_social = razon_social
    config.CUIT = CUIT
    config.punto_venta = punto_venta
    config.ambiente = ambiente
    config.estado_habilitacion = "en_proceso"
    config.fecha_actualizacion = datetime.utcnow()
    
    db.commit()
    db.refresh(config)
    
    logger.info(f"Configuración iniciada para CUIT: {CUIT}")
    
    return {
        "success": True,
        "message": "Datos básicos configurados",
        "next_step": "upload_cert",
        "estado": config.estado_habilitacion,
        "cuit_validado": True
    }


@router.post("/upload-certificate")
async def upload_certificate(
    certificado: UploadFile = File(...),
    clave_privada: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Paso 2: Subir certificado y clave con validación"""
    config = get_config(db)
    
    if not config.CUIT:
        raise HTTPException(status_code=400, detail="Primero debe configurar CUIT en Paso 1")
    
    allowed_cert_extensions = ['.pem', '.crt', '.cer']
    allowed_key_extensions = ['.key', '.pem']
    
    cert_filename = certificado.filename or ""
    key_filename = clave_privada.filename or ""
    
    cert_ext = os.path.splitext(cert_filename)[1].lower()
    key_ext = os.path.splitext(key_filename)[1].lower()
    
    if cert_ext not in allowed_cert_extensions:
        raise HTTPException(status_code=400, detail="Certificado debe ser .pem, .crt o .cer")
    
    if key_ext not in allowed_key_extensions:
        raise HTTPException(status_code=400, detail="Clave debe ser .key o .pem")
    
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "certs", str(config.id))
    os.makedirs(base_path, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cert_path = os.path.join(base_path, f"certificado_{timestamp}.pem")
    key_path = os.path.join(base_path, f"clave_privada_{timestamp}.key")
    
    with open(cert_path, "wb") as f:
        f.write(await certificado.read())
    
    with open(key_path, "wb") as f:
        f.write(await clave_privada.read())
    
    if config.cert_path and os.path.exists(config.cert_path):
        try:
            os.remove(config.cert_path)
        except:
            pass
    
    if config.key_path and os.path.exists(config.key_path):
        try:
            os.remove(config.key_path)
        except:
            pass
    
    config.cert_path = cert_path
    config.key_path = key_path
    config.estado_habilitacion = "verificando"
    config.fecha_actualizacion = datetime.utcnow()
    
    db.commit()
    
    afip_service = create_afip_service({
        "cert_path": cert_path,
        "key_path": key_path,
        "CUIT": config.CUIT,
        "ambiente": config.ambiente
    })
    
    validation = afip_service.validate_certificate()
    
    if not validation.get("valido"):
        config.errores = json.dumps(validation)
        config.estado_habilitacion = "error"
        db.commit()
        logger.error(f"Validación de certificado fallida: {validation.get('error')}")
        return {
            "success": False,
            "error": validation.get("error", "Certificado inválido"),
            "details": validation
        }
    
    pasos = {"paso1": True, "paso2": True}
    config.pasos_completados = json.dumps(pasos)
    config.estado_habilitacion = "habilitado"
    config.enabled = True
    config.fecha_actualizacion = datetime.utcnow()
    db.commit()
    
    logger.info(f"Certificado validado exitosamente para CUIT: {config.CUIT}")
    
    return {
        "success": True,
        "message": "Certificado validado correctamente",
        "cert_info": {
            "sujeto": validation.get("sujeto"),
            "expiracion": validation.get("expiracion"),
            "dias_restantes": validation.get("dias_restantes")
        },
        "estado": config.estado_habilitacion
    }


@router.post("/test-connection")
def test_connection(db: Session = Depends(get_db)):
    """Paso 3: Probar conexión con ARCA usando WSAA"""
    config = get_config(db)
    
    if not config.cert_path or not config.key_path or not config.CUIT:
        raise HTTPException(status_code=400, detail="Configuración incompleta")
    
    if not os.path.exists(config.cert_path) or not os.path.exists(config.key_path):
        raise HTTPException(status_code=400, detail="Archivos de certificado no encontrados")
    
    wsaa_client = create_wsaa_client({
        "cert_path": config.cert_path,
        "key_path": config.key_path,
        "CUIT": config.CUIT,
        "ambiente": config.ambiente
    })
    
    if not wsaa_client:
        raise HTTPException(status_code=500, detail="Error creando cliente WSAA")
    
    logger.info(f"Probando conexión WSAA para ambiente: {config.ambiente}")
    
    result = wsaa_client.request_token()
    
    config.ultimo_check = datetime.utcnow()
    if result.get("success"):
        config.errores = None
        config.estado_habilitacion = "habilitado"
        logger.info("Conexión con ARCA exitosa")
    else:
        config.errores = json.dumps(result)
        config.estado_habilitacion = "error"
        logger.error(f"Conexión con ARCA fallida: {result.get('error')}")
    
    db.commit()
    
    return result


@router.post("/enable")
def enable_electronic_invoicing(db: Session = Depends(get_db)):
    """Paso 4: Activar facturación electrónica"""
    config = get_config(db)
    
    afip_service = create_afip_service({
        "cert_path": config.cert_path,
        "key_path": config.key_path,
        "CUIT": config.CUIT,
        "ambiente": config.ambiente
    })
    
    cred_check = afip_service.check_credentials_exist()
    
    if not cred_check["ready"]:
        raise HTTPException(
            status_code=400, 
            detail="Debe completar la configuración antes de habilitar"
        )
    
    config.enabled = True
    config.estado_habilitacion = "habilitado"
    config.fecha_actualizacion = datetime.utcnow()
    db.commit()
    
    logger.info(f"Facturación electrónica habilitada para CUIT: {config.CUIT}")
    
    return {
        "success": True,
        "message": "Facturación electrónica habilitada",
        "enabled": True
    }


@router.post("/disable")
def disable_electronic_invoicing(db: Session = Depends(get_db)):
    """Desactivar facturación electrónica"""
    config = get_config(db)
    config.enabled = False
    config.fecha_actualizacion = datetime.utcnow()
    db.commit()
    
    logger.info("Facturación electrónica deshabilitada")
    
    return {
        "success": True,
        "message": "Facturación electrónica deshabilitada",
        "enabled": False
    }


@router.get("/guide")
def get_setup_guide():
    """Retorna guía paso a paso de habilitación"""
    return {
        "pasos": [
            {
                "numero": 1,
                "titulo": "Datos del Contribuyente",
                "descripcion": "Ingresa la razón social, CUIT y selecciona el punto de venta",
                "endpoint": "/electronic-invoicing/setup",
                "required_fields": ["razon_social", "CUIT", "punto_venta"],
                "notas": "El CUIT se valida con algoritmo oficial de ARCA"
            },
            {
                "numero": 2,
                "titulo": "Certificado Digital",
                "descripcion": "Sube el certificado (.pem, .crt, .cer) y clave privada (.key, .pem) de ARCA",
                "endpoint": "/electronic-invoicing/upload-certificate",
                "required_fields": ["certificado", "clave_privada"]
            },
            {
                "numero": 3,
                "titulo": "Verificar Conexión",
                "descripcion": "Prueba la conexión con WSAA de ARCA",
                "endpoint": "/electronic-invoicing/test-connection",
                "notas": "Obtiene token de acceso para WSFE"
            },
            {
                "numero": 4,
                "titulo": "Habilitar",
                "descripcion": "Activa la facturación electrónica para emitir facturas con CAE real",
                "endpoint": "/electronic-invoicing/enable"
            }
        ],
        "requisitos": {
            "para_produccion": [
                "Certificado digital de ARCA vigente",
                "CUIT activo y sin restricciones",
                "Haber completado el alta en ARCA/AFIP",
                "Configurar ambiente 'production'"
            ]
        }
    }


@router.get("/options")
def get_options(db: Session = Depends(get_db)):
    """Opciones disponibles (puntos de venta, tipos de comprobante)"""
    config = get_config(db)
    
    afip_service = create_afip_service({
        "ambiente": config.ambiente if config else "testing"
    })
    
    return {
        "puntos_venta": afip_service.get_puntos_venta(),
        "tipos_comprobante": afip_service.get_tipos_comprobante()
    }


@router.post("/check-cert-expiry")
def check_cert_expiry(db: Session = Depends(get_db)):
    """Verifica si el certificado está por vencer"""
    config = get_config(db)
    
    if not config or not config.cert_path:
        return {
            "success": False,
            "error": "No hay certificado configurado"
        }
    
    afip_service = create_afip_service({
        "cert_path": config.cert_path,
        "key_path": config.key_path,
        "CUIT": config.CUIT,
        "ambiente": config.ambiente
    })
    
    validation = afip_service.validate_certificate()
    
    days_left = validation.get("dias_restantes", 0)
    
    alert_level = "none"
    if days_left <= 0:
        alert_level = "expired"
    elif days_left <= 30:
        alert_level = "critical"
    elif days_left <= 90:
        alert_level = "warning"
    
    return {
        "success": True,
        "dias_restantes": days_left,
        "expiracion": validation.get("expiracion"),
        "alert_level": alert_level,
        "mensaje": {
            "none": "Certificado sin problemas",
            "warning": f"Certificado vence en {days_left} días",
            "critical": f"Certificado vence en {days_left} días - Renovarlo urgentemente",
            "expired": "CERTIFICADO VENCIDO - La facturación no funcionará"
        }.get(alert_level)
    }
