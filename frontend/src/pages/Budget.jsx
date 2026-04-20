import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../services/api";
import { downloadPDFToFolder, ensureDownloadFolder } from "../services/downloadService";

export default function Budget() {
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState("list");
  const [presupuestos, setPresupuestos] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Vista de detalles
  const [detallePresupuesto, setDetallePresupuesto] = useState(null);
  
  const [form, setForm] = useState({
    nombre: "",
    cliente_nombre: "",
    cliente_telefono: "",
    cliente_email: "",
    costo_mano_obra: 0,
    margen: 0,
    notas: "",
    items: []
  });
  
  const [editingId, setEditingId] = useState(null);
  const [mensaje, setMensaje] = useState({ type: "", text: "" });

  useEffect(() => {
    loadData(1);
  }, []);

  // Auto-open highlighted presupuesto from search
  useEffect(() => {
    const highlightId = searchParams.get("highlight");
    if (highlightId && presupuestos.length > 0) {
      const id = parseInt(highlightId);
      const presupuesto = presupuestos.find(p => p.id === id);
      if (presupuesto) {
        verDetalle(id);
      }
    }
  }, [searchParams, presupuestos]);

  // Paginación
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const itemsPerPage = 20;

  const loadData = async (page = 1) => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const skip = (page - 1) * itemsPerPage;
      
      const [presRes, matRes, countRes] = await Promise.all([
        api.get(`/presupuestos?skip=${skip}&limit=${itemsPerPage}`, { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/materials", { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/presupuestos/count", { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setPresupuestos(presRes.data);
      setMaterials(matRes.data);
      setCurrentPage(page);
      setTotalPages(Math.ceil((countRes.data.count || 0) / itemsPerPage));
    } catch (err) {
      console.error("Error loading data:", err);
    }
    setLoading(false);
  };

  const addItem = () => {
    setForm({
      ...form,
      items: [...form.items, { material_id: "", cantidad: 1 }]
    });
  };

  const removeItem = (index) => {
    const newItems = form.items.filter((_, i) => i !== index);
    setForm({ ...form, items: newItems });
  };

  const updateItem = (index, field, value) => {
    const newItems = [...form.items];
    newItems[index][field] = value;
    setForm({ ...form, items: newItems });
  };

  const calculateCosts = () => {
    let costoMateriales = 0;
    const itemsWithPrices = form.items.map(item => {
      const material = materials.find(m => m.id == item.material_id);
      const precio = material ? (material.unit_cost || 0) : 0;
      const subtotal = precio * item.cantidad;
      costoMateriales += subtotal;
      return { ...item, precio_unitario: precio, subtotal };
    });
    
    const precioFinal = costoMateriales + form.costo_mano_obra + form.margen;
    
    return { costoMateriales, itemsWithPrices, precioFinal };
  };

  const savePresupuesto = async () => {
    if (!form.nombre) {
      alert("Ingrese un nombre para el presupuesto");
      return;
    }
    if (form.items.length === 0 || !form.items.some(i => i.material_id)) {
      alert("Agregue al menos un material");
      return;
    }

    const validItems = form.items
      .filter(i => i.material_id && i.cantidad > 0)
      .map(i => ({
        material_id: Number(i.material_id),  // Convertir string a int para Pydantic
        cantidad: i.cantidad
      }));
    if (validItems.length === 0) {
      alert("Complete los items del presupuesto");
      return;
    }

    try {
      const token = localStorage.getItem("token");
      const payload = {
        nombre: form.nombre,
        cliente_nombre: form.cliente_nombre || null,
        cliente_telefono: form.cliente_telefono || null,
        cliente_email: form.cliente_email || null,
        costo_mano_obra: form.costo_mano_obra || 0,
        margen: form.margen || 0,
        notas: form.notas || null,
        items: validItems
      };

      if (editingId) {
        await api.put(`/presupuestos/${editingId}`, payload, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setMensaje({ type: "success", text: "Presupuesto actualizado" });
      } else {
        await api.post("/presupuestos", payload, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setMensaje({ type: "success", text: "Presupuesto creado" });
      }

      resetForm();
      loadData();
    } catch (err) {
      // Handle 422 validation errors and other errors properly
      let errorMessage = "Error al guardar";
      if (err.response?.data?.detail) {
        // Pydantic validation error - format as readable message
        const details = err.response.data.detail;
        if (Array.isArray(details)) {
          // Field validation errors
          errorMessage = details.map(d => `${d.loc?.[1] || 'campo'}: ${d.msg}`).join(', ');
        } else if (typeof details === 'string') {
          errorMessage = details;
        } else {
          errorMessage = JSON.stringify(details);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      setMensaje({ type: "error", text: String(errorMessage) });
    }
  };

  const resetForm = () => {
    setForm({
      nombre: "",
      cliente_nombre: "",
      cliente_telefono: "",
      cliente_email: "",
      costo_mano_obra: 0,
      margen: 0,
      notas: "",
      items: []
    });
    setEditingId(null);
    setActiveTab("list");
  };

  const editPresupuesto = (p) => {
    setForm({
      nombre: p.nombre,
      cliente_nombre: p.cliente_nombre || "",
      cliente_telefono: p.cliente_telefono || "",
      cliente_email: p.cliente_email || "",
      costo_mano_obra: p.costo_mano_obra || 0,
      margen: p.margen || 0,
      notas: p.notas || "",
      items: p.items.map(i => ({
        material_id: i.material_id,
        cantidad: i.cantidad
      }))
    });
    setEditingId(p.id);
    setActiveTab("create");
  };

  const confirmarVenta = async (id) => {
    if (!confirm("¿Confirmar esta venta? Se descontarán los materiales del stock y se registrará en ventas.")) {
      return;
    }

    try {
      const token = localStorage.getItem("token");
      const res = await api.post(`/presupuestos/${id}/confirmar-venta`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      alert(res.data.message);
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al confirmar venta");
    }
  };

  const aceptarPresupuesto = async (id) => {
    try {
      const token = localStorage.getItem("token");
      await api.post(`/presupuestos/${id}/aceptar`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Error");
    }
  };

  const rechazarPresupuesto = async (id) => {
    try {
      const token = localStorage.getItem("token");
      await api.post(`/presupuestos/${id}/rechazar`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Error");
    }
  };

  const deletePresupuesto = async (id) => {
    if (!confirm("¿Eliminar este presupuesto?")) {
      return;
    }
    try {
      const token = localStorage.getItem("token");
      await api.delete(`/presupuestos/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Error");
    }
  };

  const verDetalle = async (id) => {
    console.log("Click en verDetalle, id:", id);
    try {
      const token = localStorage.getItem("token");
      console.log("Token:", token ? "presente" : "NO HAY TOKEN");
      const res = await api.get(`/presupuestos/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      console.log("Respuesta:", res.data);
      setDetallePresupuesto(res.data);
      setActiveTab("detail");
    } catch (err) {
      console.error("Error completo:", err);
      console.error("Response:", err.response);
      alert(err.response?.data?.detail || "Error al cargar detalles");
    }
  };

const downloadPDF = async (id) => {
    try {
      const response = await api.get(`/presupuestos/${id}/pdf`, {
        responseType: 'blob',
        timeout: 30000
      });
      
      // Check if response is valid
      if (!response.data) {
        throw new Error('El servidor no devolvió datos');
      }
      
      const blob = response.data;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Nombre de archivo: ElMenestral_Presupuesto_{id}.pdf
      link.setAttribute('download', `ElMenestral_Presupuesto_${id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      // Mostrar mensaje de éxito
      alert('✅ PDF descargado: ElMenestral_Presupuesto_' + id + '.pdf');
      
    } catch (err) {
      console.error('Error descargando PDF:', err);
      alert('Error al generar PDF. Verifique que el backend esté corriendo.');
    }
  };

  const getEstadoColor = (estado) => {
    switch(estado) {
      case "pendiente": return "#f59e0b";
      case "aceptado": return "#3b82f6";
      case "rechazado": return "#ef4444";
      case "vendido": return "#22c55e";
      default: return "#666";
    }
  };

  const { costoMateriales, precioFinal } = calculateCosts();

  return (
    <div className="container">
      <h2>📝 Módulo de Presupuestos</h2>
      
      {/* Tabs */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
        <button 
          className={`btn ${activeTab === "list" ? "" : "btn-edit"}`}
          onClick={() => setActiveTab("list")}
        >
          📋 Lista
        </button>
        <button 
          className={`btn ${activeTab === "create" ? "" : "btn-save"}`}
          onClick={() => { resetForm(); setActiveTab("create"); }}
        >
          ➕ Nuevo Presupuesto
        </button>
        {detallePresupuesto && (
          <button 
            className={`btn ${activeTab === "detail" ? "" : "btn-edit"}`}
            onClick={() => setActiveTab("detail")}
          >
            👁️ Ver Detalle
          </button>
        )}
      </div>

      {loading && <div>Cargando...</div>}

      {/* LISTA */}
      {activeTab === "list" && (
        <div className="card">
          <h3>Presupuestos</h3>
          
          {presupuestos.length === 0 ? (
            <p style={{ color: "#666" }}>No hay presupuestos</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Cliente</th>
                  <th>Total</th>
                  <th>Estado</th>
                  <th>Fecha</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {presupuestos.map(p => (
                  <tr key={p.id}>
                    <td>
                      <button 
                        style={{ 
                          background: "none", 
                          border: "none", 
                          color: "#2e86de", 
                          cursor: "pointer",
                          textDecoration: "underline",
                          padding: 0,
                          font: "inherit"
                        }}
                        onClick={() => verDetalle(p.id)}
                        title="Ver detalles"
                      >
                        {p.nombre}
                      </button>
                    </td>
                    <td>{p.cliente_nombre || "-"}</td>
                    <td>${p.precio_final?.toLocaleString() || 0}</td>
                    <td>
                      <span style={{ 
                        padding: "4px 8px", 
                        borderRadius: "4px",
                        backgroundColor: getEstadoColor(p.estado),
                        color: "white",
                        fontSize: "12px"
                      }}>
                        {p.estado}
                      </span>
                    </td>
                    <td>{new Date(p.fecha_creacion).toLocaleDateString()}</td>
                    <td>
                      <div style={{ display: "flex", gap: "5px", flexWrap: "wrap" }}>
                        <button className="btn btn-edit" style={{ padding: "4px 8px" }} onClick={() => verDetalle(p.id)}>👁️</button>
                        {p.estado === "pendiente" && (
                          <>
                            <button className="btn btn-edit" style={{ padding: "4px 8px" }} onClick={() => editPresupuesto(p)}>✏️</button>
                            <button className="btn" style={{ padding: "4px 8px" }} onClick={() => aceptarPresupuesto(p.id)}>✓</button>
                            <button className="btn btn-delete" style={{ padding: "4px 8px" }} onClick={() => rechazarPresupuesto(p.id)}>✗</button>
                          </>
                        )}
                        <button className="btn btn-save" style={{ padding: "4px 8px" }} onClick={() => downloadPDF(p.id)}>📄 PDF</button>
                        {p.estado === "aceptado" && (
                          <button className="btn btn-save" style={{ padding: "4px 8px" }} onClick={() => confirmarVenta(p.id)}>💰</button>
                        )}
                        {p.estado !== "vendido" && (
                          <button className="btn btn-delete" style={{ padding: "4px 8px" }} onClick={() => deletePresupuesto(p.id)}>🗑️</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          
          {/* Paginación */}
          {totalPages > 1 && (
            <div style={{ display: "flex", justifyContent: "center", gap: "10px", marginTop: "20px", padding: "10px" }}>
              <button 
                className="btn" 
                onClick={() => loadData(currentPage - 1)}
                disabled={currentPage === 1}
                style={{ padding: "8px 16px" }}
              >
                ← Anterior
              </button>
              <span style={{ padding: "8px 16px", alignSelf: "center" }}>
                Página {currentPage} de {totalPages}
              </span>
              <button 
                className="btn" 
                onClick={() => loadData(currentPage + 1)}
                disabled={currentPage >= totalPages}
                style={{ padding: "8px 16px" }}
              >
                Siguiente →
              </button>
            </div>
          )}
        </div>
      )}

      {/* CREAR/EDITAR */}
      {activeTab === "create" && (
        <div className="card">
          <h3>{editingId ? "Editar Presupuesto" : "Nuevo Presupuesto"}</h3>
          
          {mensaje.text && (
            <div style={{ 
              padding: "10px", 
              marginBottom: "15px",
              backgroundColor: mensaje.type === "success" ? "#dcfce7" : "#fee2e2",
              color: mensaje.type === "success" ? "#166534" : "#991b1b",
              borderRadius: "4px"
            }}>
              {mensaje.text}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "15px" }}>
            <div className="form-group">
              <label>Nombre del Trabajo *</label>
              <input
                type="text"
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                placeholder="Ej: Mueble Cocina Gladis"
                style={{ width: "100%", padding: "8px" }}
              />
            </div>
            
            <div className="form-group">
              <label>Cliente</label>
              <input
                type="text"
                value={form.cliente_nombre}
                onChange={(e) => setForm({ ...form, cliente_nombre: e.target.value })}
                placeholder="Nombre del cliente"
                style={{ width: "100%", padding: "8px" }}
              />
            </div>

            <div className="form-group">
              <label>Teléfono (para WhatsApp)</label>
              <input
                type="text"
                value={form.cliente_telefono}
                onChange={(e) => setForm({ ...form, cliente_telefono: e.target.value })}
                placeholder="Ej: 11 1234 5678"
                style={{ width: "100%", padding: "8px" }}
              />
            </div>

            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={form.cliente_email}
                onChange={(e) => setForm({ ...form, cliente_email: e.target.value })}
                placeholder="cliente@email.com"
                style={{ width: "100%", padding: "8px" }}
              />
            </div>
          </div>

          {/* Items */}
          <h4 style={{ marginTop: "20px" }}>Materiales</h4>
          
          {form.items.map((item, i) => (
            <div key={i} style={{ display: "flex", gap: "10px", marginBottom: "10px" }}>
              <select
                value={item.material_id}
                onChange={(e) => updateItem(i, "material_id", e.target.value)}
                style={{ flex: 2, padding: "8px" }}
              >
                <option value="">-- Material --</option>
                {materials.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.name} (Stock: {m.stock || 0}) - ${m.unit_cost || 0}
                  </option>
                ))}
              </select>
              <input
                type="number"
                placeholder="Cant"
                value={item.cantidad}
                onChange={(e) => updateItem(i, "cantidad", Number(e.target.value))}
                style={{ width: "80px", padding: "8px" }}
              />
              <button className="btn btn-delete" onClick={() => removeItem(i)}>❌</button>
            </div>
          ))}
          
          <button className="btn btn-edit" onClick={addItem}>➕ Agregar Material</button>

          {/* Costos */}
          <div style={{ marginTop: "20px", padding: "20px", backgroundColor: "#f9fafb", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
            <h4 style={{ marginTop: 0, marginBottom: "15px", color: "#374151" }}>💵 Resumen de Costos</h4>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
              <div style={{ backgroundColor: "white", padding: "15px", borderRadius: "8px" }}>
                <label style={{ display: "block", color: "#6b7280", fontSize: "14px", marginBottom: "5px" }}>Costo Materiales:</label>
                <div style={{ fontSize: "28px", fontWeight: "bold", color: "#1f2937" }}>
                  ${costoMateriales.toLocaleString()}
                </div>
              </div>
              
              <div style={{ backgroundColor: "white", padding: "15px", borderRadius: "8px" }}>
                <label style={{ display: "block", color: "#6b7280", fontSize: "14px", marginBottom: "5px" }}>Mano de Obra ($):</label>
                <input
                  type="number"
                  value={form.costo_mano_obra}
                  onChange={(e) => setForm({ ...form, costo_mano_obra: Number(e.target.value) })}
                  placeholder="0"
                  style={{ width: "100%", padding: "12px", fontSize: "18px", border: "1px solid #d1d5db", borderRadius: "4px" }}
                />
              </div>
              
              <div style={{ backgroundColor: "white", padding: "15px", borderRadius: "8px" }}>
                <label style={{ display: "block", color: "#6b7280", fontSize: "14px", marginBottom: "5px" }}>Margen/Ganancia ($):</label>
                <input
                  type="number"
                  value={form.margen}
                  onChange={(e) => setForm({ ...form, margen: Number(e.target.value) })}
                  placeholder="0"
                  style={{ width: "100%", padding: "12px", fontSize: "18px", border: "1px solid #d1d5db", borderRadius: "4px" }}
                />
              </div>
              
              <div style={{ backgroundColor: "#22c55e", color: "white", padding: "20px", borderRadius: "8px" }}>
                <label style={{ display: "block", fontSize: "14px", opacity: 0.9, marginBottom: "5px" }}>💰 PRECIO FINAL:</label>
                <div style={{ fontSize: "32px", fontWeight: "bold" }}>
                  ${precioFinal.toLocaleString()}
                </div>
              </div>
            </div>
          </div>

          {/* Notas */}
          <div className="form-group" style={{ marginTop: "15px" }}>
            <label>Notas adicionales</label>
            <textarea
              value={form.notas}
              onChange={(e) => setForm({ ...form, notas: e.target.value })}
              placeholder="Observaciones adicionales..."
              style={{ width: "100%", padding: "8px", height: "80px" }}
            />
          </div>

          {/* Botones */}
          <div style={{ marginTop: "20px", display: "flex", gap: "10px" }}>
            <button className="btn btn-save" onClick={savePresupuesto}>
              💾 {editingId ? "Actualizar" : "Crear"} Presupuesto
            </button>
            <button className="btn" onClick={resetForm}>❌ Cancelar</button>
          </div>
        </div>
      )}

      {/* VER DETALLE */}
      {activeTab === "detail" && detallePresupuesto && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <h3>📋 Detalle del Presupuesto</h3>
            <button className="btn" onClick={() => { setDetallePresupuesto(null); setActiveTab("list"); }}>✖ Cerrar</button>
          </div>

          {/* Info principal */}
          <div style={{ backgroundColor: "#f9fafb", padding: "20px", borderRadius: "8px", marginBottom: "20px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "15px" }}>
              <div>
                <strong>Nombre:</strong> {detallePresupuesto.nombre}
              </div>
              <div>
                <strong>Estado:</strong> 
                <span style={{ 
                  marginLeft: "10px",
                  padding: "4px 8px", 
                  borderRadius: "4px",
                  backgroundColor: getEstadoColor(detallePresupuesto.estado),
                  color: "white",
                  fontSize: "12px"
                }}>
                  {detallePresupuesto.estado}
                </span>
              </div>
              <div><strong>Cliente:</strong> {detallePresupuesto.cliente_nombre || "Sin nombre"}</div>
              <div><strong>Fecha:</strong> {new Date(detallePresupuesto.fecha_creacion).toLocaleDateString()}</div>
              <div><strong>Teléfono:</strong> {detallePresupuesto.cliente_telefono || "Sin teléfono"}</div>
              <div><strong>Email:</strong> {detallePresupuesto.cliente_email || "Sin email"}</div>
            </div>
          </div>

          {/* Materiales */}
          <h4>📦 Materiales</h4>
          <table className="table">
            <thead>
              <tr>
                <th>Material</th>
                <th>Cantidad</th>
                <th>Precio Unit.</th>
                <th>Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {Array.isArray(detallePresupuesto.items) && detallePresupuesto.items.map((item, i) => (
                <tr key={i}>
                  <td>{(item.material && item.material.name) || item.material_name || "Material"}</td>
                  <td>{item.cantidad}</td>
                  <td>${(item.precio_unitario || 0).toLocaleString()}</td>
                  <td>${(item.subtotal || 0).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Costos */}
          <div style={{ marginTop: "20px", padding: "20px", backgroundColor: "#f9fafb", borderRadius: "8px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "15px" }}>
              <div><strong>Materiales:</strong> ${(detallePresupuesto.costo_materiales || 0).toLocaleString()}</div>
              <div><strong>Mano de Obra:</strong> ${(detallePresupuesto.costo_mano_obra || 0).toLocaleString()}</div>
              <div><strong>Margen:</strong> ${(detallePresupuesto.margen || 0).toLocaleString()}</div>
            </div>
            <div style={{ marginTop: "15px", padding: "15px", backgroundColor: "#22c55e", color: "white", borderRadius: "8px", textAlign: "center" }}>
              <strong style={{ fontSize: "24px" }}>TOTAL: ${(detallePresupuesto.precio_final || 0).toLocaleString()}</strong>
            </div>
          </div>

          {/* Notas */}
          {detallePresupuesto.notas && (
            <div style={{ marginTop: "20px" }}>
              <strong>Notas:</strong>
              <p style={{ color: "#666" }}>{detallePresupuesto.notas}</p>
            </div>
          )}

          {/* Acciones rápidas */}
          <div style={{ marginTop: "20px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <button className="btn btn-save" onClick={() => downloadPDF(detallePresupuesto.id)}>
              📄 Descargar PDF
            </button>
            {detallePresupuesto.estado === "pendiente" && (
              <>
                <button className="btn" onClick={() => aceptarPresupuesto(detallePresupuesto.id)}>✓ Aceptar</button>
                <button className="btn btn-delete" onClick={() => rechazarPresupuesto(detallePresupuesto.id)}>✗ Rechazar</button>
              </>
            )}
            {detallePresupuesto.estado === "aceptado" && (
              <button className="btn btn-save" onClick={() => confirmarVenta(detallePresupuesto.id)}>
                💰 Confirmar Venta
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}