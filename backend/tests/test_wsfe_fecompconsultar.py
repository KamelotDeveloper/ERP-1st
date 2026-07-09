"""Unit tests for FECompConsultar — WSFEClient.consultar_comprobante().

Tests cover:
1. SOAP XML builder produces correct CbteTipo, CbteNro, PtoVta tags
2. Response parser extracts all fields from FeCompConsResponse
3. Error handling: Errores block, SOAP Fault, missing fields, XML parse errors
4. Network fallback: timeout, HTTP error, auth failure
5. Auto-retry on auth error codes
"""

from unittest.mock import MagicMock, patch
import httpx
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

class TestBuildFeCompConsultarRequest:
    """Verify the SOAP XML structure for FECompConsultar."""

    def test_contains_fecompconsultar_verb(self, wsfe_client):
        """The root SOAP body element must be FECompConsultar."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_fecompconsultar_request(auth, 6, 42, 1)
        assert "<ns1:FECompConsultar>" in xml
        assert "</ns1:FECompConsultar>" in xml

    def test_contains_auth_block(self, wsfe_client):
        """Auth block with Token, Sign, Cuit must be present."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_fecompconsultar_request(auth, 6, 42, 1)
        assert "<ns1:Auth>" in xml
        assert "<ns1:Token>test_token_value</ns1:Token>" in xml
        assert "<ns1:Sign>test_sign_value</ns1:Sign>" in xml
        assert "<ns1:Cuit>20305060708</ns1:Cuit>" in xml

    def test_contains_fecompconsreq_block(self, wsfe_client):
        """FeCompConsReq block must be present."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_fecompconsultar_request(auth, 6, 42, 1)
        assert "<ns1:FeCompConsReq>" in xml
        assert "</ns1:FeCompConsReq>" in xml

    def test_cbte_tipo_tag(self, wsfe_client):
        """<CbteTipo> tag must contain the comprobante type code."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_fecompconsultar_request(auth, 11, 42, 1)
        assert "<ns1:CbteTipo>11</ns1:CbteTipo>" in xml

    def test_cbte_nro_tag(self, wsfe_client):
        """<CbteNro> tag must contain the comprobante number."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_fecompconsultar_request(auth, 6, 99999, 1)
        assert "<ns1:CbteNro>99999</ns1:CbteNro>" in xml

    def test_pto_vta_tag(self, wsfe_client):
        """<PtoVta> tag must contain the point of sale number."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_fecompconsultar_request(auth, 6, 42, 42)
        assert "<ns1:PtoVta>42</ns1:PtoVta>" in xml

    def test_full_xml_is_valid_soap_envelope(self, wsfe_client):
        """The generated XML must be parseable by ElementTree."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_fecompconsultar_request(auth, 6, 42, 1)
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
        xml = wsfe_client._build_fecompconsultar_request(auth, 6, 42, 1)
        assert "&lt;" in xml
        assert "&amp;" in xml
        token_content = xml.split("<ns1:Token>")[1].split("</ns1:Token>")[0]
        assert "<" not in token_content


# ===========================================================================
# 2. Response parser
# ===========================================================================

class TestParseFeCompConsultarResponse:
    """Verify response parsing extracts fields from FeCompConsResponse."""

    SUCCESS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FECompConsultarResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FECompConsultarResult>
        <ResultGet>
          <Resultado>A</Resultado>
          <CodAutorizacion>62345678901234</CodAutorizacion>
          <EmisionTipo>CAE</EmisionTipo>
          <FchComprobante>20260708</FchComprobante>
          <FchVencimientoCAE>20261008</FchVencimientoCAE>
          <PtoVta>1</PtoVta>
          <CbteTipo>6</CbteTipo>
          <CbteNro>42</CbteNro>
          <ImpTotal>10000.00</ImpTotal>
          <ImpNeto>8264.46</ImpNeto>
          <ImpIVA>1735.54</ImpIVA>
        </ResultGet>
      </FECompConsultarResult>
    </FECompConsultarResponse>
  </soap:Body>
</soap:Envelope>"""

    def test_parses_all_fields_success(self, wsfe_client):
        """Happy path: response with Resultado=A returns all fields."""
        result = wsfe_client._parse_fecompconsultar_response(
            self.SUCCESS_XML
        )
        assert result["success"] is True
        data = result["data"]
        assert data["resultado"] == "A"
        assert data["codAutorizacion"] == "62345678901234"
        assert data["emisionTipo"] == "CAE"
        assert data["fchComprobante"] == "20260708"
        assert data["fchVencimientoCAE"] == "20261008"
        assert data["ptoVta"] == "1"
        assert data["cbteTipo"] == "6"
        assert data["cbteNro"] == "42"

    def test_rejected_comprobante(self, wsfe_client):
        """Rejected comprobante (Resultado=R) returns data without CAE."""
        xml = self.SUCCESS_XML.replace(">A<", ">R<", 1)
        result = wsfe_client._parse_fecompconsultar_response(xml)
        assert result["success"] is True
        assert result["data"]["resultado"] == "R"

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
        result = wsfe_client._parse_fecompconsultar_response(fault_xml)
        assert result["success"] is False
        assert "SOAP Fault" in result.get("error", "")

    def test_arca_errores_block(self, wsfe_client):
        """ARCA errors block (Errores/Err) returns success=False with codes."""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FECompConsultarResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FECompConsultarResult>
        <ResultGet>
          <Errores>
            <Err>
              <Code>10001</Code>
              <Msg>Comprobante no encontrado</Msg>
            </Err>
          </Errores>
        </ResultGet>
      </FECompConsultarResult>
    </FECompConsultarResponse>
  </soap:Body>
