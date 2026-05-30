import os
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Request
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Text, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel
import mercadopago

# ====== CONFIGURACIÓN ======
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")  # PostgreSQL URL from Railway
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable required")

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET")

# ====== DATABASE SETUP ======
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ====== MODELS ======
class Plan(Base):
    __tablename__ = "planes"
    id = Column(String, primary_key=True)
    nombre = Column(String)
    precio = Column(Integer)
    precio_mes = Column(Integer)
    duracion_dias = Column(Integer)
    ahorro = Column(Integer, default=0)
    activo = Column(Boolean, default=True)

class Licencia(Base):
    __tablename__ = "licencias"
    usuario_id = Column(String, primary_key=True)
    plan = Column(String)
    fecha_inicio = Column(String)
    fecha_vencimiento = Column(String)
    activa = Column(Boolean, default=False)

# Crear tablas al iniciar
Base.metadata.create_all(bind=engine)

# ====== SCHEMAS ======
class GenerarPagoRequest(BaseModel):
    usuario_id: str
    plan_id: str

# ====== HELPERS ======
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_planes(db: Session):
    """Insertar planes por defecto si la tabla está vacía"""
    count = db.execute(text("SELECT COUNT(*) FROM planes")).scalar()
    if count == 0:
        planes_default = [
            ("mensual", "Mensual", 30000, 30000, 30, 0),
            ("semestral", "Semestral", 150000, 25000, 180, 30000),
            ("anual", "Anual", 300000, 25000, 365, 120000)
        ]
        for p in planes_default:
            db.execute(
                text("INSERT INTO planes (id, nombre, precio, precio_mes, duracion_dias, ahorro, activo) VALUES (:id, :nombre, :precio, :precio_mes, :dias, :ahorro, 1)"),
                {"id": p[0], "nombre": p[1], "precio": p[2], "precio_mes": p[3], "dias": p[4], "ahorro": p[5]}
            )
        db.commit()
        logger.info("✅ Planes por defecto insertados")

# ====== APP ======
app = FastAPI(title="GA ERP - Licenses API")

@app.on_event("startup")
async def startup():
    db = SessionLocal()
    try:
        init_planes(db)
    finally:
        db.close()

@app.get("/planes")
async def get_planes(db: Session = Depends(get_db)):
    """Lista de planes activos - Público"""
    result = db.execute(
        text("SELECT id, nombre, precio, precio_mes, duracion_dias, ahorro FROM planes WHERE activo = 1")
    ).fetchall()
    
    return [
        {
            "id": r[0],
            "nombre": r[1],
            "precio": r[2],
            "precio_mes": r[3],
            "duracion_dias": r[4],
            "ahorro": r[5]
        } for r in result
    ]

@app.post("/generar-pago")
async def generar_pago(request: GenerarPagoRequest, db: Session = Depends(get_db)):
    """Generar link de pago de MercadoPago"""
    if not MP_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="MercadoPago not configured")
    
    # Buscar plan
    plan = db.execute(
        text("SELECT id, nombre, precio, duracion_dias FROM planes WHERE id = :plan_id AND activo = 1"),
        {"plan_id": request.plan_id}
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        # Inicializar MercadoPago
        sdk = mercadopago.SDK(access_token=MP_ACCESS_TOKEN)
        
        preference_data = {
            "items": [
                {
                    "title": f"GA ERP - {plan[1]}",
                    "quantity": 1,
                    "unit_price": float(plan[2]),
                    "currency_id": "ARS"
                }
            ],
            "external_reference": f"{request.usuario_id}_{request.plan_id}",
            "notification_url": f"{os.getenv('RAILWAY_URL', '')}/webhook/mp",
            "back_urls": {
                "success": f"{os.getenv('RAILWAY_URL', '')}/success",
                "failure": f"{os.getenv('RAILWAY_URL', '')}/failure",
                "pending": f"{os.getenv('RAILWAY_URL', '')}/pending"
            }
        }
        
        preference = sdk.preference().create(preference_data)
        init_point = preference["response"]["init_point"]
        
        logger.info(f"✅ Payment link generated for {request.usuario_id}")
        return {"link": init_point}
        
    except Exception as e:
        logger.error(f"❌ MercadoPago error: {e}")
        raise HTTPException(status_code=500, detail=f"Payment error: {str(e)}")

@app.post("/webhook/mp")
async def webhook_mp(request: Request, db: Session = Depends(get_db)):
    """Webhook de MercadoPago"""
    try:
        # Verificar firma
        signature = request.headers.get("x-signature")
        if MP_WEBHOOK_SECRET and signature != MP_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        body = await request.json()
        
        if body.get("type") != "payment":
            return {"status": "ignored"}
        
        payment_data = body.get("data", {})
        external_reference = payment_data.get("external_reference")
        
        if not external_reference:
            return {"status": "no reference"}
        
        # Parsear usuario_id y plan_id
        try:
            usuario_id, plan_id = external_reference.split("_")
        except:
            return {"status": "invalid reference"}
        
        # Verificar estado del pago (simplificado - en producción consultar API MP)
        if payment_data.get("status") == "approved":
            # Buscar plan para calcular vencimiento
            plan = db.execute(
                text("SELECT duracion_dias FROM planes WHERE id = :plan_id"),
                {"plan_id": plan_id}
            ).first()
            
            if not plan:
                return {"status": "plan not found"}
            
            fecha_inicio = datetime.now().strftime("%Y-%m-%d")
            fecha_vencimiento = (datetime.now() + timedelta(days=plan[0])).strftime("%Y-%m-%d")
            
            # Upsert licencia
            existing = db.execute(
                text("SELECT usuario_id FROM licencias WHERE usuario_id = :uid"),
                {"uid": usuario_id}
            ).first()
            
            if existing:
                db.execute(
                    text("UPDATE licencias SET plan = :plan, fecha_inicio = :inicio, fecha_vencimiento = :vto, activa = 1 WHERE usuario_id = :uid"),
                    {"plan": plan_id, "inicio": fecha_inicio, "vto": fecha_vencimiento, "uid": usuario_id}
                )
            else:
                db.execute(
                    text("INSERT INTO licencias (usuario_id, plan, fecha_inicio, fecha_vencimiento, activa) VALUES (:uid, :plan, :inicio, :vto, 1)"),
                    {"uid": usuario_id, "plan": plan_id, "inicio": fecha_inicio, "vto": fecha_vencimiento}
                )
            
            db.commit()
            logger.info(f"✅ Licencia activada para {usuario_id}")
            
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return {"status": "error", "detail": str(e)}

@app.get("/licencia/{usuario_id}")
async def get_licencia(usuario_id: str, db: Session = Depends(get_db)):
    """Consultar licencia de un usuario"""
    result = db.execute(
        text("SELECT plan, fecha_vencimiento, activa FROM licencias WHERE usuario_id = :uid"),
        {"uid": usuario_id}
    ).first()
    
    if not result:
        return {"activa": False}
    
    # Verificar si no está vencida
    if result[2] and result[1] >= datetime.now().strftime("%Y-%m-%d"):
        return {"activa": True, "plan": result[0], "fecha_vencimiento": result[1]}
    
    return {"activa": False, "plan": result[0], "fecha_vencimiento": result[1]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
