import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from database import SessionLocal
import models
import schemas
from services.comprobante_numbering import get_next_numero
from services.comprobante_fiscal import generate_mock_cae, get_tipo_afip_from_tipo, get_client_tipo_doc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comprobantes", tags=["Comprobantes"])

FISCAL_TIPOS_A = {"FACTURA_A", "NOTA_DEBITO_A", "NOTA_CREDITO_A", "FACTURA_M"}
FISCAL_TIPOS_B = {"FACTURA_B", "NOTA_DEBITO_B", "NOTA_CREDITO_B"}
FISCAL_TIPOS_C = {"FACTURA_C", "NOTA_DEBITO_C", "NOTA_CREDITO_C"}


def _get_iva_condition(tipo: str) -> str:
    if tipo in FISCAL_TIPOS_A:
        return "IVA RESPONSABLE INSCRITO"
    if tipo in FISCAL_TIPOS_B:
        return "IVA RESPONSABLE INSCRITO"
    if tipo in FISCAL_TIPOS_C:
        return "RESPONSABLE MONOTRIBUTO"
    if tipo == "FACTURA_E":
        return "IVA RESPONSABLE INSCRITO - EXPORTACIÓN"
    return "IVA RESPONSABLE INSCRITO"


_INFACTURA_CLIENT_COND = {
    "FACTURA_A": "Responsable Inscripto",
    "FACTURA_B": "Consumidor Final",
    "FACTURA_C": "Consumidor Final / Monotributo",
    "FACTURA_M": "Responsable Inscripto",
    "FACTURA_E": "Exportación",
    "NOTA_DEBITO_A": "Responsable Inscripto",
    "NOTA_DEBITO_B": "Consumidor Final",
    "NOTA_DEBITO_C": "Consumidor Final / Monotributo",
    "NOTA_CREDITO_A": "Responsable Inscripto",
    "NOTA_CREDITO_B": "Consumidor Final",
    "NOTA_CREDITO_C": "Consumidor Final / Monotributo",
}


def _get_cliente_iva_condition(tipo: str) -> str:
    return _INFACTURA_CLIENT_COND.get(tipo, "Consumidor Final")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tipo classification sets
# ---------------------------------------------------------------------------
FISCAL_TIPOS = {
    "FACTURA_A", "FACTURA_B", "FACTURA_C", "FACTURA_M", "FACTURA_E",
    "NOTA_DEBITO_A", "NOTA_DEBITO_B", "NOTA_DEBITO_C",
    "NOTA_CREDITO_A", "NOTA_CREDITO_B", "NOTA_CREDITO_C",
}

NC_TIPOS = {
    "NOTA_CREDITO_A", "NOTA_CREDITO_B", "NOTA_CREDITO_C",
}

NC_ND_TIPOS = {
    "NOTA_DEBITO_A", "NOTA_DEBITO_B", "NOTA_DEBITO_C",
    "NOTA_CREDITO_A", "NOTA_CREDITO_B", "NOTA_CREDITO_C",
}

