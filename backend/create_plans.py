from database import SessionLocal
import models

db = SessionLocal()
try:
    # Verificar si ya hay planes
    existing = db.query(models.Plan).count()
    if existing > 0:
        print(f"Ya existen {existing} planes en la DB. No se crearon nuevos.")
    else:
        # Crear planes por defecto
        planes = [
            models.Plan(
                name='Mensual', 
                months=1, 
                price=15000.0, 
                features='["Acceso completo", "Soporte por email", "Hasta 5 usuarios"]'
            ),
            models.Plan(
                name='Trimestral', 
                months=3, 
                price=40000.0, 
                features='["Acceso completo", "Soporte prioritario", "Hasta 10 usuarios", "5% descuento"]'
            ),
            models.Plan(
                name='Anual', 
                months=12, 
                price=150000.0, 
                features='["Acceso completo", "Soporte 24/7", "Usuarios ilimitados", "15% descuento", "Actualizaciones gratis"]'
            )
        ]
        db.add_all(planes)
        db.commit()
        print('Planes creados exitosamente:')
        for p in db.query(models.Plan).all():
            print(f"  - {p.name}: ${p.price:,.0f} / {p.months} meses")
finally:
    db.close()
