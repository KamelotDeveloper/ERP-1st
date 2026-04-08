import os
import json
import base64
import hashlib
import subprocess
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import pkcs12
import logging
import httpx

logger = logging.getLogger(__name__)


class WSAAClient:
    """Cliente para WSAA (Autenticación) de ARCA/AFIP"""
    
    # URLs de homologación (testing) - ARCA
    WSAA_URL_TEST = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
    WSAA_URL_PROD = "https://wsaa.afip.gov.ar/WS/services/LoginCms"
    
    # URLs de homologación (testing) - ARCA
    WSFE_URL_TEST = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx"
    WSFE_URL_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx"
    
    TRA_SERVICE = "wsfe"
    
    def __init__(self, cert_path: str, key_path: str, CUIT: str, ambiente: str = "testing"):
        self.cert_path = cert_path
        self.key_path = key_path
        self.CUIT = CUIT
        self.ambiente = ambiente
        
        self._token = None
        self._sign = None
        self._token_expiration = None
    
    def get_wsaa_url(self) -> str:
        return self.WSAA_URL_PROD if self.ambiente == "production" else self.WSAA_URL_TEST
    
    def get_wsfe_url(self) -> str:
        return self.WSFE_URL_PROD if self.ambiente == "production" else self.WSFE_URL_TEST
    
    def _load_certificate(self) -> tuple:
        """Carga certificado y clave privada desde archivos PEM"""
        with open(self.cert_path, "rb") as cert_file:
            cert_data = cert_file.read()
        
        with open(self.key_path, "rb") as key_file:
            key_data = key_file.read()
        
        cert = x509.load_pem_x509_certificate(cert_data)
        key = serialization.load_pem_private_key(key_data, password=None)
        
        return cert, key
    
    def _create_tra(self) -> str:
        """Crea el Ticket de Requerimiento de Acceso (TRA)"""
        unique_id = str(int(datetime.now().timestamp()))
        generation_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S-00:00")
        expiration_time = (datetime.utcnow() + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S-00:00")
        
        tra = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{generation_time}</generationTime>
    <expirationTime>{expiration_time}</expirationTime>
  </header>
  <service>{self.TRA_SERVICE}</service>
</loginTicketRequest>"""
        
        return tra.strip()
    
    def _sign_tra(self, tra: str, cert, key) -> str:
        """Firma el TRA con el certificado usando PKCS#7/CMS con formato válido para WSAA"""
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization.pkcs7 import PKCS7SignatureBuilder, PKCS7Options
        import email.generator
        import io
        
        tra_bytes = tra.encode('utf-8')
        
        # Cargar certificado y clave desde archivos
        with open(self.cert_path, 'rb') as f:
            cert_pem = f.read()
        with open(self.key_path, 'rb') as f:
            key_pem = f.read()
        
        # Cargar certificado X509
        certificate = x509.load_pem_x509_certificate(cert_pem)
        
        # Cargar clave privada
        private_key = serialization.load_pem_private_key(key_pem, password=None)
        
        try:
            # Crear estructura PKCS#7 signed data (formato SMIME como M2Crypto)
            # Primero: crear firma PKCS#7
            builder = PKCS7SignatureBuilder()
            builder = builder.set_data(tra_bytes)
            builder = builder.add_signer(certificate, private_key, hashes.SHA256())
            
            # Firmar en formato DER - incluir certificados para que sea válido
            signed_data = builder.sign(
                serialization.Encoding.DER, 
                []  # Sin opciones especiales - incluir certificados
            )
            
            # Convertir a base64 directamente (formato SMIME)
            cms_b64 = base64.b64encode(signed_data).decode('utf-8')
            
            logger.info("Firma PKCS#7 creada exitosamente (cryptography)")
            return cms_b64
            
        except Exception as e:
            logger.error(f"Error firmando PKCS#7: {e}")
            raise
    
    def _sign_tra_openssl(self, tra: str) -> str:
        """Firma usando openssl directamente como último recurso"""
        import tempfile
        import subprocess
        
        tra_bytes = tra.encode('utf-8')
        
        # Crear archivos temporales
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.tra', delete=False) as tra_file:
            tra_file.write(tra_bytes)
            tra_path = tra_file.name
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pem', delete=False) as cert_file:
            cert_file.write(open(self.cert_path, 'rb').read())
            cert_path = cert_file.name
            
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.key', delete=False) as key_file:
            key_file.write(open(self.key_path, 'rb').read())
            key_path = key_file.name
        
        output_path = tra_path + '.sig'
        
        try:
            # Usar openssl para firmar
            cmd = [
                'openssl', 'smime', '-sign',
                '-in', tra_path,
                '-signer', cert_path,
                '-inkey', key_path,
                '-outform', 'DER',
                '-out', output_path,
                '-nodetach'
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"OpenSSL error: {result.stderr.decode()}")
            
            with open(output_path, 'rb') as f:
                cms_der = f.read()
            
            cms_b64 = base64.b64encode(cms_der).decode('utf-8')
            logger.info("Firma OpenSSL smime creada exitosamente")
            return cms_b64
            
        finally:
            # Limpiar archivos temporales
            for p in [tra_path, cert_path, key_path, output_path]:
                try:
                    os.unlink(p)
                except:
                    pass
    
    def request_token(self) -> Dict[str, Any]:
        """Obtiene el token de acceso desde WSAA"""
        try:
            cert, key = self._load_certificate()
            tra = self._create_tra()
            cms = self._sign_tra(tra, cert, key)
            
            wsaa_url = self.get_wsaa_url()
            logger.info(f"Solicitando token a WSAA: {wsaa_url}")
            
            # Enviar como SOAP XML con el CMS
            soap_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <loginCms xmlns="http://wsaa.view.servicios.afip.gov.ar">
      <in0>{cms}</in0>
    </loginCms>
  </soap:Body>
</soap:Envelope>'''
            
            import urllib.request
            
            req = urllib.request.Request(
                wsaa_url,
                data=soap_xml.encode('utf-8'),
                headers={
                    'Content-Type': 'text/xml; charset=utf-8',
                    'SOAPAction': 'http://ar.gov.afip.wsaa/loginCms'
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                response_xml = response.read().decode('utf-8')
                response_status = response.status
            
            if response_status != 200:
                return {
                    "success": False,
                    "error": f"WSAA Error: HTTP {response_status}",
                    "details": response_xml
                }
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response_xml)
            
            # Buscar loginCmsReturn - contiene el XML con el token
            ns = {'ns': 'http://wsaa.view.servicios.afip.gov.ar'}
            
            login_return_elem = root.find('.//ns:loginCmsReturn', ns)
            
            if login_return_elem is None:
                return {
                    "success": False,
                    "error": "No se encontró loginCmsReturn en respuesta WSAA",
                    "details": response_xml
                }
            
            # El loginCmsReturn contiene otro XML con el token
            inner_xml = login_return_elem.text
            inner_root = ET.fromstring(inner_xml)
            
            # Buscar token y sign dentro del XML interno
            token_elem = inner_root.find('.//token')
            sign_elem = inner_root.find('.//sign')
            
            if token_elem is not None and sign_elem is not None:
                self._token = token_elem.text
                self._sign = sign_elem.text
                self._token_expiration = datetime.now() + timedelta(hours=12)
                
                logger.info("Token WSAA obtenido exitosamente")
                
                return {
                    "success": True,
                    "token": self._token,
                    "sign": self._sign,
                    "expiration": self._token_expiration.isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "No se encontró token en respuesta WSAA",
                    "details": response_xml
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo token WSAA: {str(e)}")
            return {
                "success": False,
                "error": f"Error WSAA: {str(e)}"
            }
    
    def get_valid_token(self) -> Optional[Dict[str, Any]]:
        """Obtiene un token válido, reutilizando si aún es vigente"""
        if self._token and self._token_expiration:
            if datetime.now() < self._token_expiration:
                return {
                    "success": True,
                    "token": self._token,
                    "sign": self._sign
                }
        
        return self.request_token()


class WSFEClient:
    """Cliente para WSFE (Facturación Electrónica) de ARCA/AFIP"""
    
    def __init__(self, wsaa_client: WSAAClient):
        self.wsaa_client = wsaa_client
    
    def _build_fe_cae_request(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Construye el request para FECAESolicitar"""
        return {
            "FeCAEReq": {
                "FeCabReq": {
                    "CantReg": 1,
                    "PrestaS": 1,
                    "PtoVta": invoice_data.get("punto_venta", 1),
                    "CbteTipo": invoice_data.get("tipo_comprobante", 6)
                },
                "FeDetReq": {
                    "FECAEDetRequest": {
                        "DocNro": invoice_data.get("cliente_cuit", "0"),
                        "DocTipo": invoice_data.get("cliente_tipo_doc", 96),
                        "CbteDesde": invoice_data.get("cbte_desde", 1),
                        "CbteHasta": invoice_data.get("cbte_hasta", 1),
                        "CbteFch": datetime.now().strftime("%Y%m%d"),
                        "ImpTotConc": 0,
                        "ImpNeto": invoice_data.get("subtotal", 0),
                        "ImpOpEx": 0,
                        "ImpTrib": 0,
                        "ImpIVA": invoice_data.get("iva", 0),
                        "MonId": "PES",
                        "MonCotiz": 1,
                        "Iva": {
                            "AlicIva": [
                                {
                                    "Id": invoice_data.get("iva_tipo", 5),
                                    "BaseImp": invoice_data.get("subtotal", 0),
                                    "Importe": invoice_data.get("iva", 0)
                                }
                            ]
                        }
                    }
                }
            }
        }
    
    def request_cae(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Solicita CAE a ARCA via WSFE"""
        auth = self.wsaa_client.get_valid_token()
        
        if not auth or not auth.get("success"):
            return {
                "success": False,
                "error": "No se pudo obtener token de autenticación",
                "details": auth
            }
        
        try:
            wsfe_url = self.wsaa_client.get_wsfe_url()
            logger.info(f"Solicitando CAE a WSFE: {wsfe_url}")
            
            fe_request = self._build_fe_cae_request(invoice_data)
            
            soap_body = self._build_soap_request(auth, fe_request)
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': ''
            }
            
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    wsfe_url,
                    content=soap_body,
                    headers=headers
                )
            
            result = self._parse_wsfe_response(response.text)
            return result
            
        except Exception as e:
            logger.error(f"Error solicitando CAE: {str(e)}")
            return {
                "success": False,
                "error": f"Error WSFE: {str(e)}"
            }
    
    def _build_soap_request(self, auth: Dict[str, Any], fe_data: Dict[str, Any]) -> str:
        """Construye el envelope SOAP para WSFE siguiendo la API de AFIP"""
        token = auth.get("token", "")
        sign = auth.get("sign", "")
        cuit = self.wsaa_client.CUIT
        
        # Estructura según la API de AFIP
        # El Auth va dentro del FeCAEReq, no en el header SOAP
        request_data = {
            "Auth": {
                "Token": token,
                "Sign": sign,
                "Cuit": int(cuit)
            },
            "FeCAEReq": fe_data.get("FeCAEReq")
        }
        
        request_json = json.dumps(request_data)
        
        # Usar namespace soap y ns1 correctamente
        soap = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:ns1="http://ar.gov.afip.dif.fev1/">
    <soap:Header/>
    <soap:Body>
        <ns1:FECAESolicitar>
            <ns1:FeCAEReq>{request_json}</ns1:FeCAEReq>
        </ns1:FECAESolicitar>
    </soap:Body>
</soap:Envelope>'''
        
        return soap
    
    def _parse_wsfe_response(self, response_xml: str) -> Dict[str, Any]:
        """Parsea la respuesta XML de WSFE"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response_xml)
            
            cae_elem = root.find('.//CAE')
            cae_vto_elem = root.find('.//CAEFchVto')
            resultado_elem = root.find('.//Resultado')
            errores_elem = root.find('.//Errores')
            
            cae = cae_elem.text if cae_elem is not None else None
            cae_vto = cae_vto_elem.text if cae_vto_elem is not None else None
            resultado = resultado_elem.text if resultado_elem is not None else None
            
            errores = []
            if errores_elem is not None:
                for err in errores_elem.findall('.//Err'):
                    code_elem = err.find('Code')
                    errores.append({
                        "code": code_elem.text if code_elem is not None else "0",
                        "msg": err.text if err.text else "Error desconocido"
                    })
            
            if resultado == "A" and cae:
                return {
                    "success": True,
                    "CAE": cae,
                    "CAE_vto": cae_vto,
                    "resultado": resultado,
                    "observaciones": []
                }
            else:
                return {
                    "success": False,
                    "CAE": cae,
                    "CAE_vto": cae_vto,
                    "resultado": resultado,
                    "errores": errores
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error parseando respuesta WSFE: {str(e)}",
                "raw_response": response_xml[:500]
            }
    
    def get_last_invoice_number(self, punto_venta: int, tipo_comprobante: int) -> Dict[str, Any]:
        """Obtiene el último número de comprobante autorizado"""
        auth = self.wsaa_client.get_valid_token()
        
        if not auth or not auth.get("success"):
            return {
                "success": False,
                "error": "No se pudo obtener token"
            }
        
        try:
            wsfe_url = self.wsaa_client.get_wsfe_url()
            
            soap_body = f'''<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" 
                   xmlns:ns1="http://ar.gov.afip.dif.fev1/">
    <SOAP-ENV:Header>
        <ns1:Auth>
            <Token>{auth.get("token")}</Token>
            <Sign>{auth.get("sign")}</Sign>
            <Cuit>{self.wsaa_client.CUIT}</Cuit>
        </ns1:Auth>
    </SOAP-ENV:Header>
    <SOAP-ENV:Body>
        <ns1:FECompTotXRequest>
            <PtoVta>{punto_venta}</PtoVta>
            <CbteTipo>{tipo_comprobante}</CbteTipo>
        </ns1:FECompTotXRequest>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>'''
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    wsfe_url,
                    content=soap_body,
                    headers={'Content-Type': 'text/xml; charset=utf-8'}
                )
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            
            nro_elem = root.find('.//Nro')
            nro = int(nro_elem.text) if nro_elem is not None else 0
            
            return {
                "success": True,
                "ultimo_numero": nro
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


def create_wsaa_client(config: dict) -> Optional[WSAAClient]:
    """Factory para crear cliente WSAA"""
    if not config.get("cert_path") or not config.get("key_path") or not config.get("CUIT"):
        return None
    
    if not os.path.exists(config["cert_path"]) or not os.path.exists(config["key_path"]):
        return None
    
    return WSAAClient(
        cert_path=config["cert_path"],
        key_path=config["key_path"],
        CUIT=config["CUIT"],
        ambiente=config.get("ambiente", "testing")
    )


def create_wsfe_client(config: dict) -> Optional[WSFEClient]:
    """Factory para crear cliente WSFE"""
    wsaa = create_wsaa_client(config)
    if not wsaa:
        return None
    return WSFEClient(wsaa)
