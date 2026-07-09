"""Unit tests for FEDummy — WSFEClient.dummy().

Tests cover:
1. SOAP XML builder produces valid envelope without Auth block
2. Response parser extracts AppServerStatus, DbServerStatus, AuthServerStatus
3. Error handling: SOAP Fault, missing fields, XML parse errors
4. Network fallback: timeout, HTTP error
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
    wsaa.get_wsfe_url.return_value = \
        "https://wswhomo.afip.gov.ar/wsfev1/service.asmx"
    return WSFEClient(wsaa)


# ===========================================================================
# 1. SOAP XML builder
# ===========================================================================

class TestBuildDummyRequest:
    """Verify the SOAP XML structure for FEDummy."""

    def test_contains_fedummy_verb(self, wsfe_client):
        """The root SOAP body element must be FEDummy (self-closing)."""
        xml = wsfe_client._build_dummy_request()
        assert "<ns1:FEDummy/>" in xml

    def test_no_auth_block(self, wsfe_client):
        """FEDummy must NOT contain an Auth block."""
        xml = wsfe_client._build_dummy_request()
        assert "<ns1:Auth>" not in xml
        assert "Token" not in xml
        assert "Sign" not in xml
        assert "Cuit" not in xml

    def test_full_xml_is_valid_soap_envelope(self, wsfe_client):
        """The generated XML must be parseable by ElementTree."""
        xml = wsfe_client._build_dummy_request()
        root = ET.fromstring(xml)
        ns_soap = "http://schemas.xmlsoap.org/soap/envelope/"
        assert root.tag == f"{{{ns_soap}}}Envelope"

    def test_contains_soap_body(self, wsfe_client):
        """SOAP Body must be present."""
        xml = wsfe_client._build_dummy_request()
        assert "<soap:Body>" in xml
        assert "</soap:Body>" in xml

    def test_minimal_envelope(self, wsfe_client):
        """FEDummy envelope is minimal — no Auth block, only FEDummy inside Body."""
        xml = wsfe_client._build_dummy_request()
        # No extra request data inside Body
        assert "<ns1:FEDummy/>" in xml
        assert "<ns1:Auth>" not in xml
        assert "FeCompConsReq" not in xml


# ===========================================================================
# 2. Response parser
# ===========================================================================

class TestParseDummyResponse:
    """Verify response parsing extracts server status fields."""

    SUCCESS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEDummyResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEDummyResult>
        <AppServerStatus>OK</AppServerStatus>
        <DbServerStatus>OK</DbServerStatus>
        <AuthServerStatus>OK</AuthServerStatus>
      </FEDummyResult>
    </FEDummyResponse>
  </soap:Body>
</soap:Envelope>"""

    def test_parses_all_status_fields(self, wsfe_client):
        """Happy path: response with OK status returns all fields."""
        result = wsfe_client._parse_dummy_response(self.SUCCESS_XML)
        assert result["success"] is True
        data = result["data"]
        assert data["app_server"] == "OK"
        assert data["db_server"] == "OK"
        assert data["auth_server"] == "OK"

    def test_parses_error_status(self, wsfe_client):
        """Server error status is preserved (not filtered)."""
        xml = self.SUCCESS_XML.replace(
            "<DbServerStatus>OK</DbServerStatus>",
            "<DbServerStatus>ERROR</DbServerStatus>",
        )
        result = wsfe_client._parse_dummy_response(xml)
        assert result["success"] is True
        assert result["data"]["db_server"] == "ERROR"

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
        result = wsfe_client._parse_dummy_response(fault_xml)
        assert result["success"] is False
        assert "SOAP Fault" in result.get("error", "")

    def test_partial_response_returns_what_it_has(self, wsfe_client):
        """Partial response returns available fields, success if any found."""
        xml = self.SUCCESS_XML.replace(
            "<DbServerStatus>OK</DbServerStatus>", ""
        )
        result = wsfe_client._parse_dummy_response(xml)
        assert result["success"] is True
        assert result["data"]["app_server"] == "OK"
        assert result["data"]["auth_server"] == "OK"
        assert result["data"].get("db_server", "") == ""

    def test_empty_result_returns_error(self, wsfe_client):
        """Response without any status fields returns success=False."""
        empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <FEDummyResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEDummyResult>
      </FEDummyResult>
    </FEDummyResponse>
  </soap:Body>
</soap:Envelope>"""
        result = wsfe_client._parse_dummy_response(empty_xml)
        assert result["success"] is False

    def test_invalid_xml_returns_error(self, wsfe_client):
        """Garbage XML returns success=False."""
        result = wsfe_client._parse_dummy_response("not valid xml {{{")
        assert result["success"] is False
        assert "Error parseando" in result.get("error", "")


# ===========================================================================
# 3. Orchestrator — network error handling
# ===========================================================================

class TestDummyFallback:
    """Verify dummy() handles network errors gracefully."""

    SUCCESS_RESPONSE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEDummyResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEDummyResult>
        <AppServerStatus>OK</AppServerStatus>
        <DbServerStatus>OK</DbServerStatus>
        <AuthServerStatus>OK</AuthServerStatus>
      </FEDummyResult>
    </FEDummyResponse>
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

            result = wsfe_client.dummy()

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

            result = wsfe_client.dummy()

        assert result["success"] is False
        assert "error" in result

    def test_successful_request(self, wsfe_client):
        """Happy path: successful POST returns parsed data."""
        mock_response = MagicMock()
        mock_response.text = self.SUCCESS_RESPONSE_XML

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            result = wsfe_client.dummy()

        assert result["success"] is True
        assert result["data"]["app_server"] == "OK"
        assert result["data"]["db_server"] == "OK"
        assert result["data"]["auth_server"] == "OK"

    def test_no_auth_token_needed(self, wsfe_client):
        """dummy() does not call get_valid_token at all."""
        mock_response = MagicMock()
        mock_response.text = self.SUCCESS_RESPONSE_XML

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            wsfe_client.dummy()

        wsfe_client.wsaa_client.get_valid_token.assert_not_called()

    def test_uses_correct_soap_action(self, wsfe_client):
        """dummy() sends the correct SOAPAction header."""
        mock_response = MagicMock()
        mock_response.text = self.SUCCESS_RESPONSE_XML

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            wsfe_client.dummy()

        # Check the headers passed to post
        call_kwargs = mock_instance.post.call_args[1]
        assert call_kwargs["headers"]["SOAPAction"] == \
            "http://ar.gov.afip.dif.FEV1/FEDummy"