</soap:Envelope>"""
        result = wsfe_client._parse_fecompconsultar_response(error_xml)
        assert result["success"] is False
        assert len(result.get("errores", [])) > 0
        assert result["errores"][0]["code"] == "10001"

    def test_missing_resultado_returns_error(self, wsfe_client):
        """Response without Resultado returns success=False."""
        no_result_xml = self.SUCCESS_XML.replace(
            "<Resultado>A</Resultado>", ""
        )
        result = wsfe_client._parse_fecompconsultar_response(no_result_xml)
        assert result["success"] is False

    def test_invalid_xml_returns_error(self, wsfe_client):
        """Garbage XML returns success=False."""
        result = wsfe_client._parse_fecompconsultar_response(
            "not valid xml {{{"
        )
        assert result["success"] is False
        assert "Error parseando" in result.get("error", "")


# ===========================================================================
# 3. Orchestrator — network error handling
# ===========================================================================

class TestConsultarComprobanteFallback:
    """Verify consultar_comprobante handles network errors gracefully."""

    SUCCESS_RESPONSE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FECompConsultarResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FECompConsultarResult>
        <ResultGet>
          <Resultado>A</Resultado>
          <CodAutorizacion>62345678901234</CodAutorizacion>
          <EmisionTipo>CAE</EmisionTipo>
          <FchComprobante>20260708</FchComprobante>
          <PtoVta>1</PtoVta>
          <CbteTipo>6</CbteTipo>
          <CbteNro>42</CbteNro>
        </ResultGet>
      </FECompConsultarResult>
    </FECompConsultarResponse>
  </soap:Body>
</soap:Envelope>"""

    def test_timeout_returns_success_false(self, wsfe_client):
        """httpx timeout raises TimeoutException success=False."""
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.side_effect = httpx.TimeoutException(
                "Connection timed out"
            )

            result = wsfe_client.consultar_comprobante(6, 42, 1)

        assert result["success"] is False
        assert "error" in result

    def test_network_error_returns_success_false(self, wsfe_client):
        """httpx.HTTPStatusError returns success=False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.side_effect = httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=mock_response,
            )

            result = wsfe_client.consultar_comprobante(6, 42, 1)

        assert result["success"] is False
        assert "error" in result

    def test_auth_failure_returns_success_false(self, wsfe_client):
        """If WSAA token cannot be obtained, returns error immediately."""
        wsfe_client.wsaa_client.get_valid_token.return_value = {
            "success": False,
            "error": "Token expired",
        }
        result = wsfe_client.consultar_comprobante(6, 42, 1)
        assert result["success"] is False
        assert "token" in result.get("error", "").lower()

    def test_successful_request(self, wsfe_client):
        """Happy path: successful POST returns parsed data."""
        mock_response = MagicMock()
        mock_response.text = self.SUCCESS_RESPONSE_XML

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            result = wsfe_client.consultar_comprobante(6, 42, 1)

        assert result["success"] is True
        assert result["data"]["resultado"] == "A"
        assert result["data"]["codAutorizacion"] == "62345678901234"

    def test_auto_retry_on_auth_error(self, wsfe_client):
        """Auth error code (600) triggers token renewal and retry."""
        auth_error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FECompConsultarResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FECompConsultarResult>
        <ResultGet>
          <Errores>
            <Err>
              <Code>600</Code>
              <Msg>Token inválido</Msg>
            </Err>
          </Errores>
        </ResultGet>
      </FECompConsultarResult>
    </FECompConsultarResponse>
  </soap:Body>
</soap:Envelope>"""

        mock_response_auth_error = MagicMock()
        mock_response_auth_error.text = auth_error_xml

        mock_response_success = MagicMock()
        mock_response_success.text = self.SUCCESS_RESPONSE_XML

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            # First call fails with auth error, second succeeds
            mock_instance.post.side_effect = [
                mock_response_auth_error,
                mock_response_success,
            ]

            # Mock token renewal
            wsfe_client.wsaa_client.request_token.return_value = {
                "success": True,
                "token": "new_token",
                "sign": "new_sign",
            }

            result = wsfe_client.consultar_comprobante(6, 42, 1)

        assert result["success"] is True
        assert result["data"]["resultado"] == "A"
        # Verify token was renewed
        wsfe_client.wsaa_client.request_token.assert_called_once()

    def test_no_retry_when_disabled(self, wsfe_client):
        """When retry=False, auth error returns immediately without retry."""
        auth_error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FECompConsultarResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FECompConsultarResult>
        <ResultGet>
          <Errores>
            <Err>
              <Code>600</Code>
              <Msg>Token inválido</Msg>
            </Err>
          </Errores>
        </ResultGet>
      </FECompConsultarResult>
    </FECompConsultarResponse>
  </soap:Body>
</soap:Envelope>"""

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.return_value = MagicMock(
                text=auth_error_xml
            )

            result = wsfe_client.consultar_comprobante(
                6, 42, 1, retry=False
            )

        assert result["success"] is False
        mock_instance.post.assert_called_once()
        wsfe_client.wsaa_client.request_token.assert_not_called()
