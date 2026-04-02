"""
Routers para el Módulo de Producción
- Plantillas de producción (recetas)
- Órdenes de producción
- Explosión de materiales
- Ejecución de producción con transacción
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database import SessionLocal
import models, schemas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy user for no-auth mode
class DummyUser:
    id = 1
    username = "system"
    role = "admin"

def get_current_user():
    """No authentication required"""
    return DummyUser()

router = APIRouter(prefix="/produccion", tags=["Producción"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== PLANTILLAS DE PRODUCCIÓN ====================

@router.get("/plantillas", response_model=List[schemas.PlantillaProduccion])
def list_plantillas(
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """Listar todas las plantillas de producción"""
    query = db.query(models.PlantillaProduccion)
    
    if not include_inactive:
        query = query.filter(models.PlantillaProduccion.is_active == True)
    
    plantillas = query.offset(skip).limit(limit).all()
    
    # Agregar info del producto
    result = []
    for p in plantillas:
        p.product_name = p.product.name if p.product else None
        p.product_sku = p.product.sku if p.product else None
        for m in p.materiales:
            m.material_name = m.material.name if m.material else None
            m.material_sku = m.material.sku if m.material else None
            # Calculate stock from movements (using current_stock as base + movements)
            if m.material:
                # Use current_stock as base, adjust by movements
                total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                    models.MaterialMovement.material_id == m.material_id,
                    models.MaterialMovement.type == "IN"
                ).scalar() or 0
                total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                    models.MaterialMovement.material_id == m.material_id,
                    models.MaterialMovement.type == "OUT"
                ).scalar() or 0
                # Start from current_stock and adjust
                m.material_stock = (m.material.current_stock or 0) + total_in - total_out
            else:
                m.material_stock = None
        result.append(p)
    
    return result


@router.get("/plantillas/{plantilla_id}", response_model=schemas.PlantillaProduccion)
def get_plantilla(plantilla_id: int, db: Session = Depends(get_db)):
    """Obtener una plantilla específica"""
    plantilla = db.query(models.PlantillaProduccion).filter(
        models.PlantillaProduccion.id == plantilla_id
    ).first()
    
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    
    plantilla.product_name = plantilla.product.name
    plantilla.product_sku = plantilla.product.sku
    
    for m in plantilla.materiales:
        m.material_name = m.material.name
        m.material_sku = m.material.sku
        # Calculate stock from movements
        if m.material:
            total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                models.MaterialMovement.material_id == m.material_id,
                models.MaterialMovement.type == "IN"
            ).scalar() or 0
            total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                models.MaterialMovement.material_id == m.material_id,
                models.MaterialMovement.type == "OUT"
            ).scalar() or 0
            m.material_stock = (m.material.current_stock or 0) + total_in - total_out
        else:
            m.material_stock = None
    
    return plantilla


@router.post("/plantillas", response_model=schemas.PlantillaProduccion)
def create_plantilla(
    data: schemas.PlantillaProduccionCreate,
    db: Session = Depends(get_db)
):
    """Crear una nueva plantilla de producción (receta)"""
    # Verificar que el producto existe
    product = db.query(models.Product).filter(models.Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar que no exista una plantilla activa para este producto
    existing = db.query(models.PlantillaProduccion).filter(
        models.PlantillaProduccion.product_id == data.product_id,
        models.PlantillaProduccion.is_active == True
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Ya existe una plantilla activa para este producto. Desactívala primero."
        )
    
    # Crear plantilla
    plantilla = models.PlantillaProduccion(
        product_id=data.product_id,
        is_active=data.is_active
    )
    db.add(plantilla)
    db.flush()  # Para obtener el ID
    
    # Agregar materiales
    for m in data.materiales:
        material = db.query(models.Material).filter(models.Material.id == m.material_id).first()
        if not material:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Material con ID {m.material_id} no encontrado")
        
        plantilla_material = models.PlantillaMaterial(
            plantilla_id=plantilla.id,
            material_id=m.material_id,
            cantidad=m.cantidad
        )
        db.add(plantilla_material)
    
    db.commit()
    db.refresh(plantilla)
    
    logger.info(f"Plantilla de producción creada para producto {product.name}")
    return plantilla


@router.put("/plantillas/{plantilla_id}", response_model=schemas.PlantillaProduccion)
def update_plantilla(
    plantilla_id: int,
    data: schemas.PlantillaProduccionUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar una plantilla de producción"""
    plantilla = db.query(models.PlantillaProduccion).filter(
        models.PlantillaProduccion.id == plantilla_id
    ).first()
    
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    
    # Actualizar producto si se proporciona
    if data.product_id is not None:
        product = db.query(models.Product).filter(models.Product.id == data.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        plantilla.product_id = data.product_id
    
    # Actualizar estado activo
    if data.is_active is not None:
        plantilla.is_active = data.is_active
    
    # Actualizar materiales si se proporciona
    if data.materiales is not None:
        # Eliminar materiales existentes
        db.query(models.PlantillaMaterial).filter(
            models.PlantillaMaterial.plantilla_id == plantilla_id
        ).delete()
        
        # Agregar nuevos materiales
        for m in data.materiales:
            material = db.query(models.Material).filter(models.Material.id == m.material_id).first()
            if not material:
                db.rollback()
                raise HTTPException(status_code=404, detail=f"Material con ID {m.material_id} no encontrado")
            
            plantilla_material = models.PlantillaMaterial(
                plantilla_id=plantilla.id,
                material_id=m.material_id,
                cantidad=m.cantidad
            )
            db.add(plantilla_material)
    
    db.commit()
    db.refresh(plantilla)
    
    return plantilla


@router.delete("/plantillas/{plantilla_id}")
def delete_plantilla(plantilla_id: int, db: Session = Depends(get_db)):
    """Eliminar (desactivar) una plantilla de producción"""
    plantilla = db.query(models.PlantillaProduccion).filter(
        models.PlantillaProduccion.id == plantilla_id
    ).first()
    
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    
    plantilla.is_active = False
    db.commit()
    
    return {"ok": True, "message": "Plantilla desactivada"}


@router.get("/productos-sin-plantilla")
def productos_sin_plantilla(db: Session = Depends(get_db)):
    """Listar productos que no tienen plantilla activa"""
    productos_con_plantilla = db.query(models.PlantillaProduccion.product_id).filter(
        models.PlantillaProduccion.is_active == True
    ).subquery()
    
    productos = db.query(models.Product).filter(
        ~models.Product.id.in_(productos_con_plantilla)
    ).all()
    
    return [{"id": p.id, "sku": p.sku, "name": p.name, "stock": p.stock} for p in productos]


# ==================== EXPLOSIÓN DE MATERIALES ====================

@router.get("/explosion-materiales", response_model=schemas.ExplosiónMaterialesResponse)
@router.post("/explosion-materiales", response_model=schemas.ExplosiónMaterialesResponse)
def explode_materiales(
    plantilla_id: int,
    cantidad: int,
    db: Session = Depends(get_db)
):
    """Calcular materiales necesarios para una cantidad de producción"""
    if cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    
    # Obtener plantilla
    plantilla = db.query(models.PlantillaProduccion).filter(
        models.PlantillaProduccion.id == plantilla_id,
        models.PlantillaProduccion.is_active == True
    ).first()
    
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada o inactiva")
    
    # Calcular materiales necesarios
    materiales = []
    materiales_faltantes = []
    puede_producir = True
    
    for m in plantilla.materiales:
        cantidad_necesaria = m.cantidad * cantidad
        # Calculate stock: current_stock as base + movements
        if m.material:
            total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                models.MaterialMovement.material_id == m.material_id,
                models.MaterialMovement.type == "IN"
            ).scalar() or 0
            total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                models.MaterialMovement.material_id == m.material_id,
                models.MaterialMovement.type == "OUT"
            ).scalar() or 0
            stock_actual = (m.material.current_stock or 0) + total_in - total_out
        else:
            stock_actual = 0
        
        tiene_suficiente = stock_actual >= cantidad_necesaria
        
        if not tiene_suficiente:
            puede_producir = False
            materiales_faltantes.append(
                f"{m.material.name}: necesita {cantidad_necesaria}, hay {stock_actual}"
            )
        
        materiales.append({
            "id": m.id,
            "material_id": m.material_id,
            "cantidad_necesaria": cantidad_necesaria,
            "material_name": m.material.name,
            "material_sku": m.material.sku,
            "stock_actual": stock_actual,
            "tiene_suficiente": tiene_suficiente
        })
    
    return {
        "plantilla_id": plantilla.id,
        "product_id": plantilla.product_id,
        "product_name": plantilla.product.name,
        "cantidad_producir": cantidad,
        "materiales": materiales,
        "puede_producir": puede_producir,
        "materiales_faltantes": materiales_faltantes if materiales_faltantes else None
    }


