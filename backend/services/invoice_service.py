import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import random
import os

logger = logging.getLogger(__name__)


class InvoiceService:
    """Abstraction layer for invoice generation"""
    
    MODE_MOCK = "mock"
    MODE_REAL = "real"
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.mode = self._determine_mode()
    
    def _determine_mode(self) -> str:
        """Determine if mock or real mode based on config and settings"""
        from config import settings
        
        # First check settings for explicit mode
        if settings.is_afip_mock_mode:
            return self.MODE_MOCK
        
        if settings.is_afip_real_mode:
            return self.MODE_REAL
        
        # Fallback to checking config from database
        if self._is_configured():
            return self.MODE_REAL
        
        return self.MODE_MOCK
    
    def _is_configured(self) -> bool:
        """Check if system is configured for real invoicing"""
        if not self.config.get("enabled"):
            return False
        
        cert_path = self.config.get("cert_path")
        key_path = self.config.get("key_path")
        CUIT = self.config.get("CUIT")
        
        if not all([cert_path, key_path, CUIT]):
            return False
        
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            return False
        
        return True
    
    def is_ready(self) -> Dict[str, Any]:
        """Get system readiness status"""
        from config import settings
        
        return {
            "ready": True,
            "mode": self.mode,
            "mock_mode": self.mode == self.MODE_MOCK,
            "configured": self._is_configured() or settings.is_afip_real_mode,
            "has_certificate": bool(self.config.get("cert_path")) or bool(settings.AFIP_CERT_PATH),
            "has_cuit": bool(self.config.get("CUIT")) or bool(settings.AFIP_CUIT)
        }
    
    def generate_cae(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate CAE (mock or real)"""
        logger.info(f"Generating CAE in mode: {self.mode}")
        
        if self.mode == self.MODE_REAL:
            return self._generate_real_cae(invoice_data)
        else:
            return self._generate_mock_cae(invoice_data)
    
    def _generate_mock_cae(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate simulated CAE with realistic behavior"""
        from config import settings
        
        # Simulate occasional failures for realism (10% chance)
        simulate_failure = random.random() < 0.1
        
        # Get optional simulation parameters from invoice_data or use defaults
        force_result = invoice_data.get("_force_result")
        
        if force_result == "success" or (not simulate_failure and force_result != "failure"):
            # Generate realistic CAE number
            # CAE format: 14 digits starting with 61, 62, or 63 for different invoice types
            prefix = random.choice([61, 62, 63])
            cae_number = f"{prefix}{random.randint(1000000000, 9999999999)}"
            
            vencimiento = datetime.now() + timedelta(days=10)
            
            logger.info(f"Mock CAE generated successfully: {cae_number}")
            
            return {
                "success": True,
                "CAE": cae_number,
                "CAE_vto": vencimiento.isoformat(),
                "modo": self.MODE_MOCK,
                "resultado": "A",  # A = Accepted
                "message": "CAE generado en modo simulación (sin certificado ARCA)",
                "observaciones": [],
                "numero_comprobante": invoice_data.get("numero", 1)
            }
        else:
            # Simulate failure
            error_codes = [
                ("10001", "Error de autenticación - Token expirado"),
                ("10002", "Error de validación - Falta dato obligatorio"),
                ("10003", "Error de certificación - Certificado vencido"),
                ("10004", "Error de conexión - Servicio no disponible"),
                ("10005", "Error de validación -CUIT del emisor inválido"),
            ]
            
            error_code, error_msg = random.choice(error_codes)
            
            logger.warning(f"Mock CAE failed with code {error_code}: {error_msg}")
            
            return {
                "success": False,
                "CAE": None,
                "CAE_vto": None,
                "modo": self.MODE_MOCK,
                "resultado": "R",  # R = Rejected
                "message": error_msg,
                "error_code": error_code,
                "observaciones": [error_msg]
            }
    
    def _generate_real_cae(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate real CAE via ARCA/AFIP (requires full WSFE implementation)"""
        logger.warning("Real CAE generation not fully implemented - falling back to mock")
        return self._generate_mock_cae(invoice_data)
    
    def validate_invoice_data(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate invoice data before generation"""
        errors = []
        
        if not invoice_data.get("client_id"):
            errors.append("Client is required")
        
        if not invoice_data.get("items"):
            errors.append("At least one item is required")
        
        items = invoice_data.get("items", [])
        for i, item in enumerate(items):
            if not item.get("quantity") or item["quantity"] <= 0:
                errors.append(f"Item {i+1}: invalid quantity")
            
            if not item.get("unit_price") or item["unit_price"] <= 0:
                errors.append(f"Item {i+1}: invalid price")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def calculate_totals(self, items: list) -> Dict[str, float]:
        """Calculate invoice totals"""
        subtotal = sum(item.get("quantity", 0) * item.get("unit_price", 0) for item in items)
        iva = subtotal * 0.21
        total = subtotal + iva
        
        return {
            "subtotal": round(subtotal, 2),
            "iva": round(iva, 2),
            "total": round(total, 2)
        }


def create_invoice_service(config: Dict[str, Any] = None) -> InvoiceService:
    """Factory function to create invoice service"""
    return InvoiceService(config)


def get_invoice_config(db_session) -> Dict[str, Any]:
    """Get invoice configuration from database"""
    from database import SessionLocal
    import models
    
    if db_session is None:
        db_session = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        config = db_session.query(models.ElectronicInvoiceConfig).first()
        
        if not config:
            return {}
        
        return {
            "enabled": config.enabled,
            "ambiente": config.ambiente,
            "CUIT": config.CUIT,
            "cert_path": config.cert_path,
            "key_path": config.key_path,
            "punto_venta": config.punto_venta
        }
    finally:
        if should_close:
            db_session.close()
