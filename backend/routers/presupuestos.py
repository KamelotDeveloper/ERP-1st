"""
Routers para el Módulo de Presupuestos
- Crear presupuestos personalizados
- Calcular costos de materiales + mano de obra + margen
- Enviar por WhatsApp y Email
- Convertir a venta (restar stock)
"""

import logging
import urllib.parse
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SessionLocal
import models, schemas

# Dummy user for no-auth mode
class DummyUser:
    id = 1
    username = "system"
    role = "admin"

def get_current_user():
    """No authentication required"""
    return DummyUser()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/presupuestos", tags=["Presupuestos"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calcular_costo_materiales(items: List[dict], db: Session) -> float:
    """Calcula el costo total de materiales basado en los items del presupuesto"""
    total = 0
    for item in items:
        material = db.query(models.Material).filter(models.Material.id == item['material_id']).first()
        if material:
            # Calcular stock actual
            total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                models.MaterialMovement.material_id == item['material_id'],
                models.MaterialMovement.type == "IN"
            ).scalar() or 0
            total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
                models.MaterialMovement.material_id == item['material_id'],
                models.MaterialMovement.type == "OUT"
            ).scalar() or 0
            current_stock = (material.current_stock or 0) + total_in - total_out
            
            # Usar el precio actual del material
            precio = material.unit_cost or 0
            total += precio * item['cantidad']
    return total


def calcular_precio_final(costo_materiales: float, costo_mano_obra: float, margen: float) -> float:
    """Calcula el precio final: (costo materiales + mano obra) + margen"""
    return costo_materiales + costo_mano_obra + margen


# ==================== CRUD PRESUPUESTOS ====================

