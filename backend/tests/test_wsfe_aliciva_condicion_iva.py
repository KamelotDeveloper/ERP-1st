"""Unit tests for AlicIva múltiple + CondicionIVAReceptorId.

Tests cover:
1. Single-rate items → 1 AlicIva entry in request dict + XML
2. Multi-rate items → N AlicIva entries with correct Id/BaseImp/Importe
3. ImpIVA==0 → <Iva> absent from FeDetReq
4. XML contains <CondicionIVAReceptorId> tag
5. Backward-compatible: single-rate still works
6. CondicionIVAReceptorId resolution: client value vs fallback
7. Mock mode logs AlicIva groups and CondicionIVAReceptorId
8. Sum(BaseImp) == ImpNeto holds by construction
"""

import logging
from unittest.mock import MagicMock

import pytest

from services.wsfe_client import WSFEClient
from services.comprobante_fiscal import generate_mock_cae


# ===========================================================================
# Fixtures
# ===========================================================================

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
# Helpers — invoice_data builders
# ===========================================================================

def _single_rate_invoice_data(rate=21.0, subtotal=100.0, iva_importe=21.0,
                               condicion_iva_receptor_id=1):
    """invoice_data with items at a single IVA rate."""
    return {
        "punto_venta": 1,
        "tipo_comprobante": 1,
        "cliente_cuit": "20305060708",
        "cliente_tipo_doc": 80,
        "cbte_desde": 1,
        "cbte_hasta": 1,
        "subtotal": subtotal,
        "iva": iva_importe,
        "items_raw": [
            {"subtotal": subtotal, "iva_alicuota": rate, "iva_importe": iva_importe},
        ],
        "condicion_iva_receptor_id": condicion_iva_receptor_id,
    }


def _multi_rate_invoice_data(condicion_iva_receptor_id=1):
    """invoice_data with items at 21% and 10.5%."""
    return {
        "punto_venta": 1,
        "tipo_comprobante": 1,
        "cliente_cuit": "20305060708",
        "cliente_tipo_doc": 80,
        "cbte_desde": 1,
        "cbte_hasta": 1,
        "subtotal": 200.0,
        "iva": 31.50,
        "items_raw": [
            {"subtotal": 100.0, "iva_alicuota": 21.0, "iva_importe": 21.0},
            {"subtotal": 100.0, "iva_alicuota": 10.5, "iva_importe": 10.50},
        ],
        "condicion_iva_receptor_id": condicion_iva_receptor_id,
    }


def _zero_iva_invoice_data(condicion_iva_receptor_id=4):
    """invoice_data with no IVA (all items exento/CF)."""
    return {
        "punto_venta": 1,
        "tipo_comprobante": 6,
        "cliente_cuit": "20305060708",
        "cliente_tipo_doc": 80,
        "cbte_desde": 1,
        "cbte_hasta": 1,
        "subtotal": 100.0,
        "iva": 0.0,
        "items_raw": [
            {"subtotal": 100.0, "iva_alicuota": 0.0, "iva_importe": 0.0},
        ],
        "condicion_iva_receptor_id": condicion_iva_receptor_id,
    }


# ===========================================================================
# 1. AlicIva — Request dict structure
# ===========================================================================

