"""Servicio de exportación Libro IVA Digital (RG 4291/2018 / RG 3685).

Produce archivos CSV y XML con el detalle de comprobantes emitidos
en un período, aptos para importar en el libro IVA digital de ARCA.

Encoding:
  - CSV: ISO-8859-1 (ANSÍ) según especificación ARCA RG 3685
  - XML: ISO-8859-1 con declaración de encoding
"""

import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
from io import StringIO, BytesIO
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# ARCA requiere ISO-8859-1 (ANSÍ) para archivos de importación
OUTPUT_ENCODING = "iso-8859-1"


def export_comprobantes_csv(comprobantes: List) -> bytes:
    """Exporta comprobantes emitidos a CSV (formato CITI Ventas, ISO-8859-1).

    Args:
        comprobantes: Lista de models.Comprobante con relaciones cargadas.

    Returns:
        Contenido CSV como bytes en encoding ISO-8859-1.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "TipoComprobante", "PuntoVenta", "Numero", "FechaEmision",
        "TipoDocReceptor", "NroDocReceptor", "RazonSocial",
        "Subtotal", "IVA", "Total", "CAE", "CAEVencimiento",
        "Moneda", "Cotizacion",
    ])

    for c in comprobantes:
        if c.estado != "issued":
            continue

        tipo_afip = c.tipo_afip or ""
        pv = c.punto_venta
        nro = c.numero
        fecha = c.fecha_emision.strftime("%Y%m%d") if c.fecha_emision else ""

        cliente = c.cliente
        if cliente and cliente.tax_id:
            tax_clean = cliente.tax_id.replace("-", "")
            if len(tax_clean) == 11:
                tipo_doc = 80
                nro_doc = tax_clean
            else:
                tipo_doc = 96
                nro_doc = tax_clean
            razon = cliente.name or ""
        else:
            tipo_doc = 99
            nro_doc = "0"
            razon = "Consumidor Final"

        subtotal = round(c.subtotal or 0, 2)
        iva = round(c.iva_importe or 0, 2)
        total = round(c.total or 0, 2)
        cae = c.cae or ""
        cae_vto = c.cae_vto.strftime("%Y%m%d") if c.cae_vto else ""

        writer.writerow([
            tipo_afip, pv, nro, fecha,
            tipo_doc, nro_doc, razon,
            subtotal, iva, total, cae, cae_vto,
            "PES", 1,
        ])

    # Convertir a ISO-8859-1 (reemplazar caracteres no convertibles)
    utf8_content = output.getvalue()
    output.close()
    return utf8_content.encode(OUTPUT_ENCODING, errors="replace")


def export_comprobantes_xml(comprobantes: List) -> bytes:
    """Exporta comprobantes emitidos a XML (formato Libro IVA Digital, ISO-8859-1).

    Args:
        comprobantes: Lista de models.Comprobante con relaciones cargadas.

    Returns:
        Contenido XML como bytes en encoding ISO-8859-1.
    """
    root = ET.Element("LibroIVADigital")
    root.set("version", "1.0")
    root.set("fecha_generacion", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")

    comp_element = ET.SubElement(root, "Comprobantes")

    for c in comprobantes:
        if c.estado != "issued":
            continue

        emi = ET.SubElement(comp_element, "Comprobante")

        tipo = ET.SubElement(emi, "TipoComprobante")
        tipo.text = str(c.tipo_afip or "")

        pv = ET.SubElement(emi, "PuntoVenta")
        pv.text = str(c.punto_venta)

        nro = ET.SubElement(emi, "Numero")
        nro.text = str(c.numero)

        fecha = ET.SubElement(emi, "FechaEmision")
        fecha.text = c.fecha_emision.strftime("%Y-%m-%d") if c.fecha_emision else ""

        subtotal = ET.SubElement(emi, "Subtotal")
        subtotal.text = f"{c.subtotal or 0:.2f}"

        iva = ET.SubElement(emi, "IVA")
        iva.text = f"{c.iva_importe or 0:.2f}"

        total = ET.SubElement(emi, "Total")
        total.text = f"{c.total or 0:.2f}"

        cae_el = ET.SubElement(emi, "CAE")
        cae_el.text = c.cae or ""

        cae_vto_el = ET.SubElement(emi, "CAEVencimiento")
        cae_vto_el.text = c.cae_vto.strftime("%Y-%m-%d") if c.cae_vto else ""

        moneda = ET.SubElement(emi, "Moneda")
        moneda.text = "PES"

        # Receptor
        receptor = ET.SubElement(emi, "Receptor")
        cliente = c.cliente
        if cliente and cliente.tax_id:
            tax_clean = cliente.tax_id.replace("-", "")
            tipo_doc_el = ET.SubElement(receptor, "TipoDocumento")
            nro_doc_el = ET.SubElement(receptor, "NumeroDocumento")
            nombre_el = ET.SubElement(receptor, "RazonSocial")

            if len(tax_clean) == 11:
                tipo_doc_el.text = "80"
            else:
                tipo_doc_el.text = "96"
            nro_doc_el.text = tax_clean
            nombre_el.text = cliente.name or ""
        else:
            ET.SubElement(receptor, "TipoDocumento").text = "99"
            ET.SubElement(receptor, "NumeroDocumento").text = "0"
            ET.SubElement(receptor, "RazonSocial").text = "Consumidor Final"

    # Pretty-print con declaración XML y encoding ISO-8859-1
    rough_string = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(rough_string.encode("utf-8"))
    pretty = dom.toprettyxml(indent="  ", encoding=OUTPUT_ENCODING)
    # toprettyxml con encoding= devuelve bytes con la declaración XML correcta
    return pretty
