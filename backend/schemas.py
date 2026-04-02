from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.USER


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=6)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 30 * 60  # seconds


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    username: Optional[str] = None


class ClientBase(BaseModel):
    name: str
    email: str
    phone: str
    address: Optional[str] = None
    tax_id: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientBase):
    pass


class Client(ClientBase):
    id: int

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    sku: str
    name: str
    price: float
    stock: int


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    pass


class Product(ProductBase):
    id: int

    class Config:
        from_attributes = True


class MaterialBase(BaseModel):
    sku: str
    name: str
    category: str
    stock: float
    unit_cost: float


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(MaterialBase):
    pass


class Material(MaterialBase):
    id: int
    total_value: float

    class Config:
        from_attributes = True


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: int


class SaleCreate(BaseModel):
    client_id: int
    items: List[SaleItemCreate]


class Sale(BaseModel):
    id: int
    client_id: int
    total: float
    date: datetime

    class Config:
        from_attributes = True


class MaterialMovement(BaseModel):
    material_id: int
    quantity: float
    type: str


class InvoiceItemCreate(BaseModel):
    product_id: int
    quantity: int
    unit_price: float


class InvoiceCreate(BaseModel):
    client_id: int
    sale_id: Optional[int] = None
    tipo_factura: int = 6
    items: List[InvoiceItemCreate]


class Invoice(BaseModel):
    id: int
    sale_id: Optional[int]
    client_id: int
    cae: Optional[str]
    cae_vto: Optional[datetime]
    punto_venta: int
    numero: int
    tipo_factura: int
    subtotal: float
    iva: float
    total: float
    estado: str
    fecha: datetime

    class Config:
        from_attributes = True


class AfipConfig(BaseModel):
    cert_path: str
    key_path: str
    cuit: str
    punto_venta: int = 1
    ambiente: str = "testing"


# ==================== ESQUEMAS DE PRODUCCIÓN ====================

class PlantillaMaterialBase(BaseModel):
    material_id: int
    cantidad: float


class PlantillaMaterialCreate(PlantillaMaterialBase):
    pass


class PlantillaMaterial(PlantillaMaterialBase):
    id: int
    material_name: Optional[str] = None
    material_sku: Optional[str] = None
    material_stock: Optional[float] = None

    class Config:
        from_attributes = True


class PlantillaProduccionBase(BaseModel):
    product_id: int
    is_active: bool = True


class PlantillaProduccionCreate(PlantillaProduccionBase):
    materiales: List[PlantillaMaterialCreate]


class PlantillaProduccionUpdate(BaseModel):
    product_id: Optional[int] = None
    is_active: Optional[bool] = None
    materiales: Optional[List[PlantillaMaterialCreate]] = None


class PlantillaProduccion(PlantillaProduccionBase):
    id: int
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    materiales: List[PlantillaMaterial] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialConsumoBase(BaseModel):
    material_id: int
    cantidad_necesaria: float


class MaterialConsumo(MaterialConsumoBase):
    id: int
    material_name: Optional[str] = None
    material_sku: Optional[str] = None
    stock_actual: Optional[float] = None
    tiene_suficiente: Optional[bool] = None

    class Config:
        from_attributes = True


class OrdenProduccionBase(BaseModel):
    plantilla_id: int
    cantidad: int
    notas: Optional[str] = None


class OrdenProduccionCreate(OrdenProduccionBase):
    pass


class OrdenProduccion(OrdenProduccionBase):
    id: int
    estado: str
    product_name: Optional[str] = None
    materiales: List[MaterialConsumo] = []
    fecha_creacion: datetime
    fecha_fin: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExplosiónMaterialesResponse(BaseModel):
    """Respuesta de la explosión de materiales"""
    plantilla_id: int
    product_id: int
    product_name: str
    cantidad_producir: int
    materiales: List[MaterialConsumo]
    puede_producir: bool
    materiales_faltantes: Optional[List[str]] = None


class ProduccionEjecutarRequest(BaseModel):
    """Request para ejecutar una orden de producción"""
    plantilla_id: int
    cantidad: int
    notas: Optional[str] = None


class ProduccionEjecutarResponse(BaseModel):
    """Response después de ejecutar la producción"""
    success: bool
    message: str
    orden_id: Optional[int] = None
    materiales_actualizados: Optional[List[dict]] = None
    producto_actualizado: Optional[dict] = None


# ==================== ESQUEMAS DE PRESUPUESTOS ====================

class PresupuestoItemBase(BaseModel):
    material_id: int
    cantidad: float


class PresupuestoItemCreate(PresupuestoItemBase):
    pass


class PresupuestoItem(PresupuestoItemBase):
    id: int
    material_name: Optional[str] = None
    material_sku: Optional[str] = None
    precio_unitario: float
    subtotal: float

    class Config:
        from_attributes = True


class PresupuestoBase(BaseModel):
    nombre: str
    cliente_nombre: Optional[str] = None
    cliente_telefono: Optional[str] = None
    cliente_email: Optional[str] = None
    costo_mano_obra: float = 0
    margen: float = 0
    notas: Optional[str] = None


class PresupuestoCreate(PresupuestoBase):
    items: List[PresupuestoItemCreate]


class PresupuestoUpdate(BaseModel):
    nombre: Optional[str] = None
    cliente_nombre: Optional[str] = None
    cliente_telefono: Optional[str] = None
    cliente_email: Optional[str] = None
    costo_mano_obra: Optional[float] = None
    margen: Optional[float] = None
    notas: Optional[str] = None
    items: Optional[List[PresupuestoItemCreate]] = None


class Presupuesto(PresupuestoBase):
    id: int
    estado: str
    costo_materiales: float
    precio_final: float
    items: List[PresupuestoItem] = []
    fecha_creacion: datetime
    fecha_aceptacion: Optional[datetime] = None

    class Config:
        from_attributes = True


class PresupuestoConfirmarVentaResponse(BaseModel):
    success: bool
    message: str
    venta_id: Optional[int] = None
    materiales_actualizados: Optional[List[dict]] = None
