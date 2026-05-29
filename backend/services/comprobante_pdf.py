"""Generación de PDF para comprobantes fiscales, tickets, remitos, etc."""

import json
import base64
import logging
from io import BytesIO
from datetime import datetime
from xhtml2pdf import pisa
import qrcode

logger = logging.getLogger(__name__)

FISCAL_TIPOS = {
    "FACTURA_A", "FACTURA_B", "FACTURA_C", "FACTURA_M", "FACTURA_E",
    "NOTA_DEBITO_A", "NOTA_DEBITO_B", "NOTA_DEBITO_C",
    "NOTA_CREDITO_A", "NOTA_CREDITO_B", "NOTA_CREDITO_C",
}

TIPO_LABELS = {
    "FACTURA_A": "Factura A", "FACTURA_B": "Factura B", "FACTURA_C": "Factura C",
    "FACTURA_M": "Factura M", "FACTURA_E": "Factura E",
    "NOTA_DEBITO_A": "ND A", "NOTA_DEBITO_B": "ND B", "NOTA_DEBITO_C": "ND C",
    "NOTA_CREDITO_A": "NC A", "NOTA_CREDITO_B": "NC B", "NOTA_CREDITO_C": "NC C",
    "REMITO_X": "Remito X", "REMITO_R": "Remito R",
    "TICKET": "Ticket",
    "NOTA_ENVIO": "Nota de Envío", "NOTA_RECEPCION": "Nota de Recepción",
    "ORDEN_REPARACION": "Ord. Reparación",
}

ESTADO_LABELS = {
    "draft": "Borrador", "issued": "Emitido", "cancelled": "Anulado", "error": "Error",
    "en_taller": "En Taller", "listo": "Listo", "entregado": "Entregado",
    "recibido_parcial": "Recibido Parcial", "recibido_total": "Recibido Total",
}


UNIDADES = ("", "UN ", "DOS ", "TRES ", "CUATRO ", "CINCO ", "SEIS ", "SIETE ", "OCHO ", "NUEVE ")
DECENAS = ("", "DIEZ ", "ONCE ", "DOCE ", "TRECE ", "CATORCE ", "QUINCE ", "DIECISÉIS ", "DIECISIETE ", "DIECIOCHO ", "DIECINUEVE ",
           "VEINTE ", "VEINTIÚN ", "VEINTIDÓS ", "VEINTITRÉS ", "VEINTICUATRO ", "VEINTICINCO ", "VEINTISÉIS ", "VEINTISIETE ", "VEINTIOCHO ", "VEINTINUEVE ")
DECENAS2 = ("", "DIEZ ", "VEINTE ", "TREINTA ", "CUARENTA ", "CINCUENTA ", "SESENTA ", "SETENTA ", "OCHENTA ", "NOVENTA ")
CENTENAS = ("", "CIENTO ", "DOSCIENTOS ", "TRESCIENTOS ", "CUATROCIENTOS ", "QUINIENTOS ", "SEISCIENTOS ", "SETECIENTOS ", "OCHOCIENTOS ", "NOVECIENTOS ")


def _numero_a_letras(numero: float) -> str:
    """Convierte un número a letras (para total en palabras)."""
    entero = int(numero)
    decimales = round((numero - entero) * 100)
    if entero == 0:
        palabras = "CERO "
    else:
        palabras = ""
        if entero >= 1000000:
            millones = entero // 1000000
            if millones == 1:
                palabras += "UN MILLÓN "
            else:
                palabras += _numero_a_letras_menor_1000(millones) + "MILLONES "
            entero %= 1000000
        if entero >= 1000:
            miles = entero // 1000
            if miles == 1:
                palabras += "MIL "
            else:
                palabras += _numero_a_letras_menor_1000(miles) + "MIL "
            entero %= 1000
        if entero > 0:
            palabras += _numero_a_letras_menor_1000(entero)
    return f"{palabras.strip()} CON {decimales:02d}/100"


