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
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=300)
    # Acepta CUIT con o sin guiones: XX-XXXXXXXX-X o XXXXXXXXXXX o vacio
    tax_id: Optional[str] = Field(None, pattern=r"^\d{2}-\d{8}-\d{1}$|^\d{11}$|^$")


class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientBase):
    pass


class Client(ClientBase):
    id: int

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    price: float = Field(..., ge=0)
    stock: int = Field(..., ge=0)
    stock_minimo: int = Field(0, ge=0)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    pass


class Product(ProductBase):
    id: int

    class Config:
        from_attributes = True


class MaterialBase(BaseModel):
    sku: Optional[str] = Field(None, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    current_stock: float = Field(..., ge=0)
    unit_cost: float = Field(..., ge=0)
    stock_minimo: int = Field(0, ge=0)


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
    product_id: int = Field(..., gt=0)  # Mayor que 0
    quantity: int = Field(..., gt=0)    # Mayor que 0


class SaleCreate(BaseModel):
    client_id: int = Field(..., gt=0)  # Mayor que 0
    items: List[SaleItemCreate] = Field(..., min_length=1)  # Al menos 1 item


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
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)


class InvoiceCreate(BaseModel):
    client_id: int = Field(..., gt=0)
    sale_id: Optional[int] = None
    tipo_factura: int = Field(..., ge=1, le=11)  # Entre 1 y 11
    items: List[InvoiceItemCreate] = Field(..., min_length=1)


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
    material_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)


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
    nombre: str = Field(..., min_length=1, max_length=200)
    cliente_nombre: Optional[str] = Field(None, max_length=200)
    cliente_telefono: Optional[str] = Field(None, max_length=20)
    cliente_email: Optional[EmailStr] = None
    costo_mano_obra: float = Field(0, ge=0)
    margen: float = Field(0, ge=0)
    notas: Optional[str] = Field(None, max_length=1000)


class PresupuestoCreate(PresupuestoBase):
    items: List[PresupuestoItemCreate] = Field(..., min_length=1)


class PresupuestoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    cliente_nombre: Optional[str] = Field(None, max_length=200)
    cliente_telefono: Optional[str] = Field(None, max_length=20)
    cliente_email: Optional[EmailStr] = None
    costo_mano_obra: Optional[float] = Field(None, ge=0)
    margen: Optional[float] = Field(None, ge=0)
    notas: Optional[str] = Field(None, max_length=1000)
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


# ==================== ESQUEMAS DE COMPROBANTES FISCALES ====================

class TipoComprobante(str, Enum):
    """Tipos de comprobantes del sistema (fiscales + internos)"""
    FACTURA_A = "FACTURA_A"
    FACTURA_B = "FACTURA_B"
    FACTURA_C = "FACTURA_C"
    FACTURA_M = "FACTURA_M"
    FACTURA_E = "FACTURA_E"
    NOTA_DEBITO_A = "NOTA_DEBITO_A"
    NOTA_DEBITO_B = "NOTA_DEBITO_B"
    NOTA_DEBITO_C = "NOTA_DEBITO_C"
    NOTA_CREDITO_A = "NOTA_CREDITO_A"
    NOTA_CREDITO_B = "NOTA_CREDITO_B"
    NOTA_CREDITO_C = "NOTA_CREDITO_C"
    RECIBO_A = "RECIBO_A"
    RECIBO_B = "RECIBO_B"
    RECIBO_C = "RECIBO_C"
    REMITO_X = "REMITO_X"
    REMITO_R = "REMITO_R"
    TICKET = "TICKET"
    NOTA_ENVIO = "NOTA_ENVIO"
    NOTA_RECEPCION = "NOTA_RECEPCION"
    ORDEN_REPARACION = "ORDEN_REPARACION"
    NOTA_VENTA = "NOTA_VENTA"


class ComprobanteItemBase(BaseModel):
    comprobante_id: Optional[int] = None
    product_id: Optional[int] = None
    descripcion: Optional[str] = None
    cantidad: float = 1
    unidad_medida: str = "unidad"
    precio_unitario: float = 0
    subtotal: float = 0
    orden: int = 0
    iva_alicuota: Optional[float] = None
    iva_importe: Optional[float] = None


class ComprobanteItemCreate(ComprobanteItemBase):
    pass


class ComprobanteItem(ComprobanteItemBase):
    id: int

    class Config:
        from_attributes = True