VALID_ESTADO_TRANSITIONS = {
    "draft": {"issued", "cancelled"},
    "issued": {"cancelled"},
    "cancelled": set(),
    "error": {"draft", "issued"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def format_numero(punto_venta: int, numero: int) -> str:
    return f"{punto_venta:05d}-{numero:08d}"


def _build_list_item(c: models.Comprobante) -> dict:
    return {
        "id": c.id,
        "tipo": c.tipo,
        "estado": c.estado,
        "fecha_emision": c.fecha_emision,
        "punto_venta": c.punto_venta,
        "numero": c.numero,
        "total": c.total,
        "cliente": c.cliente.name if c.cliente else None,
        "numero_formateado": format_numero(c.punto_venta, c.numero),
    }


def _build_detail(c: models.Comprobante) -> dict:
    return {
        "id": c.id,
        "tipo": c.tipo,
        "estado": c.estado,
        "fecha_emision": c.fecha_emision,
        "fecha_contable": c.fecha_contable,
        "client_id": c.client_id,
        "punto_venta": c.punto_venta,
        "numero": c.numero,
        "subtotal": c.subtotal,
        "iva_importe": c.iva_importe,
        "total": c.total,
        "notas": c.notas,
        "created_by": c.created_by,
        "version": c.version,
        "fecha_creacion": c.fecha_creacion,
        "fecha_actualizacion": c.fecha_actualizacion,
        "tipo_afip": c.tipo_afip,
        "cae": c.cae,
        "cae_vto": c.cae_vto,
        "afip_response": c.afip_response,
        "comprobante_asociado_id": c.comprobante_asociado_id,
        "remito_tipo": c.remito_tipo,
        "orden_compra_ref": c.orden_compra_ref,
        "direccion_envio": c.direccion_envio,
        "fecha_estimada_envio": c.fecha_estimada_envio,
        "proveedor_ref": c.proveedor_ref,
        "producto_recibido": c.producto_recibido,
        "diagnostico": c.diagnostico,
        "tecnico_asignado": c.tecnico_asignado,
        "horas_trabajo": c.horas_trabajo,
        "fecha_ingreso": c.fecha_ingreso,
        "fecha_entrega_estimada": c.fecha_entrega_estimada,
        "cliente": c.cliente.name if c.cliente else None,
        "stock_reversed": c.stock_reversed or False,
        "items": [
            {
                "id": item.id,
                "comprobante_id": item.comprobante_id,
                "product_id": item.product_id,
                "material_id": item.material_id,
                "material_name": item.material.name if item.material else None,
                "descripcion": item.descripcion,
                "cantidad": item.cantidad,
                "unidad_medida": item.unidad_medida,
                "precio_unitario": item.precio_unitario,
                "subtotal": item.subtotal,
                "orden": item.orden,
                "iva_alicuota": item.iva_alicuota,
                "iva_importe": item.iva_importe,
            }
            for item in (c.items or [])
        ],
        "numero_formateado": format_numero(c.punto_venta, c.numero),
    }


# ---------------------------------------------------------------------------
# Helpers — Stock reversal (Nota de Crédito)
# ---------------------------------------------------------------------------
def _reverse_stock(db: Session, c: models.Comprobante):
    """Reverse product/material stock for a Nota de Crédito emission.

    Idempotent: skips if c.stock_reversed is already True.
    Runs inside the emitir transaction — failure rolls back CAE too.
    """
    if c.stock_reversed:
        return

    for item in (c.items or []):
        if item.product_id:
            p = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if p:
                p.stock = (p.stock or 0) + int(item.cantidad)
                db.flush()

        if item.material_id:
            m = db.query(models.Material).filter(models.Material.id == item.material_id).first()
            if m:
                m.current_stock = (m.current_stock or 0) + item.cantidad
                db.flush()

            movement = models.MaterialMovement(
                material_id=item.material_id,
                quantity=item.cantidad,
                type="IN",
                reason=f"NC {c.punto_venta:05d}-{c.numero:08d}",
            )
            db.add(movement)

    c.stock_reversed = True


# CondicionIVAReceptorId fallback per comprobante tipo (RG 5616)
COND_IVA_RECEPTOR_FALLBACK: dict[str, int] = {
    "FACTURA_A": 1, "NOTA_DEBITO_A": 1, "NOTA_CREDITO_A": 1,
    "FACTURA_B": 4, "NOTA_DEBITO_B": 4, "NOTA_CREDITO_B": 4,
    "FACTURA_C": 5, "NOTA_DEBITO_C": 5, "NOTA_CREDITO_C": 5,
    "FACTURA_M": 1, "FACTURA_E": 8,
}


# ---------------------------------------------------------------------------
# POST /comprobantes/{id}/emitir — Emitir (solicitar CAE) un comprobante fiscal
# ---------------------------------------------------------------------------
@router.post("/{id}/emitir", response_model=schemas.ComprobanteDetail)
def emitir_comprobante(id: int, db: Session = Depends(get_db)):
    """Emitir un comprobante fiscal: solicita CAE a ARCA (real o mock según config).

    Business validations (Fix 5):
      - Factura A: cliente debe tener CUIT válido de 11 dígitos
      - Factura B: total no puede superar $10,000,000
    """
    c = (
        db.query(models.Comprobante)
        .options(
            joinedload(models.Comprobante.items),
            joinedload(models.Comprobante.cliente),
        )
        .filter(models.Comprobante.id == id)
        .first()
    )

    if not c:
        raise HTTPException(404, detail="Comprobante no encontrado")

    if c.estado != "draft":
        raise HTTPException(409, detail=f"El comprobante ya está en estado '{c.estado}'")

    is_fiscal = c.tipo in FISCAL_TIPOS
    if not is_fiscal:
        raise HTTPException(400, detail="Solo comprobantes fiscales se pueden emitir con CAE")

    tipo = c.tipo

    # -- Business validations (Fix 5) --
    # Factura A: CUIT obligatorio
    if tipo in FISCAL_TIPOS_A:
        if not c.cliente or not c.cliente.tax_id:
            raise HTTPException(400, detail="Factura A requiere cliente con CUIT")
        tax_clean = c.cliente.tax_id.replace("-", "")
        if len(tax_clean) != 11 or not tax_clean.isdigit():
            raise HTTPException(400, detail="CUIT del cliente inválido para Factura A")

    # Factura B: límite $10M
    if tipo in FISCAL_TIPOS_B and (c.total or 0) > 10_000_000:
        raise HTTPException(400, detail="Factura B no puede superar $10,000,000")

    # -- CbtesAsoc for NC/ND (tipos AFIP: 2,3,7,8,12,13) --
    NC_ND_CBTES_ASOC_TIPOS = {2, 3, 7, 8, 12, 13}
    cbtes_asoc = None
    if c.tipo_afip in NC_ND_CBTES_ASOC_TIPOS:
        asoc = c.comprobante_asociado
        if not asoc:
            raise HTTPException(
                400,
                detail="NC/ND requieren un comprobante asociado",
            )
        if not asoc.tipo_afip:
            raise HTTPException(
                400,
                detail="El comprobante asociado no tiene código AFIP (tipo_afip)",
            )
        if not asoc.punto_venta:
            raise HTTPException(
                400,
                detail="El comprobante asociado no tiene punto de venta",
            )
        if not asoc.numero:
            raise HTTPException(
                400,
                detail="El comprobante asociado no tiene número",
            )
        cbtes_asoc = [
            {"Tipo": asoc.tipo_afip, "PtoVta": asoc.punto_venta, "Nro": asoc.numero},
        ]

    # -- Check ARCA config for real or mock --
    config = db.query(models.ElectronicInvoiceConfig).first()
    use_real = (
        config
        and config.enabled
        and config.cert_path
        and config.key_path
        and config.CUIT
    )

    # -- Resolve CondicionIVAReceptorId (needed for both real and mock) --
    cond_iva_receptor = c.cliente.condicion_iva_receptor_id if c.cliente else None
    if cond_iva_receptor is None:
        cond_iva_receptor = COND_IVA_RECEPTOR_FALLBACK.get(tipo, 4)

    # -- Build items_raw for per-rate IVA grouping (needed for both real and mock) --
    items_raw = []
    for item in (c.items or []):
        items_raw.append({
            "subtotal": round(item.subtotal or 0, 2),
            "iva_alicuota": item.iva_alicuota or 0.0,
            "iva_importe": round(item.iva_importe or 0, 2),
        })

    if use_real:
        # Real WSFE
        from services.wsfe_client import create_wsfe_client

        wsfe = create_wsfe_client({
            "cert_path": config.cert_path,
            "key_path": config.key_path,
            "CUIT": config.CUIT,
            "ambiente": config.ambiente
        })

        if not wsfe:
            raise HTTPException(500, detail="No se pudo inicializar cliente WSFE")

        # -- FECompUltimoAutorizado: resolver número real de ARCA --
        pv = c.punto_venta
        tipo_afip = c.tipo_afip or 6
        ultimo_result = wsfe.get_ultimo_autorizado(pv, tipo_afip)

        if ultimo_result.get("success"):
            arca_numero = ultimo_result["ultimo_numero"] + 1
            logger.info(
                f"FECompUltimoAutorizado OK: último={ultimo_result['ultimo_numero']} "
                f"→ usando número {arca_numero} para PV={pv} Tipo={tipo_afip}"
            )
            c.numero = arca_numero
        else:
            logger.warning(
                f"FECompUltimoAutorizado falló — "
                f"usando número local {c.numero} como fallback. "
                f"Error: {ultimo_result.get('error', 'desconocido')}"
            )

        # Preparar datos para WSFE
        cliente_cuit = c.cliente.tax_id.replace("-", "") if c.cliente and c.cliente.tax_id else "0"
        doc_tipo, doc_nro = get_client_tipo_doc(cliente_cuit)

        invoice_data = {
            "punto_venta": pv,
            "tipo_comprobante": tipo_afip,
            "cliente_cuit": doc_nro,
            "cliente_tipo_doc": doc_tipo,
            "cbte_desde": c.numero,
            "cbte_hasta": c.numero,
            "subtotal": round(c.subtotal or 0, 2),
            "iva": round(c.iva_importe or 0, 2),
            "total": round(c.total or 0, 2),
            "items_raw": items_raw,
            "condicion_iva_receptor_id": cond_iva_receptor,
        }

        if cbtes_asoc is not None:
            invoice_data["CbtesAsoc"] = cbtes_asoc

        cae_result = wsfe.request_cae(invoice_data)
    else:
        # Mock CAE (testing / sin certificado)
        mock_data = {
            "numero": c.numero,
            "tipo": tipo,
            "items_raw": items_raw,
            "condicion_iva_receptor_id": cond_iva_receptor,
        }
        if cbtes_asoc is not None:
            mock_data["CbtesAsoc"] = cbtes_asoc
        cae_result = generate_mock_cae(mock_data)

    if cae_result.get("success"):
        c.cae = cae_result["CAE"]
        if cae_result.get("CAE_vto"):
            try:
                c.cae_vto = datetime.fromisoformat(cae_result["CAE_vto"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                c.cae_vto = None
        c.afip_response = json.dumps(cae_result)
        c.estado = "issued"

        # Reverse stock for Nota de Crédito (runs in same transaction)
        if c.tipo in NC_TIPOS:
            _reverse_stock(db, c)
    else:
        c.afip_response = json.dumps(cae_result)
        c.estado = "error"

    db.commit()
    db.refresh(c)

    return _build_detail(c)


# ---------------------------------------------------------------------------
# GET /comprobantes/tipos — List available tipos grouped by category
# ---------------------------------------------------------------------------
@router.get("/tipos")
def list_tipos():
    """Lista los tipos de comprobantes agrupados por categoría."""
    return [
        {
            "label": "Fiscales",
            "tipos": [
                "FACTURA_A", "FACTURA_B", "FACTURA_C", "FACTURA_M", "FACTURA_E",
                "NOTA_CREDITO_A", "NOTA_CREDITO_B", "NOTA_CREDITO_C",
                "NOTA_DEBITO_A", "NOTA_DEBITO_B", "NOTA_DEBITO_C",
            ],
        },
        {
            "label": "Remitos",
            "tipos": ["REMITO_X", "REMITO_R"],
        },
        {
            "label": "Tickets",
            "tipos": ["TICKET"],
        },
        {
            "label": "Notas",
            "tipos": ["NOTA_ENVIO", "NOTA_RECEPCION"],
        },
        {
            "label": "Órdenes",
            "tipos": ["ORDEN_REPARACION"],
        },
    ]


# ---------------------------------------------------------------------------
# POST /comprobantes — Create
# ---------------------------------------------------------------------------
@router.post("/", response_model=schemas.ComprobanteDetail, status_code=201)
def create_comprobante(data: schemas.ComprobanteCreate, db: Session = Depends(get_db)):
    """Crea un nuevo comprobante con validación por tipo."""
    tipo = data.tipo.value if hasattr(data.tipo, 'value') else str(data.tipo)
    is_fiscal = tipo in FISCAL_TIPOS
    is_nc_nd = tipo in NC_ND_TIPOS

    # -- Validation --
    # Validate client for fiscal tipos
    if is_fiscal and not data.client_id:
        raise HTTPException(400, detail="Comprobantes fiscales requieren un cliente")

    # Validate NC/ND have comprobante_asociado_id referencing an issued fiscal comprobante
    if is_nc_nd:
        if not data.comprobante_asociado_id:
            raise HTTPException(400, detail="NC/ND requieren un comprobante asociado")
        asoc = db.query(models.Comprobante).filter(
            models.Comprobante.id == data.comprobante_asociado_id
        ).first()
        if not asoc:
            raise HTTPException(404, detail="Comprobante asociado no encontrado")
        if asoc.tipo not in FISCAL_TIPOS:
            raise HTTPException(400, detail="El comprobante asociado debe ser fiscal")
        if asoc.estado != "issued":
            raise HTTPException(400, detail="El comprobante asociado debe estar emitido")

    # -- Auto-numbering --
    numero = get_next_numero(db, data.punto_venta, tipo)

    # -- Auto-set tipo_afip for fiscal --
    tipo_afip = data.tipo_afip
    if is_fiscal and not tipo_afip:
        tipo_afip = get_tipo_afip_from_tipo(tipo)

    # -- Process items (auto-calc subtotals and IVA) --
    items_data = []
    subtotal_total = 0.0
    iva_total = 0.0

    for i, item_data in enumerate(data.items):
        item_subtotal = item_data.cantidad * item_data.precio_unitario
        subtotal_total += item_subtotal

        if is_fiscal:
            if item_data.iva_alicuota is not None and item_data.iva_importe is not None:
                iva_item = item_data.iva_importe
            else:
                iva_item = round(item_subtotal * 0.21, 2)
            iva_total += iva_item
            iva_alicuota_val = item_data.iva_alicuota or 21.0
        else:
            iva_item = 0.0
            iva_alicuota_val = None

        items_data.append(models.ComprobanteItem(
            product_id=item_data.product_id,
            material_id=item_data.material_id,
            descripcion=item_data.descripcion,
            cantidad=item_data.cantidad,
            unidad_medida=item_data.unidad_medida,
            precio_unitario=item_data.precio_unitario,
            subtotal=round(item_subtotal, 2),
            orden=i,
            iva_alicuota=iva_alicuota_val,
            iva_importe=round(iva_item, 2) if is_fiscal else None,
        ))

    # -- Create comprobante --
    comprobante = models.Comprobante(
        tipo=tipo,
        estado="draft",
        fecha_emision=data.fecha_emision or datetime.utcnow(),
        fecha_contable=data.fecha_contable,
        client_id=data.client_id,
        punto_venta=data.punto_venta,
        numero=numero,
        subtotal=round(subtotal_total, 2),
        iva_importe=round(iva_total, 2),
        total=round(subtotal_total + iva_total, 2),
        notas=data.notas,
        tipo_afip=tipo_afip,
        comprobante_asociado_id=data.comprobante_asociado_id,
        remito_tipo=data.remito_tipo,
        orden_compra_ref=data.orden_compra_ref,
        direccion_envio=data.direccion_envio,
        fecha_estimada_envio=data.fecha_estimada_envio,
        proveedor_ref=data.proveedor_ref,
        producto_recibido=data.producto_recibido,
        diagnostico=data.diagnostico,
        tecnico_asignado=data.tecnico_asignado,
        horas_trabajo=data.horas_trabajo,
        fecha_ingreso=data.fecha_ingreso,
        fecha_entrega_estimada=data.fecha_entrega_estimada,
    )

    db.add(comprobante)
    db.flush()

    for item in items_data:
        item.comprobante_id = comprobante.id
        db.add(item)

    # Fiscal types se crean como draft — la emisión (CAE) se hace en POST /{id}/emitir
    db.commit()
    db.refresh(comprobante)

    return _build_detail(comprobante)


# ---------------------------------------------------------------------------
# GET /comprobantes — List (paginated, filterable)
# ---------------------------------------------------------------------------
@router.get("/", response_model=List[schemas.ComprobanteListItem])
def list_comprobantes(
    tipo: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Lista comprobantes con filtros opcionales y paginación."""
    query = db.query(models.Comprobante).options(joinedload(models.Comprobante.cliente))

    if tipo:
        query = query.filter(models.Comprobante.tipo == tipo)
    if estado:
        query = query.filter(models.Comprobante.estado == estado)

    total = query.count()

    offset = (page - 1) * limit
    comprobantes = (
        query.order_by(models.Comprobante.fecha_creacion.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    response.headers["X-Total-Count"] = str(total)
    return [_build_list_item(c) for c in comprobantes]


# ---------------------------------------------------------------------------
# GET /comprobantes/{id} — Detail
# ---------------------------------------------------------------------------
@router.get("/{id}", response_model=schemas.ComprobanteDetail)
def get_comprobante(id: int, db: Session = Depends(get_db)):
    """Obtiene detalle completo de un comprobante con sus items."""
    c = (
        db.query(models.Comprobante)
        .options(
            joinedload(models.Comprobante.items),
            joinedload(models.Comprobante.cliente),
        )
        .filter(models.Comprobante.id == id)
        .first()
    )

    if not c:
        raise HTTPException(404, detail="Comprobante no encontrado")

    return _build_detail(c)


# ---------------------------------------------------------------------------
# GET /comprobantes/{id}/pdf — Descargar PDF
# ---------------------------------------------------------------------------
@router.get("/{id}/pdf")
def descargar_pdf_comprobante(id: int, db: Session = Depends(get_db)):
    """Genera y descarga PDF del comprobante según su tipo."""
    from services.comprobante_pdf import generar_pdf

    c = (
        db.query(models.Comprobante)
        .options(
            joinedload(models.Comprobante.items),
            joinedload(models.Comprobante.cliente),
            joinedload(models.Comprobante.created_by_user),
        )
        .filter(models.Comprobante.id == id)
        .first()
    )

    if not c:
        raise HTTPException(404, detail="Comprobante no encontrado")

    # Buscar config de empresa (o defaults)
    config = db.query(models.ElectronicInvoiceConfig).first()
    empresa_data = {
        "razon_social": config.razon_social if config and config.razon_social else "El Menestral",
        "cuit": config.CUIT if config and config.CUIT else "30-XXXXXXXX-X",
        "domicilio": "",
        "telefono": "",
        "iibb": "",
        "inicio_actividades": "01/01/2020",
        "iva_condition": _get_iva_condition(c.tipo),
    }

    pdf = generar_pdf(c, empresa_data)
    if not pdf:
        raise HTTPException(500, detail="Error al generar PDF")

    tipo_clean = c.tipo.lower().replace("_", "-")
    filename = f"ElMenestral_{tipo_clean}_{c.punto_venta:05d}-{c.numero:08d}.pdf"

    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# PUT /comprobantes/{id} — Update
# ---------------------------------------------------------------------------
@router.put("/{id}", response_model=schemas.ComprobanteDetail)
def update_comprobante(id: int, data: schemas.ComprobanteUpdate, db: Session = Depends(get_db)):
    """Actualiza un comprobante con validación de transiciones de estado."""
    c = (
        db.query(models.Comprobante)
        .options(
            joinedload(models.Comprobante.items),
            joinedload(models.Comprobante.cliente),
        )
        .filter(models.Comprobante.id == id)
        .first()
    )

    if not c:
        raise HTTPException(404, detail="Comprobante no encontrado")

    # Do NOT allow changing tipo discriminator
    if data.tipo is not None:
        raise HTTPException(400, detail="No se puede cambiar el tipo del comprobante")

    # Validate estado transition
    if data.estado is not None and data.estado != c.estado:
        # Block draft→issued via PUT — must use POST /{id}/emitir
        if data.estado == "issued" and c.estado == "draft":
            raise HTTPException(
                409,
                detail="Para emitir un comprobante use POST /comprobantes/{id}/emitir"
            )
        allowed = VALID_ESTADO_TRANSITIONS.get(c.estado, set())
        if data.estado not in allowed:
            raise HTTPException(
                409,
                detail=(
                    f"Transición inválida: {c.estado} → {data.estado}. "
                    f"Transiciones permitidas: {', '.join(sorted(allowed)) or 'ninguna'}"
                ),
            )

    # Update scalar fields (partial update)
    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("tipo", None)   # already rejected above
    update_data.pop("items", None)  # handled separately

    for key, value in update_data.items():
        if value is not None:
            setattr(c, key, value)

    # Handle items replacement
    if data.items is not None:
        # Delete existing items
        for old_item in c.items:
            db.delete(old_item)

        # Create new items
        subtotal_total = 0.0
        iva_total = 0.0
        is_fiscal = c.tipo in FISCAL_TIPOS

        for i, item_data in enumerate(data.items):
            item_subtotal = item_data.cantidad * item_data.precio_unitario
            subtotal_total += item_subtotal

            if is_fiscal:
                if item_data.iva_alicuota is not None and item_data.iva_importe is not None:
                    iva_item = item_data.iva_importe
                else:
                    iva_item = round(item_subtotal * 0.21, 2)
                iva_total += iva_item
                iva_alicuota_val = item_data.iva_alicuota or 21.0
            else:
                iva_item = 0.0
                iva_alicuota_val = None

            new_item = models.ComprobanteItem(
                comprobante_id=c.id,
                product_id=item_data.product_id,
                material_id=item_data.material_id,
                descripcion=item_data.descripcion,
                cantidad=item_data.cantidad,
                unidad_medida=item_data.unidad_medida,
                precio_unitario=item_data.precio_unitario,
                subtotal=round(item_subtotal, 2),
                orden=i,
                iva_alicuota=iva_alicuota_val,
                iva_importe=round(iva_item, 2) if is_fiscal else None,
            )
            db.add(new_item)

        # Re-calc totals
        c.subtotal = round(subtotal_total, 2)
        c.iva_importe = round(iva_total, 2)
        c.total = round(subtotal_total + iva_total, 2)

    db.commit()
    db.refresh(c)

    return _build_detail(c)


# ---------------------------------------------------------------------------
# DELETE /comprobantes/{id} — Soft delete (anular)
# ---------------------------------------------------------------------------
@router.delete("/{id}")
def delete_comprobante(id: int, db: Session = Depends(get_db)):
    """Anula o elimina un comprobante según su tipo y estado."""
    c = db.query(models.Comprobante).filter(models.Comprobante.id == id).first()

    if not c:
        raise HTTPException(404, detail="Comprobante no encontrado")

    is_fiscal = c.tipo in FISCAL_TIPOS

    if is_fiscal:
        # Fiscal — soft delete only (ARCA compliance)
        c.estado = "cancelled"
        db.commit()
    elif c.estado == "draft":
        # Non-fiscal draft — hard delete
        db.delete(c)
        db.commit()
    else:
        # Non-fiscal, already issued or other — soft delete
        c.estado = "cancelled"
        db.commit()

    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /comprobantes/libro-iva-digital — Exportar Libro IVA Digital (Fix 4)
# ---------------------------------------------------------------------------
@router.get("/export/libro-iva-digital")
def export_libro_iva_digital(
    formato: str = Query("csv", pattern="^(csv|xml)$"),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Exporta comprobantes emitidos para Libro IVA Digital (RG 4291).

    Args:
        formato: "csv" (default) o "xml".
        desde: Fecha inicio (YYYY-MM-DD). Default: principio del mes actual.
        hasta: Fecha fin (YYYY-MM-DD). Default: hoy.
    """
    now = datetime.utcnow()

    if desde:
        try:
            f_desde = datetime.strptime(desde, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, detail="Formato 'desde' inválido. Use YYYY-MM-DD")
    else:
        f_desde = datetime(now.year, now.month, 1)

    if hasta:
        try:
            f_hasta = datetime.strptime(hasta, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, detail="Formato 'hasta' inválido. Use YYYY-MM-DD")
    else:
        f_hasta = now

    query = (
        db.query(models.Comprobante)
        .options(
            joinedload(models.Comprobante.cliente),
            joinedload(models.Comprobante.items),
        )
        .filter(
            models.Comprobante.estado == "issued",
            models.Comprobante.fecha_emision >= f_desde,
            models.Comprobante.fecha_emision <= f_hasta,
        )
        .order_by(models.Comprobante.fecha_emision)
    )

    comprobantes = query.all()

    from services.libro_iva_digital import export_comprobantes_csv, export_comprobantes_xml

    if formato == "xml":
        content = export_comprobantes_xml(comprobantes)
        media = "application/xml; charset=iso-8859-1"
        ext = "xml"
    else:
        content = export_comprobantes_csv(comprobantes)
        media = "text/csv; charset=iso-8859-1"
        ext = "csv"

    period = f"{f_desde.strftime('%Y%m%d')}_{f_hasta.strftime('%Y%m%d')}"
    filename = f"libro_iva_digital_{period}.{ext}"

    # content ya viene como bytes con encoding ISO-8859-1
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# GET /comprobantes/next-number/{tipo} — Next sequence
# ---------------------------------------------------------------------------
@router.get("/next-number/{tipo}")
def get_next_number(tipo: str, pv: int = Query(1, alias="pv"), db: Session = Depends(get_db)):
    """Obtiene el próximo número correlativo para un tipo y PV."""
    next_num = get_next_numero(db, pv, tipo)
    return {
        "punto_venta": pv,
        "tipo": tipo,
        "next": next_num,
    }
