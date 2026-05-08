@router.post("/iniciar-sesion")
def iniciar_sesion(data: dict, db: Session = Depends(get_db)):
    """
    Verifica licencia en Supabase y maneja trial local.
    Body: { "client_id": "uuid-from-localStorage" }
    """
    try:
        client_id = data.get("client_id")
        
        if not client_id:
            raise HTTPException(status_code=400, detail="client_id requerido")
        
        # 1. Intentar consultar Supabase (NO interrumpir si falla)
        license_data = None
        try:
            import requests
            supabase_url = f"{settings.SUPABASE_URL}/rest/v1/licencias"
            headers = {
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}"
            }
            
            params = {
                "client_id": f"eq.{client_id}",
                "estado": "eq.activa",
                "order": "fecha_inicio.desc",
                "limit": "1"
            }
            
            response = requests.get(supabase_url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                licenses = response.json()
                if licenses:
                    license_data = licenses[0]
        except Exception as e:
            # Si Supabase falla, seguimos con license_data = None
            logger.warning(f"Supabase no disponible: {e}. Usando trial local.")
        
        # 2. Si no hay licencia en Supabase, verificar trial local
        if not license_data:
            trial = db.query(models.LicenseTrial).filter(
                models.LicenseTrial.client_id == client_id,
                models.LicenseTrial.activo == True
            ).first()
            
            from datetime import datetime, timedelta
            
            if trial:
                trial_end = trial.fecha_inicio + timedelta(days=30)
                now = datetime.now()
                
                if now < trial_end:
                    return {
                        "ok": True,
                        "tipo": "trial",
                        "dias_restantes": (trial_end - now).days,
                        "fecha_fin": trial_end.isoformat()
                    }
                else:
                    trial.activo = False
                    db.commit()
                    return {
                        "ok": False,
                        "error": "trial_expirado",
                        "mensaje": "El periodo de prueba ha finalizado"
                    }
            else:
                # Crear NUEVO trial
                new_trial = models.LicenseTrial(
                    client_id=client_id,
                    fecha_inicio=datetime.now(),
                    activo=True
                )
                db.add(new_trial)
                db.commit()
                return {
                    "ok": True,
                    "tipo": "trial",
                    "dias_restantes": 30,
                    "fecha_fin": (datetime.now() + timedelta(days=30)).isoformat()
                }
        
        # 3. Licencia de Supabase encontrada
        from datetime import datetime
        now = datetime.now()
        fecha_fin = datetime.fromisoformat(license_data["fecha_fin"].replace("Z", ""))
        
        if now < fecha_fin:
            return {
                "ok": True,
                "tipo": "licencia",
                "plan": license_data["plan_tipo"],
                "dias_restantes": (fecha_fin - now).days,
                "fecha_fin": license_data["fecha_fin"]
            }
        else:
            return {
                "ok": False,
                "error": "licencia_expirada"
            }
            
    except Exception as e:
        logger.error(f"Error en iniciar_sesion: {e}")
        raise HTTPException(status_code=500, detail="Error interno")
