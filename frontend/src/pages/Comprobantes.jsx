import { useEffect, useState } from "react";
import api from "../services/api";

const TIPO_LABELS = {
  FACTURA_A: "Factura A",
  FACTURA_B: "Factura B",
  FACTURA_C: "Factura C",
  FACTURA_M: "Factura M",
  FACTURA_E: "Factura E",
  NOTA_CREDITO_A: "NC A",
  NOTA_CREDITO_B: "NC B",
  NOTA_CREDITO_C: "NC C",
  NOTA_DEBITO_A: "ND A",
  NOTA_DEBITO_B: "ND B",
  NOTA_DEBITO_C: "ND C",
  REMITO_X: "Remito X",
  REMITO_R: "Remito R",
  TICKET: "Ticket",
  NOTA_ENVIO: "Nota de Envío",
  NOTA_RECEPCION: "Nota de Recepción",
  ORDEN_REPARACION: "Ord. Reparación",
};

const ESTADO_LABELS = {
  draft: "Borrador",
  issued: "Emitido",
  cancelled: "Anulado",
  error: "Error",
};

const FISCAL_TIPOS = new Set([
  "FACTURA_A", "FACTURA_B", "FACTURA_C", "FACTURA_M", "FACTURA_E",
  "NOTA_CREDITO_A", "NOTA_CREDITO_B", "NOTA_CREDITO_C",
  "NOTA_DEBITO_A", "NOTA_DEBITO_B", "NOTA_DEBITO_C",
]);

const NC_ND_TIPOS = new Set([
  "NOTA_CREDITO_A", "NOTA_CREDITO_B", "NOTA_CREDITO_C",
  "NOTA_DEBITO_A", "NOTA_DEBITO_B", "NOTA_DEBITO_C",
]);

const INITIAL_FORM = {
  tipo: "",
  fecha_emision: new Date().toISOString().split("T")[0],
  client_id: "",
  notas: "",
  punto_venta: 1,
  comprobante_asociado_id: "",
  remito_tipo: "X",
  orden_compra_ref: "",
  direccion_envio: "",
  fecha_estimada_envio: "",
  proveedor_ref: "",
  producto_recibido: "",
  diagnostico: "",
  tecnico_asignado: "",
  horas_trabajo: "",
  fecha_ingreso: new Date().toISOString().split("T")[0],
  fecha_entrega_estimada: "",
  items: [],
};

