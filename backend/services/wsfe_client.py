import os
import json
import base64
import hashlib
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import pkcs12
import logging
import httpx
from services.key_encrypt import decrypt_key

logger = logging.getLogger(__name__)


class WSAAClient:
    """Cliente para WSAA (Autenticación) de ARCA/AFIP"""
    
    # URLs de homologación (testing) - ARCA
    WSAA_URL_TEST = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
    WSAA_URL_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
    
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
        """Carga certificado y clave privada desde archivos PEM.
        
        La clave privada se desencripta automáticamente si está cifrada.
        """
        with open(self.cert_path, "rb") as cert_file:
            cert_data = cert_file.read()
        
        with open(self.key_path, "rb") as key_file:
            key_data = key_file.read()
        
        cert = x509.load_pem_x509_certificate(cert_data)
        
        # Intentar desencriptar (si está cifrada con key_encrypt)
        try:
            key_data = decrypt_key(key_data)
        except Exception:
            # Si falla, asumir que es PEM sin encriptar (migración/legacy)
            pass
        
        key = serialization.load_pem_private_key(key_data, password=None)
        
        return cert, key
    
    def _create_tra(self) -> str:
        """Crea el Ticket de Requerimiento de Acceso (TRA)"""
        unique_id = str(int(datetime.now(timezone.utc).timestamp()))
        now = datetime.now(timezone.utc)
        expiration = now + timedelta(hours=12)
        # ARCA espera formato ISO 8601 con timezone
        generation_time = now.strftime("%Y-%m-%dT%H:%M:%S%z")
        expiration_time = expiration.strftime("%Y-%m-%dT%H:%M:%S%z")
        # Asegurar formato con dos puntos en timezone (ej: -03:00)
        generation_time = generation_time[:-2] + ":" + generation_time[-2:]
        expiration_time = expiration_time[:-2] + ":" + expiration_time[-2:]
        
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
        """Firma el TRA con el certificado usando OpenSSL (PKCS#7/CMS).

        Usa OpenSSL vía subprocess porque la librería cryptography produce un
        formato PKCS#7 que WSAA rechaza (cms.sign.invalid).
        """
        import tempfile
        import subprocess
        
        tra_bytes = tra.encode('utf-8')
        
        # Escribir TRA a archivo temporal
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tra_file:
            tra_file.write(tra_bytes)
            tra_path = tra_file.name
        
        out_path = tra_path + '.cms'
        # Find openssl: check PATH first, fall back to Git for Windows path
        openssl = "openssl"
        git_openssl = r"C:\Program Files\Git\mingw64\bin\openssl.exe"
        if os.path.exists(git_openssl):
            openssl = git_openssl
        
        try:
            cmd = [
                openssl, 'smime', '-sign',
                '-in', tra_path,
                '-signer', self.cert_path,
                '-inkey', self.key_path,
                '-outform', 'DER',
                '-out', out_path,
                '-nodetach',  # WSAA espera CMS con datos incluidos
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='replace')
                logger.error(f"Error OpenSSL firmando TRA: {error_msg}")
                raise RuntimeError(f"OpenSSL signing failed: {error_msg}")
            
            with open(out_path, 'rb') as f:
                cms_der = f.read()
            
            cms_b64 = base64.b64encode(cms_der).decode('utf-8')
            logger.info(f"Firma PKCS#7 creada via OpenSSL ({len(cms_b64)} chars)")
            return cms_b64
            
        finally:
            for p in [tra_path, out_path]:
                try:
                    os.unlink(p)
                except Exception:
                    pass
    
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
            import urllib.error
            
            req = urllib.request.Request(
                wsaa_url,
                data=soap_xml.encode('utf-8'),
                headers={
                    'Content-Type': 'text/xml; charset=utf-8',
                    'SOAPAction': 'http://ar.gov.afip.wsaa/loginCms'
                }
            )
            
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    response_xml = response.read().decode('utf-8')
                    response_status = response.status
            except urllib.error.HTTPError as e:
                # WSAA devuelve 500 con SOAP Fault — leer el body para el detalle
                body = e.read().decode('utf-8', errors='replace')
                
                # coe.alreadyAuthenticated = el token ya fue emitido y sigue vigente
                if "coe.alreadyAuthenticated" in body:
                    logger.info("WSAA: CEE ya posee TA valido (alreadyAuthenticated)")
                    return {"success": True, "message": "Token ya existe (alreadyAuthenticated)"}
                
                logger.error(f"WSAA HTTP {e.code}: {body[:500]}")
                return {
                    "success": False,
                    "error": f"WSAA Error: HTTP {e.code}",
                    "details": body
                }
            
            if response_status != 200:
                # coe.alreadyAuthenticated es normal en testing — el token ya existe y es válido
                if "coe.alreadyAuthenticated" in response_xml:
                    logger.info("WSAA: el CEE ya posee un TA válido (alreadyAuthenticated en testing)")
                    return {"success": True, "message": "Token ya existe (alreadyAuthenticated en testing)"}
                    
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
                self._token_expiration = datetime.now(timezone.utc) + timedelta(hours=12)
                
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
            logger.error(f"Error obteniendo token WSAA: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Error WSAA: {str(e)}"
            }
    
    def get_valid_token(self) -> Optional[Dict[str, Any]]:
        """Obtiene un token válido, reutilizando si aún es vigente"""
        if self._token and self._token_expiration:
            if datetime.now(timezone.utc) < self._token_expiration:
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
        """Construye el request para FECAESolicitar según WSDL de ARCA.

        Retorna un dict con los datos; _build_soap_request lo convierte a XML nativo.
        """
        cbte_tipo = invoice_data.get("tipo_comprobante", 6)
        pto_vta = invoice_data.get("punto_venta", 1)
        cbte_desde = invoice_data.get("cbte_desde", 1)
        cbte_hasta = invoice_data.get("cbte_hasta", 1)
        subtotal = invoice_data.get("subtotal", 0)
        iva_importe = invoice_data.get("iva", 0)
        total = subtotal + iva_importe

        return {
            "FeCabReq": {
                "CantReg": 1,
                "PtoVta": pto_vta,
                "CbteTipo": cbte_tipo,
            },
            "FeDetReq": [{
                "Concepto": invoice_data.get("concepto", 1),  # 1=Productos, 2=Servicios, 3=Ambos
                "DocTipo": invoice_data.get("cliente_tipo_doc", 96),
                "DocNro": invoice_data.get("cliente_cuit", "0"),
                "CbteDesde": cbte_desde,
                "CbteHasta": cbte_hasta,
                "CbteFch": datetime.now().strftime("%Y%m%d"),
                "ImpTotal": round(total, 2),
                "ImpTotConc": 0,
                "ImpNeto": round(subtotal, 2),
                "ImpOpEx": 0,
                "ImpTrib": 0,
                "ImpIVA": round(iva_importe, 2),
                "MonId": "PES",
                "MonCotiz": 1,
                "Iva": [{
                    "Id": invoice_data.get("iva_tipo", 5),
                    "BaseImp": round(subtotal, 2),
                    "Importe": round(iva_importe, 2),
                }],
            }],
        }
    
    def request_cae(self, invoice_data: Dict[str, Any], retry: bool = True) -> Dict[str, Any]:
        """Solicita CAE a ARCA via WSFE con auto-retry al renovar token.

        Si el token expiró durante la llamada, renueva automáticamente
        y reintenta una vez.

        Args:
            invoice_data: Datos del comprobante para el request SOAP.
            retry: Si debe reintentar al fallar por autenticación (default True).

        Returns:
            Dict con resultado de la solicitud.
        """
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
                'SOAPAction': 'http://ar.gov.afip.dif.fev1/FECAESolicitar'
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    wsfe_url,
                    content=soap_body,
                    headers=headers
                )

            result = self._parse_wsfe_response(response.text)

            # Auto-retry on auth errors: renovar token y reintentar una vez
            if retry and not result.get("success"):
                should_retry = False
                errores = result.get("errores", [])
                for err in errores:
                    code = str(err.get("code", ""))
                    # Códigos 600-609 son errores de autorización/autenticación ARCA
                    if code in ("600", "601", "602", "603", "604", "605", "606", "607", "608", "609"):
                        should_retry = True
                        break
                    # Error 10001 también puede ser token expirado (WSAA devuelve este código)
                    if code == "10001":
                        should_retry = True
                        break

                if should_retry:
                    logger.info("Token expirado o error de autenticación — renovando y reintentando...")
                    renewed = self.wsaa_client.request_token()
                    if renewed.get("success"):
                        soap_body_retry = self._build_soap_request(renewed, fe_request)
                        with httpx.Client(timeout=60.0) as client:
                            response = client.post(
                                wsfe_url,
                                content=soap_body_retry,
                                headers=headers
                            )
                        result = self._parse_wsfe_response(response.text)
                        logger.info(f"Reintento WSFE luego de renovar token: {'OK' if result.get('success') else 'Falló'}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP solicitando CAE: {e.response.status_code} — {e.response.text[:300]}")
            return {
                "success": False,
                "error": f"Error WSFE HTTP {e.response.status_code}",
                "details": e.response.text[:500]
            }
        except httpx.TimeoutException as e:
            logger.error(f"Timeout solicitando CAE: {str(e)}")
            return {
                "success": False,
                "error": "Timeout de conexión con ARCA — el servicio puede no estar disponible"
            }
        except Exception as e:
            logger.error(f"Error solicitando CAE: {str(e)}")
            return {
                "success": False,
                "error": f"Error WSFE: {str(e)}"
            }
    
    @staticmethod
    def _xml_esc(s) -> str:
        """XML-escape un valor string"""
        if s is None:
            return ""
        s = str(s)
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def _build_soap_request(self, auth: Dict[str, Any], fe_data: Dict[str, Any]) -> str:
        """Construye el envelope SOAP para WSFE con XML nativo según WSDL.

        Sigue la estructura exacta del WSDL de ARCA/AFIP:
        http://ar.gov.afip.dif.FEV1/ (namespace exacto, mayúsculas).
        """
        token = auth.get("token", "")
        sign = auth.get("sign", "")
        cuit = self.wsaa_client.CUIT

        # Build auth XML
        fe_cab_req = fe_data.get("FeCabReq", {})
        fe_det_req_list = fe_data.get("FeDetReq", [])

        _xml_esc = self._xml_esc

        def _dict_to_xml(d, ns=""):
            """Convierte un dict plano a XML elements.
            Para listas, usa el nombre de la clave como tag del elemento hijo.
            """
            xml_parts = []
            for key, val in d.items():
                tag = f"{ns}{key}" if ns else key
                if isinstance(val, dict):
                    xml_parts.append(f"<{tag}>{_dict_to_xml(val, ns)}</{tag}>")
                elif isinstance(val, list):
                    for item in val:
                        child_tag = key.rstrip("s") if key.endswith("s") else key  # Iva -> Iva, FeDetReq -> FECAEDetRequest
                        # Map list names to their child element names per WSDL
                        child_map = {
                            "FeDetReq": "FECAEDetRequest",
                            "Iva": "AlicIva",
                        }
                        child_name = child_map.get(key, child_tag)
                        child_tag_ns = f"{ns}{child_name}" if ns else child_name
                        if isinstance(item, dict):
                            xml_parts.append(f"<{child_tag_ns}>{_dict_to_xml(item, ns)}</{child_tag_ns}>")
                        else:
                            xml_parts.append(f"<{child_tag_ns}>{_xml_esc(item)}</{child_tag_ns}>")
                else:
                    xml_parts.append(f"<{tag}>{_xml_esc(val)}</{tag}>")
            return "".join(xml_parts)

        NS = "ns1:"  # namespace prefix

        auth_xml = (
            f"<{NS}Auth>"
            f"<{NS}Token>{_xml_esc(token)}</{NS}Token>"
            f"<{NS}Sign>{_xml_esc(sign)}</{NS}Sign>"
            f"<{NS}Cuit>{_xml_esc(cuit)}</{NS}Cuit>"
            f"</{NS}Auth>"
        )

        fe_cab_req_xml = f"<{NS}FeCabReq>{_dict_to_xml(fe_cab_req, NS)}</{NS}FeCabReq>"

        fe_det_req_xml = ""
        for det in fe_det_req_list:
            fe_det_req_xml += f"<{NS}FECAEDetRequest>{_dict_to_xml(det, NS)}</{NS}FECAEDetRequest>"
        if fe_det_req_xml:
            fe_det_req_xml = f"<{NS}FeDetReq>{fe_det_req_xml}</{NS}FeDetReq>"

        soap = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:ns1="http://ar.gov.afip.dif.FEV1/">
    <soap:Header/>
    <soap:Body>
        <ns1:FECAESolicitar>
            {auth_xml}
            <ns1:FeCAEReq>
                {fe_cab_req_xml}
                {fe_det_req_xml}
            </ns1:FeCAEReq>
        </ns1:FECAESolicitar>
    </soap:Body>
