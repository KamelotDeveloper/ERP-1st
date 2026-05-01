"""
Router de Suscripciones Fase 1 - Integracion con Supabase REST API
"""
import requests
import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import settings

router = APIRouter(prefix="/api/suscripcion", tags=["Suscripciones Fase 1"])

# ==================== SCHEMAS ====================

class CrearPreferenciaRequest(BaseModel):
    client_id: str
    email: str
    plan: str  # '1_mes', '6_meses', '1_anio'
    codigo_descuento: Optional[str] = None

class VerificarRequest(BaseModel):
    client_id: str

class CodigoDescuentoRequest(BaseModel):
    codigo: str
    plan: Optional[str] = None

# ==================== HELPERS SUPABASE ====================

def get_supabase_headers():
    """Headers para autenticar con Supabase REST API usando Service Role Key"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(status_code=500, detail="Supabase no configurado")
    
    return {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def get_supabase_url():
    """Devuelve la URL base de Supabase"""
    if not settings.SUPABASE_URL:
        raise HTTPException(status_code=500, detail="SUPABASE_URL no configurado")
    return settings.SUPABASE_URL.rstrip('/')

# ==================== PLANES ====================

# Planes por defecto (en caso de que Supabase no responda)
DEFAULT_PLANES = [
    {
        "id": "1_mes",
        "nombre": "Mensual",
        "descripcion": "Acceso completo por 1 mes",
        "precio": 35000,  # ARS
        "dias": 30
    },
    {
        "id": "6_meses",
        "nombre": "Semestral",
        "descripcion": "Acceso completo por 6 meses",
        "precio": 180000,  # ARS
        "dias": 180
    },
    {
        "id": "1_anio",
        "nombre": "Anual",
        "descripcion": "Acceso completo por 1 año",
        "precio": 300000,  # ARS
        "dias": 365
    }
]

PRUEBA_GRATIS = {
    "id": "prueba",
    "nombre": "Prueba Gratis",
    "descripcion": "7 dias de acceso completo gratis",
    "precio": 0,
    "dias": 7
}

def get_planes_from_supabase():
    """
    Lee planes desde Supabase (remoto y modificable).
    Si Supabase falla, devuelve DEFAULT_PLANES.
    """
    try:
        supabase_url = get_supabase_url()
        headers = get_supabase_headers()
        
        url = f"{supabase_url}/rest/v1/planes_suscripcion?select=*&activo=eq.true"
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        
        planes_supabase = resp.json()
        
        if planes_supabase and len(planes_supabase) > 0:
            # Convertir formato Supabase a formato interno
            return [{
                "id": p["id"],
                "nombre": p["nombre"],
                "descripcion": p["descripcion"],
                "precio": p["precio"],
                "dias": p["dias"]
            } for p in planes_supabase]
    except Exception as e:
        print(f"Error leyendo planes de Supabase: {e}")
    
    # Fallback a planes por defecto
    return DEFAULT_PLANES

@router.get("/planes")
def obtener_planes():
    """Devuelve los planes disponibles desde Supabase (o fallback local)"""
    planes = get_planes_from_supabase()
    return {
        "ok": True,
        "planes": planes,
        "prueba_gratis": PRUEBA_GRATIS
    }

# ==================== CREAR PREFERENCIA (CHECKOUT) ====================

@router.post("/crear-preferencia")
def crear_preferencia(data: CrearPreferenciaRequest):
    """
    Crea o actualiza una suscripcion en Supabase y genera link de MercadoPago.
    Fase 1: Si no hay MP_ACCESS_TOKEN, devuelve mock.
    """
    # Validar plan
    plan_info = next((p for p in PLANES if p["id"] == data.plan), None)
    if not plan_info:
        raise HTTPException(status_code=400, detail="Plan invalido")
    
    # Calcular fecha de expiracion
    fecha_expiracion = datetime.utcnow() + timedelta(days=plan_info["dias"])
    
    # Aplicar codigo de descuento si existe
    precio_final = plan_info["precio"]
    if data.codigo_descuento:
        codigo_info = validar_codigo_supabase(data.codigo_descuento, data.plan)
        if codigo_info:
            descuento = int(precio_final * codigo_info["descuento_porcentaje"] / 100)
            precio_final = precio_final - descuento
    
    # Guardar/Actualizar en Supabase
    supabase_url = get_supabase_url()
    headers = get_supabase_headers()
    
    # Verificar si ya existe
    check_url = f"{supabase_url}/rest/v1/suscripciones?client_id=eq.{data.client_id}"
    try:
        check_resp = requests.get(check_url, headers=headers, timeout=10)
        check_resp.raise_for_status()
        existentes = check_resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando Supabase: {str(e)}")
    
    suscripcion_data = {
        "client_id": data.client_id,
        "email": data.email,
        "plan": data.plan,
        "estado": "prueba" if precio_final == 0 else "activo",
        "fecha_inicio": datetime.utcnow().isoformat(),
        "fecha_expiracion": fecha_expiracion.isoformat(),
        "mp_payment_id": None
    }
    
    try:
        if existentes and len(existentes) > 0:
            # Actualizar existente
            update_url = f"{supabase_url}/rest/v1/suscripciones?client_id=eq.{data.client_id}"
            resp = requests.patch(update_url, headers=headers, json=suscripcion_data, timeout=10)
        else:
            # Crear nuevo
            create_url = f"{supabase_url}/rest/v1/suscripciones"
            resp = requests.post(create_url, headers=headers, json=suscripcion_data, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando en Supabase: {str(e)}")
    
    # Generar link de MercadoPago (Fase 1: Mock o real)
    if precio_final == 0:
        # Es gratis (prueba o codigo 100%)
        return {
            "success": True,
            "message": "Suscripcion gratuita activada",
            "suscripcion": suscripcion_data,
            "payment_url": None,
            "modo": "gratis"
        }
    
    if not settings.MP_ACCESS_TOKEN:
        # Mock: No hay token de MP configurado
        mock_payment_id = f"mock_{data.client_id}_{datetime.utcnow().timestamp()}"
        
        # Actualizar mp_payment_id en Supabase
        update_url = f"{supabase_url}/rest/v1/suscripciones?client_id=eq.{data.client_id}"
        requests.patch(update_url, headers=headers, json={"mp_payment_id": mock_payment_id}, timeout=10)
        
        return {
            "success": True,
            "message": "Modo simulado (sin MP_ACCESS_TOKEN)",
            "payment_id": mock_payment_id,
            "payment_url": f"http://127.0.0.1:8000/api/suscripcion/mock-pago?payment_id={mock_payment_id}",
            "modo": "mock",
            "suscripcion": suscripcion_data
        }
    
    # Real: Generar preferencia de MercadoPago
    mp_url = "https://api.mercadopago.com/checkout/preferences"
    mp_headers = {
        "Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    preference_data = {
        "items": [
            {
                "title": f"Suscripcion GA ERP - {plan_info['nombre']}",
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": float(precio_final)
            }
        ],
        "payer": {
            "email": data.email
        },
        "back_urls": {
            "success": settings.MP_SUCCESS_URL,
            "failure": settings.MP_FAILURE_URL,
            "pending": settings.MP_PENDING_URL
        },
        "auto_return": "approved",
        "external_reference": data.client_id
    }
    
    try:
        mp_resp = requests.post(mp_url, headers=mp_headers, json=preference_data, timeout=30)
        mp_resp.raise_for_status()
        mp_data = mp_resp.json()
        
        # Actualizar mp_payment_id
        update_url = f"{supabase_url}/rest/v1/suscripciones?client_id=eq.{data.client_id}"
        requests.patch(update_url, headers=headers, json={"mp_payment_id": mp_data.get("id")}, timeout=10)
        
        return {
            "success": True,
            "preference_id": mp_data.get("id"),
            "payment_url": mp_data.get("init_point"),  # URL para redirigir a MP
            "modo": "real",
            "suscripcion": suscripcion_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando preferencia MP: {str(e)}")

# ==================== VERIFICAR SUSCRIPCION ====================

@router.post("/verificar")
def verificar_suscripcion(data: VerificarRequest):
    """
    Consulta Supabase y devuelve el estado de la suscripcion.
    """
    supabase_url = get_supabase_url()
    headers = get_supabase_headers()
    
    url = f"{supabase_url}/rest/v1/suscripciones?client_id=eq.{data.client_id}&select=*"
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        suscripciones = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando Supabase: {str(e)}")
    
    if not suscripciones or len(suscripciones) == 0:
        return {
            "activo": False,
            "estado": None,
            "message": "No se encontro suscripcion"
        }
    
    sub = suscripciones[0]
    
    # Verificar si expiro
    fecha_exp = datetime.fromisoformat(sub["fecha_expiracion"].replace("Z", "+00:00"))
    ahora = datetime.utcnow()
    
    if fecha_exp < ahora and sub["estado"] == "activo":
        # Actualizar a expirado en Supabase
        update_url = f"{supabase_url}/rest/v1/suscripciones?client_id=eq.{data.client_id}"
        requests.patch(update_url, headers=headers, json={"estado": "expirado"}, timeout=10)
        sub["estado"] = "expirado"
    
    return {
        "activo": sub["estado"] in ["activo", "prueba"],
        "estado": sub["estado"],
        "plan": sub["plan"],
        "fecha_expiracion": sub["fecha_expiracion"],
        "dias_restantes": (fecha_exp - ahora).days if fecha_exp > ahora else 0,
        "suscripcion": sub
    }

# ==================== VALIDAR CODIGO DE DESCUENTO ====================

@router.post("/codigo-descuento")
def validar_codigo(data: CodigoDescuentoRequest):
    """
    Valida un codigo de descuento en Supabase.
    """
    resultado = validar_codigo_supabase(data.codigo, data.plan)
    
    if not resultado:
        raise HTTPException(status_code=400, detail="Codigo invalido, expirado o sin usos disponibles")
    
    return {
        "valido": True,
        "codigo": resultado["codigo"],
        "descuento_porcentaje": resultado["descuento_porcentaje"],
        "plan_objetivo": resultado["plan_objetivo"]
    }

def validar_codigo_supabase(codigo: str, plan: Optional[str] = None):
    """
    Funcion helper para validar codigo en Supabase.
    Devuelve el codigo si es valido, None si no.
    """
    supabase_url = get_supabase_url()
    headers = get_supabase_headers()
    
    url = f"{supabase_url}/rest/v1/codigos_descuento?codigo=eq.{codigo}&select=*"
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        codigos = resp.json()
    except:
        return None
    
    if not codigos or len(codigos) == 0:
        return None
    
    codigo_info = codigos[0]
    
    # Verificar usos
    if codigo_info["usos_actuales"] >= codigo_info["usos_maximos"]:
        return None
    
    # Verificar expiracion
    if codigo_info.get("fecha_expiracion"):
        fecha_exp = datetime.fromisoformat(codigo_info["fecha_expiracion"].replace("Z", "+00:00"))
        if fecha_exp < datetime.utcnow():
            return None
    
    # Verificar plan objetivo
    if codigo_info.get("plan_objetivo") and codigo_info["plan_objetivo"] != plan:
        return None
    
    return codigo_info

# ==================== MOCK PAGO (SOLO PARA PRUEBAS) ====================

@router.get("/mock-pago")
def mock_pago(payment_id: str):
    """Simula una pagina de pago exitoso para pruebas"""
    return {
        "message": "Mock Payment Page - Simulacion de pago exitoso",
        "payment_id": payment_id,
        "instrucciones": "En produccion, esto redirigiria a MercadoPago. Para simular, hace POST a /mock-confirm",
        "confirm_url": f"http://127.0.0.1:8000/api/suscripcion/mock-confirm?payment_id={payment_id}"
    }

@router.post("/mock-confirm")
def mock_confirm(payment_id: str):
    """
    Simula la confirmacion de un pago exitoso (para Fase 1 sin webhooks reales).
    """
    supabase_url = get_supabase_url()
    headers = get_supabase_headers()
    
    # Buscar suscripcion por mp_payment_id
    url = f"{supabase_url}/rest/v1/suscripciones?mp_payment_id=eq.{payment_id}&select=*"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        suscripciones = resp.json()
    except:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    if not suscripciones or len(suscripciones) == 0:
        raise HTTPException(status_code=404, detail="Suscripcion no encontrada para este payment_id")
    
    sub = suscripciones[0]
    
    # Marcar como activo
    update_url = f"{supabase_url}/rest/v1/suscripciones?client_id=eq.{sub['client_id']}"
    try:
        resp = requests.patch(update_url, headers=headers, json={"estado": "activo"}, timeout=10)
        resp.raise_for_status()
    except:
        raise HTTPException(status_code=500, detail="Error actualizando suscripcion")
    
    return {
        "success": True,
        "message": "Pago confirmado (mock)",
        "estado": "activo",
        "suscripcion": sub
    }

# ==================== CALLBACKS DE MP (PLACEHOLDERS) ====================

@router.get("/exito")
def pago_exito():
    """Callback de exito de MercadoPago"""
    return {"message": "Pago exitoso. Tu suscripcion ha sido activada."}

@router.get("/fallo")
def pago_fallo():
    """Callback de fallo de MercadoPago"""
    return {"message": "El pago ha fallado. Por favor intenta nuevamente."}

@router.get("/pendiente")
def pago_pendiente():
    """Callback de pago pendiente de MercadoPago"""
    return {"message": "El pago esta pendiente de confirmacion."}