export default function Comprobantes() {
  const [view, setView] = useState("list");
  const [selectedId, setSelectedId] = useState(null);

  // List state
  const [comprobantes, setComprobantes] = useState([]);
  const [filtroTipo, setFiltroTipo] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Form state
  const [form, setForm] = useState({ ...INITIAL_FORM });
  const [formStep, setFormStep] = useState(1);
  const [saving, setSaving] = useState(false);

  // Detail state
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Reference data
  const [tipoGroups, setTipoGroups] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);

  const itemsPerPage = 20;

  const loadComprobantes = async (page = 1) => {
    setLoading(true);
    try {
      const params = { page, limit: itemsPerPage };
      if (filtroTipo) params.tipo = filtroTipo;
      if (filtroEstado) params.estado = filtroEstado;

      const res = await api.get("/comprobantes", { params });
      const total = parseInt(res.headers["x-total-count"] || "0", 10);
      setComprobantes(res.data);
      setCurrentPage(page);
      setTotalPages(Math.max(1, Math.ceil(total / itemsPerPage)));
      setTotalCount(total);
    } catch (error) {
      console.error("Error al cargar comprobantes:", error);
      setComprobantes([]);
    }
    setLoading(false);
  };

  const loadReferenceData = async () => {
    try {
      const [clientsRes, productsRes, tiposRes] = await Promise.all([
        api.get("/clients"),
        api.get("/products"),
        api.get("/comprobantes/tipos"),
      ]);
      setClients(clientsRes.data);
      setProducts(productsRes.data);
      setTipoGroups(tiposRes.data);
    } catch (error) {
      console.error("Error al cargar datos de referencia:", error);
    }
  };

  const handleFilterChange = () => {
    loadComprobantes(1);
  };

  const goToList = () => {
    setView("list");
    setSelectedId(null);
    setDetail(null);
    setForm({ ...INITIAL_FORM });
    setFormStep(1);
    loadComprobantes(1);
  };

  const goToCreate = () => {
    setForm({ ...INITIAL_FORM, fecha_emision: new Date().toISOString().split("T")[0], fecha_ingreso: new Date().toISOString().split("T")[0] });
    setFormStep(1);
    setView("create");
  };

  const handleTipoSelect = (tipo) => {
    setForm({ ...form, tipo });
    setFormStep(2);
  };

  const goToDetail = async (id) => {
    setSelectedId(id);
    setView("detail");
    setLoadingDetail(true);
    try {
      const res = await api.get(`/comprobantes/${id}`);
      setDetail(res.data);
    } catch (error) {
      console.error("Error al cargar detalle:", error);
      alert("Error al cargar el detalle del comprobante");
      goToList();
    }
    setLoadingDetail(false);
  };

  // --- Items helpers ---

  const addItem = () => {
    setForm({
      ...form,
      items: [...form.items, { product_id: "", cantidad: 1, precio_unitario: 0, descripcion: "" }],
    });
  };

  const updateItem = (index, field, value) => {
    const newItems = [...form.items];
    newItems[index][field] = value;

    if (field === "product_id") {
      const product = products.find((p) => p.id === parseInt(value));
      if (product) {
        newItems[index].precio_unitario = product.price;
        newItems[index].descripcion = product.name;
      }
    }

    setForm({ ...form, items: newItems });
  };

  const removeItem = (index) => {
    setForm({ ...form, items: form.items.filter((_, i) => i !== index) });
  };

  const calcSubtotal = () => {
    return form.items.reduce((sum, item) => sum + (parseFloat(item.cantidad) || 0) * (parseFloat(item.precio_unitario) || 0), 0);
  };

  const calcIVA = () => {
    if (FISCAL_TIPOS.has(form.tipo)) {
      return calcSubtotal() * 0.21;
    }
    return 0;
  };

  const calcTotal = () => calcSubtotal() + calcIVA();

  const handleCreate = async () => {
    if (!form.tipo) {
      alert("Seleccioná un tipo de comprobante");
      return;
    }
    if (form.items.length === 0) {
      alert("Agregá al menos un item");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        tipo: form.tipo,
        punto_venta: parseInt(form.punto_venta) || 1,
        fecha_emision: form.fecha_emision
          ? new Date(form.fecha_emision + "T12:00:00").toISOString()
          : null,
        notas: form.notas || null,
        client_id: form.client_id ? parseInt(form.client_id) : null,
        items: form.items.map((item) => ({
          product_id: item.product_id ? parseInt(item.product_id) : null,
          descripcion: item.descripcion || null,
          cantidad: parseFloat(item.cantidad) || 1,
          precio_unitario: parseFloat(item.precio_unitario) || 0,
          unidad_medida: "unidad",
        })),
      };

      if (FISCAL_TIPOS.has(form.tipo)) {
        if (form.comprobante_asociado_id) {
          payload.comprobante_asociado_id = parseInt(form.comprobante_asociado_id);
        }
      }

      if (form.tipo.startsWith("REMITO")) {
        payload.remito_tipo = form.remito_tipo || null;
        payload.orden_compra_ref = form.orden_compra_ref || null;
      }

      if (form.tipo === "NOTA_ENVIO") {
        payload.direccion_envio = form.direccion_envio || null;
        payload.fecha_estimada_envio = form.fecha_estimada_envio
          ? new Date(form.fecha_estimada_envio + "T12:00:00").toISOString()
          : null;
      }

      if (form.tipo === "NOTA_RECEPCION") {
        payload.proveedor_ref = form.proveedor_ref || null;
        payload.orden_compra_ref = form.orden_compra_ref || null;
      }

      if (form.tipo === "ORDEN_REPARACION") {
        payload.producto_recibido = form.producto_recibido || null;
        payload.diagnostico = form.diagnostico || null;
        payload.tecnico_asignado = form.tecnico_asignado || null;
        payload.horas_trabajo = form.horas_trabajo ? parseFloat(form.horas_trabajo) : null;
        payload.fecha_ingreso = form.fecha_ingreso
          ? new Date(form.fecha_ingreso + "T12:00:00").toISOString()
          : null;
        payload.fecha_entrega_estimada = form.fecha_entrega_estimada
          ? new Date(form.fecha_entrega_estimada + "T12:00:00").toISOString()
          : null;
      }

      await api.post("/comprobantes", payload);
      alert("Comprobante creado correctamente");
      goToList();
    } catch (error) {
      alert("Error al crear comprobante: " + (error.response?.data?.detail || error.message));
    }
    setSaving(false);
  };

  const handleAnular = async (id) => {
    if (!window.confirm("¿Estás seguro de anular este comprobante?")) return;
    try {
      await api.delete(`/comprobantes/${id}`);
      alert("Comprobante anulado correctamente");
      goToList();
    } catch (error) {
      alert("Error al anular: " + (error.response?.data?.detail || error.message));
    }
  };

  const handleDownloadPDF = async (id) => {
    try {
      const response = await api.get(`/comprobantes/${id}/pdf`, {
        responseType: "blob",
        timeout: 30000,
      });
      if (!response.data) {
        throw new Error("El servidor no devolvió datos");
      }
      const blob = response.data;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `comprobante_${id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error descargando PDF:", error);
      alert("Error al generar PDF. Verificá que el backend esté corriendo.");
    }
  };

  useEffect(() => {
    loadComprobantes(1);
    loadReferenceData();
  }, []);

  // --- RENDER HELPERS ---

  const renderEstadoBadge = (estado) => {
    const label = ESTADO_LABELS[estado] || estado;
    return <span className={`status status-${estado}`}>{label}</span>;
  };

  const renderTipoBadge = (tipo) => {
    const label = TIPO_LABELS[tipo] || tipo;
    const fiscal = FISCAL_TIPOS.has(tipo);
    return (
      <span className={`tipo-badge ${fiscal ? "tipo-fiscal" : ""}`}>
        {label}
      </span>
    );
  };

  // =====================================================================
  // VIEW 1: LIST
  // =====================================================================
  const renderList = () => (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <h2 style={{ border: "none", margin: 0, padding: 0 }}>Comprobantes</h2>
        <button className="btn btn-save" onClick={goToCreate}>
          + Nuevo Comprobante
        </button>
      </div>

      <div className="comprobante-filters">
        <div className="filter-group">
          <label>Tipo</label>
          <select
            value={filtroTipo}
            onChange={(e) => setFiltroTipo(e.target.value)}
          >
            <option value="">Todos los tipos</option>
            {tipoGroups.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.tipos.map((t) => (
                  <option key={t} value={t}>
                    {TIPO_LABELS[t] || t}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Estado</label>
          <select
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
          >
            <option value="">Todos los estados</option>
            {Object.entries(ESTADO_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <button className="btn" onClick={handleFilterChange} style={{ marginTop: "22px" }}>
          Filtrar
        </button>
      </div>

      {loading ? (
        <p style={{ textAlign: "center", color: "#64748b", padding: "40px" }}>Cargando...</p>
      ) : comprobantes.length === 0 ? (
        <div className="empty-state">
          <p>No se encontraron comprobantes</p>
          <button className="btn btn-save" onClick={goToCreate}>
            + Crear primer comprobante
          </button>
        </div>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Número</th>
                <th>Tipo</th>
                <th>Cliente</th>
                <th>Total</th>
                <th>Estado</th>
                <th>Fecha</th>
              </tr>
            </thead>
            <tbody>
              {comprobantes.map((c) => (
                <tr key={c.id} className="clickable-row" onClick={() => goToDetail(c.id)}>
                  <td>{c.numero_formateado || c.numero}</td>
                  <td>{renderTipoBadge(c.tipo)}</td>
                  <td>{c.cliente || "-"}</td>
                  <td>${(c.total || 0).toFixed(2)}</td>
                  <td>{renderEstadoBadge(c.estado)}</td>
                  <td>
                    {c.fecha_emision
                      ? new Date(c.fecha_emision).toLocaleDateString()
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="btn"
                onClick={() => loadComprobantes(currentPage - 1)}
                disabled={currentPage === 1}
              >
                ← Anterior
              </button>
              <span>
                Página {currentPage} de {totalPages} ({totalCount} comprobantes)
              </span>
              <button
                className="btn"
                onClick={() => loadComprobantes(currentPage + 1)}
                disabled={currentPage >= totalPages}
              >
                Siguiente →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );

  // =====================================================================
  // VIEW 2: CREATE / EDIT
  // =====================================================================
  const renderCreate = () => {
    if (formStep === 1) {
      return (
        <div>
          <h2>Nuevo Comprobante</h2>
          <p style={{ color: "#64748b", marginBottom: "20px" }}>
            Seleccioná el tipo de comprobante
          </p>

          <div className="tipo-selector">
            {tipoGroups.map((group) => (
              <div key={group.label} className="tipo-group">
                <h4 className="tipo-group-title">{group.label}</h4>
                <div className="tipo-group-grid">
                  {group.tipos.map((t) => (
                    <button
                      key={t}
                      className="tipo-btn"
                      onClick={() => handleTipoSelect(t)}
                    >
                      <span className="tipo-btn-label">{TIPO_LABELS[t] || t}</span>
                      <span className="tipo-btn-code">{t}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <button className="btn" onClick={goToList} style={{ marginTop: "20px" }}>
            ← Volver
          </button>
        </div>
      );
    }

    const isFiscal = FISCAL_TIPOS.has(form.tipo);
    const isNcNd = NC_ND_TIPOS.has(form.tipo);
    const isRemito = form.tipo.startsWith("REMITO");
    const isNotaEnvio = form.tipo === "NOTA_ENVIO";
    const isNotaRecepcion = form.tipo === "NOTA_RECEPCION";
    const isOrdenRep = form.tipo === "ORDEN_REPARACION";

    return (
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <h2 style={{ border: "none", margin: 0, padding: 0 }}>
            Nuevo {TIPO_LABELS[form.tipo] || form.tipo}
          </h2>
          <button className="btn" onClick={() => setFormStep(1)}>
            ← Cambiar tipo
          </button>
        </div>

        <div className="comprobante-form">
          {/* === COMMON FIELDS === */}
          <div className="form-row">
            <div className="form-group">
              <label>Fecha de emisión</label>
              <input
                type="date"
                value={form.fecha_emision}
                onChange={(e) => setForm({ ...form, fecha_emision: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label>Cliente</label>
              <select
                value={form.client_id}
                onChange={(e) => setForm({ ...form, client_id: e.target.value })}
              >
                <option value="">Sin cliente</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* === FISCAL: comprobante_asociado_id === */}
          {isFiscal && (
            <div className="form-row">
              {isNcNd && (
                <div className="form-group">
                  <label>Comprobante asociado (ID)</label>
                  <input
                    type="number"
                    placeholder="ID del comprobante origen"
                    value={form.comprobante_asociado_id}
                    onChange={(e) =>
                      setForm({ ...form, comprobante_asociado_id: e.target.value })
                    }
                  />
                </div>
              )}
            </div>
          )}

          {/* === REMITO FIELDS === */}
          {isRemito && (
            <div className="form-row">
              <div className="form-group">
                <label>Tipo de Remito</label>
                <select
                  value={form.remito_tipo}
                  onChange={(e) => setForm({ ...form, remito_tipo: e.target.value })}
                >
                  <option value="X">Remito X (entre empresas)</option>
                  <option value="R">Remito R (interno)</option>
                </select>
              </div>
              <div className="form-group">
                <label>Orden de compra ref.</label>
                <input
                  type="text"
                  placeholder="Referencia"
                  value={form.orden_compra_ref}
                  onChange={(e) =>
                    setForm({ ...form, orden_compra_ref: e.target.value })
                  }
                />
              </div>
            </div>
          )}

          {/* === NOTA ENVÍO FIELDS === */}
          {isNotaEnvio && (
            <div className="form-row">
              <div className="form-group" style={{ width: "100%" }}>
                <label>Dirección de envío</label>
                <textarea
                  rows="3"
                  placeholder="Dirección completa"
                  value={form.direccion_envio}
                  onChange={(e) =>
                    setForm({ ...form, direccion_envio: e.target.value })
                  }
                  style={{ width: "100%", padding: "10px 12px", border: "2px solid #93c5fd", borderRadius: "6px", fontSize: "0.95rem", fontFamily: "inherit" }}
                />
              </div>
              <div className="form-group">
                <label>Fecha estimada de envío</label>
                <input
                  type="date"
                  value={form.fecha_estimada_envio}
                  onChange={(e) =>
                    setForm({ ...form, fecha_estimada_envio: e.target.value })
                  }
                />
              </div>
            </div>
          )}

          {/* === NOTA RECEPCIÓN FIELDS === */}
          {isNotaRecepcion && (
            <div className="form-row">
              <div className="form-group">
                <label>Proveedor</label>
                <input
                  type="text"
                  placeholder="Nombre del proveedor"
                  value={form.proveedor_ref}
                  onChange={(e) =>
                    setForm({ ...form, proveedor_ref: e.target.value })
                  }
                />
              </div>
              <div className="form-group">
                <label>Orden de compra ref.</label>
                <input
                  type="text"
                  placeholder="Referencia"
                  value={form.orden_compra_ref}
                  onChange={(e) =>
                    setForm({ ...form, orden_compra_ref: e.target.value })
                  }
                />
              </div>
            </div>
          )}

          {/* === ORDEN REPARACIÓN FIELDS === */}
          {isOrdenRep && (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>Producto recibido</label>
                  <input
                    type="text"
                    placeholder="Descripción del producto"
                    value={form.producto_recibido}
                    onChange={(e) =>
                      setForm({ ...form, producto_recibido: e.target.value })
                    }
                  />
                </div>
                <div className="form-group">
                  <label>Técnico asignado</label>
                  <input
                    type="text"
                    placeholder="Nombre del técnico"
                    value={form.tecnico_asignado}
                    onChange={(e) =>
                      setForm({ ...form, tecnico_asignado: e.target.value })
                    }
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group" style={{ width: "100%" }}>
                  <label>Diagnóstico</label>
                  <textarea
                    rows="3"
                    placeholder="Descripción del problema"
                    value={form.diagnostico}
                    onChange={(e) => setForm({ ...form, diagnostico: e.target.value })}
                    style={{ width: "100%", padding: "10px 12px", border: "2px solid #93c5fd", borderRadius: "6px", fontSize: "0.95rem", fontFamily: "inherit" }}
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Horas de trabajo</label>
                  <input
                    type="number"
                    placeholder="0"
                    step="0.5"
                    value={form.horas_trabajo}
                    onChange={(e) =>
                      setForm({ ...form, horas_trabajo: e.target.value })
                    }
                  />
                </div>
                <div className="form-group">
                  <label>Fecha de ingreso</label>
                  <input
                    type="date"
                    value={form.fecha_ingreso}
                    onChange={(e) =>
                      setForm({ ...form, fecha_ingreso: e.target.value })
                    }
                  />
                </div>
                <div className="form-group">
                  <label>Fecha entrega estimada</label>
                  <input
                    type="date"
                    value={form.fecha_entrega_estimada}
                    onChange={(e) =>
                      setForm({ ...form, fecha_entrega_estimada: e.target.value })
                    }
                  />
                </div>
              </div>
            </>
          )}

          {/* === NOTES === */}
          <div className="form-row">
            <div className="form-group" style={{ width: "100%" }}>
              <label>Notas</label>
              <textarea
                rows="2"
                placeholder="Notas adicionales (opcional)"
                value={form.notas}
                onChange={(e) => setForm({ ...form, notas: e.target.value })}
                style={{ width: "100%", padding: "10px 12px", border: "2px solid #93c5fd", borderRadius: "6px", fontSize: "0.95rem", fontFamily: "inherit" }}
              />
            </div>
          </div>

          {/* === ITEMS SECTION === */}
          <h3>Items</h3>

          {form.items.map((item, index) => (
            <div key={index} className="form-row" style={{ alignItems: "center" }}>
              <select
                value={item.product_id}
                onChange={(e) => updateItem(index, "product_id", e.target.value)}
                style={{ minWidth: "200px" }}
              >
                <option value="">Producto</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>

              <input
                type="number"
                placeholder="Cantidad"
                value={item.cantidad}
                onChange={(e) => updateItem(index, "cantidad", e.target.value)}
                min="1"
                style={{ width: "100px" }}
              />

              <input
                type="number"
                placeholder="Precio unit."
                value={item.precio_unitario}
                onChange={(e) => updateItem(index, "precio_unitario", e.target.value)}
                step="0.01"
                style={{ width: "120px" }}
              />

              <span style={{ padding: "8px", fontWeight: "bold", minWidth: "100px" }}>
                ${(
                  (parseFloat(item.cantidad) || 0) *
                  (parseFloat(item.precio_unitario) || 0)
                ).toFixed(2)}
              </span>

              <button className="btn btn-delete" onClick={() => removeItem(index)}>
                X
              </button>
            </div>
          ))}

          <button onClick={addItem} style={{ marginBottom: "20px" }}>
            + Agregar Item
          </button>

          {/* === TOTALS === */}
          <div className="comprobante-totals">
            <p>Subtotal: ${calcSubtotal().toFixed(2)}</p>
            {isFiscal && <p>IVA (21%): ${calcIVA().toFixed(2)}</p>}
            <p className="total">Total: ${calcTotal().toFixed(2)}</p>
          </div>

          {/* === ACTION BUTTONS === */}
          <div style={{ display: "flex", gap: "10px" }}>
            <button className="btn btn-save" onClick={handleCreate} disabled={saving}>
              {saving ? "Guardando..." : "Guardar Comprobante"}
            </button>
            <button className="btn" onClick={goToList}>
              Cancelar
            </button>
          </div>
        </div>
      </div>
    );
  };

  // =====================================================================
  // VIEW 3: DETAIL
  // =====================================================================
  const renderDetail = () => {
    if (loadingDetail) {
      return <p style={{ textAlign: "center", color: "#64748b", padding: "40px" }}>Cargando detalle...</p>;
    }
    if (!detail) {
      return <p style={{ textAlign: "center", color: "#ef4444", padding: "40px" }}>Comprobante no encontrado</p>;
    }

    const isFiscal = FISCAL_TIPOS.has(detail.tipo);
    const isRemito = detail.tipo.startsWith("REMITO");
    const isNotaEnvio = detail.tipo === "NOTA_ENVIO";
    const isNotaRecepcion = detail.tipo === "NOTA_RECEPCION";
    const isOrdenRep = detail.tipo === "ORDEN_REPARACION";

    return (
      <div>
        <div className="detail-header">
          <div>
            <h2 style={{ border: "none", margin: 0, padding: 0, display: "flex", alignItems: "center", gap: "12px" }}>
              {renderTipoBadge(detail.tipo)}
              {renderEstadoBadge(detail.estado)}
            </h2>
            <p className="detail-number">{detail.numero_formateado}</p>
          </div>
        </div>

        <div className="comprobante-detail-card">
          {/* === COMMON INFO === */}
          <div className="detail-grid">
            <div className="detail-field">
              <span className="detail-label">Cliente</span>
              <span className="detail-value">{detail.cliente || "-"}</span>
            </div>
            <div className="detail-field">
              <span className="detail-label">Fecha de emisión</span>
              <span className="detail-value">
                {detail.fecha_emision
                  ? new Date(detail.fecha_emision).toLocaleDateString()
                  : "-"}
              </span>
            </div>
            <div className="detail-field">
              <span className="detail-label">Punto de venta</span>
              <span className="detail-value">{detail.punto_venta || "-"}</span>
            </div>
            <div className="detail-field">
              <span className="detail-label">Número</span>
              <span className="detail-value">{detail.numero || "-"}</span>
            </div>
          </div>

          {/* === FISCAL SECTION === */}
          {isFiscal && (
            <div className="detail-section">
              <h4>Datos Fiscales</h4>
              <div className="detail-grid">
                <div className="detail-field">
                  <span className="detail-label">CAE</span>
                  <span className="detail-value">{detail.cae || "-"}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">CAE Vto.</span>
                  <span className="detail-value">
                    {detail.cae_vto
                      ? new Date(detail.cae_vto).toLocaleDateString()
                      : "-"}
                  </span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">Tipo AFIP</span>
                  <span className="detail-value">{detail.tipo_afip || "-"}</span>
                </div>
                {detail.comprobante_asociado_id && (
                  <div className="detail-field">
                    <span className="detail-label">Comprobante asociado</span>
                    <span className="detail-value">{detail.comprobante_asociado_id}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* === REMITO SECTION === */}
          {isRemito && (
            <div className="detail-section">
              <h4>Datos del Remito</h4>
              <div className="detail-grid">
                <div className="detail-field">
                  <span className="detail-label">Tipo</span>
                  <span className="detail-value">{detail.remito_tipo === "X" ? "Remito X (entre empresas)" : detail.remito_tipo === "R" ? "Remito R (interno)" : "-"}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">Orden de compra ref.</span>
                  <span className="detail-value">{detail.orden_compra_ref || "-"}</span>
                </div>
              </div>
            </div>
          )}

          {/* === NOTA ENVÍO SECTION === */}
          {isNotaEnvio && (
            <div className="detail-section">
              <h4>Datos del Envío</h4>
              <div className="detail-grid">
                <div className="detail-field" style={{ gridColumn: "1 / -1" }}>
                  <span className="detail-label">Dirección de envío</span>
                  <span className="detail-value">{detail.direccion_envio || "-"}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">Fecha estimada de envío</span>
                  <span className="detail-value">
                    {detail.fecha_estimada_envio
                      ? new Date(detail.fecha_estimada_envio).toLocaleDateString()
                      : "-"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* === NOTA RECEPCIÓN SECTION === */}
          {isNotaRecepcion && (
            <div className="detail-section">
              <h4>Datos de Recepción</h4>
              <div className="detail-grid">
                <div className="detail-field">
                  <span className="detail-label">Proveedor</span>
                  <span className="detail-value">{detail.proveedor_ref || "-"}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">Orden de compra ref.</span>
                  <span className="detail-value">{detail.orden_compra_ref || "-"}</span>
                </div>
              </div>
            </div>
          )}

          {/* === ORDEN REPARACIÓN SECTION === */}
          {isOrdenRep && (
            <div className="detail-section">
              <h4>Datos de la Reparación</h4>
              <div className="detail-grid">
                <div className="detail-field">
                  <span className="detail-label">Producto recibido</span>
                  <span className="detail-value">{detail.producto_recibido || "-"}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">Técnico asignado</span>
                  <span className="detail-value">{detail.tecnico_asignado || "-"}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">Horas de trabajo</span>
                  <span className="detail-value">{detail.horas_trabajo || "-"}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">Fecha de ingreso</span>
                  <span className="detail-value">
                    {detail.fecha_ingreso
                      ? new Date(detail.fecha_ingreso).toLocaleDateString()
                      : "-"}
                  </span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">Fecha entrega estimada</span>
                  <span className="detail-value">
                    {detail.fecha_entrega_estimada
                      ? new Date(detail.fecha_entrega_estimada).toLocaleDateString()
                      : "-"}
                  </span>
                </div>
                <div className="detail-field" style={{ gridColumn: "1 / -1" }}>
                  <span className="detail-label">Diagnóstico</span>
                  <span className="detail-value">{detail.diagnostico || "-"}</span>
                </div>
              </div>
            </div>
          )}

          {/* === NOTES === */}
          {detail.notas && (
            <div className="detail-section">
              <h4>Notas</h4>
              <p style={{ color: "#475569", lineHeight: 1.6 }}>{detail.notas}</p>
            </div>
          )}

          {/* === ITEMS TABLE === */}
          <div className="detail-section">
            <h4>Items</h4>
            <table className="table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Cantidad</th>
                  <th>Precio Unit.</th>
                  <th>Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {detail.items && detail.items.length > 0 ? (
                  detail.items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.descripcion || `Producto #${item.product_id}`}</td>
                      <td>{item.cantidad}</td>
                      <td>${(item.precio_unitario || 0).toFixed(2)}</td>
                      <td>${(item.subtotal || 0).toFixed(2)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="4" style={{ textAlign: "center", color: "#94a3b8" }}>
                      Sin items
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Totals in detail */}
            <div className="comprobante-totals" style={{ marginTop: "10px" }}>
              <p>Subtotal: ${(detail.subtotal || 0).toFixed(2)}</p>
              {isFiscal && <p>IVA: ${(detail.iva_importe || 0).toFixed(2)}</p>}
              <p className="total">Total: ${(detail.total || 0).toFixed(2)}</p>
            </div>
          </div>

          {/* === ACTION BUTTONS === */}
          <div style={{ display: "flex", gap: "10px", marginTop: "20px", flexWrap: "wrap" }}>
            {detail.estado !== "cancelled" && (
              <button className="btn btn-delete" onClick={() => handleAnular(detail.id)}>
                Anular Comprobante
              </button>
            )}
            <button className="btn btn-save" onClick={() => handleDownloadPDF(detail.id)}>
              Descargar PDF
            </button>
            <button className="btn" onClick={goToList}>
              ← Volver
            </button>
          </div>
        </div>
      </div>
    );
  };

  // =====================================================================
  // MAIN RENDER
  // =====================================================================
  return (
    <div className="container">
      {view === "list" && renderList()}
      {view === "create" && renderCreate()}
      {view === "detail" && renderDetail()}

      <style>{`
        .comprobante-filters {
          display: flex;
          gap: 15px;
          align-items: flex-end;
          margin-bottom: 25px;
          flex-wrap: wrap;
          background: white;
          padding: 20px;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }

        .filter-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .filter-group label {
          font-size: 0.85rem;
          font-weight: 600;
          color: #0f172a;
        }

        .filter-group select {
          padding: 10px 12px;
          border: 2px solid #93c5fd;
          border-radius: 6px;
          font-size: 0.95rem;
          min-width: 200px;
          background: white;
        }

        .filter-group select:focus {
          outline: none;
          border-color: #0ea5e9;
        }

        .empty-state {
          text-align: center;
          padding: 60px 20px;
          background: white;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }

        .empty-state p {
          color: #64748b;
          font-size: 1.1rem;
          margin-bottom: 20px;
        }

        .pagination {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 15px;
          margin-top: 25px;
          background: white;
          padding: 15px;
          border-radius: 8px;
        }

        .pagination span {
          color: #475569;
          font-size: 0.95rem;
        }

        .clickable-row {
          cursor: pointer;
        }

        .clickable-row:hover {
          background: #f0f9ff !important;
        }

        .tipo-selector {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .tipo-group {
          background: white;
          padding: 20px;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }

        .tipo-group-title {
          margin: 0 0 12px 0;
          color: #0f172a;
          font-size: 1rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .tipo-group-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }

        .tipo-btn {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 14px 18px;
          border: 2px solid #e2e8f0;
          border-radius: 8px;
          background: #f8fafc;
          cursor: pointer;
          transition: all 0.2s;
          min-width: 130px;
          min-height: 70px;
        }

        .tipo-btn:hover {
          border-color: #0ea5e9;
          background: #f0f9ff;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(14, 165, 233, 0.15);
        }

        .tipo-btn-label {
          font-size: 0.95rem;
          font-weight: 600;
          color: #0f172a;
        }

        .tipo-btn-code {
          font-size: 0.7rem;
          color: #94a3b8;
          margin-top: 4px;
        }

        .comprobante-form {
          background: white;
          padding: 25px;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }

        .comprobante-totals {
          background: #f8f9fa;
          padding: 15px;
          border-radius: 6px;
          margin: 20px 0;
        }

        .comprobante-totals p {
          margin: 5px 0;
        }

        .comprobante-totals .total {
          font-size: 18px;
          font-weight: bold;
          color: #22c55e;
        }

        .status {
          padding: 4px 10px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }

        .status-draft {
          background: #fef3c7;
          color: #92400e;
        }

        .status-issued {
          background: #dcfce7;
          color: #166534;
        }

        .status-cancelled {
          background: #fee2e2;
          color: #991b1b;
        }

        .status-error {
          background: #fce7f3;
          color: #9d174d;
        }

        .tipo-badge {
          display: inline-block;
          padding: 4px 10px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
          background: #e2e8f0;
          color: #475569;
        }

        .tipo-badge.tipo-fiscal {
          background: #e0f2fe;
          color: #075985;
        }

        .detail-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 25px;
        }

        .detail-number {
          font-size: 1.3rem;
          font-weight: 700;
          color: #0f172a;
          margin: 8px 0 0 0;
          font-family: monospace;
        }

        .comprobante-detail-card {
          background: white;
          padding: 25px;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }

        .detail-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }

        .detail-field {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .detail-label {
          font-size: 0.8rem;
          font-weight: 600;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .detail-value {
          font-size: 1rem;
          color: #0f172a;
        }

        .detail-section {
          margin-top: 25px;
          padding-top: 25px;
          border-top: 1px solid #e2e8f0;
        }

        .detail-section h4 {
          margin: 0 0 15px 0;
          color: #0f172a;
          font-size: 1rem;
          font-weight: 700;
        }

        textarea {
          font-family: inherit;
          resize: vertical;
        }

        .form-group textarea {
          width: 100%;
          padding: 10px 12px;
          border: 2px solid #93c5fd;
          border-radius: 6px;
          font-size: 0.95rem;
        }

        .form-group textarea:focus {
          outline: none;
          border-color: #0ea5e9;
        }
      `}</style>
    </div>
  );
}