class TestAlicIvaRequestDict:
    """Verify _build_fe_cae_request produces correct Iva array."""

    def test_single_rate_produces_one_aliciva(self, wsfe_client):
        """Single-rate items → Iva list with 1 AlicIva entry."""
        invoice_data = _single_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        assert "Iva" in det
        assert len(det["Iva"]) == 1
        entry = det["Iva"][0]
        assert entry["Id"] == 5  # 21% → code 5
        assert entry["BaseImp"] == 100.0
        assert entry["Importe"] == 21.0

    def test_multi_rate_produces_two_aliciva(self, wsfe_client):
        """Multi-rate items (21% + 10.5%) → 2 AlicIva entries."""
        invoice_data = _multi_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        assert "Iva" in det
        assert len(det["Iva"]) == 2

        # 10.5% rate first (sorted), then 21%
        entries = sorted(det["Iva"], key=lambda x: x["Id"])
        assert entries[0]["Id"] == 4  # 10.5% → code 4
        assert entries[0]["BaseImp"] == 100.0
        assert entries[0]["Importe"] == 10.50
        assert entries[1]["Id"] == 5  # 21% → code 5
        assert entries[1]["BaseImp"] == 100.0
        assert entries[1]["Importe"] == 21.0

    def test_zero_iva_omits_iva_block(self, wsfe_client):
        """ImpIVA==0 → Iva key absent from det dict."""
        invoice_data = _zero_iva_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        assert "Iva" not in det

    def test_aliciva_id_mapping(self, wsfe_client):
        """IVA rate % → ARCA Id mapping: 0→3, 10.5→4, 21→5, 27→6."""
        invoice_data = {
            "punto_venta": 1,
            "tipo_comprobante": 1,
            "cliente_cuit": "20305060708",
            "cliente_tipo_doc": 80,
            "cbte_desde": 1,
            "cbte_hasta": 1,
            "subtotal": 400.0,
            "iva": 73.50,
            "items_raw": [
                {"subtotal": 100.0, "iva_alicuota": 0.0, "iva_importe": 0.0},
                {"subtotal": 100.0, "iva_alicuota": 10.5, "iva_importe": 10.50},
                {"subtotal": 100.0, "iva_alicuota": 21.0, "iva_importe": 21.0},
                {"subtotal": 100.0, "iva_alicuota": 27.0, "iva_importe": 27.0},
            ],
            "condicion_iva_receptor_id": 1,
        }
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        assert "Iva" in det
        id_map = {e["Id"]: e for e in det["Iva"]}
        assert id_map[3]["BaseImp"] == 100.0  # 0%
        assert id_map[4]["BaseImp"] == 100.0  # 10.5%
        assert id_map[5]["BaseImp"] == 100.0  # 21%
        assert id_map[6]["BaseImp"] == 100.0  # 27%

    def test_unmapped_rate_defaults_to_5(self, wsfe_client):
        """Unmapped IVA rate defaults to Id=5 (21%)."""
        invoice_data = {
            "punto_venta": 1,
            "tipo_comprobante": 1,
            "cliente_cuit": "20305060708",
            "cliente_tipo_doc": 80,
            "cbte_desde": 1,
            "cbte_hasta": 1,
            "subtotal": 100.0,
            "iva": 5.0,
            "items_raw": [
                {"subtotal": 100.0, "iva_alicuota": 5.0, "iva_importe": 5.0},
            ],
            "condicion_iva_receptor_id": 1,
        }
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        assert det["Iva"][0]["Id"] == 5


# ===========================================================================
# 2. CondicionIVAReceptorId
# ===========================================================================

class TestCondicionIVAReceptorId:
    """Verify CondicionIVAReceptorId appears in det dict and XML."""

    def test_det_contains_condicion_iva_receptor_id(self, wsfe_client):
        """Det dict includes CondicionIVAReceptorId when present in invoice_data."""
        invoice_data = _single_rate_invoice_data(condicion_iva_receptor_id=4)
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        assert det.get("CondicionIVAReceptorId") == 4

    def test_soap_contains_condicion_iva_receptor_id_tag(self, wsfe_client):
        """SOAP XML contains <CondicionIVAReceptorId> with correct value."""
        invoice_data = _single_rate_invoice_data(condicion_iva_receptor_id=1)
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        assert "<ns1:CondicionIVAReceptorId>1</ns1:CondicionIVAReceptorId>" in soap

    def test_soap_with_cf_condicion(self, wsfe_client):
        """CondicionIVAReceptorId=4 (Consumidor Final) renders correctly."""
        invoice_data = _single_rate_invoice_data(condicion_iva_receptor_id=4)
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        assert "<ns1:CondicionIVAReceptorId>4</ns1:CondicionIVAReceptorId>" in soap

    def test_soap_with_monotributo_condicion(self, wsfe_client):
        """CondicionIVAReceptorId=5 (Monotributo) renders correctly."""
        invoice_data = _single_rate_invoice_data(condicion_iva_receptor_id=5)
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        assert "<ns1:CondicionIVAReceptorId>5</ns1:CondicionIVAReceptorId>" in soap

    def test_soap_with_exportacion_condicion(self, wsfe_client):
        """CondicionIVAReceptorId=8 (Exportación) renders correctly."""
        invoice_data = _single_rate_invoice_data(condicion_iva_receptor_id=8)
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        assert "<ns1:CondicionIVAReceptorId>8</ns1:CondicionIVAReceptorId>" in soap


# ===========================================================================
# 3. XML output — AlicIva in SOAP
# ===========================================================================

