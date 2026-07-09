"""Unit tests for FEParamGet* — WSFEClient reference data methods.

Tests cover:
1. SOAP XML builder produces correct envelope for all 7 verbs
2. Response parser extracts entries for each entry_tag type
3. Cache hit/miss behavior
4. Auto-retry on auth error
"""

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import httpx
import pytest
import xml.etree.ElementTree as ET

from services.wsfe_client import WSFEClient, ENTRY_MAP


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

class TestBuildFEParamGetRequest:
    """Verify the SOAP XML structure for all 7 FEParamGet verbs."""

    def test_contains_verb_tag_and_auth_only(self, wsfe_client):
        """Each verb produces a valid SOAP envelope with only <ns1:Auth> in body."""
        for verb, entry_tag in ENTRY_MAP.items():
            auth = wsfe_client.wsaa_client.get_valid_token()
            xml = wsfe_client._build_feparamget_request(auth, verb)

            # Verb tag present
            assert f"<ns1:{verb}>" in xml
            assert f"</ns1:{verb}>" in xml

            # Auth block present
            assert "<ns1:Auth>" in xml
            assert "<ns1:Cuit>20305060708</ns1:Cuit>" in xml

            # NO request body beyond Auth (no FeCAEReq, no PtoVta, etc.)
            assert "<ns1:FeCAEReq>" not in xml
            assert "<ns1:PtoVta>" not in xml
            assert "<ns1:CbteTipo>" not in xml

            # Auth is the ONLY child of the verb element
            # Extract the verb element content and verify
            verb_open = f"<ns1:{verb}>"
            verb_close = f"</ns1:{verb}>"
            start = xml.index(verb_open) + len(verb_open)
            end = xml.index(verb_close)
            body_content = xml[start:end].strip()
            assert body_content.startswith("<ns1:Auth>")
            assert body_content.endswith("</ns1:Auth>")
            # No other elements between verb tags
            assert body_content.count("<ns1:") == 4  # Auth + Token + Sign + Cuit

    def test_valid_xml_for_all_verbs(self, wsfe_client):
        """Generated XML must be parseable by ElementTree for every verb."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        for verb in ENTRY_MAP:
            xml = wsfe_client._build_feparamget_request(auth, verb)
            root = ET.fromstring(xml)
            ns_soap = "http://schemas.xmlsoap.org/soap/envelope/"
            assert root.tag == f"{{{ns_soap}}}Envelope"

    def test_auth_values_in_xml(self, wsfe_client):
        """Token, Sign, and Cuit values appear correctly in the XML."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_feparamget_request(
            auth, "FEParamGetTiposCbte"
        )
        assert "<ns1:Token>test_token_value</ns1:Token>" in xml
        assert "<ns1:Sign>test_sign_value</ns1:Sign>" in xml
        assert "<ns1:Cuit>20305060708</ns1:Cuit>" in xml

    def test_xml_escape_token(self, wsfe_client):
        """XML-special chars in Token must be escaped."""
        wsfe_client.wsaa_client.get_valid_token.return_value = {
            "success": True,
            "token": 'token<with>&special"chars',
            "sign": "sign",
        }
        auth = wsfe_client.wsaa_client.get_valid_token()
        xml = wsfe_client._build_feparamget_request(
            auth, "FEParamGetTiposCbte"
        )
        assert "&lt;" in xml
        assert "&amp;" in xml
        token_content = xml.split("<ns1:Token>")[1].split("</ns1:Token>")[0]
        assert "<" not in token_content

    def test_verb_names_match_entry_map(self, wsfe_client):
        """Every verb in ENTRY_MAP has a matching ns1 tag in the XML."""
        auth = wsfe_client.wsaa_client.get_valid_token()
        for verb in ENTRY_MAP:
            xml = wsfe_client._build_feparamget_request(auth, verb)
            assert f"<ns1:{verb}>" in xml


# ===========================================================================
# 2. Response parser
# ===========================================================================

class TestParseFEParamGetResponse:
    """Verify response parsing extracts entries correctly."""

    SAMPLE_XML_TPL = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGet{verb}Response xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGet{verb}Result>
        <ResultGet>
          {entries_xml}
        </ResultGet>
      </FEParamGet{verb}Result>
    </FEParamGet{verb}Response>
  </soap:Body>