class ComprobanteBase(BaseModel):
    tipo: TipoComprobante
    estado: str = "draft"
    fecha_emision: Optional[datetime] = None
    fecha_contable: Optional[datetime] = None
    client_id: Optional[int] = None
    punto_venta: int = 1
    numero: Optional[int] = None
    subtotal: float = 0
    iva_importe: float = 0
    total: float = 0
    notas: Optional[str] = None

    # Fiscal group
    tipo_afip: Optional[int] = None
    cae: Optional[str] = None
    cae_vto: Optional[datetime] = None
    afip_response: Optional[str] = None
    comprobante_asociado_id: Optional[int] = None

    # Remito group
    remito_tipo: Optional[str] = None
    orden_compra_ref: Optional[str] = None

    # Nota de envío group
    direccion_envio: Optional[str] = None
    fecha_estimada_envio: Optional[datetime] = None

    # Nota de recepción group
    proveedor_ref: Optional[str] = None

    # Orden de reparación group
    producto_recibido: Optional[str] = None
    diagnostico: Optional[str] = None
    tecnico_asignado: Optional[str] = None
    horas_trabajo: Optional[float] = None
    fecha_ingreso: Optional[datetime] = None
    fecha_entrega_estimada: Optional[datetime] = None


class ComprobanteCreate(ComprobanteBase):
    items: List[ComprobanteItemCreate] = Field(..., min_length=1)


class ComprobanteUpdate(BaseModel):
    tipo: Optional[TipoComprobante] = None
    estado: Optional[str] = None
    fecha_emision: Optional[datetime] = None
    fecha_contable: Optional[datetime] = None
    client_id: Optional[int] = None
    punto_venta: Optional[int] = None
    numero: Optional[int] = None
    subtotal: Optional[float] = None
    iva_importe: Optional[float] = None
    total: Optional[float] = None
    notas: Optional[str] = None

    # Fiscal group
    tipo_afip: Optional[int] = None
    cae: Optional[str] = None
    cae_vto: Optional[datetime] = None
    afip_response: Optional[str] = None
    comprobante_asociado_id: Optional[int] = None

    # Remito group
    remito_tipo: Optional[str] = None
    orden_compra_ref: Optional[str] = None

    # Nota de envío group
    direccion_envio: Optional[str] = None
    fecha_estimada_envio: Optional[datetime] = None

    # Nota de recepción group
    proveedor_ref: Optional[str] = None

    # Orden de reparación group
    producto_recibido: Optional[str] = None
    diagnostico: Optional[str] = None
    tecnico_asignado: Optional[str] = None
    horas_trabajo: Optional[float] = None
    fecha_ingreso: Optional[datetime] = None
    fecha_entrega_estimada: Optional[datetime] = None


class Comprobante(ComprobanteBase):
    id: int
    created_by: Optional[int] = None
    version: int = 1
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None
    items: List[ComprobanteItem] = []

    class Config:
        from_attributes = True


class ComprobanteListItem(BaseModel):
    """Lightweight response for list endpoint."""
    id: int
    tipo: str
    estado: str
    fecha_emision: Optional[datetime] = None
    punto_venta: int = 0
    numero: int = 0
    total: float = 0
    cliente: Optional[str] = None
    numero_formateado: str = ""

    class Config:
        from_attributes = True


class ComprobanteDetail(BaseModel):
    """Full detail response with items and client name."""
    id: int
    tipo: str
    estado: str
    fecha_emision: Optional[datetime] = None
    fecha_contable: Optional[datetime] = None
    client_id: Optional[int] = None
    cliente: Optional[str] = None
    punto_venta: int = 0
    numero: int = 0
    subtotal: float = 0
    iva_importe: float = 0
    total: float = 0
    notas: Optional[str] = None
    created_by: Optional[int] = None
    version: int = 1
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None
    # Fiscal group
    tipo_afip: Optional[int] = None
    cae: Optional[str] = None
    cae_vto: Optional[datetime] = None
    afip_response: Optional[str] = None
    comprobante_asociado_id: Optional[int] = None
    # Remito group
    remito_tipo: Optional[str] = None
    orden_compra_ref: Optional[str] = None
    # Nota de envío group
    direccion_envio: Optional[str] = None
    fecha_estimada_envio: Optional[datetime] = None
    # Nota de recepción group
    proveedor_ref: Optional[str] = None
    # Orden de reparación group
    producto_recibido: Optional[str] = None
    diagnostico: Optional[str] = None
    tecnico_asignado: Optional[str] = None
    horas_trabajo: Optional[float] = None
    fecha_ingreso: Optional[datetime] = None
    fecha_entrega_estimada: Optional[datetime] = None
    # Extra
    items: List[ComprobanteItem] = []
    numero_formateado: str = ""

    class Config:
        from_attributes = True
