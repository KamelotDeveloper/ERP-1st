"""Unit tests for FECompUltimoAutorizado — WSFEClient.get_ultimo_autorizado().

Tests cover:
1. SOAP XML builder produces correct <PtoVta> and <CbteTipo> tags
2. Response parser extracts <CbteNro> correctly
3. Fallback on timeout/error returns success=false
"""

from unittest.mock import MagicMock, patch
import pytest
import xml.etree.ElementTree as ET

from services.wsfe_client import WSFEClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wsfe_client():
    """WSFEClient with a mocked WSAAClient (no real cert/network needed)."""
    wsaa = MagicMock()
    wsaa.get_valid_token.return_value = {
        "success": True,
        "token": "test_token_value",
        "sign": "test_sign_value",
    }
    wsaa.CUIT = "20305060708"
    wsaa.get_wsfe_url.return_value = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx"
    return WSFEClient(wsaa)


# ===========================================================================
# 1. SOAP XML builder
# ===========================================================================

class TestBuildUltimoAutorizadoRequest:
    """Verify the SOAP XML structure for FECompUltimoAutorizado."""

    def test_contains_fecompultimoautorizado_verb(self, wsfe_client):
        """The root SOAP body element must be FECompUltimoAutorizado."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_ultimo_autorizado_request(auth, 1, 6)
        assert "<ns1:FECompUltimoAutorizado>" in xml
        assert "</ns1:FECompUltimoAutorizado>" in xml

    def test_contains_auth_block(self, wsfe_client):
        """Auth block with Token, Sign, Cuit must be present."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_ultimo_autorizado_request(auth, 1, 6)
        assert "<ns1:Auth>" in xml
        assert "<ns1:Token>test_token_value</ns1:Token>" in xml
        assert "<ns1:Sign>test_sign_value</ns1:Sign>" in xml
        assert "<ns1:Cuit>20305060708</ns1:Cuit>" in xml

    def test_contains_fecompultimoautorizadoreq(self, wsfe_client):
        """FeCompUltimoAutorizadoReq block must be present."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_ultimo_autorizado_request(auth, 1, 6)
        assert "<ns1:FeCompUltimoAutorizadoReq>" in xml
        assert "</ns1:FeCompUltimoAutorizadoReq>" in xml

    def test_pto_vta_tag_with_value(self, wsfe_client):
        """<PtoVta> tag must contain the PV number."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_ultimo_autorizado_request(auth, 42, 6)
        assert "<ns1:PtoVta>42</ns1:PtoVta>" in xml

    def test_cbte_tipo_tag_with_value(self, wsfe_client):
        """<CbteTipo> tag must contain the comprobante type code."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_ultimo_autorizado_request(auth, 1, 11)
        assert "<ns1:CbteTipo>11</ns1:CbteTipo>" in xml

    def test_full_xml_is_valid_soap_envelope(self, wsfe_client):
        """The generated XML must be parseable by ElementTree."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_ultimo_autorizado_request(auth, 1, 6)
        root = ET.fromstring(xml)
        ns_soap = "http://schemas.xmlsoap.org/soap/envelope/"
        assert root.tag == f"{{{ns_soap}}}Envelope"

    def test_xml_escape_token(self, wsfe_client):
        """XML-special chars in Token must be escaped."""
        wsfe_client.wsaa_client.get_valid_token.return_value = {
            "success": True,
            "token": 'token<with>&special"chars',
            "sign": "sign",
        }
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_ultimo_autorizado_request(auth, 1, 6)
        assert "&lt;" in xml
        assert "&amp;" in xml
        assert "<" not in xml.split("<ns1:Token>")[1].split("</ns1:Token>")[0]


# ===========================================================================
# 2. Response parser
# ===========================================================================

class TestParseUltimoAutorizadoResponse:
    """Verify response parsing extracts <CbteNro> correctly."""

    SUCCESS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FECompUltimoAutorizadoResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FECompUltimoAutorizadoResult>
        <PtoVta>1</PtoVta>
        <CbteTipo>6</CbteTipo>
        <CbteNro>42</CbteNro>
      </FECompUltimoAutorizadoResult>
    </FECompUltimoAutorizadoResponse>
  </soap:Body>