</soap:Envelope>"""

    @staticmethod
    def _make_entry(entry_tag: str, fields: dict) -> str:
        items = "".join(
            f"<{k}>{v}</{k}>" for k, v in fields.items()
        )
        return f"<{entry_tag}>{items}</{entry_tag}>"

    def _build_response(self, verb: str, entry_tag: str, entries: list[dict]) -> str:
        entries_xml = "\n          ".join(
            self._make_entry(entry_tag, e) for e in entries
        )
        return self.SAMPLE_XML_TPL.format(verb=verb, entries_xml=entries_xml)

    # --- TipoCbte ---

    def test_parse_tipos_cbte(self, wsfe_client):
        """Parses TipoCbte entries with Id, Desc, FchDesde, FchHasta."""
        xml = self._build_response("TiposCbte", "TipoCbte", [
            {"Id": "1", "Desc": "Factura A", "FchDesde": "20200101", "FchHasta": ""},
            {"Id": "6", "Desc": "Factura B", "FchDesde": "20200101", "FchHasta": ""},
        ])
        result = wsfe_client._parse_feparamget_response(xml, "TipoCbte")
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == "1"
        assert result["data"][0]["desc"] == "Factura A"
        assert result["data"][0]["fchDesde"] == "20200101"
        assert result["data"][1]["id"] == "6"

    # --- PtoVenta ---

    def test_parse_ptos_venta(self, wsfe_client):
        """Parses PtoVenta entries with Nro, EmisionTipo, Bloqueado, FchBaja."""
        xml = self._build_response("PtosVenta", "PtoVenta", [
            {"Nro": "1", "EmisionTipo": "CAE", "Bloqueado": "N", "FchBaja": ""},
            {"Nro": "5", "EmisionTipo": "CAE", "Bloqueado": "N", "FchBaja": ""},
        ])
        result = wsfe_client._parse_feparamget_response(xml, "PtoVenta")
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["nro"] == "1"
        assert result["data"][0]["emisionTipo"] == "CAE"
        assert result["data"][0]["bloqueado"] == "N"

    # --- IvaTipo ---

    def test_parse_tipos_iva(self, wsfe_client):
        """Parses IvaTipo entries."""
        xml = self._build_response("TiposIva", "IvaTipo", [
            {"Id": "3", "Desc": "0%", "FchDesde": "20200101", "FchHasta": ""},
            {"Id": "4", "Desc": "10.5%", "FchDesde": "20200101", "FchHasta": ""},
            {"Id": "5", "Desc": "21%", "FchDesde": "20200101", "FchHasta": ""},
        ])
        result = wsfe_client._parse_feparamget_response(xml, "IvaTipo")
        assert result["success"] is True
        assert len(result["data"]) == 3
        assert result["data"][2]["id"] == "5"
        assert result["data"][2]["desc"] == "21%"

    # --- DocTipo ---

    def test_parse_tipos_doc(self, wsfe_client):
        """Parses DocTipo entries."""
        xml = self._build_response("TiposDoc", "DocTipo", [
            {"Id": "80", "Desc": "CUIT", "FchDesde": "20000101", "FchHasta": ""},
            {"Id": "96", "Desc": "DNI", "FchDesde": "20000101", "FchHasta": ""},
        ])
        result = wsfe_client._parse_feparamget_response(xml, "DocTipo")
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == "80"
        assert result["data"][0]["desc"] == "CUIT"

    # --- Moneda ---

    def test_parse_tipos_monedas(self, wsfe_client):
        """Parses Moneda entries."""
        xml = self._build_response("TiposMonedas", "Moneda", [
            {"Id": "PES", "Desc": "Pesos", "FchDesde": "20000101", "FchHasta": ""},
            {"Id": "DOL", "Desc": "Dolar", "FchDesde": "20000101", "FchHasta": ""},
        ])
        result = wsfe_client._parse_feparamget_response(xml, "Moneda")
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == "PES"
        assert result["data"][1]["desc"] == "Dolar"

    # --- Tributo ---

    def test_parse_tipos_tributos(self, wsfe_client):
        """Parses Tributo entries."""
        xml = self._build_response("TiposTributos", "Tributo", [
            {"Id": "1", "Desc": "IIBB", "FchDesde": "20000101", "FchHasta": ""},
        ])
        result = wsfe_client._parse_feparamget_response(xml, "Tributo")
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == "1"
        assert result["data"][0]["desc"] == "IIBB"

    # --- CondicionIVAReceptorId ---

    def test_parse_condiciones_iva_receptor(self, wsfe_client):
        """Parses CondicionIVAReceptorId entries."""
        xml = self._build_response(
            "CondicionesIVAReceptor", "CondicionIVAReceptorId", [
                {"Id": "1", "Desc": "Responsable Inscripto", "FchDesde": "20200101", "FchHasta": ""},
                {"Id": "2", "Desc": "Monotributo", "FchDesde": "20200101", "FchHasta": ""},
            ]
        )
        result = wsfe_client._parse_feparamget_response(
            xml, "CondicionIVAReceptorId"
        )
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == "1"
        assert result["data"][0]["desc"] == "Responsable Inscripto"

    # --- General parsing edge cases ---

    def test_empty_result_get(self, wsfe_client):
        """Empty ResultGet (no entries) returns empty data list."""
        xml = self._build_response("TiposCbte", "TipoCbte", [])
        result = wsfe_client._parse_feparamget_response(xml, "TipoCbte")
        assert result["success"] is True
        assert result["data"] == []

    def test_arca_errores_block(self, wsfe_client):
        """ARCA Errores/Err block returns success=False with error codes."""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <Errores>
          <Err><Code>10001</Code><Msg>Token expirado</Msg></Err>
        </Errores>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""
        result = wsfe_client._parse_feparamget_response(error_xml, "TipoCbte")
        assert result["success"] is False
        assert len(result.get("errores", [])) > 0
        assert result["errores"][0]["code"] == "10001"

    def test_soap_fault_returns_error(self, wsfe_client):
        """SOAP Fault in response returns success=False."""
        fault_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Server</faultcode>
      <faultstring>Server Error</faultstring>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""
        result = wsfe_client._parse_feparamget_response(fault_xml, "TipoCbte")
        assert result["success"] is False
        assert "SOAP Fault" in result.get("error", "")

    def test_invalid_xml_returns_error(self, wsfe_client):
        """Garbage XML returns success=False."""
        result = wsfe_client._parse_feparamget_response(
            "not valid xml {{{", "TipoCbte"
        )
        assert result["success"] is False
        assert "Error parseando" in result.get("error", "")


# ===========================================================================
# 3. Cache layer
# ===========================================================================

class TestFEParamGetCache:
    """Verify cache hit/miss and TTL behavior."""

    def test_cache_hit_returns_cached_data(self, wsfe_client):
        """When cache is fresh, returns cached data without HTTP call."""
        # Pre-populate cache
        cached_data = [{"id": "1", "desc": "Factura A"}]
        wsfe_client._feparamget_cache["FEParamGetTiposCbte"] = {
            "data": cached_data,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        result = wsfe_client._call_feparamget(
            "FEParamGetTiposCbte", "TipoCbte"
        )
        assert result["success"] is True
        assert result["data"] == cached_data
        assert result.get("cached") is True

    def test_cache_miss_calls_http(self, wsfe_client):
        """When cache is empty, performs the full HTTP flow."""
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance

            # Return a valid-looking SOAP response
            mock_response = MagicMock()
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <ResultGet>
          <TipoCbte><Id>1</Id><Desc>Factura A</Desc><FchDesde>20200101</FchDesde><FchHasta></FchHasta></TipoCbte>
        </ResultGet>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""
            mock_instance.post.return_value = mock_response

            result = wsfe_client._call_feparamget(
                "FEParamGetTiposCbte", "TipoCbte"
            )

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert "cached" not in result
        # Verify HTTP was called
        mock_instance.post.assert_called_once()

    def test_expired_cache_re_fetches(self, wsfe_client):
        """When cache TTL has expired, re-fetches from HTTP."""
        # Pre-populate with expired cache
        cached_data = [{"id": "1", "desc": "Factura A"}]
        wsfe_client._feparamget_cache["FEParamGetTiposCbte"] = {
            "data": cached_data,
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
        }

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_response = MagicMock()
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <ResultGet>
          <TipoCbte><Id>2</Id><Desc>Factura B</Desc><FchDesde>20200101</FchDesde><FchHasta></FchHasta></TipoCbte>
        </ResultGet>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""
            mock_instance.post.return_value = mock_response

            result = wsfe_client._call_feparamget(
                "FEParamGetTiposCbte", "TipoCbte"
            )

        assert result["success"] is True
        # Should have fresh data, not the old cached data
        assert result["data"][0]["id"] == "2"
        assert result["data"][0]["desc"] == "Factura B"

    def test_cache_after_successful_fetch(self, wsfe_client):
        """After a successful HTTP fetch, data is stored in cache."""
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_response = MagicMock()
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <ResultGet>
          <TipoCbte><Id>1</Id><Desc>Factura A</Desc><FchDesde>20200101</FchDesde><FchHasta></FchHasta></TipoCbte>
        </ResultGet>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""
            mock_instance.post.return_value = mock_response

            # First call populates cache
            wsfe_client._call_feparamget("FEParamGetTiposCbte", "TipoCbte")

        assert "FEParamGetTiposCbte" in wsfe_client._feparamget_cache
        cached = wsfe_client._feparamget_cache["FEParamGetTiposCbte"]
        assert cached["data"][0]["id"] == "1"
        assert cached["expires_at"] > datetime.now(timezone.utc)

    def test_clear_cache(self, wsfe_client):
        """clear_feparamget_cache() empties the cache dict."""
        wsfe_client._feparamget_cache["FEParamGetTiposCbte"] = {
            "data": [],
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        wsfe_client._feparamget_cache["FEParamGetPtosVenta"] = {
            "data": [],
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        assert len(wsfe_client._feparamget_cache) == 2
        wsfe_client.clear_feparamget_cache()
        assert len(wsfe_client._feparamget_cache) == 0


# ===========================================================================
# 4. Auto-retry
# ===========================================================================

class TestFEParamGetAutoRetry:
    """Verify auto-retry on auth error codes."""

    def test_retry_on_auth_error(self, wsfe_client):
        """When response has auth error (code 600), retries with renewed token."""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <Errores>
          <Err><Code>600</Code><Msg>Token expirado</Msg></Err>
        </Errores>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""

        success_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <ResultGet>
          <TipoCbte><Id>1</Id><Desc>Factura A</Desc><FchDesde>20200101</FchDesde><FchHasta></FchHasta></TipoCbte>
        </ResultGet>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance

            # First call returns auth error, second call returns success
            mock_responses = [
                MagicMock(text=error_xml),
                MagicMock(text=success_xml),
            ]
            mock_instance.post.side_effect = mock_responses

            # Mock token renewal
            wsfe_client.wsaa_client.request_token.return_value = {
                "success": True,
                "token": "renewed_token",
                "sign": "renewed_sign",
            }

            result = wsfe_client._call_feparamget(
                "FEParamGetTiposCbte", "TipoCbte"
            )

        assert result["success"] is True
        assert result["data"][0]["id"] == "1"
        # Two POST calls: original + retry
        assert mock_instance.post.call_count == 2
        # request_token was called once for renewal
        wsfe_client.wsaa_client.request_token.assert_called_once()

    def test_retry_on_error_10001(self, wsfe_client):
        """Auth error code 10001 also triggers retry."""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <Errores>
          <Err><Code>10001</Code><Msg>Token invalido</Msg></Err>
        </Errores>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""

        success_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <ResultGet>
          <TipoCbte><Id>6</Id><Desc>Factura B</Desc><FchDesde>20200101</FchDesde><FchHasta></FchHasta></TipoCbte>
        </ResultGet>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_responses = [
                MagicMock(text=error_xml),
                MagicMock(text=success_xml),
            ]
            mock_instance.post.side_effect = mock_responses

            wsfe_client.wsaa_client.request_token.return_value = {
                "success": True,
                "token": "renewed",
                "sign": "renewed",
            }

            result = wsfe_client._call_feparamget(
                "FEParamGetTiposCbte", "TipoCbte"
            )

        assert result["success"] is True
        assert result["data"][0]["id"] == "6"
        assert mock_instance.post.call_count == 2

    def test_no_retry_when_disabled(self, wsfe_client):
        """When retry=False, auth error returns immediately without retrying."""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <Errores>
          <Err><Code>600</Code><Msg>Token expirado</Msg></Err>
        </Errores>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_response = MagicMock(text=error_xml)
            mock_instance.post.return_value = mock_response

            result = wsfe_client._call_feparamget(
                "FEParamGetTiposCbte", "TipoCbte", retry=False
            )

        assert result["success"] is False
        # Only one POST call (no retry)
        mock_instance.post.assert_called_once()
        # request_token should NOT have been called
        wsfe_client.wsaa_client.request_token.assert_not_called()

    def test_retry_fails_returns_error(self, wsfe_client):
        """When retry also fails, returns the error from the second attempt."""
        error_xml_1 = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <Errores>
          <Err><Code>600</Code><Msg>Token expirado</Msg></Err>
        </Errores>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""

        error_xml_2 = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soap:Body>
    <FEParamGetTiposCbteResponse xmlns="http://ar.gov.afip.dif.FEV1/">
      <FEParamGetTiposCbteResult>
        <Errores>
          <Err><Code>700</Code><Msg>Otro error</Msg></Err>
        </Errores>
      </FEParamGetTiposCbteResult>
    </FEParamGetTiposCbteResponse>
  </soap:Body>
</soap:Envelope>"""

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_responses = [
                MagicMock(text=error_xml_1),
                MagicMock(text=error_xml_2),
            ]
            mock_instance.post.side_effect = mock_responses

            wsfe_client.wsaa_client.request_token.return_value = {
                "success": True,
                "token": "renewed",
                "sign": "renewed",
            }

            result = wsfe_client._call_feparamget(
                "FEParamGetTiposCbte", "TipoCbte"
            )

        assert result["success"] is False
        assert mock_instance.post.call_count == 2

    def test_network_timeout_returns_error(self, wsfe_client):
        """httpx timeout raises TimeoutException → success=False."""
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.post.side_effect = httpx.TimeoutException(
                "Connection timed out"
            )

            result = wsfe_client._call_feparamget(
                "FEParamGetTiposCbte", "TipoCbte"
            )

        assert result["success"] is False
        assert "error" in result

    def test_auth_failure_returns_error(self, wsfe_client):
        """If WSAA token cannot be obtained, returns error immediately."""
        wsfe_client.wsaa_client.get_valid_token.return_value = {
            "success": False,
            "error": "Token expired",
        }
        result = wsfe_client._call_feparamget(
            "FEParamGetTiposCbte", "TipoCbte"
        )
        assert result["success"] is False
        assert "token" in result.get("error", "").lower()


