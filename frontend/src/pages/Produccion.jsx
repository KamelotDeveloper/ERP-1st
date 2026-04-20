import { useState, useEffect } from "react";
import api from "../services/api";

export default function Produccion() {
  console.log("=== Produccion component MOUNTED ===");
  const [activeTab, setActiveTab] = useState("ordenes");
  const [ordenes, setOrdenes] = useState([]);
  const [plantillas, setPlantillas] = useState([]);
  const [products, setProducts] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Nueva plantilla
  const [showNewPlantilla, setShowNewPlantilla] = useState(false);
  const [editingPlantilla, setEditingPlantilla] = useState(null);
  const [newPlantilla, setNewPlantilla] = useState({
    product_id: "",
    materiales: []
  });
  
  // Para nueva orden
  const [selectedPlantilla, setSelectedPlantilla] = useState(null);
  const [cantidad, setCantidad] = useState(1);
  const [explosion, setExplosion] = useState(null);
  const [ejecutando, setEjecutando] = useState(false);
  const [mensaje, setMensaje] = useState({ type: "", text: "" });

  useEffect(() => {
    // Load all production data on mount
const loadAllData = async () => {
      setLoading(true);
      try {
        const token = localStorage.getItem("token");
        console.log("Token exists:", !!token, token ? "YES" : "NO");
        
        // Products and materials don't need auth
        const [prodsRes, matsRes] = await Promise.all([
          api.get("/products"),
          api.get("/materials")
        ]);
        
        // Always load ordenes and plantillas (even without token, just try)
        let ordenesRes = { data: [] };
        let plantillasRes = { data: [] };
        
        const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
        
        try {
          const [oRes, pRes] = await Promise.all([
            api.get("/produccion/ordenes", { headers: authHeaders }).catch(e => ({ data: [] })),
            api.get("/produccion/plantillas", { headers: authHeaders }).catch(e => ({ data: [] }))
          ]);
          ordenesRes = oRes;
          plantillasRes = pRes;
        } catch (e) {
          console.error("Error loading ordenes/plantillas:", e);
        }
        
        console.log("=== DEBUG PROD ===");
        console.log("Products:", prodsRes.data?.length);
        console.log("Materials:", matsRes.data?.length);
        console.log("Ordenes:", ordenesRes.data?.length);
        console.log("Plantillas:", plantillasRes.data?.length);
        
        setProducts(prodsRes.data || []);
        setMaterials(matsRes.data || []);
        setOrdenes(ordenesRes.data || []);
        setPlantillas(plantillasRes.data || []);
      } catch (err) {
        console.error("Error loading production data:", err);
        console.error("Error response:", err.response?.data);
      }
      setLoading(false);
    };
    
    loadAllData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      console.log("Loading production data, token:", token ? "present" : "missing");
      
      const [ordenesRes, plantillasRes] = await Promise.all([
        api.get("/produccion/ordenes", { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/produccion/plantillas", { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setOrdenes(ordenesRes.data);
      setPlantillas(plantillasRes.data);
    } catch (err) {
      console.error("Error loading data:", err);
      console.error("Error response:", err.response?.data);
    }
    setLoading(false);
  };

  const checkExplosion = async () => {
    if (!selectedPlantilla || cantidad <= 0) return;
    
    try {
      const token = localStorage.getItem("token");
      const res = await api.post(
        `/produccion/explosion-materiales?plantilla_id=${selectedPlantilla}&cantidad=${cantidad}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setExplosion(res.data);
    } catch (err) {
      console.error("Error en explosión:", err);
    }
  };

  useEffect(() => {
    if (selectedPlantilla && cantidad > 0) {
      checkExplosion();
    }
  }, [selectedPlantilla, cantidad]);

  const ejecutarProduccion = async () => {
    if (!explosion || !explosion.puede_producir) return;
    
    setEjecutando(true);
    setMensaje({ type: "", text: "" });
    
    try {
      const token = localStorage.getItem("token");
      const res = await api.post(
        "/produccion/ejecutar",
        {
          plantilla_id: selectedPlantilla,
          cantidad: cantidad
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      setMensaje({ 
        type: "success", 
        text: `¡Producción completada! Se crearon ${cantidad} unidades.` 
      });
      
      setSelectedPlantilla(null);
      setCantidad(1);
      setExplosion(null);
      loadData();
      
    } catch (err) {
      setMensaje({ 
        type: "error", 
        text: err.response?.data?.detail || "Error al ejecutar producción" 
      });
    }
    
    setEjecutando(false);
  };

  // Agregar material a la nueva plantilla
  const addMaterialToPlantilla = () => {
    setNewPlantilla({
      ...newPlantilla,
      materiales: [...newPlantilla.materiales, { material_id: "", cantidad: 1 }]
    });
  };

  // Guardar nueva plantilla
  const savePlantilla = async () => {
    if (!newPlantilla.product_id || newPlantilla.materiales.length === 0) {
      alert("Selecciona un producto y agrega al menos un material");
      return;
    }

    // Filtrar materiales sin completar y convertir material_id a número
    const materialesValidos = newPlantilla.materiales
      .filter(m => m.material_id && m.cantidad > 0)
      .map(m => ({
        material_id: Number(m.material_id),
        cantidad: m.cantidad
      }));
    if (materialesValidos.length === 0) {
      alert("Agrega materiales válidos");
      return;
    }

    try {
      const token = localStorage.getItem("token");
      await api.post(
        "/produccion/plantillas",
        {
          product_id: Number(newPlantilla.product_id),
          is_active: true,
          materiales: materialesValidos
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      alert("¡Plantilla creada exitosamente!");
      setShowNewPlantilla(false);
      setNewPlantilla({ product_id: "", materiales: [] });
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al crear plantilla");
    }
  };

  // Editar plantilla
  const editPlantilla = (plantilla) => {
    setEditingPlantilla({
      id: plantilla.id,
      product_id: plantilla.product_id,
      materiales: plantilla.materiales.map(m => ({
        material_id: m.material_id,
        cantidad: m.cantidad
      }))
    });
    setShowNewPlantilla(true);
  };

  // Guardar edición de plantilla
  const saveEditPlantilla = async () => {
    if (!editingPlantilla || editingPlantilla.materiales.length === 0) {
      alert("La plantilla debe tener al menos un material");
      return;
    }

    // Filtrar y convertir material_id a número
    const materialesValidos = editingPlantilla.materiales
      .filter(m => m.material_id && m.cantidad > 0)
      .map(m => ({
        material_id: Number(m.material_id),
        cantidad: m.cantidad
      }));
    if (materialesValidos.length === 0) {
      alert("Agrega materiales válidos");
      return;
    }

    try {
      const token = localStorage.getItem("token");
      await api.put(
        `/produccion/plantillas/${editingPlantilla.id}`,
        {
          materiales: materialesValidos
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      alert("¡Plantilla actualizada!");
      setShowNewPlantilla(false);
      setEditingPlantilla(null);
      setNewPlantilla({ product_id: "", materiales: [] });
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al actualizar plantilla");
    }
  };

  // Eliminar plantilla
  const deletePlantilla = async (plantillaId) => {
    if (!confirm("¿Estás seguro de eliminar esta plantilla?")) {
      return; // user clicked Cancel - do nothing
    }
    
    try {
      const token = localStorage.getItem("token");
      await api.delete(
        `/produccion/plantillas/${plantillaId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      alert("¡Plantilla eliminada!");
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar plantilla");
    }
  };

  // Cancelar edición/creación
  const cancelPlantilla = () => {
    setShowNewPlantilla(false);
    setEditingPlantilla(null);
    setNewPlantilla({ product_id: "", materiales: [] });
  };

  return (
    <div className="container">
      <h2>🏭 Módulo de Producción</h2>
      
      {/* Tabs */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
        <button 
          className={`btn ${activeTab === "ordenes" ? "" : "btn-edit"}`}
          onClick={() => setActiveTab("ordenes")}
        >
          📋 Órdenes
        </button>
        <button 
          className={`btn ${activeTab === "plantillas" ? "" : "btn-edit"}`}
          onClick={() => setActiveTab("plantillas")}
        >
          📝 Plantillas
        </button>
        <button 
          className={`btn ${activeTab === "nueva-orden" ? "" : "btn-save"}`}
          onClick={() => setActiveTab("nueva-orden")}
        >
          ➕ Nueva Producción
        </button>
      </div>

      {loading && <div>Cargando...</div>}

      {/* TAB: ÓRDENES */}
      {activeTab === "ordenes" && (
        <div className="card">
          <h3>Historial de Órdenes de Producción</h3>
          {ordenes.length === 0 ? (
            <p style={{ color: "#666" }}>No hay órdenes de producción</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Producto</th>
                  <th>Cantidad</th>
                  <th>Estado</th>
                  <th>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {ordenes.map(orden => (
                  <tr key={orden.id}>
                    <td>#{orden.id}</td>
                    <td>{orden.product_name}</td>
                    <td>{orden.cantidad}</td>
                    <td>
                      <span className={`status status-${orden.estado}`}>
                        {orden.estado === "completada" ? "✅ Completada" : 
                         orden.estado === "pendiente" ? "⏳ Pendiente" :
                         orden.estado === "cancelada" ? "❌ Cancelada" : orden.estado}
                      </span>
                    </td>
                    <td>{new Date(orden.fecha_creacion).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* TAB: PLANTILLAS */}
      {activeTab === "plantillas" && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3>Plantillas de Producción (Recetas)</h3>
            <button className="btn btn-save" onClick={() => { setEditingPlantilla(null); setNewPlantilla({ product_id: "", materiales: [] }); setShowNewPlantilla(true); }}>
              ➕ Nueva Plantilla
            </button>
          </div>

          {/* Formulario nueva/edit plantilla */}
          {showNewPlantilla && (
            <div style={{ 
              marginTop: "20px", 
              padding: "15px", 
              backgroundColor: "#f0f9ff",
              borderRadius: "8px",
              border: "1px solid #bae6fd"
            }}>
              <h4>{editingPlantilla ? "Editar Plantilla" : "Crear Nueva Plantilla"}</h4>
              
              <div className="form-group">
                <label>Producto</label>
                <select 
                  value={editingPlantilla ? editingPlantilla.product_id : newPlantilla.product_id}
                  onChange={(e) => editingPlantilla 
                    ? setEditingPlantilla({ ...editingPlantilla, product_id: e.target.value })
                    : setNewPlantilla({ ...newPlantilla, product_id: e.target.value })
                  }
                  style={{ width: "100%", padding: "8px" }}
                  disabled={!!editingPlantilla}
                >
                  <option value="">-- Seleccionar producto --</option>
                  {products.length === 0 && <option>NO HAY PRODUCTOS DEBUG</option>}
                  {products.map(p => (
                    <option key={p.id} value={p.id}>{p.name} (SKU: {p.sku})</option>
                  ))}
                </select>
              </div>

              <h5 style={{ marginTop: "15px" }}>Materiales Necesarios</h5>
              {(editingPlantilla ? editingPlantilla.materiales : newPlantilla.materiales).map((m, i) => (
                <div key={i} style={{ display: "flex", gap: "10px", marginBottom: "10px" }}>
                  <select 
                    value={m.material_id}
                    onChange={(e) => {
                      const target = editingPlantilla ? setEditingPlantilla : setNewPlantilla;
                      const state = editingPlantilla ? editingPlantilla : newPlantilla;
                      const key = editingPlantilla ? "materiales" : "materiales";
                      const newMaterials = [...state.materiales];
                      newMaterials[i].material_id = e.target.value;
                      target({ ...state, [key]: newMaterials });
                    }}
                    style={{ flex: 2, padding: "8px" }}
                  >
                    <option value="">-- Material --</option>
                    {materials.length === 0 && <option>NO HAY MATERIALES</option>}
                    {materials.map(mat => (
                      <option key={mat.id} value={mat.id}>{mat.name} (Stock: {mat.stock || mat.current_stock || 0})</option>
                    ))}
                  </select>
                  <input
                    type="number"
                    placeholder="Cantidad"
                    value={m.cantidad}
                    onChange={(e) => {
                      const target = editingPlantilla ? setEditingPlantilla : setNewPlantilla;
                      const state = editingPlantilla ? editingPlantilla : newPlantilla;
                      const key = editingPlantilla ? "materiales" : "materiales";
                      const newMaterials = [...state.materiales];
                      newMaterials[i].cantidad = Number(e.target.value);
                      target({ ...state, [key]: newMaterials });
                    }}
                    style={{ flex: 1, padding: "8px" }}
                  />
                  <button 
                    className="btn btn-delete"
                    onClick={() => {
                      const target = editingPlantilla ? setEditingPlantilla : setNewPlantilla;
                      const state = editingPlantilla ? editingPlantilla : newPlantilla;
                      const key = editingPlantilla ? "materiales" : "materiales";
                      const newMaterials = state.materiales.filter((_, idx) => idx !== i);
                      target({ ...state, [key]: newMaterials });
                    }}
                  >
                    ❌
                  </button>
                </div>
              ))}
              
              <button 
                className="btn btn-edit" 
                onClick={() => {
                  const target = editingPlantilla ? setEditingPlantilla : setNewPlantilla;
                  const state = editingPlantilla ? editingPlantilla : newPlantilla;
                  const key = editingPlantilla ? "materiales" : "materiales";
                  target({ ...state, [key]: [...state.materiales, { material_id: "", cantidad: 1 }] });
                }} 
                style={{ marginBottom: "15px" }}
              >
                ➕ Agregar Material
              </button>

              <div style={{ display: "flex", gap: "10px" }}>
                <button className="btn btn-save" onClick={editingPlantilla ? saveEditPlantilla : savePlantilla}>
                  💾 {editingPlantilla ? "Actualizar" : "Guardar"} Plantilla
                </button>
                <button className="btn" onClick={cancelPlantilla}>❌ Cancelar</button>
              </div>
            </div>
          )}

          {plantillas.length === 0 && !showNewPlantilla ? (
            <p style={{ color: "#666" }}>No hay plantillas. Crea una con el botón de arriba.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Producto</th>
                  <th>Materiales</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {plantillas.map(p => (
                  <tr key={p.id}>
                    <td>#{p.id}</td>
                    <td>{p.product_name}</td>
                    <td>{p.materiales?.length || 0} materiales</td>
                    <td>{p.is_active ? "✅ Activa" : "❌ Inactiva"}</td>
                    <td>
                      <button 
                        className="btn btn-edit" 
                        onClick={() => editPlantilla(p)}
                        style={{ marginRight: "5px", padding: "4px 8px" }}
                      >
                        ✏️ Editar
                      </button>
                      <button 
                        className="btn btn-delete" 
                        onClick={() => deletePlantilla(p.id)}
                        style={{ padding: "4px 8px" }}
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* TAB: NUEVA PRODUCCIÓN */}
      {activeTab === "nueva-orden" && (
        <div className="card">
          <h3>Crear Orden de Producción</h3>
          
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

          <div className="form-group">
            <label>Seleccionar Producto (Plantilla)</label>
            <select 
              value={selectedPlantilla || ""}
              onChange={(e) => setSelectedPlantilla(Number(e.target.value))}
              style={{ width: "100%", padding: "8px" }}
            >
              <option value="">-- Seleccionar producto --</option>
              {plantillas.length === 0 && <option>NO HAY PLANTILLAS</option>}
              {plantillas.filter(p => p.is_active).map(p => (
                <option key={p.id} value={p.id}>
                  {p.product_name} ({p.materiales?.length || 0} materiales)
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Cantidad a Producir</label>
            <input
              type="number"
              min="1"
              value={cantidad}
              onChange={(e) => setCantidad(Number(e.target.value))}
              style={{ width: "100%", padding: "8px" }}
            />
          </div>

          {/* EXPLOSIÓN DE MATERIALES */}
          {explosion && (
            <div style={{ 
              marginTop: "20px", 
              padding: "15px", 
              backgroundColor: "#f9fafb",
              borderRadius: "8px"
            }}>
              <h4 style={{ marginTop: 0 }}>📊 Materiales a Consumir</h4>
              
              <table className="table" style={{ marginBottom: "15px" }}>
                <thead>
                  <tr>
                    <th>Material</th>
                    <th>Stock Actual</th>
                    <th>Necesario</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {explosion.materiales.map(m => (
                    <tr key={m.material_id}>
                      <td>{m.material_name}</td>
                      <td>{m.stock_actual}</td>
                      <td>{m.cantidad_necesaria}</td>
                      <td>
                        {m.tiene_suficiente ? 
                          <span style={{ color: "green" }}>✅</span> : 
                          <span style={{ color: "red" }}>❌ Faltante</span>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {explosion.puede_producir ? (
                <button 
                  className="btn btn-save"
                  onClick={ejecutarProduccion}
                  disabled={ejecutando}
                  style={{ width: "100%" }}
                >
                  {ejecutando ? "Procesando..." : `✅ Confirmar Producción de ${cantidad} unidades`}
                </button>
              ) : (
                <div style={{ 
                  padding: "10px", 
                  backgroundColor: "#fee2e2", 
                  color: "#991b1b",
                  borderRadius: "4px"
                }}>
                  ⚠️ No hay suficiente stock de materiales para producir {cantidad} unidades
                </div>
              )}
            </div>
          )}

          {!explosion && selectedPlantilla && (
            <div style={{ color: "#666", fontStyle: "italic" }}>
              Ingrese la cantidad para ver los materiales necesarios
            </div>
          )}
        </div>
      )}
    </div>
  );
}