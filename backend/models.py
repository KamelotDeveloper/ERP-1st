from sqlalchemy import Column,Integer,String,Float,DateTime,ForeignKey,Boolean,Text,func
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import bcrypt


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    version = Column(Integer, default=1)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    
    def set_password(self, password: str):
        self.hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.hashed_password.encode())


class Client(Base):
    __tablename__="clients"

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String)
    email=Column(String)
    phone=Column(String)
    address=Column(String, nullable=True)
    tax_id=Column(String, nullable=True)  # CUIT para factura


class Product(Base):
    __tablename__="products"

    id=Column(Integer,primary_key=True,index=True)
    sku=Column(String, unique=True, index=True)
    name=Column(String, nullable=False)
    price=Column(Float, nullable=False)
    stock=Column(Integer, default=0)
    stock_minimo=Column(Integer, default=0)
    version=Column(Integer, default=1)
    updated_at=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Material(Base):
    __tablename__="materials"

    id=Column(Integer,primary_key=True,index=True)
    sku=Column(String, unique=True, index=True)
    name=Column(String, nullable=False)
    category=Column(String)
    unit_cost=Column(Float, default=0)
    current_stock=Column(Float, default=0)
    stock_minimo=Column(Integer, default=0)
    version=Column(Integer, default=1)
    updated_at=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    movements = relationship("MaterialMovement", back_populates="material")


class MaterialMovement(Base):
    __tablename__="material_movements"

    id=Column(Integer,primary_key=True,index=True)
    material_id=Column(Integer,ForeignKey("materials.id"))
    quantity=Column(Float)
    type=Column(String)  # IN / OUT
    reason=Column(String, nullable=True)  # Reason for movement
    date=Column(DateTime,default=datetime.utcnow)

    material = relationship("Material", back_populates="movements")


class Sale(Base):
    __tablename__="sales"

    id=Column(Integer,primary_key=True,index=True)
    client_id=Column(Integer,ForeignKey("clients.id"))
    total=Column(Float)
    date=Column(DateTime,default=datetime.utcnow)

    items=relationship("SaleItem",back_populates="sale")


class SaleItem(Base):
    __tablename__="sale_items"

    id=Column(Integer,primary_key=True,index=True)
    sale_id=Column(Integer,ForeignKey("sales.id"))
    product_id=Column(Integer,ForeignKey("products.id"))
    quantity=Column(Integer)
    price=Column(Float)

    sale=relationship("Sale",back_populates="items")


class Invoice(Base):
    __tablename__="invoices"

    id=Column(Integer,primary_key=True,index=True)
    sale_id=Column(Integer,ForeignKey("sales.id"), nullable=True)
    client_id=Column(Integer,ForeignKey("clients.id"))
    cae=Column(String, nullable=True)  # Código de Autorización Electrónico
    cae_vto=Column(DateTime, nullable=True)  # Vencimiento CAE
    punto_venta=Column(Integer, default=1)
    numero=Column(Integer)
    tipo_factura=Column(Integer, default=1)  # 1=Factura A, 6=Factura B, 11=Factura C
    subtotal=Column(Float)
    iva=Column(Float)
    total=Column(Float)
    estado=Column(String, default="draft")  # draft, issued, error
    afip_response=Column(String, nullable=True)  # Respuesta completa de AFIP
    fecha=Column(DateTime,default=datetime.utcnow)


class ElectronicInvoiceConfig(Base):
    __tablename__ = "electronic_invoice_config"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=False)
    ambiente = Column(String, default="testing")
    
    razon_social = Column(String, nullable=True)
    CUIT = Column(String, nullable=True)
    punto_venta = Column(Integer, default=1)
    
    cert_path = Column(String, nullable=True)
    key_path = Column(String, nullable=True)
    
    estado_habilitacion = Column(String, default="no_iniciado")
    pasos_completados = Column(Text, nullable=True)
    
    ultimo_check = Column(DateTime, nullable=True)
    errores = Column(Text, nullable=True)
    
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AfipAuthToken(Base):
    __tablename__ = "afip_auth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, nullable=True)
    sign = Column(String, nullable=True)
    expiration = Column(DateTime, nullable=True)
    ambiente = Column(String, default="testing")
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


