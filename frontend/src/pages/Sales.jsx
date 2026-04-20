import { useEffect, useState } from "react";
import api from "../services/api";

export default function Sales() {
  const [sales, setSales] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [client, setClient] = useState("");
  const [product, setProduct] = useState("");
  const [qty, setQty] = useState(1);
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
      
      const [salesRes, clientsRes, productsRes, countRes] = await Promise.all([
        api.get(`/sales?skip=${skip}&limit=${itemsPerPage}`, { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/clients", { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/products", { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/sales/count", { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setSales(salesRes.data || []);
      setClients(clientsRes.data || []);
      setProducts(productsRes.data || []);
      setCurrentPage(page);
      setTotalPages(Math.ceil((countRes.data.count || 0) / itemsPerPage));
    } catch (err) {
      console.error("Error loading:", err);
    }
    setLoading(false);
  };

  const create = async () => {
    setError("");
    if (!client || !product) {
      setError("Selecciona cliente y producto");
      return;
    }
    try {
      const token = localStorage.getItem("token");
      await api.post("/sales", {
        client_id: Number(client),
        items: [
          {
            product_id: Number(product),
            quantity: Number(qty),
          },
        ],
      }, { headers: { Authorization: `Bearer ${token}` } });

      setClient("");
      setProduct("");
      setQty(1);
      loadData(currentPage);
    } catch (err) {
      setError("Error al crear venta: " + (err.response?.data?.detail || err.message));
    }
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar venta?")) {
      return;
    }
    try {
      await api.delete("/sales/" + id);
      loadData(currentPage);
    } catch (err) {
      alert("Error al eliminar");
    }
  };

  useEffect(() => {
    loadData(1);
  }, []);

  const getClientName = (id) => {
    const c = clients.find((c) => c.id === id);
    return c ? c.name : `Cliente #${id}`;
  };

  return (
    <div className="container">
      <h2>Ventas</h2>

      {error && (
        <div style={{ color: "red", marginBottom: "15px" }}>{error}</div>
      )}

      <div className="sales-form" style={{ marginBottom: "40px" }}>
        <div className="form-group">
          <label>Cliente:</label>
          <select
            value={client}
            onChange={(e) => setClient(e.target.value)}
            style={{
              padding: "10px 12px",
              border: "2px solid #D4C4A8",
              borderRadius: "6px",
              fontSize: "0.95rem",
              minWidth: "180px",
              background: "white",
            }}
          >
            <option value="">Seleccionar cliente</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Producto:</label>
          <select
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            style={{
              padding: "10px 12px",
              border: "2px solid #D4C4A8",
              borderRadius: "6px",
              fontSize: "0.95rem",
              minWidth: "180px",
              background: "white",
            }}
          >
            <option value="">Seleccionar producto</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} - ${p.price} (Stock: {p.stock})
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Cantidad:</label>
          <input
            type="number"
            min="1"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            style={{ width: "80px" }}
          />
        </div>

        <div className="form-group" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-save" onClick={create}>
            💰 Crear Venta
          </button>
        </div>
      </div>

      {loading && <div style={{ textAlign: "center", padding: "10px" }}>Cargando...</div>}

      <h3 style={{ marginTop: "30px", marginBottom: "15px", color: "#654321" }}>
        Historial de Ventas
      </h3>

      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Cliente</th>
            <th>Total</th>
            <th>Fecha</th>
            <th>Acciones</th>
          </tr>
        </thead>

        <tbody>
          {sales.length === 0 ? (
            <tr>
              <td colSpan="5" style={{ textAlign: "center", padding: "30px" }}>
                No hay ventas registradas
              </td>
            </tr>
          ) : (
            sales.map((s) => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{getClientName(s.client_id)}</td>
                <td style={{ fontWeight: "bold", color: "#22c55e" }}>
                  ${s.total}
                </td>
                <td>{new Date(s.date).toLocaleDateString()}</td>
                <td>
                  <div className="action-buttons">
                    <button
                      className="btn btn-delete"
                      onClick={() => del(s.id)}
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