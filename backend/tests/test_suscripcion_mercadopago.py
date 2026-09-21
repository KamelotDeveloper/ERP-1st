"""Backend tests for the MercadoPago preference contract and subscription lifecycle.

Slice A of the `cobros-reales-mercadopago` change (tasks T1-T5):
- T1 pricing fallback (ordo | canyp) + unknown app_id -> 400
- T2 preference payload contract (metadata / external_reference / notification_url)
- T3 lifecycle: paid -> 'pendiente', gratis -> 'prueba', verificar maps pendiente
- T4 discount code consumed ONLY after a successful MP POST
- T5 these tests

All network I/O is faked: `requests.{get,post,patch}` are routed by URL so no
real Supabase or MercadoPago call ever happens.
"""

from datetime import datetime, timedelta

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import suscripcion
from routers.suscripcion import router


# ---------------------------------------------------------------------------
# Fake HTTP layer (URL-routed double for `requests`)
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeHTTP:
    """Routes requests by URL. Captures every call for assertions."""

    def __init__(self):
        self.calls = []
        self.planes = []                 # GET planes_suscripcion ([] -> fallback)
        self.suscripcion_existente = None  # GET suscripciones
        self.creadas = []                # POST suscripciones
        self.patched = []                # PATCH suscripciones
        self.codigo = None               # GET codigos_descuento
        self.usos_patch = None           # PATCH codigos_descuento
        self.usos_creados = []           # POST uso_codigos
        self.fail_mp = False             # POST /checkout/preferences -> 500

    def _resp(self, payload, status=200):
        return FakeResponse(payload, status)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if "/rest/v1/planes_suscripcion" in url:
            return self._resp(self.planes)
        if "/rest/v1/suscripciones" in url:
            return self._resp([self.suscripcion_existente] if self.suscripcion_existente else [])
        if "/rest/v1/codigos_descuento" in url:
            return self._resp([self.codigo] if self.codigo else [])
        raise AssertionError(f"Unexpected GET {url}")

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if "/checkout/preferences" in url:
            if self.fail_mp:
                return self._resp({"error": "mp unavailable"}, 500)
            return self._resp({"id": "pref-123", "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref=pref-123"})
        if "/rest/v1/suscripciones" in url:
            self.creadas.append(kwargs.get("json") or {})
            return self._resp([kwargs.get("json") or {}])
        if "/rest/v1/uso_codigos" in url:
            self.usos_creados.append(kwargs.get("json") or {})
            return self._resp([kwargs.get("json") or {}])
        raise AssertionError(f"Unexpected POST {url}")

    def patch(self, url, **kwargs):
        self.calls.append(("PATCH", url, kwargs))
        if "/rest/v1/codigos_descuento" in url:
            self.usos_patch = kwargs.get("json") or {}
            return self._resp([self.usos_patch])
        if "/rest/v1/suscripciones" in url:
            self.patched.append(kwargs.get("json") or {})
            return self._resp([kwargs.get("json") or {}])
        raise AssertionError(f"Unexpected PATCH {url}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def supabase_config(monkeypatch):
    """get_supabase_headers() 500s without a service key; provide a fake one."""
    monkeypatch.setattr(suscripcion.settings, "SUPABASE_SERVICE_KEY", "sb-test-service-key")
    return suscripcion.settings


@pytest.fixture
def fake_http(monkeypatch):
    fh = FakeHTTP()
    monkeypatch.setattr(requests, "get", fh.get)
    monkeypatch.setattr(requests, "post", fh.post)
    monkeypatch.setattr(requests, "patch", fh.patch)
    return fh


@pytest.fixture
def mp_real(supabase_config, monkeypatch):
    monkeypatch.setattr(suscripcion.settings, "MP_ACCESS_TOKEN", "TEST-ACCESS-TOKEN")


@pytest.fixture
def mp_mock(supabase_config, monkeypatch):
    monkeypatch.setattr(suscripcion.settings, "MP_ACCESS_TOKEN", None)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _mp_payload(fh):
    posts = [c for c in fh.calls if c[0] == "POST" and "/checkout/preferences" in c[1]]
    assert len(posts) == 1, "expected exactly one MP preference POST"
    return posts[0][2]["json"]


def _codigo(porcentaje=10, plan_objetivo="6_meses", usos_actuales=0):
    return {
        "codigo": "DESCUENTO10",
        "descuento_porcentaje": porcentaje,
        "plan_objetivo": plan_objetivo,
        "fecha_expiracion": None,
        "usos_maximos": 100,
        "usos_actuales": usos_actuales,
    }


# ---------------------------------------------------------------------------
# T1 - pricing fallback + fail-loud unknown app
# ---------------------------------------------------------------------------

def test_planes_fallback_prices_both_apps(client, fake_http):
    ordo = client.get("/api/suscripcion/planes", params={"app_id": "ordo"}).json()
    assert [p["id"] for p in ordo["planes"]] == ["1_mes", "6_meses", "1_anio"]
    assert [p["precio"] for p in ordo["planes"]] == [70000, 360000, 720000]

    canyp = client.get("/api/suscripcion/planes", params={"app_id": "canyp"}).json()
    assert [p["id"] for p in canyp["planes"]] == ["canyp_1_mes", "canyp_6_meses", "canyp_1_anio"]
    assert [p["precio"] for p in canyp["planes"]] == [120000, 617000, 1234000]

    for plan in ordo["planes"] + canyp["planes"]:
        assert {"id", "nombre", "precio", "dias", "descuento"} <= set(plan)


def test_planes_unknown_app_400(client, fake_http):
    resp = client.get("/api/suscripcion/planes", params={"app_id": "otra"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# T2 / T3 - preference payload contract + pendiente lifecycle
# ---------------------------------------------------------------------------

def test_create_preference_happy_metadata_and_pendiente(client, fake_http, mp_real):
    resp = client.post("/api/suscripcion/crear-preferencia", json={
        "client_id": "c-123", "app_id": "ordo", "plan": "6_meses", "email": "test@example.com",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["modo"] == "real"

    payload = _mp_payload(fake_http)
    assert payload["external_reference"] == "ordo:c-123"
    assert payload["notification_url"] == suscripcion.settings.MP_NOTIFICATION_URL
    assert payload["metadata"] == {
        "app_id": "ordo", "client_id": "c-123", "plan": "6_meses", "email": "test@example.com",
    }
    assert payload["items"][0]["unit_price"] == 360000.0

    assert fake_http.creadas[0]["estado"] == "pendiente"
    assert fake_http.creadas[0]["plan"] == "6_meses"


def test_create_preference_invalid_plan_400(client, fake_http, mp_real):
    resp = client.post("/api/suscripcion/crear-preferencia", json={
        "client_id": "c-123", "app_id": "ordo", "plan": "mensual",
    })
    assert resp.status_code == 400


def test_create_preference_mock_mode_pendiente(client, fake_http, mp_mock):
    resp = client.post("/api/suscripcion/crear-preferencia", json={
        "client_id": "c-123", "app_id": "ordo", "plan": "6_meses",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["modo"] == "mock"
    assert "mock-pago" in body["payment_url"]
    # D6: mock mode never becomes active at creation
    assert fake_http.creadas[0]["estado"] == "pendiente"
    assert not [c for c in fake_http.calls if "/checkout/preferences" in c[1]]


# ---------------------------------------------------------------------------
# T4 - discount consumption only after a successful MP POST
# ---------------------------------------------------------------------------

def test_create_preference_mp_failure_does_not_consume_discount(client, fake_http, mp_real):
    fake_http.codigo = _codigo(porcentaje=10)
    fake_http.fail_mp = True

    resp = client.post("/api/suscripcion/crear-preferencia", json={
        "client_id": "c-123", "app_id": "ordo", "plan": "6_meses", "codigo_descuento": "DESCUENTO10",
    })
    assert resp.status_code == 500
    assert fake_http.usos_patch is None
    assert fake_http.usos_creados == []


def test_descuento_reduces_price_and_consumes(client, fake_http, mp_real):
    fake_http.codigo = _codigo(porcentaje=10)

    resp = client.post("/api/suscripcion/crear-preferencia", json={
        "client_id": "c-123", "app_id": "ordo", "plan": "6_meses", "codigo_descuento": "DESCUENTO10",
    })
    assert resp.status_code == 200
    assert _mp_payload(fake_http)["items"][0]["unit_price"] == 324000.0  # 360000 - 10%
    assert fake_http.usos_patch == {"usos_actuales": 1}
    assert fake_http.usos_creados == [
        {"codigo": "DESCUENTO10", "client_id": "c-123", "plan": "6_meses"}
    ]


def test_descuento_100_makes_gratis_and_consumes(client, fake_http, mp_real):
    fake_http.codigo = _codigo(porcentaje=100)

    resp = client.post("/api/suscripcion/crear-preferencia", json={
        "client_id": "c-123", "app_id": "ordo", "plan": "6_meses", "codigo_descuento": "DESCUENTO10",
    })
    assert resp.status_code == 200
    assert resp.json()["modo"] == "gratis"
    # D5: gratis keeps 'prueba' (already treated as active by verificar)
    assert fake_http.creadas[0]["estado"] == "prueba"
    # D4: the gratis path consumes the code too
    assert fake_http.usos_patch == {"usos_actuales": 1}
    assert len(fake_http.usos_creados) == 1


# ---------------------------------------------------------------------------
# T3 - verificar maps 'pendiente'
# ---------------------------------------------------------------------------

def test_verificar_pendiente_not_active(client, fake_http):
    fake_http.suscripcion_existente = {
        "client_id": "c-123",
        "app_id": "ordo",
        "email": "test@example.com",
        "plan": "6_meses",
        "estado": "pendiente",
        "fecha_expiracion": (datetime.utcnow() + timedelta(days=180)).isoformat(),
        "mp_payment_id": None,
    }

    resp = client.post("/api/suscripcion/verificar", json={"client_id": "c-123", "app_id": "ordo"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["activo"] is False
    assert body["estado"] == "pendiente"
    assert "Pago pendiente de aprobación" == body["message"]
    assert fake_http.patched == []  # never flipped to 'expirado'
