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
