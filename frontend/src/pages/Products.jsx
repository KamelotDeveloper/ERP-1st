import { useEffect, useState } from "react";
import api from "../services/api";

export default function Products() {
  const [data, setData] = useState([]);
  const [form, setForm] = useState({ sku: "", name: "", price: "", stock: "", stock_minimo: "" });
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
      
      const [productsRes, countRes] = await Promise.all([
        api.get(`/products?skip=${skip}&limit=${itemsPerPage}`, { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/products/count", { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setData(productsRes.data || []);
      setCurrentPage(page);
      setTotalPages(Math.ceil((countRes.data.count || 0) / itemsPerPage));
    } catch (err) {
      console.error("Error loading products:", err);
      setError("Error al cargar productos");
    }
    setLoading(false);
  };

  const save = async () => {
    setError("");
    try {
      const productData = {
        sku: form.sku,
        name: form.name,
        price: parseFloat(form.price) || 0,
        stock: parseInt(form.stock) || 0,
        stock_minimo: parseInt(form.stock_minimo) || 0,
      };

      if (editId) {
        await api.put("/products/" + editId, productData);
      } else {
        await api.post("/products", productData);
      }

      setForm({ sku: "", name: "", price: "", stock: "", stock_minimo: "" });
      setEditId(null);
      loadData(currentPage);
    } catch (err) {
      console.error("Error saving product:", err);
      setError("Error al guardar: " + (err.response?.data?.detail || err.message));
    }
  };

  const edit = (p) => {
    setForm({
      sku: p.sku || "",
      name: p.name || "",
      price: String(p.price || ""),
      stock: String(p.stock || ""),
      stock_minimo: String(p.stock_minimo || ""),
    });
    setEditId(p.id);
  };

  const restock = async (id) => {
    const qty = prompt("Cantidad a agregar:");
    if (!qty || isNaN(qty)) return;
    try {
      await api.put(`/products/${id}/restock?quantity=${qty}`);
      loadData(currentPage);
    } catch (err) {
      alert("Error al reponer stock");
    }
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar producto?")) return;
    try {
      await api.delete("/products/" + id);
      loadData(currentPage);
    } catch (err) {
      alert("Error al eliminar");
    }
  };

  useEffect(() => {
    loadData(1);
  }, []);

  return (
    <div className="container">
      <h2>Productos</h2>

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
            placeholder="Código SKU"
          />
        </div>

        <div className="form-group">
          <label>Nombre:</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Nombre del producto"
          />
        </div>

        <div className="form-group">
          <label>Precio ($):</label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={form.price}
            onChange={(e) => setForm({ ...form, price: e.target.value })}
            placeholder="0.00"
          />
        </div>

        <div className="form-group">
          <label>Stock:</label>
          <input
            type="number"
            min="0"
            value={form.stock}
            onChange={(e) => setForm({ ...form, stock: e.target.value })}
            placeholder="0"
          />
        </div>

        <div className="form-group">
          <label>Stock mínimo:</label>
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
                setForm({ sku: "", name: "", price: "", stock: "", stock_minimo: "" });
              }}
              style={{ marginLeft: "5px" }}
            >
              Cancelar
            </button>
          )}
        </div>
      </div>

      {loading && <div style={{ textAlign: "center", padding: "10px" }}>Cargando...</div>}

      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>SKU</th>
            <th>Nombre</th>
            <th>Precio</th>
            <th>Stock</th>
            <th>Acciones</th>
          </tr>
        </thead>

        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan="6" style={{ textAlign: "center", padding: "20px" }}>
                No hay productos. Agrega uno arriba.
              </td>
            </tr>
          ) : (
            data.map((i) => (
              <tr key={i.id}>
                <td>{i.id}</td>
                <td>{i.sku}</td>
                <td>{i.name}</td>
                <td>${i.price}</td>
                <td>{i.stock}</td>

                <td>
                  <div className="action-buttons">
                    <button className="btn btn-edit" onClick={() => edit(i)}>
                      Editar
                    </button>
                    <button
                      className="btn btn-delete"
                      onClick={() => del(i.id)}
                    >
                      Eliminar
                    </button>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

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