</soap:Envelope>'''

        logger.debug(f"SOAP Request XML:\n{soap}")
        return soap
    
    def _parse_wsfe_response(self, response_xml: str) -> Dict[str, Any]:
        """Parsea la respuesta XML de WSFE, incluyendo SOAP Faults"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response_xml)
            
            # Detectar SOAP Fault (error de infraestructura, no de negocio)
            fault_elem = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
            if fault_elem is None:
                # Try without namespace
                fault_elem = root.find('.//Fault')
            if fault_elem is not None:
                fault_code = fault_elem.find('faultcode')
                fault_string = fault_elem.find('faultstring')
                detail = fault_elem.find('detail')
                return {
                    "success": False,
                    "error": f"SOAP Fault: {fault_string.text if fault_string is not None else 'Unknown'}",
                    "fault_code": fault_code.text if fault_code is not None else "",
                    "errores": [{
                        "code": fault_code.text if fault_code is not None else "SOAP",
                        "msg": fault_string.text if fault_string is not None else "Error SOAP"
                    }],
                    "raw_response": response_xml[:500]
                }
            
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
                    msg_elem = err.find('Msg')
                    errores.append({
                        "code": code_elem.text if code_elem is not None else "0",
                        "msg": msg_elem.text if msg_elem is not None else (err.text or "Error desconocido")
                    })
            
            # También buscar Observaciones (no bloqueante, pero informativo)
            obs = []
            obs_elem = root.find('.//Observaciones')
            if obs_elem is not None:
                for ob in obs_elem.findall('.//Obs'):
                    code_elem = ob.find('Code')
                    msg_elem = ob.find('Msg')
                    if code_elem is not None or msg_elem is not None:
                        obs.append({
                            "code": code_elem.text if code_elem is not None else "",
                            "msg": msg_elem.text if msg_elem is not None else ""
                        })
            
            if resultado == "A" and cae:
                return {
                    "success": True,
                    "CAE": cae,
                    "CAE_vto": cae_vto,
                    "resultado": resultado,
                    "observaciones": obs
                }
            else:
                return {
                    "success": False,
                    "CAE": cae,
                    "CAE_vto": cae_vto,
                    "resultado": resultado,
                    "errores": errores,
                    "observaciones": obs
                }
                
        except ET.ParseError as e:
            return {
                "success": False,
                "error": f"Error parseando XML respuesta WSFE: {str(e)}",
                "raw_response": response_xml[:500]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error parseando respuesta WSFE: {str(e)}",
                "raw_response": response_xml[:500]
            }
    
    # ------------------------------------------------------------------
    # FECompUltimoAutorizado
    # ------------------------------------------------------------------
    def _build_ultimo_autorizado_request(self, auth: Dict[str, Any], pto_vta: int, cbte_tipo: int) -> str:
        """Construye el SOAP envelope para FECompUltimoAutorizado.

        Args:
            auth: Dict con Token, Sign del WSAA.
            pto_vta: Número de punto de venta.
            cbte_tipo: Código de tipo de comprobante AFIP.

        Returns:
            String XML del SOAP envelope listo para POST.
        """
        token = self._xml_esc(auth.get("token", ""))
        sign = self._xml_esc(auth.get("sign", ""))
        cuit = self._xml_esc(self.wsaa_client.CUIT)

        soap = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:ns1="http://ar.gov.afip.dif.FEV1/">
    <soap:Header/>
    <soap:Body>
        <ns1:FECompUltimoAutorizado>
            <ns1:Auth>
                <ns1:Token>{token}</ns1:Token>
                <ns1:Sign>{sign}</ns1:Sign>
                <ns1:Cuit>{cuit}</ns1:Cuit>
            </ns1:Auth>
            <ns1:FeCompUltimoAutorizadoReq>
                <ns1:PtoVta>{pto_vta}</ns1:PtoVta>
                <ns1:CbteTipo>{cbte_tipo}</ns1:CbteTipo>
            </ns1:FeCompUltimoAutorizadoReq>
        </ns1:FECompUltimoAutorizado>
    </soap:Body>
</soap:Envelope>'''
        return soap

    def _parse_ultimo_autorizado_response(self, response_xml: str) -> Dict[str, Any]:
        """Parsea la respuesta XML de FECompUltimoAutorizado.

        Args:
            response_xml: Respuesta XML cruda de ARCA.

        Returns:
            Dict con success, ultimo_numero en éxito;
            success=False con error/errores en fallo.
        """
        NS_FEV1 = "http://ar.gov.afip.dif.FEV1/"

        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response_xml)

            # --- SOAP Fault ---
            fault_elem = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
            if fault_elem is not None:
                fault_string = fault_elem.find('faultcode')
                return {
                    "success": False,
                    "error": f"SOAP Fault: {fault_string.text if fault_string is not None else 'Unknown'}",
                    "errores": [{
                        "code": fault_string.text if fault_string is not None else "SOAP",
                        "msg": "Error SOAP en FECompUltimoAutorizado"
                    }],
                }

            # --- CbteNro (éxito) ---
            cbte_nro = root.find(f'.//{{{NS_FEV1}}}CbteNro')

            # Fallback: buscar sin namespace (algunos entornos testing omiten xmlns)
            if cbte_nro is None:
                cbte_nro = root.find('.//CbteNro')

            if cbte_nro is not None and cbte_nro.text is not None:
                return {
                    "success": True,
                    "ultimo_numero": int(cbte_nro.text),
                }

            # --- Errores de negocio ---
            errores = []
            for err in root.findall(f'.//{{{NS_FEV1}}}Err'):
                code_el = err.find(f'{{{NS_FEV1}}}Code')
                msg_el = err.find(f'{{{NS_FEV1}}}Msg')
                if code_el is not None or msg_el is not None:
                    errores.append({
                        "code": code_el.text if code_el is not None else "0",
                        "msg": msg_el.text if msg_el is not None else "Error desconocido",
                    })

            # Fallback sin namespace
            if not errores:
                for err in root.findall('.//Err'):
                    code_el = err.find('Code')
                    msg_el = err.find('Msg')
                    if code_el is not None or msg_el is not None:
                        errores.append({
                            "code": code_el.text if code_el is not None else "0",
                            "msg": msg_el.text if msg_el is not None else "Error desconocido",
                        })

            if errores:
                return {
                    "success": False,
                    "error": f"ARCA error: {errores[0]['code']} — {errores[0]['msg']}",
                    "errores": errores,
                }

            return {
                "success": False,
                "error": "No se encontró CbteNro en la respuesta de FECompUltimoAutorizado",
            }

        except ET.ParseError as e:
            return {
                "success": False,
                "error": f"Error parseando XML respuesta FECompUltimoAutorizado: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error parseando FECompUltimoAutorizado: {str(e)}",
            }

    def get_ultimo_autorizado(self, pto_vta: int, cbte_tipo: int, retry: bool = True) -> Dict[str, Any]:
        """FECompUltimoAutorizado — último nro autorizado por ARCA para PV+tipo.

        Llama al verbo WSDL FECompUltimoAutorizado con Auth + PtoVta + CbteTipo.
        Si el token expira, renueva automáticamente y reintenta una vez.

        Args:
            pto_vta: Número de punto de venta (ej: 1).
            cbte_tipo: Código AFIP de tipo de comprobante (ej: 6 para Factura B).
            retry: Si debe reintentar al fallar por autenticación (default True).

        Returns:
            {"success": True, "ultimo_numero": int} en éxito.
            {"success": False, "error": str, ...} en fallo.
        """
        auth = self.wsaa_client.get_valid_token()

        if not auth or not auth.get("success"):
            return {
                "success": False,
                "error": "No se pudo obtener token de autenticación",
                "details": auth,
            }

        try:
            wsfe_url = self.wsaa_client.get_wsfe_url()
            logger.info(f"FECompUltimoAutorizado — PV={pto_vta} Tipo={cbte_tipo} → {wsfe_url}")

            soap_body = self._build_ultimo_autorizado_request(auth, pto_vta, cbte_tipo)

            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://ar.gov.afip.dif.FEV1/FECompUltimoAutorizado',
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.post(wsfe_url, content=soap_body, headers=headers)

            result = self._parse_ultimo_autorizado_response(response.text)

            # Auto-retry on auth errors: renovar token y reintentar una vez
            if retry and not result.get("success"):
                should_retry = False
                errores = result.get("errores", [])
                for err in errores:
                    code = str(err.get("code", ""))
                    if code in (
                        "600", "601", "602", "603", "604", "605",
                        "606", "607", "608", "609", "10001",
                    ):
                        should_retry = True
                        break

                if should_retry:
                    logger.info(
                        "Token expirado en FECompUltimoAutorizado — "
                        "renovando y reintentando..."
                    )
                    renewed = self.wsaa_client.request_token()
                    if renewed.get("success"):
                        soap_body_retry = self._build_ultimo_autorizado_request(
                            renewed, pto_vta, cbte_tipo
                        )
                        with httpx.Client(timeout=30.0) as client:
                            response = client.post(
                                wsfe_url, content=soap_body_retry, headers=headers
                            )
                        result = self._parse_ultimo_autorizado_response(response.text)
                        logger.info(
                            f"Reintento FECompUltimoAutorizado: "
                            f"{'OK' if result.get('success') else 'Falló'}"
                        )

            return result

        except httpx.TimeoutException as e:
            logger.error(f"Timeout en FECompUltimoAutorizado: {str(e)}")
            return {
                "success": False,
                "error": "Timeout de conexión con ARCA — FECompUltimoAutorizado no disponible",
            }
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Error HTTP en FECompUltimoAutorizado: "
                f"{e.response.status_code} — {e.response.text[:300]}"
            )
            return {
                "success": False,
                "error": f"Error HTTP {e.response.status_code} en FECompUltimoAutorizado",
            }
        except Exception as e:
            logger.error(f"Error en FECompUltimoAutorizado: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Error FECompUltimoAutorizado: {str(e)}",
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