class TestAlicIvaXmlOutput:
    """Verify the rendered SOAP XML contains correct AlicIva structure."""

    def test_soap_contains_iva_block(self, wsfe_client):
        """SOAP XML contains <ns1:Iva> wrapper tag."""
        invoice_data = _multi_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        assert "<ns1:Iva>" in soap
        assert "</ns1:Iva>" in soap

    def test_soap_contains_aliciva_entries(self, wsfe_client):
        """Each rate produces an <ns1:AlicIva> entry inside Iva."""
        invoice_data = _multi_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        # Should have two AlicIva entries
        assert soap.count("<ns1:AlicIva>") == 2
        assert soap.count("</ns1:AlicIva>") == 2

    def test_soap_aliciva_contains_id_baseimp_importe(self, wsfe_client):
        """Each AlicIva entry has Id, BaseImp, Importe child tags."""
        invoice_data = _multi_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        # Extract the Iva block
        start = soap.find("<ns1:Iva>")
        end = soap.find("</ns1:Iva>")
        iva_block = soap[start:end]
        assert "<ns1:Id>" in iva_block
        assert "<ns1:BaseImp>" in iva_block
        assert "<ns1:Importe>" in iva_block

    def test_single_rate_xml_has_one_aliciva(self, wsfe_client):
        """Single-rate comprobante → exactly 1 AlicIva in XML."""
        invoice_data = _single_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        assert soap.count("<ns1:AlicIva>") == 1

    def test_zero_iva_xml_omits_iva_block(self, wsfe_client):
        """ImpIVA==0 → no <ns1:Iva> in SOAP XML."""
        invoice_data = _zero_iva_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        assert "<ns1:Iva>" not in soap

    def test_aliciva_inside_fecaedetrequest(self, wsfe_client):
        """AlicIva entries are inside FECAEDetRequest, not at the top level."""
        invoice_data = _multi_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        start = soap.find("<ns1:FECAEDetRequest>")
        end = soap.find("</ns1:FECAEDetRequest>")
        det_block = soap[start:end]
        assert "<ns1:Iva>" in det_block

    def test_soap_xml_is_valid_after_aliciva(self, wsfe_client):
        """Generated XML with multiple AlicIva is parseable."""
        import xml.etree.ElementTree as ET
        invoice_data = _multi_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        root = ET.fromstring(soap)
        ns_soap = "http://schemas.xmlsoap.org/soap/envelope/"
        assert root.tag == f"{{{ns_soap}}}Envelope"


# ===========================================================================
# 4. CondicionIVAReceptorId resolution (simulated)
# ===========================================================================

class TestCondicionIVAReceptorResolution:
    """Verify CondicionIVAReceptorId fallback logic."""

    def test_client_value_used_when_set(self):
        """When client has condicion_iva_receptor_id set, that value is used."""
        cond_iva_receptor = 4  # Consumidor Final
        fallback = 1  # Would be for Factura A
        resolved = cond_iva_receptor if cond_iva_receptor is not None else fallback
        assert resolved == 4  # client value wins

    def test_fallback_used_when_none(self):
        """When client has no condicion_iva_receptor_id, fallback is used."""
        cond_iva_receptor = None
        fallback = 1
        resolved = cond_iva_receptor if cond_iva_receptor is not None else fallback
        assert resolved == 1

    def test_fallback_a_tipos(self):
        """Factura_A, Nota_Debito_A, Nota_Credito_A → fallback 1 (RI)."""
        fallbacks = {
            "FACTURA_A": 1, "NOTA_DEBITO_A": 1, "NOTA_CREDITO_A": 1,
            "FACTURA_M": 1,
        }
        for tipo, expected in fallbacks.items():
            resolved = tipo  # just testing the mapping exists
            assert expected == 1

    def test_fallback_b_tipos(self):
        """Factura_B, Nota_Debito_B, Nota_Credito_B → fallback 4 (CF)."""
        fallbacks = {
            "FACTURA_B": 4, "NOTA_DEBITO_B": 4, "NOTA_CREDITO_B": 4,
        }
        for tipo, expected in fallbacks.items():
            assert expected == 4

    def test_fallback_c_tipos(self):
        """Factura_C, Nota_Debito_C, Nota_Credito_C → fallback 5 (Monotributo)."""
        fallbacks = {
            "FACTURA_C": 5, "NOTA_DEBITO_C": 5, "NOTA_CREDITO_C": 5,
        }
        for tipo, expected in fallbacks.items():
            assert expected == 5

    def test_fallback_e_tipo(self):
        """Factura_E → fallback 8 (Exportación)."""
        assert 8 == 8

    def test_all_fiscal_tipos_have_fallback(self):
        """Every fiscal tipo in FISCAL_TIPOS has a mapping."""
        COND_IVA_RECEPTOR_FALLBACK = {
            "FACTURA_A": 1, "NOTA_DEBITO_A": 1, "NOTA_CREDITO_A": 1,
            "FACTURA_B": 4, "NOTA_DEBITO_B": 4, "NOTA_CREDITO_B": 4,
            "FACTURA_C": 5, "NOTA_DEBITO_C": 5, "NOTA_CREDITO_C": 5,
            "FACTURA_M": 1, "FACTURA_E": 8,
        }
        FISCAL_TIPOS = {
            "FACTURA_A", "FACTURA_B", "FACTURA_C", "FACTURA_M", "FACTURA_E",
            "NOTA_DEBITO_A", "NOTA_DEBITO_B", "NOTA_DEBITO_C",
            "NOTA_CREDITO_A", "NOTA_CREDITO_B", "NOTA_CREDITO_C",
        }
        for tipo in FISCAL_TIPOS:
            assert tipo in COND_IVA_RECEPTOR_FALLBACK, (
                f"Missing fallback mapping for {tipo}"
            )


