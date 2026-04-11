import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from database import SessionLocal
import models, schemas
from typing import Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_optional(db: Session = Depends(get_db), token: Optional[str] = None) -> Optional[models.User]:
    """Optional authentication - returns None if not authenticated"""
    try:
        from fastapi import Depends as FastAPIDepends
        from fastapi.security import OAuth2PasswordBearer
        from jose import JWTError, jwt
        from config import settings
        
        if not token:
            return None
            
        oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)
        
        credentials_exception = HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
        except JWTError:
            return None

        user = db.query(models.User).filter(models.User.username == username).first()
        return user
    except Exception:
        return None


# -------------------------
# CLIENTS
# -------------------------

@router.post("/clients")
def create_client(data: schemas.ClientCreate, db: Session = Depends(get_db)):

    client = models.Client(**data.dict())

    db.add(client)
    db.commit()
    db.refresh(client)

    return client


@router.get("/clients")
def list_clients(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return db.query(models.Client).offset(skip).limit(limit).all()


@router.get("/clients/count")
def count_clients(db: Session = Depends(get_db)):
    count = db.query(models.Client).count()
    return {"count": count}


@router.put("/clients/{id}")
def update_client(id: int, data: schemas.ClientUpdate, db: Session = Depends(get_db)):

    client = db.query(models.Client).filter(models.Client.id == id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    for key, value in data.dict().items():
        setattr(client, key, value)

    db.commit()
    db.refresh(client)

    return client


@router.delete("/clients/{id}")
def delete_client(id: int, db: Session = Depends(get_db)):

    client = db.query(models.Client).filter(models.Client.id == id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    db.delete(client)
    db.commit()

    return {"ok": True}


# -------------------------
# PRODUCTS
# -------------------------

@router.post("/products")
def create_product(
    data: schemas.ProductCreate,
    db: Session = Depends(get_db)
):

    product = models.Product(**data.dict())

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


@router.get("/products")
def list_products(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return db.query(models.Product).offset(skip).limit(limit).all()


@router.get("/products/count")
def count_products(db: Session = Depends(get_db)):
    count = db.query(models.Product).count()
    return {"count": count}


@router.get("/products/alertas")
def get_alertas_productos(db: Session = Depends(get_db)):
    """Get products with low stock"""
    productos = db.query(models.Product).filter(
        models.Product.stock <= models.Product.stock_minimo,
        models.Product.stock_minimo > 0
    ).order_by(
        (models.Product.stock_minimo - models.Product.stock).desc()
    ).all()
    
    return [
        {
            "id": p.id,
            "nombre": p.name,
            "stock": p.stock,
            "stock_minimo": p.stock_minimo,
            "tipo": "producto"
        }
        for p in productos
    ]


@router.put("/products/{id}")
def update_product(
    id: int,
    data: schemas.ProductUpdate,
    db: Session = Depends(get_db)
):

    product = db.query(models.Product).filter(models.Product.id == id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for key, value in data.dict().items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)

    return product


@router.put("/products/{id}/restock")
def restock_product(
    id: int,
    quantity: int,
    db: Session = Depends(get_db)
):

    product = db.query(models.Product).filter(models.Product.id == id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.stock += quantity

    db.commit()
    db.refresh(product)

    return product


@router.delete("/products/{id}")
def delete_product(
    id: int,
    db: Session = Depends(get_db)
):

    product = db.query(models.Product).filter(models.Product.id == id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()

    return {"ok": True}


# -------------------------
# MATERIALS
# -------------------------

@router.post("/materials")
def create_material(
    data: schemas.MaterialCreate,
    db: Session = Depends(get_db)
):

    material = models.Material(
        sku=data.sku,
        name=data.name,
        category=data.category,
        unit_cost=data.unit_cost,
        stock_minimo=data.stock_minimo or 0
    )

    db.add(material)
    db.flush()   # obtiene el ID sin hacer commit

    if data.current_stock and data.current_stock > 0:

        movement = models.MaterialMovement(
            material_id=material.id,
            quantity=data.current_stock,
            type="IN"
        )

        db.add(movement)

    db.commit()
    db.refresh(material)

    return material


@router.get("/materials")
def list_materials(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):

    materials = db.query(models.Material)\
        .order_by(models.Material.category, models.Material.name)\
        .offset(skip)\
        .limit(limit)\
        .all()

    result = []

    for m in materials:

        total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
            models.MaterialMovement.material_id == m.id,
            models.MaterialMovement.type == "IN"
        ).scalar() or 0

        total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
            models.MaterialMovement.material_id == m.id,
            models.MaterialMovement.type == "OUT"
        ).scalar() or 0

        stock = total_in - total_out
        total_value = stock * (m.unit_cost or 0)

        result.append({
            "id": m.id,
            "sku": m.sku,
            "name": m.name,
            "category": m.category,
            "unit_cost": m.unit_cost,
            "current_stock": stock,
            "stock_minimo": m.stock_minimo,
            "total_value": total_value
        })

    return result


@router.get("/materials/count")
def count_materials(db: Session = Depends(get_db)):
    count = db.query(models.Material).count()
    return {"count": count}


@router.get("/materials/alertas")
def get_alertas_materiales(db: Session = Depends(get_db)):
    """Get materials with low stock"""
    materiales = db.query(models.Material).filter(
        models.Material.current_stock <= models.Material.stock_minimo,
        models.Material.stock_minimo > 0
    ).order_by(
        (models.Material.stock_minimo - models.Material.current_stock).desc()
    ).all()
    
    return [
        {
            "id": m.id,
            "nombre": m.name,
            "categoria": m.category,
            "stock": m.current_stock,
            "stock_minimo": m.stock_minimo,
            "tipo": "material"
        }
        for m in materiales
    ]


@router.put("/materials/{id}")
def update_material(
    id: int,
    data: schemas.MaterialUpdate,
    db: Session = Depends(get_db)
):

    material = db.query(models.Material).filter(models.Material.id == id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    material.sku = data.sku
    material.name = data.name
    material.category = data.category
    material.unit_cost = data.unit_cost
    material.stock_minimo = data.stock_minimo or 0

    total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
        models.MaterialMovement.material_id == id,
        models.MaterialMovement.type == "IN"
    ).scalar() or 0

    total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
        models.MaterialMovement.material_id == id,
        models.MaterialMovement.type == "OUT"
    ).scalar() or 0

    current_stock = total_in - total_out
    diff = data.current_stock - current_stock

    if diff != 0:

        movement = models.MaterialMovement(
            material_id=id,
            quantity=abs(diff),
            type="IN" if diff > 0 else "OUT"
        )

        db.add(movement)

    db.commit()
    db.refresh(material)

    return material


@router.delete("/materials/{id}")
def delete_material(
    id: int,
    db: Session = Depends(get_db)
):

    material = db.query(models.Material).filter(models.Material.id == id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    db.delete(material)
    db.commit()

    return {"ok": True}

# -------------------------
# SALES
# -------------------------

@router.get("/sales")
def list_sales(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List all sales (public endpoint)"""
    sales = db.query(models.Sale).order_by(models.Sale.date.desc()).offset(skip).limit(limit).all()

    result = []
    for s in sales:
        client = db.query(models.Client).filter(models.Client.id == s.client_id).first()
        result.append({
            "id": s.id,
            "client_id": s.client_id,
            "client_name": client.name if client else "Unknown",
            "total": s.total,
            "date": s.date.isoformat() if s.date else None
        })

    return result


@router.get("/sales/count")
def count_sales(db: Session = Depends(get_db)):
    count = db.query(models.Sale).count()
    return {"count": count}


@router.get("/sales/{sale_id}")
def get_sale(sale_id: int, db: Session = Depends(get_db)):
    """Get sale details with items"""
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    client = db.query(models.Client).filter(models.Client.id == sale.client_id).first()
    
    items = []
    for item in sale.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        items.append({
            "id": item.id,
            "product_id": item.product_id,
            "product_name": product.name if product else "Unknown",
            "quantity": item.quantity,
            "price": item.price,
            "subtotal": item.quantity * item.price
        })
    
    return {
        "id": sale.id,
        "client_id": sale.client_id,
        "client_name": client.name if client else "Unknown",
        "total": sale.total,
        "date": sale.date.isoformat() if sale.date else None,
        "items": items
    }


@router.post("/sales")
def create_sale(
    data: schemas.SaleCreate,
    db: Session = Depends(get_db)
):
    """Create a new sale with atomic transaction and stock deduction"""
    logger.info("Creating sale")
    
    # Validate client exists
    client = db.query(models.Client).filter(models.Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    if not data.items:
        raise HTTPException(status_code=400, detail="Sale must have at least one item")
    
    total = 0
    items_data = []
    
    try:
        # First pass: validate stock availability
        for item in data.items:
            product = db.query(models.Product).filter(
                models.Product.id == item.product_id
            ).first()
            
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product with id {item.product_id} not found"
                )
            
            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for product '{product.name}'. Available: {product.stock}, requested: {item.quantity}"
                )
            
            subtotal = product.price * item.quantity
            total += subtotal
            
            items_data.append({
                "product_id": product.id,
                "product_name": product.name,
                "quantity": item.quantity,
                "price": product.price,
                "subtotal": subtotal
            })
        
        # Create sale record
        sale = models.Sale(
            client_id=data.client_id,
            total=total
        )
        db.add(sale)
        db.flush()  # Get sale ID without committing
        
        # Second pass: deduct stock and create sale items with optimistic locking
        for item_data in items_data:
            product = db.query(models.Product).filter(
                models.Product.id == item_data["product_id"]
            ).with_for_update().first()  # Row-level lock
            
            if product.version is None:
                product.version = 1
            
            if product.stock < item_data["quantity"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for product '{product.name}'. Available: {product.stock}, requested: {item_data['quantity']}"
                )
            
            product.stock -= item_data["quantity"]
            product.version += 1
            product.updated_at = datetime.utcnow()
            
            logger.info(f"Stock deducted: {item_data['product_name']} (-{item_data['quantity']}), remaining: {product.stock}, version: {product.version}")
            
            # Create sale item
            sale_item = models.SaleItem(
                sale_id=sale.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                price=item_data["price"]
            )
            db.add(sale_item)
        
        # Commit transaction atomically
        db.commit()
        db.refresh(sale)
        
        logger.info(f"Sale created successfully: ID={sale.id}, total=${total:.2f}, items={len(items_data)}")
        
        return {
            "id": sale.id,
            "client_id": sale.client_id,
            "client_name": client.name,
            "total": sale.total,
            "date": sale.date.isoformat() if sale.date else None,
            "items": items_data,
            "message": "Sale created successfully"
        }
        
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating sale: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error creating sale")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating sale: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error creating sale")


# -------------------------
# DASHBOARD
# -------------------------

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):

    clients = db.query(func.count(models.Client.id)).scalar()
    products = db.query(func.count(models.Product.id)).scalar()
    materials = db.query(func.count(models.Material.id)).scalar()
    sales = db.query(func.sum(models.Sale.total)).scalar() or 0

    return {
        "clients": clients,
        "products": products,
        "materials": materials,
        "sales": sales
    }


# -------------------------
# GLOBAL SEARCH
# -------------------------

@router.get("/search")
def global_search(q: str, db: Session = Depends(get_db)):

    q_like = f"%{q}%"

    products = db.query(models.Product).filter(
        models.Product.name.ilike(q_like) |
        models.Product.sku.ilike(q_like)
    ).limit(5).all()

    materials = db.query(models.Material).filter(
        models.Material.name.ilike(q_like) |
        models.Material.sku.ilike(q_like)
    ).limit(5).all()

    clients = db.query(models.Client).filter(
        models.Client.name.ilike(q_like) |
        models.Client.email.ilike(q_like)
    ).limit(5).all()

    presupuestos = db.query(models.Presupuesto).filter(
        models.Presupuesto.nombre.ilike(q_like) |
        models.Presupuesto.cliente_nombre.ilike(q_like)
    ).limit(5).all()

    result = []

    for p in products:
        result.append({
            "type": "product",
            "id": p.id,
            "label": f"Producto: {p.name}",
            "page": "/products"
        })

    for m in materials:
        result.append({
            "type": "material",
            "id": m.id,
            "label": f"Material: {m.name}",
            "page": "/materials"
        })

    for c in clients:
        result.append({
            "type": "client",
            "id": c.id,
            "label": f"Cliente: {c.name}",
            "page": "/clients"
        })

    for pre in presupuestos:
        result.append({
            "type": "presupuesto",
            "id": pre.id,
            "label": f"Presupuesto: {pre.nombre} ({pre.cliente_nombre or 'Sin cliente'}) - ${pre.precio_final:,.0f}",
            "page": "/budget"
        })

    return result