def _numero_a_letras_menor_1000(n: int) -> str:
    if n < 10:
        return UNIDADES[n]
    elif n < 20:
        return DECENAS[n - 10]
    elif n < 30:
        return DECENAS[n - 10]
    elif n < 100:
        d = n // 10
        u = n % 10
        return DECENAS2[d].rstrip(" ") + (" Y " if u > 0 else " ") + UNIDADES[u] if u > 0 else DECENAS2[d]
    else:
        c = n // 100
        r = n % 100
        if n == 100:
            return "CIEN "
        if r == 0:
            return CENTENAS[c]
        return CENTENAS[c] + _numero_a_letras_menor_1000(r)


def _generate_qr_html(comp, e: dict) -> str:
    """Genera el código QR según especificación ARCA (RG 4892/2020).

    El QR codifica una URL: https://www.afip.gob.ar/fe/qr/?p=<base64>
    donde el payload base64 es un JSON con los datos del comprobante.
    """
    tipo_cmp = comp.tipo_afip or 6

    # Determinar tipo documento receptor
    cliente_cuit = comp.cliente.tax_id if comp.cliente and comp.cliente.tax_id else ""
    if cliente_cuit and len(cliente_cuit.replace("-", "")) == 11:
        tipo_doc_rec = 80
        nro_doc_rec = int(cliente_cuit.replace("-", ""))
    elif not cliente_cuit or cliente_cuit == "0":
        tipo_doc_rec = 99
        nro_doc_rec = 0
    else:
        tipo_doc_rec = 96
        nro_doc_rec = int(cliente_cuit.replace("-", ""))

    fecha = comp.fecha_emision.strftime("%Y-%m-%d") if comp.fecha_emision else datetime.now().strftime("%Y-%m-%d")
    cae = int(comp.cae) if comp.cae and comp.cae.replace("-", "").isdigit() else 0

    # Sanitize CUIT: keep only digits
    cuit_raw = str(e.get("cuit", "0") or "0").replace("-", "")
    cuit_str = "".join(c for c in cuit_raw if c.isdigit()) or "0"
    qr_data = {
        "fecha": fecha,
        "cuit": int(cuit_str),
        "ptoVta": comp.punto_venta,
        "tipoCmp": tipo_cmp,
        "nroCmp": comp.numero,
        "importe": comp.total or 0,
        "moneda": "PES",
        "ctz": 1,
        "tipoDocRec": tipo_doc_rec,
        "nroDocRec": nro_doc_rec,
        "codAut": cae,
    }

    payload_json = json.dumps(qr_data, ensure_ascii=False)
    payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")
    qr_url = f"https://www.afip.gob.ar/fe/qr/?p={payload_b64}"

    # Generar imagen QR en memoria
    qr_img = qrcode.make(qr_url, box_size=4)
    img_bytes = BytesIO()
    qr_img.save(img_bytes, format="PNG")
    img_b64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

    return f'''
    <div class="qr-box">
        <img src="data:image/png;base64,{img_b64}" alt="QR ARCA" width="110" height="110" />
        <p class="qr-text">Código QR - RG 4892/2020</p>
    </div>'''


def _get_empresa_html(e: dict) -> str:
    """HTML del encabezado de la empresa."""
    dom = e.get("domicilio", "")
    tel = e.get("telefono", "")
    dom_line = f"<p>{dom}</p>" if dom else ""
    tel_line = f"<p>Tel: {tel}</p>" if tel else ""
    return f"""
    <div class="empresa">
        <h2>{e['razon_social']}</h2>
        <p>CUIT: {e['cuit']}</p>
        {dom_line}
        {tel_line}
        <p class="iva-cond">{e['iva_condition']}</p>
    </div>
    """


def _format_numero(pv: int, num: int) -> str:
    return f"{pv:05d}-{num:08d}"


