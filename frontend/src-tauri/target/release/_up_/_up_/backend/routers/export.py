from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models,schemas

router = APIRouter()


@router.post("/materials")
def create_material(data: schemas.MaterialCreate, db: Session = Depends(get_db)):

    material = models.Material(
        sku=data.sku,
        name=data.name,
        category=data.category,
        unit_cost=data.unit_cost
    )

    db.add(material)
    db.flush()

    if data.stock and data.stock > 0:

        movement=models.MaterialMovement(
            material_id=material.id,
            quantity=data.stock,
            type="IN"
        )

        db.add(movement)

    db.commit()
    db.refresh(material)

    return material


@router.get("/materials")
def list_materials(db: Session = Depends(get_db)):

    materials=db.query(models.Material).all()

    result=[]

    for m in materials:

        totals=db.query(
            func.sum(
                func.case(
                    (models.MaterialMovement.type=="IN",models.MaterialMovement.quantity),
                    else_=-models.MaterialMovement.quantity
                )
            )
        ).filter(
            models.MaterialMovement.material_id==m.id
        ).scalar()

        stock=totals or 0
        total_value=stock*(m.unit_cost or 0)

        result.append({
            "id":m.id,
            "sku":m.sku,
            "name":m.name,
            "category":m.category,
            "unit_cost":m.unit_cost,
            "stock":stock,
            "total_value":total_value
        })

    return result