# ==================== ÓRDENES DE PRODUCCIÓN ====================

@router.get("/ordenes", response_model=List[schemas.OrdenProduccion])
def list_ordenes(
    skip: int = 0,
    limit: int = 50,
    estado: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Listar órdenes de producción"""
    query = db.query(models.OrdenProduccion)
    
    if estado:
        query = query.filter(models.OrdenProduccion.estado == estado)
    
    ordenes = query.order_by(models.OrdenProduccion.fecha_creacion.desc()).offset(skip).limit(limit).all()
    
    result = []
    for o in ordenes:
        o.product_name = o.plantilla.product.name if o.plantilla and o.plantilla.product else None
        for m in o.materiales_consumidos:
            m.material_name = m.material.name if m.material else None
            m.material_sku = m.material.sku if m.material else None
            m.stock_actual = stock_actual if m.material else None
        result.append(o)
    
    return result


@router.get("/ordenes/{orden_id}", response_model=schemas.OrdenProduccion)
def get_orden(orden_id: int, db: Session = Depends(get_db)):
    """Obtener una orden de producción específica"""
    orden = db.query(models.OrdenProduccion).filter(
        models.OrdenProduccion.id == orden_id
    ).first()
    
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    orden.product_name = orden.plantilla.product.name if orden.plantilla else None
    
    for m in orden.materiales_consumidos:
        m.material_name = m.material.name if m.material else None
        m.material_sku = m.material.sku if m.material else None
        m.stock_actual = stock_actual if m.material else None
    
    return orden


@router.post("/ordenes", response_model=schemas.OrdenProduccion)
def create_orden(
    data: schemas.OrdenProduccionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear una orden de producción (sin ejecutar aún)"""
    # Verificar plantilla
    plantilla = db.query(models.PlantillaProduccion).filter(
        models.PlantillaProduccion.id == data.plantilla_id,
        models.PlantillaProduccion.is_active == True
    ).first()
    
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada o inactiva")
    
    if data.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    
    # Crear orden
    orden = models.OrdenProduccion(
        plantilla_id=data.plantilla_id,
        cantidad=data.cantidad,
        notas=data.notas,
        estado="pendiente",
        created_by=current_user.id
    )
    db.add(orden)
    db.flush()
    
    # Calcular materiales necesarios y guardarlos
    for m in plantilla.materiales:
        cantidad_necesaria = m.cantidad * data.cantidad
        consumo = models.MaterialConsumo(
            orden_id=orden.id,
            material_id=m.material_id,
            cantidad_necesaria=cantidad_necesaria
        )
        db.add(consumo)
    
    db.commit()
    db.refresh(orden)
    
    logger.info(f"Orden de producción {orden.id} creada para {data.cantidad} unidades")
    
    orden.product_name = plantilla.product.name
    return orden


# ==================== EJECUCIÓN DE PRODUCCIÓN (TRANSACCIÓN) ====================

@router.post("/ejecutar", response_model=schemas.ProduccionEjecutarResponse)
def ejecutar_produccion(
    data: schemas.ProduccionEjecutarRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ejecutar una orden de producción:
    1. Verificar stock de materiales
    2. Crear registro de orden
    3. Restar materiales del inventario
    4. Sumar producto al inventario
    Todo dentro de una transacción SQL
    """
    
    # Obtener plantilla
    plantilla = db.query(models.PlantillaProduccion).filter(
        models.PlantillaProduccion.id == data.plantilla_id,
        models.PlantillaProduccion.is_active == True
    ).first()
    
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada o inactiva")
    
    if data.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    
    # Verificar que tenemos todos los materiales disponibles
    materiales_faltantes = []
    for m in plantilla.materiales:
        cantidad_necesaria = m.cantidad * data.cantidad
        # Calculate current stock from movements
        if m.material:
            total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                models.MaterialMovement.material_id == m.material_id,
                models.MaterialMovement.type == "IN"
            ).scalar() or 0
            total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                models.MaterialMovement.material_id == m.material_id,
                models.MaterialMovement.type == "OUT"
            ).scalar() or 0
            stock_actual = (m.material.current_stock or 0) + total_in - total_out
        else:
            stock_actual = 0
            
        if stock_actual < cantidad_necesaria:
            materiales_faltantes.append(
                f"{m.material.name}: necesita {cantidad_necesaria}, hay {stock_actual}"
            )
    
    if materiales_faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficiente stock. Faltantes: {', '.join(materiales_faltantes)}"
        )
    
    # ============ INICIO DE TRANSACCIÓN ============
    try:
        # 1. Crear la orden de producción
        orden = models.OrdenProduccion(
            plantilla_id=data.plantilla_id,
            cantidad=data.cantidad,
            notas=data.notas,
            estado="completada",
            fecha_inicio=datetime.utcnow(),
            fecha_fin=datetime.utcnow(),
            created_by=current_user.id
        )
        db.add(orden)
        db.flush()
        
        materiales_actualizados = []
        
        # 2. Registrar materiales consumidos Y restar del inventario
        for m in plantilla.materiales:
            cantidad_necesaria = m.cantidad * data.cantidad
            
            # Calcular stock actual (from movements + current_stock for compatibility)
            if m.material:
                total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                    models.MaterialMovement.material_id == m.material_id,
                    models.MaterialMovement.type == "IN"
                ).scalar() or 0
                total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                    models.MaterialMovement.material_id == m.material_id,
                    models.MaterialMovement.type == "OUT"
                ).scalar() or 0
                calculated_stock = (m.material.current_stock or 0) + total_in - total_out
                # Also update current_stock for backwards compatibility
                m.material.current_stock = calculated_stock
            
            # Crear registro de consumo
            consumo = models.MaterialConsumo(
                orden_id=orden.id,
                material_id=m.material_id,
                cantidad_necesaria=cantidad_necesaria,
                cantidad_consumida=cantidad_necesaria
            )
            db.add(consumo)
            
            # Restar del stock (now using calculated stock)
            if m.material:
                new_stock = m.material.current_stock - cantidad_necesaria
                # Don't allow negative stock
                if new_stock < 0:
                    new_stock = 0
                m.material.current_stock = new_stock
            
            # Registrar movimiento de salida
            movimiento = models.MaterialMovement(
                material_id=m.material_id,
                quantity=cantidad_necesaria,
                type="OUT",
                reason=f"Producción orden {orden.id}"
            )
            db.add(movimiento)
            
            materiales_actualizados.append({
                "material_id": m.material_id,
                "material_name": m.material.name,
                "cantidad_consumida": cantidad_necesaria,
                "stock_restante": m.material.current_stock if m.material else 0
            })
        
        # 3. Sumar producto al inventario
        producto = db.query(models.Product).filter(
            models.Product.id == plantilla.product_id
        ).first()
        
        producto.stock += data.cantidad
        
        producto_actualizado = {
            "product_id": producto.id,
            "product_name": producto.name,
            "cantidad_producida": data.cantidad,
            "stock_nuevo": producto.stock
        }
        
        # Confirmar transacción
        db.commit()
        
        logger.info(f"Producción ejecutada: orden {orden.id}, {data.cantidad} {producto.name}")
        
        return {
            "success": True,
            "message": f"Producción de {data.cantidad} {producto.name} completada",
            "orden_id": orden.id,
            "materiales_actualizados": materiales_actualizados,
            "producto_actualizado": producto_actualizado
        }
        
    except Exception as e:
        # Rollback en caso de error
        db.rollback()
        logger.error(f"Error al ejecutar producción: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar producción: {str(e)}"
        )


@router.post("/ordenes/{orden_id}/cancelar")
def cancelar_orden(
    orden_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancelar una orden de producción"""
    orden = db.query(models.OrdenProduccion).filter(
        models.OrdenProduccion.id == orden_id
    ).first()
    
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    if orden.estado == "completada":
        raise HTTPException(status_code=400, detail="No se puede cancelar una orden completada")
    
    orden.estado = "cancelada"
    db.commit()
    
    return {"ok": True, "message": "Orden cancelada"}