def _render_items_table(items: list) -> str:
    """Renderiza la tabla de items común a todos los tipos."""
    rows = ""
    for item in items:
        desc = item.descripcion or (item.product.name if item.product else "")
        rows += f"""
        <tr>
            <td>{desc}</td>
            <td style="text-align:center">{item.cantidad}</td>
            <td style="text-align:right">${item.precio_unitario:,.2f}</td>
            <td style="text-align:right">${item.subtotal:,.2f}</td>
        </tr>"""
    return rows


def _render_items_table_ticket(items: list) -> str:
    """Renderiza items para ticket angosto."""
    rows = ""
    for item in items:
        desc = item.descripcion or (item.product.name if item.product else "")
        rows += f"""
        <tr>
            <td colspan="2">{desc}</td>
        </tr>
        <tr>
            <td>x{item.cantidad}</td>
            <td style="text-align:right">${item.subtotal:,.2f}</td>
        </tr>"""
    return rows


# ===========================================================================
# TEMPLATES
# ===========================================================================

# Tipos que discriminan IVA (Factura A, M, E, ND/NC A)
TIPO_IVA_DISCRIMINADO = {"FACTURA_A", "FACTURA_M", "FACTURA_E",
                         "NOTA_DEBITO_A", "NOTA_CREDITO_A"}
# Tipos con IVA incluido (Factura B, ND/NC B)
TIPO_IVA_INCLUIDO = {"FACTURA_B", "NOTA_DEBITO_B", "NOTA_CREDITO_B"}
# Tipos sin IVA (Factura C, ND/NC C)
TIPO_SIN_IVA = {"FACTURA_C", "NOTA_DEBITO_C", "NOTA_CREDITO_C"}

