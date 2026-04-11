import { useEffect, useState } from "react";
import api from "../services/api";

export default function Materials() {
  const [data, setData] = useState([]);
  const [form, setForm] = useState({
    sku: "",
    name: "",
    category: "",
    current_stock: "",
    unit_cost: "",
    stock_minimo: "",
  });
  const [editId, setEditId] = useState(null);
  const [error, setError] = useState("");
  
  // Paginación
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const itemsPerPage = 20;
  const [loading, setLoading] = useState(false);

  const loadData = async (page = 1) => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const skip = (page - 1) * itemsPerPage;
      
      const [materialsRes, countRes] = await Promise.all([
        api.get(`/materials?skip=${skip}&limit=${itemsPerPage}`, { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/materials/count", { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setData(materialsRes.data || []);
      setCurrentPage(page);
      setTotalPages(Math.ceil((countRes.data.count || 0) / itemsPerPage));
    } catch (err) {
      console.error("Error loading materials:", err);
      setError("Error al cargar materiales");
    }
    setLoading(false);
  };

  const save = async () => {
    setError("");
    if (!form.name || !form.category) {
      setError("Nombre y categoría son requeridos");
      return;
    }
    try {
      const payload = {
        sku: form.sku,
        name: form.name,
        category: form.category,
        current_stock: parseFloat(form.current_stock) || 0,
        unit_cost: parseFloat(form.unit_cost) || 0,
        stock_minimo: parseInt(form.stock_minimo) || 0,
      };

      if (editId) {
        await api.put("/materials/" + editId, payload);
      } else {
        await api.post("/materials", payload);
      }

      setForm({ sku: "", name: "", category: "", current_stock: "", unit_cost: "", stock_minimo: "" });
      setEditId(null);
      loadData(currentPage);
    } catch (err) {
      console.error("Error saving material:", err);
      setError("Error al guardar: " + (err.response?.data?.detail || err.message));
    }
  };

  const edit = (m) => {
    setForm({
      sku: m.sku || "",
      name: m.name || "",
      category: m.category || "",
      current_stock: String(m.current_stock || ""),
      unit_cost: String(m.unit_cost || ""),
      stock_minimo: String(m.stock_minimo || ""),
    });
    setEditId(m.id);
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar material?")) return;
    try {
      await api.delete("/materials/" + id);
      loadData(currentPage);
    } catch (err) {
      alert("Error al eliminar");
    }
  };

  useEffect(() => {
    loadData(1);
  }, []);

  const grouped = data.reduce((acc, item) => {
    const cat = item.category || "Sin categoría";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  return (
    <div className="container">
      <h2>Materiales</h2>

      {error && (
        <div style={{ color: "red", marginBottom: "10px" }}>{error}</div>
      )}

      <div className="form-row">
        <div className="form-group">
          <label>SKU:</label>
          <input
            type="text"
            value={form.sku}
            onChange={(e) => setForm({ ...form, sku: e.target.value })}
            placeholder="Código"
          />
        </div>

        <div className="form-group">
          <label>Nombre *:</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Nombre del material"
          />
        </div>

        <div className="form-group">
          <label>Categoría *:</label>
          <input
            type="text"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            placeholder="madera, herraje, etc."
          />
        </div>

        <div className="form-group">
          <label>Stock:</label>
          <input
            type="number"
            step="0.01"
            value={form.current_stock}
            onChange={(e) => setForm({ ...form, current_stock: e.target.value })}
            placeholder="0"
          />
        </div>

        <div className="form-group">
          <label>Costo unit. ($):</label>
          <input
            type="number"
            step="0.01"
            value={form.unit_cost}
            onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
            placeholder="0.00"
          />
        </div>

        <div className="form-group">
          <label>Stock mín:</label>
          <input
            type="number"
            min="0"
            value={form.stock_minimo}
            onChange={(e) => setForm({ ...form, stock_minimo: e.target.value })}
            placeholder="0"
          />
        </div>

        <div className="form-group" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-save" onClick={save}>
            {editId ? "Actualizar" : "Crear"}
          </button>
          {editId && (
            <button
              className="btn"
              onClick={() => {
                setEditId(null);
                setForm({ sku: "", name: "", category: "", current_stock: "", unit_cost: "", stock_minimo: "" });
              }}
              style={{ marginLeft: "5px" }}
            >
              Cancelar
            </button>
          )}
        </div>
      </div>

      {loading && <div style={{ textAlign: "center", padding: "10px" }}>Cargando...</div>}

      {data.length === 0 && (
        <p style={{ textAlign: "center", padding: "20px" }}>
          No hay materiales cargados. Agrega uno arriba.
        </p>
      )}

      {Object.keys(grouped).map((cat) => (
        <div key={cat}>
          <h3 className="category-title">{cat}</h3>

          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>SKU</th>
                <th>Nombre</th>
                <th>Stock</th>
                <th>Stock mín</th>
                <th>Costo unit.</th>
                <th>Total</th>
                <th>Acciones</th>
              </tr>
            </thead>

            <tbody>
              {grouped[cat].map((i) => (
                <tr key={i.id}>
                  <td>{i.id}</td>
                  <td>{i.sku || "-"}</td>
                  <td>{i.name}</td>
                  <td>{i.current_stock}</td>
                  <td>{i.stock_minimo || 0}</td>
                  <td>${i.unit_cost}</td>
                  <td>${((i.current_stock || 0) * (i.unit_cost || 0)).toFixed(2)}</td>
                  <td>
                    <div className="action-buttons">
                      <button className="btn btn-edit" onClick={() => edit(i)}>
                        Editar
                      </button>
                      <button className="btn btn-delete" onClick={() => del(i.id)}>
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {totalPages > 1 && (
        <div className="pagination" style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "10px", marginTop: "20px" }}>
          <button
            className="btn"
            onClick={() => loadData(currentPage - 1)}
            disabled={currentPage === 1}
          >
            ← Anterior
          </button>
          <span>Página {currentPage} de {totalPages}</span>
          <button
            className="btn"
            onClick={() => loadData(currentPage + 1)}
            disabled={currentPage >= totalPages}
          >
            Siguiente →
          </button>
        </div>
      )}
    </div>
  );
}