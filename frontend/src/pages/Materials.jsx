import { useEffect, useState } from "react";
import api from "../services/api";

export default function Materials() {
  const [data, setData] = useState([]);
  const [form, setForm] = useState({
    sku: "",
    name: "",
    category: "",
    stock: "",
    unit_cost: "",
  });
  const [editId, setEditId] = useState(null);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const r = await api.get("/materials");
      setData(r.data || []);
    } catch (err) {
      console.error("Error loading materials:", err);
      setError("Error al cargar materiales");
    }
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
        stock: parseFloat(form.stock) || 0,
        unit_cost: parseFloat(form.unit_cost) || 0,
      };

      if (editId) {
        await api.put("/materials/" + editId, payload);
      } else {
        await api.post("/materials", payload);
      }

      setForm({ sku: "", name: "", category: "", stock: "", unit_cost: "" });
      setEditId(null);
      load();
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
      stock: String(m.stock || ""),
      unit_cost: String(m.unit_cost || ""),
    });
    setEditId(m.id);
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar material?")) return;
    try {
      await api.delete("/materials/" + id);
      load();
    } catch (err) {
      alert("Error al eliminar");
    }
  };

  useEffect(() => {
    load();
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
            value={form.stock}
            onChange={(e) => setForm({ ...form, stock: e.target.value })}
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

        <div className="form-group" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-save" onClick={save}>
            {editId ? "Actualizar" : "Crear"}
          </button>
          {editId && (
            <button
              className="btn"
              onClick={() => {
                setEditId(null);
                setForm({ sku: "", name: "", category: "", stock: "", unit_cost: "" });
              }}
              style={{ marginLeft: "5px" }}
            >
              Cancelar
            </button>
          )}
        </div>
      </div>

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
                  <td>{i.stock}</td>
                  <td>${i.unit_cost}</td>
                  <td>${((i.stock || 0) * (i.unit_cost || 0)).toFixed(2)}</td>
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
    </div>
  );
}