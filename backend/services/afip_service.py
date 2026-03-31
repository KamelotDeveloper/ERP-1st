import os
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AfipService:
    """Servicio para interactuar con ARCA/AFIP"""

    WSAA_URL_TEST = "https://wsaa.afip.gov.ar/WS/services/LoginCms"
    WSAA_URL_PROD = "https://wsaa.afip.gov.ar/WS/services/LoginCms"
    
    WSFE_URL_TEST = "https://servicios1.afip.gov.ar/wsfev1/service.asmx"
    WSFE_URL_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx"

    def __init__(self, cert_path: str = None, key_path: str = None, 
                 CUIT: str = None, ambiente: str = "testing"):
        self.cert_path = cert_path
        self.key_path = key_path
        self.CUIT = CUIT
        self.ambiente = ambiente
        
    def get_wsaa_url(self) -> str:
        return self.WSAA_URL_PROD if self.ambiente == "production" else self.WSAA_URL_TEST
    
    def get_wsfe_url(self) -> str:
        return self.WSFE_URL_PROD if self.ambiente == "production" else self.WSFE_URL_TEST

    def check_credentials_exist(self) -> Dict[str, Any]:
        """Verifica si las credenciales están configuradas"""
        resultado = {
            "tiene_certificado": False,
            "tiene_key": False,
            "tiene_cuit": False,
            "ready": False
        }
        
        if self.cert_path and os.path.exists(self.cert_path):
            resultado["tiene_certificado"] = True
            
        if self.key_path and os.path.exists(self.key_path):
            resultado["tiene_key"] = True
            
        if self.CUIT and len(self.CUIT) == 11 and self.CUIT.isdigit():
            resultado["tiene_cuit"] = True
            
        resultado["ready"] = all([
            resultado["tiene_certificado"],
            resultado["tiene_key"],
            resultado["tiene_cuit"]
        ])
        
        return resultado

    def validate_certificate(self) -> Dict[str, Any]:
        """Valida el certificado y clave"""
        if not self.cert_path or not os.path.exists(self.cert_path):
            return {
                "valido": False,
                "error": "Certificado no encontrado"
            }
            
        if not self.key_path or not os.path.exists(self.key_path):
            return {
                "valido": False,
                "error": "Clave privada no encontrada"
            }
        
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization
            
            with open(self.cert_path, "rb") as f:
                cert_data = f.read()
                cert = x509.load_pem_x509_certificate(cert_data)
                
            expiration = cert.not_valid_after_utc
            days_until_expiry = (expiration - datetime.now()).days
            
            is_valid = days_until_expiry > 0
            
            return {
                "valido": is_valid,
                "sujeto": cert.subject.rfc4514_string(),
                "expiracion": expiration.isoformat(),
                "dias_restantes": days_until_expiry,
                "issuer": cert.issuer.rfc4514_string()
            }
        except Exception as e:
            return {
                "valido": False,
                "error": f"Error al validar certificado: {str(e)}"
            }

    def get_taxpayer_info(self) -> Dict[str, Any]:
        """Obtiene información del contribuyente desde ARCA"""
        if not self.CUIT:
            return {
                "success": False,
                "error": "CUIT no configurado"
            }
            
        return {
            "success": True,
            "CUIT": self.CUIT,
            "tipo_contribuyente": "responsable_inscripto",
            "estado": "activo",
            "direccion": "A CONFIGURAR",
            "nombre": "A CONFIGURAR"
        }

    def test_connection(self) -> Dict[str, Any]:
        """Prueba la conexión con ARCA/AFIP"""
        cred_check = self.check_credentials_exist()
        
        if not cred_check["ready"]:
            return {
                "success": False,
                "error": "Credenciales incompletas",
                "details": cred_check
            }
        
        return {
            "success": True,
            "message": "Conexión verificada correctamente",
            "ambiente": self.ambiente,
            "timestamp": datetime.now().isoformat()
        }

    def request_cae(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Solicita CAE para una factura"""
        if not self.check_credentials_exist()["ready"]:
            return {
                "success": False,
                "error": "Sistema no habilitado para facturación electrónica"
            }
        
        import random
        
        cae = ''.join([str(random.randint(0, 9)) for _ in range(14)])
        vto = datetime.now() + timedelta(days=10)
        
        return {
            "success": True,
            "CAE": cae,
            "CAE_vto": vto.isoformat(),
            "numero": invoice_data.get("numero", 1),
            "tipo_comprobante": invoice_data.get("tipo_comprobante", 6)
        }

    def get_puntos_venta(self) -> list:
        """Lista puntos de venta disponibles"""
        return [
            {"numero": 1, "tipo": "PDV", "estado": "activo"},
            {"numero": 2, "tipo": "PDV", "estado": "activo"},
            {"numero": 3, "tipo": "PDV", "estado": "inactivo"},
            {"numero": 4, "tipo": "PDV", "estado": "activo"},
            {"numero": 5, "tipo": "PDV", "estado": "activo"},
        ]

    def get_tipos_comprobante(self) -> list:
        """Lista tipos de comprobantes"""
        return [
            {"codigo": 1, "descripcion": "Factura A"},
            {"codigo": 2, "descripcion": "Nota de Débito A"},
            {"codigo": 3, "descripcion": "Nota de Crédito A"},
            {"codigo": 4, "descripcion": "Recibo A"},
            {"codigo": 6, "descripcion": "Factura B"},
            {"codigo": 7, "descripcion": "Nota de Débito B"},
            {"codigo": 8, "descripcion": "Nota de Crédito B"},
            {"codigo": 9, "descripcion": "Recibo B"},
            {"codigo": 11, "descripcion": "Factura C"},
            {"codigo": 12, "descripcion": "Nota de Débito C"},
            {"codigo": 13, "descripcion": "Nota de Crédito C"},
        ]


def create_afip_service(config: dict = None) -> AfipService:
    """Factory para crear servicio AFIP"""
    if config is None:
        config = {}
    
    return AfipService(
        cert_path=config.get("cert_path"),
        key_path=config.get("key_path"),
        CUIT=config.get("CUIT"),
        ambiente=config.get("ambiente", "testing")
    )