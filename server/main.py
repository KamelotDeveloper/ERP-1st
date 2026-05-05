import os
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mercadopago
import requests
from datetime import datetime, timedelta

app = FastAPI()

# Variables de entorno
DATABASE_URL = os.getenv("DATABASE_URL")
MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
MERCADOPAGO_PUBLIC_KEY = os.getenv("MERCADOPAGO_PUBLIC_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Conexion a PostgreSQL
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

# Crear tablas al iniciar
@app.on_event("startup")
def startup():
    conn = get_db()
    cur = conn.cursor()
    
    # Tabla planes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS planes (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            precio DECIMAL(10,2) NOT NULL,
            duracion_dias INTEGER NOT NULL,
            descripcion TEXT,
            activo BOOLEAN DEFAULT TRUE,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabla licencias
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licencias (
            id SERIAL PRIMARY KEY,
            usuario_id VARCHAR(100) NOT NULL,
            plan_id INTEGER REFERENCES planes(id),
            mercadopago_preference_id VARCHAR(200),
            mercadopago_payment_id VARCHAR(200),
            fecha_inicio TIMESTAMP,
            fecha_fin TIMESTAMP,
            estado VARCHAR(20) DEFAULT 'pendiente',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insertar planes por defecto si no hay
    cur.execute("SELECT COUNT(*) FROM planes")
    if cur.fetchone()[0] == 0:
        planes_default = [
            ("Plan Basico", 29900, 30, "Plan mensual basico para talleres pequenos"),
            ("Plan Profesional", 49900, 30, "Plan mensual con funciones avanzadas"),
            ("Plan Enterprise", 99900, 30, "Plan mensual para empresas con multiples talleres"),
        ]
        for nombre, precio, dias, desc in planes_default:
            cur.execute(
                "INSERT INTO planes (nombre, precio, duracion_dias, descripcion) VALUES (%s, %s, %s, %s)",
                (nombre, precio, dias, desc)
            )
    
    cur.close()
    conn.close()

# Modelos
class GenerarPagoRequest(BaseModel):
    usuario_id: str
    plan_id: int

class WebhookMPRequest(BaseModel):
    type: str = None
    data: dict = None

# Endpoints
@app.get("/planes")
def get_planes():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, precio, duracion_dias, descripcion, activo FROM planes WHERE activo = TRUE")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    planes = []
    for row in rows:
        planes.append({
            "id": row[0],
            "nombre": row[1],
            "precio": float(row[2]),
            "duracion_dias": row[3],
            "descripcion": row[4],
            "activo": row[5]
        })
    return planes

@app.post("/generar-pago")
def generar_pago(req: GenerarPagoRequest):
    conn = get_db()
    cur = conn.cursor()
    
    # Obtener plan
    cur.execute("SELECT id, nombre, precio FROM planes WHERE id = %s AND activo = TRUE", (req.plan_id,))
    plan = cur.fetchone()
    if not plan:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    
    plan_id, nombre, precio = plan
    
    # Configurar MercadoPago
    mp = mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)
    
    # Crear preferencia de pago
    preference_data = {
        "items": [
            {
                "title": nombre,
                "quantity": 1,
                "unit_price": float(precio),
                "currency_id": "ARS"
            }
        ],
        "payer": {
            "email": f"{req.usuario_id}@temp.com"
        },
        "back_urls": {
            "success": f"{WEBHOOK_URL}/success",
            "failure": f"{WEBHOOK_URL}/failure",
            "pending": f"{WEBHOOK_URL}/pending"
        },
        "auto_return": "approved",
        "notification_url": f"{WEBHOOK_URL}/webhook/mp"
    }
    
    try:
        preference_response = mp.preference().create(preference_data)
        preference = preference_response["response"]
        
        # Crear licencia pendiente
        cur.execute(
            """INSERT INTO licencias (usuario_id, plan_id, mercadopago_preference_id, estado) 
               VALUES (%s, %s, %s, 'pendiente') RETURNING id""",
            (req.usuario_id, plan_id, preference["id"])
        )
        licencia_id = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            "licencia_id": licencia_id,
            "preference_id": preference["id"],
            "init_point": preference["init_point"],
            "sandbox_init_point": preference["sandbox_init_point"]
        }
    except Exception as e:
        cur.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/mp")
def webhook_mp(req: WebhookMPRequest):
    if req.type != "payment":
        return {"status": "ignored"}
    
    payment_id = req.data.get("id") if req.data else None
    if not payment_id:
        raise HTTPException(status_code=400, detail="Payment ID requerido")
    
    # Consultar pago a MercadoPago
    mp = mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)
    try:
        payment_info = mp.payment().get(payment_id)
        payment = payment_info["response"]
        
        if payment["status"] == "approved":
            conn = get_db()
            cur = conn.cursor()
            
            # Buscar licencia por preference_id
            cur.execute(
                "SELECT id, usuario_id, plan_id FROM licencias WHERE mercadopago_preference_id = %s",
                (payment["preference_id"],)
            )
            licencia = cur.fetchone()
            
            if licencia:
                licencia_id, usuario_id, plan_id = licencia
                
                # Obtener duracion del plan
                cur.execute("SELECT duracion_dias FROM planes WHERE id = %s", (plan_id,))
                plan = cur.fetchone()
                duracion_dias = plan[0] if plan else 30
                
                # Actualizar licencia
                fecha_inicio = datetime.now()
                fecha_fin = fecha_inicio + timedelta(days=duracion_dias)
                
                cur.execute(
                    """UPDATE licencias 
                       SET mercadopago_payment_id = %s, fecha_inicio = %s, fecha_fin = %s, estado = 'activa'
                       WHERE id = %s""",
                    (payment_id, fecha_inicio, fecha_fin, licencia_id)
                )
            
            cur.close()
            conn.close()
            
            return {"status": "ok", "licencia_actualizada": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return {"status": "ok"}

@app.get("/licencia/{usuario_id}")
def get_licencia(usuario_id: str):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT l.id, l.plan_id, p.nombre, l.fecha_inicio, l.fecha_fin, l.estado, p.precio
        FROM licencias l
        JOIN planes p ON l.plan_id = p.id
        WHERE l.usuario_id = %s AND l.estado = 'activa' AND l.fecha_fin > NOW()
        ORDER BY l.fecha_fin DESC
        LIMIT 1
    """, (usuario_id,))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="No se encontro licencia activa")
    
    return {
        "licencia_id": row[0],
        "plan_id": row[1],
        "plan_nombre": row[2],
        "fecha_inicio": row[3].isoformat() if row[3] else None,
        "fecha_fin": row[4].isoformat() if row[4] else None,
        "estado": row[5],
        "precio": float(row[6])
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "licencias-server"}