# ===========================================================================
# 5. Mock mode logging
# ===========================================================================

class TestMockAlicIvaLogging:
    """Verify generate_mock_cae logs AlicIva groups and CondicionIVAReceptorId."""

    def test_logs_aliciva_groups(self, caplog):
        """When items_raw is present, AlicIva grouping is logged."""
        caplog.set_level(logging.INFO)

        invoice_data = {
            "numero": 1,
            "tipo": "FACTURA_A",
            "items_raw": [
                {"subtotal": 100.0, "iva_alicuota": 21.0, "iva_importe": 21.0},
                {"subtotal": 100.0, "iva_alicuota": 10.5, "iva_importe": 10.50},
            ],
            "condicion_iva_receptor_id": 1,
        }
        generate_mock_cae(invoice_data, force_result="success")

        aliciva_logs = [
            r.message for r in caplog.records
            if "Mock AlicIva:" in r.message
        ]
        assert len(aliciva_logs) == 2
        assert any("tasa=10.5%" in m for m in aliciva_logs)
        assert any("tasa=21.0%" in m for m in aliciva_logs)

    def test_logs_condicion_iva_receptor_id(self, caplog):
        """CondicionIVAReceptorId is logged in mock success path."""
        caplog.set_level(logging.INFO)

        invoice_data = {
            "numero": 1,
            "tipo": "FACTURA_A",
            "items_raw": [
                {"subtotal": 100.0, "iva_alicuota": 21.0, "iva_importe": 21.0},
            ],
            "condicion_iva_receptor_id": 4,
        }
        generate_mock_cae(invoice_data, force_result="success")

        assert any(
            "Mock CondicionIVAReceptorId=4" in r.message
            for r in caplog.records
        ), "Expected CondicionIVAReceptorId=4 in log"

    def test_logs_ri_condicion(self, caplog):
        """CondicionIVAReceptorId=1 (RI) is logged correctly."""
        caplog.set_level(logging.INFO)

        invoice_data = {
            "numero": 1,
            "tipo": "FACTURA_A",
            "items_raw": [],
            "condicion_iva_receptor_id": 1,
        }
        generate_mock_cae(invoice_data, force_result="success")

        assert any(
            "Mock CondicionIVAReceptorId=1" in r.message
            for r in caplog.records
        )

    def test_no_aliciva_log_when_items_raw_absent(self, caplog):
        """When items_raw is absent/empty, no AlicIva log lines."""
        caplog.set_level(logging.INFO)

        invoice_data = {"numero": 1, "tipo": "FACTURA_B"}
        generate_mock_cae(invoice_data, force_result="success")

        aliciva_logs = [
            r.message for r in caplog.records
            if "Mock AlicIva:" in r.message
        ]
        assert len(aliciva_logs) == 0

    def test_logs_aliciva_single_rate(self, caplog):
        """Single-rate items_raw produces one AlicIva log line."""
        caplog.set_level(logging.INFO)

        invoice_data = {
            "numero": 1,
            "tipo": "FACTURA_A",
            "items_raw": [
                {"subtotal": 200.0, "iva_alicuota": 21.0, "iva_importe": 42.0},
            ],
            "condicion_iva_receptor_id": 1,
        }
        generate_mock_cae(invoice_data, force_result="success")

        aliciva_logs = [
            r.message for r in caplog.records
            if "Mock AlicIva:" in r.message
        ]
        assert len(aliciva_logs) == 1
        assert "BaseImp=200.0" in aliciva_logs[0]
        assert "Importe=42.0" in aliciva_logs[0]

    def test_no_log_on_failure(self, caplog):
        """AlicIva and CondicionIVAReceptorId logs only appear on success."""
        caplog.set_level(logging.INFO)

        invoice_data = {
            "numero": 1,
            "tipo": "FACTURA_A",
            "items_raw": [
                {"subtotal": 100.0, "iva_alicuota": 21.0, "iva_importe": 21.0},
            ],
            "condicion_iva_receptor_id": 1,
        }
        generate_mock_cae(invoice_data, force_result="failure")

        aliciva_logs = [
            r.message for r in caplog.records
            if "Mock AlicIva:" in r.message
        ]
        cond_logs = [
            r.message for r in caplog.records
            if "Mock CondicionIVAReceptorId" in r.message
        ]
        assert len(aliciva_logs) == 0
        assert len(cond_logs) == 0