</soap:Envelope>"""

    def test_parses_cbte_nro_success(self, wsfe_client):
        """Happy path: response with CbteNro=42 returns ultimo_numero=42."""
        result = wsfe_client._parse_ultimo_autorizado_response(self.SUCCESS_XML)
        assert result["success"] is True
        assert result["ultimo_numero"] == 42

    def test_parses_large_number(self, wsfe_client):
        """CbteNro with large value (5+ digits) is parsed correctly."""
        xml = self.SUCCESS_XML.replace("<CbteNro>42</CbteNro>", "<CbteNro>99999</CbteNro>")
        result = wsfe_client._parse_ultimo_autorizado_response(xml)
        assert result["success"] is True
        assert result["ultimo_numero"] == 99999

    def test_parses_zero(self, wsfe_client):
        """CbteNro=0 (first comprobante) is handled."""
        xml = self.SUCCESS_XML.replace("<CbteNro>42</CbteNro>", "<CbteNro>0</CbteNro>")
        result = wsfe_client._parse_ultimo_autorizado_response(xml)
        assert result["success"] is True
        assert result["ultimo_numero"] == 0

    def test_soap_fault_returns_error(self, wsfe_client):
        """SOAP Fault in response returns success=False with error."""
        fault_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Server</faultcode>
      <faultstring>Server Error</faultstring>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""
        result = wsfe_client._parse_ultimo_autorizado_response(fault_xml)
        assert result["success"] is False
        assert "SOAP Fault" in result.get("error", "")

    def test_missing_cbte_nro_returns_error(self, wsfe_client):
        """Response without CbteNro returns success=False."""
        no_nro_xml = self.SUCCESS_XML.replace("<CbteNro>42</CbteNro>", "")
        result = wsfe_client._parse_ultimo_autorizado_response(no_nro_xml)
        assert result["success"] is False

    def test_arca_errores_block(self, wsfe_client):
        """ARCA errors block (Errores/Err) returns success=False with codes."""
        error_xml = self.SUCCESS_XML.replace(
            "<CbteNro>42</CbteNro>",
            "<Errores><Err><Code>10001</Code><Msg>Token expirado</Msg></Err></Errores>",
        )
        result = wsfe_client._parse_ultimo_autorizado_response(error_xml)
        assert result["success"] is False
        assert len(result.get("errores", [])) > 0
        assert result["errores"][0]["code"] == "10001"

    def test_invalid_xml_returns_error(self, wsfe_client):
        """Garbage XML returns success=False."""
        result = wsfe_client._parse_ultimo_autorizado_response("not valid xml {{{")
        assert result["success"] is False
        assert "Error parseando" in result.get("error", "")


# ===========================================================================
# 3. Fallback on timeout/error
# ===========================================================================

class TestGetUltimoAutorizadoFallback:
    """Verify get_ultimo_autorizado handles network errors gracefully."""

    def test_timeout_returns_success_false(self, wsfe_client):
        """httpx timeout raises TimeoutException → success=False."""
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.side_effect = TimeoutError("Connection timed out")

            result = wsfe_client.get_ultimo_autorizado(1, 6)

        assert result["success"] is False
        assert "error" in result

    def test_network_error_returns_success_false(self, wsfe_client):
        """Generic HTTP error returns success=False."""
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.side_effect = ConnectionError("Connection refused")

            result = wsfe_client.get_ultimo_autorizado(1, 6)

        assert result["success"] is False
        assert "error" in result

    def test_auth_failure_returns_success_false(self, wsfe_client):
        """If WSAA token cannot be obtained, returns error immediately."""
        wsfe_client.wsaa_client.get_valid_token.return_value = {
            "success": False,
            "error": "Token expired",
        }
        result = wsfe_client.get_ultimo_autorizado(1, 6)
        assert result["success"] is False
        assert "token" in result.get("error", "").lower()