# ==================== MÓDULO DE PRODUCCIÓN ====================

class PlantillaProduccion(Base):
    """Recetas: define qué materiales necesita cada producto"""
    __tablename__ = "plantillas_produccion"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product")
    materiales = relationship("PlantillaMaterial", back_populates="plantilla", cascade="all, delete-orphan")


class PlantillaMaterial(Base):
    """Materiales que componen cada plantilla (receta)"""
    __tablename__ = "plantilla_materiales"

    id = Column(Integer, primary_key=True, index=True)
    plantilla_id = Column(Integer, ForeignKey("plantillas_produccion.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    cantidad = Column(Float, nullable=False)  # Cantidad por unidad de producto

    plantilla = relationship("PlantillaProduccion", back_populates="materiales")
    material = relationship("Material")


class OrdenProduccion(Base):
    """Órden de trabajo - orden de producción"""
    __tablename__ = "ordenes_produccion"

    id = Column(Integer, primary_key=True, index=True)
    plantilla_id = Column(Integer, ForeignKey("plantillas_produccion.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)  # Cantidad a producir
    estado = Column(String, default="pendiente")  # pendiente, en_proceso, completada, cancelada
    
    # Notas y observaciones
    notas = Column(Text, nullable=True)
    
    # Timestamps
    fecha_creacion = Column(DateTime, server_default=func.now())
    fecha_inicio = Column(DateTime, nullable=True)
    fecha_fin = Column(DateTime, nullable=True)
    
    # Usuario que creó la orden
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    plantilla = relationship("PlantillaProduccion")
    materiales_consumidos = relationship("MaterialConsumo", back_populates="orden", cascade="all, delete-orphan")


class MaterialConsumo(Base):
    """Registro de materiales consumidos en cada orden"""
    __tablename__ = "materiales_consumo"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes_produccion.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    cantidad_necesaria = Column(Float, nullable=False)
    cantidad_consumida = Column(Float, nullable=True, default=0)

    orden = relationship("OrdenProduccion", back_populates="materiales_consumidos")
    material = relationship("Material")


# ==================== MÓDULO DE SUSCRIPCIONES ====================

class Suscripcion(Base):
    __tablename__ = "suscripciones"
    
    client_id = Column(String, primary_key=True)
    email = Column(String, nullable=False)
    plan = Column(String, nullable=False, default="1_mes")  # '1_mes', '6_meses', '1_anio'
    estado = Column(String, nullable=False, default="prueba")  # 'prueba', 'activo', 'expirado', 'cancelado'
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
    fecha_expiracion = Column(DateTime, nullable=False)
    mp_payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CodigoDescuento(Base):
    __tablename__ = "codigos_descuento"
    
    codigo = Column(String, primary_key=True)
    descuento_porcentaje = Column(Integer, nullable=False)  # 0-100
    plan_objetivo = Column(String, nullable=True)  # '1_mes', '6_meses', '1_anio', NULL
    fecha_expiracion = Column(DateTime, nullable=True)
    usos_maximos = Column(Integer, default=1)
    usos_actuales = Column(Integer, default=0)


# ==================== MÓDULO DE PRESUPUESTOS ====================

class Presupuesto(Base):
    """Presupuesto personalizado para trabajos a medida"""
    __tablename__ = "presupuestos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)  # Ej: "Mueble Cocina Gladis"
    cliente_nombre = Column(String, nullable=True)
    cliente_telefono = Column(String, nullable=True)
    cliente_email = Column(String, nullable=True)
    
    # Estados: pendiente, aceptado, rechazado, vendido
    estado = Column(String, default="pendiente")
    
    # Costos
    costo_materiales = Column(Float, default=0)
    costo_mano_obra = Column(Float, default=0)
    margen = Column(Float, default=0)
    precio_final = Column(Float, default=0)
    
    # Notas adicionales
    notas = Column(Text, nullable=True)
    
    # Timestamps
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fecha_aceptacion = Column(DateTime, nullable=True)
    
    # Usuario que creó
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    items = relationship("PresupuestoItem", back_populates="presupuesto", cascade="all, delete-orphan")


class PresupuestoItem(Base):
    """Items (materiales) del presupuesto"""
    __tablename__ = "presupuesto_items"

    id = Column(Integer, primary_key=True, index=True)
    presupuesto_id = Column(Integer, ForeignKey("presupuestos.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    precio_unitario = Column(Float, nullable=False)  # Precio al momento de crear
    subtotal = Column(Float, nullable=False)

    presupuesto = relationship("Presupuesto", back_populates="items")
    material = relationship("Material")
# ==================== LICENCIAS (Fase 1) ====================

class LicenseTrial(Base):
    """Trial local de 30 días para usuarios nuevos"""
    __tablename__ = "license_trials"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, nullable=False, index=True)  # UUID from localStorage
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
    activo = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<LicenseTrial(client_id={self.client_id}, activo={self.activo})>"


# ==================== MÓDULO DE COMPROBANTES FISCALES ====================

class Comprobante(Base):
    """Comprobante multi-propósito: facturas, remitos, notas, órdenes"""
    __tablename__ = "comprobantes"

    # Core fields
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False, index=True)  # Tipo de comprobante general
    estado = Column(String, default="draft", index=True)  # draft, issued, cancelled
    fecha_emision = Column(DateTime, default=datetime.utcnow)
    fecha_contable = Column(DateTime, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    punto_venta = Column(Integer, default=1)
    numero = Column(Integer, default=0)
    subtotal = Column(Float, default=0)
    iva_importe = Column(Float, default=0)
    total = Column(Float, default=0)
    notas = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    version = Column(Integer, default=1)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Fiscal group (AFIP/ARCA)
    tipo_afip = Column(Integer, nullable=True)  # Código de comprobante AFIP: 1, 2, 3, 6, 11, etc.
    cae = Column(String, nullable=True)
    cae_vto = Column(DateTime, nullable=True)
    afip_response = Column(Text, nullable=True)
    comprobante_asociado_id = Column(Integer, ForeignKey("comprobantes.id"), nullable=True)  # NC/ND asociada

    # Remito group
    remito_tipo = Column(String, nullable=True)  # tipo de remito: proveedor, cliente, interno
    orden_compra_ref = Column(String, nullable=True)  # referencia a orden de compra

    # Nota de envío group
    direccion_envio = Column(String, nullable=True)
    fecha_estimada_envio = Column(DateTime, nullable=True)

    # Nota de recepción group
    proveedor_ref = Column(String, nullable=True)

    # Orden de reparación group
    producto_recibido = Column(String, nullable=True)
    diagnostico = Column(Text, nullable=True)
    tecnico_asignado = Column(String, nullable=True)
    horas_trabajo = Column(Float, nullable=True)
    fecha_ingreso = Column(DateTime, nullable=True)
    fecha_entrega_estimada = Column(DateTime, nullable=True)

    # Relationships
    cliente = relationship("Client", foreign_keys=[client_id])
    items = relationship("ComprobanteItem", back_populates="comprobante", cascade="all, delete-orphan")
    comprobante_asociado = relationship("Comprobante", remote_side=[id], foreign_keys=[comprobante_asociado_id])
    created_by_user = relationship("User", foreign_keys=[created_by])


class ComprobanteItem(Base):
    """Item de un comprobante (producto o descripción genérica)"""
    __tablename__ = "comprobante_items"

    id = Column(Integer, primary_key=True, index=True)
    comprobante_id = Column(Integer, ForeignKey("comprobantes.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    descripcion = Column(String, nullable=True)
    cantidad = Column(Float, default=1)
    unidad_medida = Column(String, nullable=True, default="unidad")
    precio_unitario = Column(Float, default=0)
    subtotal = Column(Float, default=0)
    orden = Column(Integer, default=0)
    iva_alicuota = Column(Float, nullable=True)  # % IVA aplicado (ej: 21.0, 10.5)
    iva_importe = Column(Float, nullable=True)

    # Relationships
    comprobante = relationship("Comprobante", back_populates="items")
    product = relationship("Product")