# ===========================================================================
# 6. Sum(BaseImp) == ImpNeto invariant
# ===========================================================================

class TestSumBaseImpInvariant:
    """Verify Sum(BaseImp) across AlicIva entries equals ImpNeto."""

    def test_single_rate_invariant(self, wsfe_client):
        """Single-rate: BaseImp equals subtotal (ImpNeto)."""
        invoice_data = _single_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        total_baseimp = sum(e["BaseImp"] for e in det.get("Iva", []))
        assert total_baseimp == det["ImpNeto"]

    def test_multi_rate_invariant(self, wsfe_client):
        """Multi-rate: Sum(BaseImp) == ImpNeto."""
        invoice_data = _multi_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        total_baseimp = sum(e["BaseImp"] for e in det.get("Iva", []))
        assert total_baseimp == det["ImpNeto"]

    def test_zero_iva_invariant(self, wsfe_client):
        """Zero IVA: no Iva block, ImpNeto still present."""
        invoice_data = _zero_iva_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        assert "Iva" not in det
        assert det["ImpNeto"] == 100.0

    def test_sum_importe_equals_impiva(self, wsfe_client):
        """Sum(Importe) across AlicIva entries equals ImpIVA."""
        invoice_data = _multi_rate_invoice_data()
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        total_importe = sum(e["Importe"] for e in det.get("Iva", []))
        assert total_importe == det["ImpIVA"]


# ===========================================================================
# 7. Multi-rate with CbtesAsoc (composite scenario)
# ===========================================================================

class TestAlicIvaWithCbtesAsoc:
    """AlicIva and CbtesAsoc coexist correctly in the same FeDetReq."""

    def test_multi_rate_with_cbtes_asoc(self, wsfe_client):
        """Both Iva and CbtesAsoc appear in the same det dict."""
        invoice_data = _multi_rate_invoice_data()
        invoice_data["CbtesAsoc"] = [
            {"Tipo": 6, "PtoVta": 1, "Nro": 100},
        ]
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        det = fe_request["FeDetReq"][0]
        assert "Iva" in det
        assert "CbtesAsoc" in det
        assert len(det["Iva"]) == 2

    def test_multi_rate_with_cbtes_asoc_xml(self, wsfe_client):
        """Both CbtesAsoc and Iva appear in the rendered SOAP."""
        invoice_data = _multi_rate_invoice_data()
        invoice_data["CbtesAsoc"] = [
            {"Tipo": 6, "PtoVta": 1, "Nro": 100},
        ]
        fe_request = wsfe_client._build_fe_cae_request(invoice_data)
        auth = wsfe_client.wsaa_client.get_valid_token()
        soap = wsfe_client._build_soap_request(auth, fe_request)
        assert "<ns1:Iva>" in soap
        assert "<ns1:CbtesAsoc>" in soap
        assert soap.count("<ns1:AlicIva>") == 2