_CLIENTE_IVA_COND = {
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


def _template_fiscal(comp, empresa_html: str, e: dict) -> str:
    """Template A4 para comprobantes fiscales — cumple RG 1415/2003.

    Diferenciación según tipo:
      - Factura A / M / E: IVA discriminado (Subtotal + IVA + Total)
      - Factura B:          IVA incluido  (Total con leyenda)
      - Factura C:          Sin IVA       (Solo Total)
    """
    tipo_label = TIPO_LABELS.get(comp.tipo, comp.tipo)
    nro = _format_numero(comp.punto_venta, comp.numero)
    cliente = comp.cliente.name if comp.cliente else "Consumidor Final"
    cuit_cliente = comp.cliente.tax_id if comp.cliente and comp.cliente.tax_id else "—"
    fecha = comp.fecha_emision.strftime("%d/%m/%Y %H:%M") if comp.fecha_emision else "—"

    items_html = _render_items_table(comp.items or [])
    subtotal = comp.subtotal or 0
    iva = comp.iva_importe or 0
    total = comp.total or 0
    cae = comp.cae or "—"
    cae_vto = comp.cae_vto.strftime("%d/%m/%Y") if comp.cae_vto else "—"

    tipo = comp.tipo
    discrimina_iva = tipo in TIPO_IVA_DISCRIMINADO
    iva_incluido = tipo in TIPO_IVA_INCLUIDO
    sin_iva = tipo in TIPO_SIN_IVA

    cliente_iva_cond = _CLIENTE_IVA_COND.get(tipo, "Consumidor Final")
    total_letras = _numero_a_letras(total)

    # IIBB / Inicio actividades desde empresa_data
    iibb = e.get("iibb", "")
    inicio = e.get("inicio_actividades", "")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    @page {{ size: A4; margin: 1.5cm; }}
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #222; }}
    .empresa {{ text-align: center; margin-bottom: 15px; border-bottom: 2px solid #2e86de; padding-bottom: 10px; }}
    .empresa h2 {{ margin: 0; color: #2e86de; font-size: 18px; }}
    .empresa p {{ margin: 2px 0; font-size: 11px; color: #555; }}
    .empresa .iva-cond {{ font-weight: bold; color: #2e86de; font-size: 11px; margin-top: 4px; }}
    .titulo-comprobante {{ text-align: center; font-size: 16px; font-weight: bold; margin: 10px 0; color: #1a1a1a; border: 1px solid #ccc; padding: 6px; display: inline-block; }}
    .titulo-wrapper {{ text-align: center; margin: 10px 0; }}
    .datos-extra {{ text-align: center; font-size: 10px; color: #666; margin-bottom: 10px; }}
    .info-grid {{ display: flex; justify-content: space-between; margin-bottom: 15px; gap: 10px; }}
    .info-box {{ border: 1px solid #ccc; padding: 10px; flex: 1; border-radius: 4px; }}
    .info-box h4 {{ margin: 0 0 5px 0; font-size: 10px; color: #666; text-transform: uppercase; }}
    .info-box p {{ margin: 2px 0; font-size: 11px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
    th {{ background: #2e86de; color: white; padding: 8px; text-align: left; font-size: 10px; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; font-size: 11px; }}
    .totales {{ margin-left: auto; width: 320px; }}
    .totales table {{ margin: 0; }}
    .totales td {{ padding: 4px 8px; border: none; font-size: 11px; }}
    .total-final td {{ font-weight: bold; font-size: 14px; color: #c0392b; }}
    .total-letras {{ text-align: right; font-size: 10px; color: #555; font-style: italic; margin: 5px 0 15px 0; }}
    .cae-box {{ margin-top: 15px; padding: 10px; border: 1px dashed #999; text-align: center; font-size: 10px; }}
    .cae-box strong {{ font-size: 13px; }}
    .qr-box {{ text-align: center; margin: 10px 0; }}
    .qr-box img {{ border: 1px solid #ddd; padding: 4px; }}
    .qr-text {{ font-size: 8px; color: #999; margin: 2px 0; }}
    .footer {{ margin-top: 20px; text-align: center; font-size: 9px; color: #999; border-top: 1px solid #ddd; padding-top: 8px; }}
    .iva-incluido-leyenda {{ text-align: right; font-size: 10px; color: #c0392b; font-weight: bold; margin: 3px 0; }}
    .renglones-fiscales {{ font-size: 9px; color: #888; text-align: center; margin-top: 10px; }}
</style>
</head>
<body>
    {empresa_html}

    <div class="titulo-wrapper">
        <div class="titulo-comprobante">{tipo_label}</div>
    </div>
    <div class="datos-extra">
        <strong>Punto de Venta:</strong> {comp.punto_venta:04d} &nbsp;|&nbsp;
        <strong>Comprobante N°:</strong> {nro} &nbsp;|&nbsp;
        <strong>Fecha:</strong> {fecha}
    </div>
    {('' + iibb + inicio) if (iibb or inicio) else ''}
    <div class="info-grid">
        <div class="info-box">
            <h4>Datos del Emisor</h4>
            <p><strong>{e['razon_social']}</strong></p>
            <p>CUIT: {e['cuit']}</p>
            {('<p>IIBB: ' + iibb + '</p>') if iibb else ''}
            {('<p>Inicio Act.: ' + inicio + '</p>') if inicio else ''}
            <p>Cond. IVA: <strong>{e['iva_condition']}</strong></p>
        </div>
        <div class="info-box">
            <h4>Datos del Receptor</h4>
            <p><strong>{cliente}</strong></p>
            <p>CUIT/DNI: {cuit_cliente}</p>
            <p>Cond. IVA: <strong>{cliente_iva_cond}</strong></p>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th style="width:50%">Descripción</th>
                <th style="text-align:center;width:10%">Cant.</th>
                <th style="text-align:right;width:15%">P. Unit.</th>
                <th style="text-align:right;width:15%">Subtotal</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>

    <div class="totales">
        <table>
            <tr><td>Subtotal</td><td style="text-align:right">$ {subtotal:,.2f}</td></tr>
            {('' if not sin_iva else '')}
            {('<tr><td>IVA 21%</td><td style="text-align:right">$ ' + f'{iva:,.2f}' + '</td></tr>') if discrimina_iva else ''}
            <tr class="total-final"><td>TOTAL</td><td style="text-align:right">$ {total:,.2f}</td></tr>
        </table>
    </div>

    {('<div class="iva-incluido-leyenda">IVA INCLUIDO</div>') if iva_incluido else ''}

    <div class="total-letras">Son: {total_letras}</div>

    <div class="cae-box">
        <p><strong>CAE N°: {cae}</strong></p>
        <p>Fecha de Vencimiento: {cae_vto}</p>
    </div>

    {_generate_qr_html(comp, e)}

    <div class="footer">
        <p>Original — Documento electrónico válido | {e['razon_social']} | CUIT: {e['cuit']}</p>
    </div>
</body>
</html>"""


def _template_ticket(comp, empresa_html: str) -> str:
    """Template angosto (58mm) para tickets."""
    tipo_label = TIPO_LABELS.get(comp.tipo, comp.tipo)
    nro = _format_numero(comp.punto_venta, comp.numero)
    fecha = comp.fecha_emision.strftime("%d/%m/%Y %H:%M") if comp.fecha_emision else "—"
    items_html = _render_items_table_ticket(comp.items or [])
    total = comp.total or 0

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    @page {{ size: 58mm 300mm; margin: 3mm; }}
    body {{ font-family: 'Courier New', monospace; font-size: 10px; width: 52mm; margin: 0 auto; color: #000; }}
    .center {{ text-align: center; }}
    .line {{ border-top: 1px dashed #000; margin: 5px 0; }}
    .empresa h2 {{ font-size: 14px; margin: 5px 0; }}
    .empresa p {{ margin: 1px 0; font-size: 9px; }}
    table {{ width: 100%; }}
    td {{ padding: 1px 0; }}
    .total {{ font-size: 14px; font-weight: bold; text-align: center; margin: 10px 0; }}
    .footer {{ text-align: center; font-size: 9px; margin-top: 10px; }}
</style>
</head>
<body>
    <div class="center empresa">
        <h2>El Menestral</h2>
        <p>CUIT: 30-XXXXXXXX-X</p>
        <div class="line"></div>
        <h3>{tipo_label}</h3>
        <p>N°: {nro}</p>
        <p>{fecha}</p>
        <div class="line"></div>
    </div>

    <table>
        {items_html}
    </table>

    <div class="line"></div>
    <div class="total">TOTAL: ${total:,.2f}</div>
    <div class="line"></div>

    <div class="footer">
        <p>¡Gracias por su compra!</p>
    </div>
</body>
</html>"""


def _template_remito(comp, empresa_html: str) -> str:
    """Template A4 para remitos."""
    tipo_label = TIPO_LABELS.get(comp.tipo, comp.tipo)
    nro = _format_numero(comp.punto_venta, comp.numero)
    cliente = comp.cliente.name if comp.cliente else "—"
    fecha = comp.fecha_emision.strftime("%d/%m/%Y") if comp.fecha_emision else "—"
    items_html = _render_items_table(comp.items or [])
    remito_tipo = comp.remito_tipo or ""
    oc = comp.orden_compra_ref or "—"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    @page {{ size: A4; margin: 1.5cm; }}
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #222; }}
    .empresa {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 15px; }}
    .empresa h2 {{ margin: 0; }}
    .empresa p {{ margin: 2px 0; font-size: 11px; color: #555; }}
    .titulo {{ font-size: 16px; font-weight: bold; text-align: center; }}
    .info p {{ margin: 3px 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
    th {{ background: #333; color: white; padding: 8px; text-align: left; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; }}
    .firma {{ margin-top: 40px; display: flex; justify-content: space-between; }}
    .firma div {{ text-align: center; width: 45%; border-top: 1px solid #333; padding-top: 5px; }}
</style>
</head>
<body>
    {empresa_html}
    <div class="titulo">{tipo_label} {remito_tipo}</div>
    <p style="text-align:center;color:#666;">N°: {nro} | Fecha: {fecha}</p>

    <div class="info">
        <p><strong>Cliente:</strong> {cliente}</p>
        <p><strong>Orden de Compra:</strong> {oc}</p>
    </div>

    <table>
        <thead>
            <tr><th>Descripción</th><th>Cant.</th><th style="text-align:right">P. Unit.</th><th style="text-align:right">Subtotal</th></tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>

    <div class="firma">
        <div>Entregó</div>
        <div>Recibió</div>
    </div>

    <div class="footer" style="text-align:center;font-size:10px;color:#999;margin-top:30px;">
        <p>Documento no fiscal — Remito</p>
    </div>
</body>
</html>"""


def _template_orden_reparacion(comp, empresa_html: str) -> str:
    """Template A4 para órdenes de reparación."""
    nro = _format_numero(comp.punto_venta, comp.numero)
    cliente = comp.cliente.name if comp.cliente else "—"
    fecha = comp.fecha_emision.strftime("%d/%m/%Y") if comp.fecha_emision else "—"
    items_html = _render_items_table(comp.items or [])

    producto = comp.producto_recibido or "—"
    diagnostico = comp.diagnostico or "—"
    tecnico = comp.tecnico_asignado or "—"
    horas = comp.horas_trabajo or "—"
    ingreso = comp.fecha_ingreso.strftime("%d/%m/%Y") if comp.fecha_ingreso else "—"
    entrega_est = comp.fecha_entrega_estimada.strftime("%d/%m/%Y") if comp.fecha_entrega_estimada else "—"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    @page {{ size: A4; margin: 1.5cm; }}
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 12px; }}
    .empresa {{ text-align: center; border-bottom: 2px solid #f59e0b; padding-bottom: 8px; }}
    .empresa h2 {{ margin: 0; color: #f59e0b; }}
    .titulo {{ font-size: 16px; font-weight: bold; text-align: center; margin: 15px 0; }}
    .info-grid {{ display: flex; gap: 15px; margin: 15px 0; }}
    .info-box {{ border: 1px solid #ccc; padding: 10px; flex: 1; }}
    .info-box h4 {{ margin: 0 0 5px 0; font-size: 11px; color: #666; }}
    .info-box p {{ margin: 2px 0; }}
    .diagnostico {{ background: #fef3c7; padding: 10px; border-left: 4px solid #f59e0b; margin: 15px 0; }}
    .diagnostico h4 {{ margin: 0 0 5px 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
    th {{ background: #f59e0b; color: white; padding: 8px; text-align: left; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; }}
    .firma {{ margin-top: 40px; display: flex; justify-content: space-between; }}
    .firma div {{ text-align: center; width: 45%; border-top: 1px solid #333; padding-top: 5px; }}
</style>
</head>
<body>
    {empresa_html}
    <div class="titulo">Orden de Reparación N° {nro}</div>
    <p style="text-align:center;color:#666;">Fecha: {fecha}</p>

    <div class="info-grid">
        <div class="info-box">
            <h4>Cliente</h4>
            <p><strong>{cliente}</strong></p>
        </div>
        <div class="info-box">
            <h4>Técnico</h4>
            <p><strong>{tecnico}</strong></p>
        </div>
        <div class="info-box">
            <h4>Fechas</h4>
            <p>Ingreso: {ingreso}</p>
            <p>Entrega est.: {entrega_est}</p>
        </div>
    </div>

    <h4>Producto Recibido: {producto}</h4>

    <div class="diagnostico">
        <h4>Diagnóstico</h4>
        <p>{diagnostico}</p>
    </div>

    <h4>Materiales / Repuestos</h4>
    <table>
        <thead>
            <tr><th>Descripción</th><th>Cant.</th><th style="text-align:right">P. Unit.</th><th style="text-align:right">Subtotal</th></tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>

    <p><strong>Horas de trabajo:</strong> {horas}</p>

    <div class="firma">
        <div>Recibió</div>
        <div>Entregó</div>
    </div>
</body>
</html>"""


def _template_nota(comp, empresa_html: str, titulo: str) -> str:
    """Template genérico para notas de envío/recepción."""
    nro = _format_numero(comp.punto_venta, comp.numero)
    cliente = comp.cliente.name if comp.cliente else "—"
    fecha = comp.fecha_emision.strftime("%d/%m/%Y") if comp.fecha_emision else "—"
    items_html = _render_items_table(comp.items or [])

    direccion = comp.direccion_envio or "—"
    fecha_est = comp.fecha_estimada_envio.strftime("%d/%m/%Y") if comp.fecha_estimada_envio else "—"
    prov = comp.proveedor_ref or cliente
    oc = comp.orden_compra_ref or "—"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    @page {{ size: A4; margin: 1.5cm; }}
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 12px; }}
    .empresa {{ text-align: center; border-bottom: 2px solid #6366f1; padding-bottom: 8px; }}
    .empresa h2 {{ margin: 0; color: #6366f1; }}
    .titulo {{ font-size: 16px; font-weight: bold; text-align: center; margin: 15px 0; }}
    .info p {{ margin: 3px 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
    th {{ background: #6366f1; color: white; padding: 8px; text-align: left; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; }}
</style>
</head>
<body>
    {empresa_html}
    <div class="titulo">{titulo}</div>
    <p style="text-align:center;color:#666;">N°: {nro} | Fecha: {fecha}</p>

    <div class="info">
        <p><strong>Cliente/Proveedor:</strong> {prov}</p>
        <p><strong>Dirección:</strong> {direccion}</p>
        <p><strong>Orden de Compra:</strong> {oc}</p>
        <p><strong>Fecha estimada:</strong> {fecha_est}</p>
    </div>

    <table>
        <thead>
            <tr><th>Descripción</th><th>Cant.</th><th style="text-align:right">P. Unit.</th><th style="text-align:right">Subtotal</th></tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>
</body>
</html>"""


# ===========================================================================
# PUBLIC API
# ===========================================================================

def generar_pdf(comp, empresa_data: dict | None = None) -> BytesIO | None:
    """Genera PDF para un comprobante según su tipo.
    
    Args:
        comp: Instancia de models.Comprobante con relaciones cargadas.
        empresa_data: Dict con datos de la empresa (razon_social, cuit, etc.)
                      Si es None, usa defaults.
    
    Returns:
        BytesIO con el PDF, o None si hubo error.
    """
    if empresa_data is None:
        empresa_data = {
            "razon_social": "El Menestral",
            "cuit": "30-XXXXXXXX-X",
            "domicilio": "",
            "telefono": "",
            "iibb": "",
            "inicio_actividades": "01/01/2020",
            "iva_condition": "IVA RESPONSABLE INSCRITO",
        }
    empresa = _get_empresa_html(empresa_data)
    tipo = comp.tipo

    if tipo == "TICKET":
        html = _template_ticket(comp, empresa)
    elif tipo.startswith("REMITO"):
        html = _template_remito(comp, empresa)
    elif tipo == "ORDEN_REPARACION":
        html = _template_orden_reparacion(comp, empresa)
    elif tipo == "NOTA_ENVIO":
        html = _template_nota(comp, empresa, "Nota de Envío")
    elif tipo == "NOTA_RECEPCION":
        html = _template_nota(comp, empresa, "Nota de Recepción")
    else:
        # Fiscal o cualquier otro → template A4 fiscal ARCA-compliant
        html = _template_fiscal(comp, empresa, empresa_data)

    result = BytesIO()
    pdf_status = pisa.CreatePDF(BytesIO(html.encode("UTF-8")), dest=result)

    if pdf_status.err:
        logger.error(f"Error generando PDF para comprobante {comp.id} ({tipo})")
        return None

    result.seek(0)
    return result
