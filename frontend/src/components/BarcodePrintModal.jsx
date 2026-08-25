import { useEffect, useRef } from "react";
import api from "../services/api";

/**
 * BarcodePrintModal — shows a thermal-label preview and prints it.
 *
 * Props:
 *   open       — boolean, show/hide the modal
 *   onClose    — callback to close
 *   items      — array of { sku, name, price } to print
 */
export default function BarcodePrintModal({ open, onClose, items = [] }) {
  const printRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handleEsc = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [open, onClose]);

  if (!open || items.length === 0) return null;

  const baseURL = api.defaults.baseURL || "";

  const handlePrint = () => {
    const printWindow = window.open("", "_blank", "width=400,height=300");

    const labelsHTML = items
      .map((item) => {
        const barcodeUrl = `${baseURL}/barcodes/${encodeURIComponent(item.sku)}.png`;
        return `
        <div class="label">
          <img src="${barcodeUrl}" alt="Barcode" class="barcode-img" />
          <div class="name">${item.name || ""}</div>
          <div class="sku">${item.sku || ""}</div>
          ${item.price != null ? `<div class="price">$${Number(item.price).toLocaleString()}</div>` : ""}
        </div>`;
      })
      .join("");

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Imprimir Etiquetas</title>
        <style>
          @page {
            size: 50mm 30mm;
            margin: 2mm;
          }
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: Arial, Helvetica, sans-serif;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          .label {
            width: 46mm;
            height: 26mm;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            border: 0.5px dashed #ccc;
            padding: 2mm;
            page-break-after: always;
            break-inside: avoid;
          }
          .label:last-child {
            page-break-after: auto;
          }
          .barcode-img {
            max-width: 40mm;
            max-height: 14mm;
            object-fit: contain;
          }
          .name {
            font-size: 7pt;
            font-weight: bold;
            text-align: center;
            margin-top: 1mm;
            max-width: 42mm;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .sku {
            font-size: 6pt;
            color: #666;
            text-align: center;
          }
          .price {
            font-size: 7pt;
            font-weight: bold;
            color: #22c55e;
            text-align: center;
          }
          @media print {
            .label { border: none; }
          }
        </style>
      </head>
      <body>
        ${labelsHTML}
        <script>
          window.onload = function() {
            setTimeout(function() { window.print(); window.close(); }, 500);
          };
        </script>
      </body>
      </html>
    `);
    printWindow.document.close();
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={printRef}
        style={{
          background: "white",
          borderRadius: "12px",
          padding: "24px",
          maxWidth: "500px",
          width: "90%",
          maxHeight: "80vh",
          overflow: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "20px",
          }}
        >
          <h3 style={{ margin: 0, color: "#0f172a" }}>Imprimir Etiquetas</h3>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              fontSize: "24px",
              cursor: "pointer",
              color: "#666",
            }}
          >
            ×
          </button>
        </div>

        {/* Preview */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "12px",
            justifyContent: "center",
            marginBottom: "20px",
          }}
        >
          {items.map((item, i) => {
            const barcodeUrl = `${baseURL}/barcodes/${encodeURIComponent(item.sku)}.png`;
            return (
              <div
                key={i}
                style={{
                  border: "1px dashed #ccc",
                  borderRadius: "8px",
                  padding: "12px",
                  textAlign: "center",
                  width: "160px",
                }}
              >
                <img
                  src={barcodeUrl}
                  alt={`Barcode ${item.sku}`}
                  style={{ width: "140px", height: "auto" }}
                  onError={(e) => {
                    e.target.alt = "Error generando barcode";
                    e.target.style.border = "1px solid red";
                  }}
                />
                <div
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: "bold",
                    marginTop: "4px",
                    color: "#333",
                  }}
                >
                  {item.name}
                </div>
                <div style={{ fontSize: "0.7rem", color: "#666" }}>
                  {item.sku}
                </div>
                {item.price != null && (
                  <div
                    style={{
                      fontSize: "0.8rem",
                      fontWeight: "bold",
                      color: "#22c55e",
                    }}
                  >
                    ${Number(item.price).toLocaleString()}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Print button */}
        <div style={{ textAlign: "center" }}>
          <button
            className="btn btn-save"
            onClick={handlePrint}
            style={{ fontSize: "16px", padding: "12px 32px" }}
          >
            🖨️ Imprimir Etiquetas
          </button>
          <div style={{ fontSize: "0.75rem", color: "#999", marginTop: "8px" }}>
            Se abrirá la ventana de impresión del navegador.
            <br />
            Seleccioná tu impresora térmica y configurá el papel a 50mm.
          </div>
        </div>
      </div>
    </div>
  );
}