@router.get("", response_model=List[schemas.Presupuesto])
def list_presupuestos(
    skip: int = 0,
    limit: int = 20,
    estado: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Listar todos los presupuestos con paginación"""
    query = db.query(models.Presupuesto)
    
    if estado:
        query = query.filter(models.Presupuesto.estado == estado)
    
    total = query.count()
    
    presupuestos = query.order_by(models.Presupuesto.fecha_creacion.desc()).offset(skip).limit(limit).all()
    
    for p in presupuestos:
        for item in p.items:
            if item.material:
                item.material_name = item.material.name
                item.material_sku = item.material.sku
    
    # Agregar header X-Total-Count para paginación
    return presupuestos


@router.get("/count")
def count_presupuestos(
    estado: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Contar total de presupuestos"""
    query = db.query(models.Presupuesto)
    
    if estado:
        query = query.filter(models.Presupuesto.estado == estado)
    
    return {"count": query.count()}
    
    if estado:
        query = query.filter(models.Presupuesto.estado == estado)
    
    presupuestos = query.order_by(models.Presupuesto.fecha_creacion.desc()).offset(skip).limit(limit).all()
    
    for p in presupuestos:
        # Cargar nombres de materiales en items
        for item in p.items:
            if item.material:
                item.material_name = item.material.name
                item.material_sku = item.material.sku
    
    return presupuestos


@router.get("/{presupuesto_id}", response_model=schemas.Presupuesto)
def get_presupuesto(presupuesto_id: int, db: Session = Depends(get_db)):
    """Obtener un presupuesto específico"""
    presupuesto = db.query(models.Presupuesto).filter(
        models.Presupuesto.id == presupuesto_id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    for item in presupuesto.items:
        if item.material:
            item.material_name = item.material.name
            item.material_sku = item.material.sku
    
    return presupuesto


@router.post("", response_model=schemas.Presupuesto)
def create_presupuesto(
    data: schemas.PresupuestoCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear un nuevo presupuesto"""
    
    # Calcular costo de materiales
    items_data = [item.dict() for item in data.items]
    costo_materiales = 0
    
    for item_data in items_data:
        material = db.query(models.Material).filter(models.Material.id == item_data['material_id']).first()
        if not material:
            raise HTTPException(status_code=404, detail=f"Material con ID {item_data['material_id']} no encontrado")
        
        precio_unitario = material.unit_cost or 0
        item_data['precio_unitario'] = precio_unitario
        item_data['subtotal'] = precio_unitario * item_data['cantidad']
        costo_materiales += item_data['subtotal']
    
    # Calcular precio final
    precio_final = calcular_precio_final(costo_materiales, data.costo_mano_obra, data.margen)
    
    # Crear presupuesto
    presupuesto = models.Presupuesto(
        nombre=data.nombre,
        cliente_nombre=data.cliente_nombre,
        cliente_telefono=data.cliente_telefono,
        cliente_email=data.cliente_email,
        estado="pendiente",
        costo_materiales=costo_materiales,
        costo_mano_obra=data.costo_mano_obra,
        margen=data.margen,
        precio_final=precio_final,
        notas=data.notas,
        created_by=current_user.id
    )
    db.add(presupuesto)
    db.flush()
    
    # Crear items
    for item_data in items_data:
        item = models.PresupuestoItem(
            presupuesto_id=presupuesto.id,
            material_id=item_data['material_id'],
            cantidad=item_data['cantidad'],
            precio_unitario=item_data['precio_unitario'],
            subtotal=item_data['subtotal']
        )
        db.add(item)
    
    db.commit()
    db.refresh(presupuesto)
    
    # Cargar nombres de materiales
    for item in presupuesto.items:
        if item.material:
            item.material_name = item.material.name
            item.material_sku = item.material.sku
    
    logger.info(f"Presupuesto {presupuesto.id} creado: {presupuesto.nombre}")
    
    return presupuesto


@router.put("/{presupuesto_id}", response_model=schemas.Presupuesto)
def update_presupuesto(
    presupuesto_id: int,
    data: schemas.PresupuestoUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar un presupuesto (modificar items, costos, cliente)"""
    presupuesto = db.query(models.Presupuesto).filter(
        models.Presupuesto.id == presupuesto_id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    if presupuesto.estado in ['vendido', 'aceptado']:
        raise HTTPException(status_code=400, detail="No se puede modificar un presupuesto ya aceptado/vendido")
    
    # Actualizar campos simples
    if data.nombre is not None:
        presupuesto.nombre = data.nombre
    if data.cliente_nombre is not None:
        presupuesto.cliente_nombre = data.cliente_nombre
    if data.cliente_telefono is not None:
        presupuesto.cliente_telefono = data.cliente_telefono
    if data.cliente_email is not None:
        presupuesto.cliente_email = data.cliente_email
    if data.costo_mano_obra is not None:
        presupuesto.costo_mano_obra = data.costo_mano_obra
    if data.margen is not None:
        presupuesto.margen = data.margen
    if data.notas is not None:
        presupuesto.notas = data.notas
    
    # Recalcular si cambiaron items
    if data.items is not None:
        # Eliminar items existentes
        db.query(models.PresupuestoItem).filter(
            models.PresupuestoItem.presupuesto_id == presupuesto_id
        ).delete()
        
        # Calcular nuevo costo de materiales
        costo_materiales = 0
        items_data = [item.dict() for item in data.items]
        
        for item_data in items_data:
            material = db.query(models.Material).filter(models.Material.id == item_data['material_id']).first()
            if not material:
                raise HTTPException(status_code=404, detail=f"Material {item_data['material_id']} no encontrado")
            
            precio_unitario = material.unit_cost or 0
            item_data['precio_unitario'] = precio_unitario
            item_data['subtotal'] = precio_unitario * item_data['cantidad']
            costo_materiales += item_data['subtotal']
            
            # Crear nuevo item
            item = models.PresupuestoItem(
                presupuesto_id=presupuesto.id,
                material_id=item_data['material_id'],
                cantidad=item_data['cantidad'],
                precio_unitario=item_data['precio_unitario'],
                subtotal=item_data['subtotal']
            )
            db.add(item)
        
        presupuesto.costo_materiales = costo_materiales
    
    # Recalcular precio final
    presupuesto.precio_final = calcular_precio_final(
        presupuesto.costo_materiales,
        presupuesto.costo_mano_obra,
        presupuesto.margen
    )
    
    db.commit()
    db.refresh(presupuesto)
    
    for item in presupuesto.items:
        if item.material:
            item.material_name = item.material.name
            item.material_sku = item.material.sku
    
    return presupuesto


@router.delete("/{presupuesto_id}")
def delete_presupuesto(
    presupuesto_id: int,
    db: Session = Depends(get_db)
):
    """Eliminar un presupuesto"""
    presupuesto = db.query(models.Presupuesto).filter(
        models.Presupuesto.id == presupuesto_id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    if presupuesto.estado == 'vendido':
        raise HTTPException(status_code=400, detail="No se puede eliminar un presupuesto vendido")
    
    # Eliminar items primero (por cascade ya debería hacer pero aseguramos)
    db.query(models.PresupuestoItem).filter(
        models.PresupuestoItem.presupuesto_id == presupuesto_id
    ).delete()
    
    db.delete(presupuesto)
    db.commit()
    
    return {"ok": True, "message": "Presupuesto eliminado"}


# ==================== CONFIRMAR VENTA ====================

@router.post("/{presupuesto_id}/confirmar-venta", response_model=schemas.PresupuestoConfirmarVentaResponse)
def confirmar_venta(
    presupuesto_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirmar presupuesto como venta: resta materiales del stock"""
    presupuesto = db.query(models.Presupuesto).filter(
        models.Presupuesto.id == presupuesto_id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    if presupuesto.estado == 'vendido':
        raise HTTPException(status_code=400, detail="Este presupuesto ya fue vendido")
    
    if presupuesto.estado == 'rechazado':
        raise HTTPException(status_code=400, detail="No se puede vender un presupuesto rechazado")
    
    # Verificar stock de materiales
    materiales_faltantes = []
    for item in presupuesto.items:
        material = item.material
        if not material:
            continue
        
        # Calcular stock actual
        total_in = db.query(func.sum(models.MaterialMovement.quantity)).filter(
            models.MaterialMovement.material_id == item.material_id,
            models.MaterialMovement.type == "IN"
        ).scalar() or 0
        total_out = db.query(func.sum(models.MaterialMovement.quantity)).filter(
            models.MaterialMovement.material_id == item.material_id,
            models.MaterialMovement.type == "OUT"
        ).scalar() or 0
        stock_actual = (material.current_stock or 0) + total_in - total_out
        
        if stock_actual < item.cantidad:
            materiales_faltantes.append(
                f"{material.name}: necesita {item.cantidad}, hay {stock_actual}"
            )
    
    if materiales_faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficiente stock. Faltantes: {', '.join(materiales_faltantes)}"
        )
    
    # Iniciar transacción
    try:
        # 1. Restar materiales del stock
        materiales_actualizados = []
        for item in presupuesto.items:
            material = item.material
            if material:
                # Actualizar current_stock
                new_stock = material.current_stock - item.cantidad
                if new_stock < 0:
                    new_stock = 0
                material.current_stock = new_stock
                
                # Registrar movimiento
                movimiento = models.MaterialMovement(
                    material_id=item.material_id,
                    quantity=item.cantidad,
                    type="OUT",
                    reason=f"Venta presupuesto {presupuesto.id}"
                )
                db.add(movimiento)
                
                materiales_actualizados.append({
                    "material_id": material.id,
                    "material_name": material.name,
                    "cantidad": item.cantidad,
                    "stock_restante": material.current_stock
                })
        
        # 2. Marcar presupuesto como vendido
        presupuesto.estado = "vendido"
        presupuesto.fecha_aceptacion = datetime.utcnow()
        
        # 3. Buscar o crear cliente si existe en presupuesto
        client_id = None
        if presupuesto.cliente_nombre:
            # Buscar cliente existente por nombre
            existing_client = db.query(models.Client).filter(
                models.Client.name == presupuesto.cliente_nombre
            ).first()
            
            if existing_client:
                client_id = existing_client.id
            else:
                # Crear nuevo cliente
                new_client = models.Client(
                    name=presupuesto.cliente_nombre,
                    phone=presupuesto.cliente_telefono,
                    email=presupuesto.cliente_email
                )
                db.add(new_client)
                db.flush()
                client_id = new_client.id
        
        # 4. Crear registro de venta (Sale) con cliente
        venta = models.Sale(
            client_id=client_id,
            total=presupuesto.precio_final,
            date=datetime.utcnow()
        )
        db.add(venta)
        db.flush()
        
        # 5. Crear sale items para cada material
        for item in presupuesto.items:
            sale_item = models.SaleItem(
                sale_id=venta.id,
                product_id=None,  # Es un trabajo personalizado, no un producto
                quantity=item.cantidad,
                price=item.subtotal
            )
            db.add(sale_item)
        
        db.commit()
        
        logger.info(f"Venta confirmada para presupuesto {presupuesto.id}: {presupuesto.nombre}")
        
        return {
            "success": True,
            "message": f"Venta confirmada por ${presupuesto.precio_final:,.0f}",
            "venta_id": presupuesto.id,
            "materiales_actualizados": materiales_actualizados
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al confirmar venta: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar venta: {str(e)}")


@router.post("/{presupuesto_id}/aceptar")
def aceptar_presupuesto(
    presupuesto_id: int,
    db: Session = Depends(get_db)
):
    """Aceptar presupuesto sin confirmar venta (queda pendiente de venta)"""
    presupuesto = db.query(models.Presupuesto).filter(
        models.Presupuesto.id == presupuesto_id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    if presupuesto.estado != 'pendiente':
        raise HTTPException(status_code=400, detail="Solo se pueden aceptar presupuestos pendientes")
    
    presupuesto.estado = "aceptado"
    presupuesto.fecha_aceptacion = datetime.utcnow()
    db.commit()
    
    return {"ok": True, "message": "Presupuesto aceptado"}


@router.post("/{presupuesto_id}/rechazar")
def rechazar_presupuesto(
    presupuesto_id: int,
    db: Session = Depends(get_db)
):
    """Rechazar presupuesto"""
    presupuesto = db.query(models.Presupuesto).filter(
        models.Presupuesto.id == presupuesto_id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    presupuesto.estado = "rechazado"
    db.commit()
    
    return {"ok": True, "message": "Presupuesto rechazado"}


# ==================== ENVÍO POR WHATSAPP Y EMAIL ====================

@router.get("/{presupuesto_id}/whatsapp")
def generar_link_whatsapp(
    presupuesto_id: int,
    db: Session = Depends(get_db)
):
    """Generar link de WhatsApp para enviar presupuesto"""
    presupuesto = db.query(models.Presupuesto).filter(
        models.Presupuesto.id == presupuesto_id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    if not presupuesto.cliente_telefono:
        raise HTTPException(status_code=400, detail="El presupuesto no tiene teléfono del cliente")
    
    # Limpiar teléfono (solo números)
    telefono = ''.join(c for c in presupuesto.cliente_telefono if c.isdigit())
    if telefono.startswith('0'):
        telefono = telefono[1:]
    if not telefono.startswith('54'):
        telefono = '54' + telefono
    
    # Construir mensaje
    mensaje = f"*{presupuesto.nombre}*\n\n"
    mensaje += "📋 *DETALLE DEL PRESUPUESTO*\n\n"
    
    for item in presupuesto.items:
        mensaje += f"• {item.material.name if item.material else 'Material'}\n"
        mensaje += f"  {item.cantidad} x ${item.precio_unitario:,.0f} = ${item.subtotal:,.0f}\n\n"
    
    mensaje += f"━━━━━━━━━━━━━━━━━━━━\n"
    mensaje += f"*MATERIALES:* ${presupuesto.costo_materiales:,.0f}\n"
    mensaje += f"*MANO DE OBRA:* ${presupuesto.costo_mano_obra:,.0f}\n"
    mensaje += f"*MARGEN:* ${presupuesto.margen:,.0f}\n"
    mensaje += f"━━━━━━━━━━━━━━━━━━━━\n"
    mensaje += f"*TOTAL:* ${presupuesto.precio_final:,.0f}\n\n"
    
    if presupuesto.notas:
        mensaje += f"📝 *Nota:* {presupuesto.notas}\n\n"
    
    mensaje += "_Gracias por confiar en El Menestral._"
    
    # Codificar mensaje
    mensaje_codificado = urllib.parse.quote(mensaje)
    
    # Construir URL
    url = f"https://wa.me/{telefono}?text={mensaje_codificado}"
    
    return {
        "url": url,
        "telefono": telefono,
        "mensaje": mensaje
    }


@router.get("/{presupuesto_id}/email")
def generar_email(
    presupuesto_id: int,
    db: Session = Depends(get_db)
):
    """Generar contenido de email para enviar presupuesto"""
    presupuesto = db.query(models.Presupuesto).filter(
        models.Presupuesto.id == presupuesto_id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    # Construir email HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background: #2e86de; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        .total {{ font-size: 18px; font-weight: bold; background: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>El Menestral - Presupuesto</h2>
    </div>
    <div class="content">
        <h3>Presupuesto: {presupuesto.nombre}</h3>
        <p><strong>Cliente:</strong> {presupuesto.cliente_nombre or 'Sin nombre'}</p>
        <p><strong>Fecha:</strong> {presupuesto.fecha_creacion.strftime('%d/%m/%Y')}</p>
        
        <h4>Detalle de Materiales</h4>
        <table>
            <thead>
                <tr>
                    <th>Material</th>
                    <th>Cantidad</th>
                    <th>Precio Unit.</th>
                    <th>Subtotal</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for item in presupuesto.items:
        html += f"""
                <tr>
                    <td>{item.material.name if item.material else 'Material'}</td>
                    <td>{item.cantidad}</td>
                    <td>${item.precio_unitario:,.0f}</td>
                    <td>${item.subtotal:,.0f}</td>
                </tr>
"""
    
    html += f"""
            </tbody>
            <tfoot>
                <tr>
                    <td colspan="3"><strong>Subtotal Materiales</strong></td>
                    <td>${presupuesto.costo_materiales:,.0f}</td>
                </tr>
                <tr>
                    <td colspan="3"><strong>Mano de Obra</strong></td>
                    <td>${presupuesto.costo_mano_obra:,.0f}</td>
                </tr>
                <tr>
                    <td colspan="3"><strong>Margen</strong></td>
                    <td>${presupuesto.margen:,.0f}</td>
                </tr>
                <tr class="total">
                    <td colspan="3"><strong>TOTAL</strong></td>
                    <td><strong>${presupuesto.precio_final:,.0f}</strong></td>
                </tr>
            </tfoot>
        </table>
"""
    
    if presupuesto.notas:
        html += f"""
        <h4>Notas:</h4>
        <p>{presupuesto.notas}</p>
"""
    
    html += """
        <p style="margin-top: 30px; color: #666;">
            Gracias por confiar en <strong>El Menestral</strong><br>
            Carpintería y más...
        </p>
    </div>
</body>
</html>
"""
    
    return {
        "to": presupuesto.cliente_email,
        "subject": f"Presupuesto: {presupuesto.nombre} - El Menestral",
        "html": html,
        "plain_text": f"Presupuesto: {presupuesto.nombre}\n\nTotal: ${presupuesto.precio_final:,.0f}"
    }