# ===========================================================================
# 5. Public methods
# ===========================================================================

class TestFEParamGetPublicMethods:
    """Verify all 7 public methods delegate correctly."""

    def test_get_tipos_cbte_delegates(self, wsfe_client):
        """get_tipos_cbte calls _call_feparamget with correct args."""
        wsfe_client._call_feparamget = MagicMock(return_value={"success": True, "data": []})
        result = wsfe_client.get_tipos_cbte()
        wsfe_client._call_feparamget.assert_called_once_with(
            "FEParamGetTiposCbte", "TipoCbte", retry=True
        )
        assert result["success"] is True

    def test_get_ptos_venta_delegates(self, wsfe_client):
        """get_ptos_venta calls _call_feparamget with correct args."""
        wsfe_client._call_feparamget = MagicMock(return_value={"success": True, "data": []})
        result = wsfe_client.get_ptos_venta()
        wsfe_client._call_feparamget.assert_called_once_with(
            "FEParamGetPtosVenta", "PtoVenta", retry=True
        )
        assert result["success"] is True

    def test_get_tipos_iva_delegates(self, wsfe_client):
        """get_tipos_iva calls _call_feparamget with correct args."""
        wsfe_client._call_feparamget = MagicMock(return_value={"success": True, "data": []})
        result = wsfe_client.get_tipos_iva()
        wsfe_client._call_feparamget.assert_called_once_with(
            "FEParamGetTiposIva", "IvaTipo", retry=True
        )
        assert result["success"] is True

    def test_get_tipos_doc_delegates(self, wsfe_client):
        """get_tipos_doc calls _call_feparamget with correct args."""
        wsfe_client._call_feparamget = MagicMock(return_value={"success": True, "data": []})
        result = wsfe_client.get_tipos_doc()
        wsfe_client._call_feparamget.assert_called_once_with(
            "FEParamGetTiposDoc", "DocTipo", retry=True
        )
        assert result["success"] is True

    def test_get_tipos_monedas_delegates(self, wsfe_client):
        """get_tipos_monedas calls _call_feparamget with correct args."""
        wsfe_client._call_feparamget = MagicMock(return_value={"success": True, "data": []})
        result = wsfe_client.get_tipos_monedas()
        wsfe_client._call_feparamget.assert_called_once_with(
            "FEParamGetTiposMonedas", "Moneda", retry=True
        )
        assert result["success"] is True

    def test_get_tipos_tributos_delegates(self, wsfe_client):
        """get_tipos_tributos calls _call_feparamget with correct args."""
        wsfe_client._call_feparamget = MagicMock(return_value={"success": True, "data": []})
        result = wsfe_client.get_tipos_tributos()
        wsfe_client._call_feparamget.assert_called_once_with(
            "FEParamGetTiposTributos", "Tributo", retry=True
        )
        assert result["success"] is True

    def test_get_condiciones_iva_receptor_delegates(self, wsfe_client):
        """get_condiciones_iva_receptor calls _call_feparamget with correct args."""
        wsfe_client._call_feparamget = MagicMock(return_value={"success": True, "data": []})
        result = wsfe_client.get_condiciones_iva_receptor()
        wsfe_client._call_feparamget.assert_called_once_with(
            "FEParamGetCondicionesIVAReceptor", "CondicionIVAReceptorId", retry=True
        )
        assert result["success"] is True
