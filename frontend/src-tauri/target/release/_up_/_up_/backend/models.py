from sqlalchemy import Column,Integer,String,Float,DateTime,ForeignKey,Boolean,Text
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
    version=Column(Integer, default=1)
    updated_at=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    movements = relationship("MaterialMovement", back_populates="material")


class MaterialMovement(Base):
    __tablename__="material_movements"

    id=Column(Integer,primary_key=True,index=True)
    material_id=Column(Integer,ForeignKey("materials.id"))
    quantity=Column(Float)
    type=Column(String)  # IN / OUT
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