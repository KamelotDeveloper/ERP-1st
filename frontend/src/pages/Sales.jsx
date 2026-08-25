import { useEffect, useState } from "react";
import api from "../services/api";
import { downloadFileFromBackend } from "../services/downloadService";

export default function Sales() {
  const [sales, setSales] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [client, setClient] = useState("");
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [scanInput, setScanInput] = useState("");
  const [scanMessage, setScanMessage] = useState("");

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

      const [salesRes, clientsRes, productsRes, materialsRes, countRes] = await Promise.all([
        api.get(`/sales?skip=${skip}&limit=${itemsPerPage}`, { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/clients", { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/products", { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/materials", { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/sales/count", { headers: { Authorization: `Bearer ${token}` } })
      ]);

      setSales(salesRes.data || []);
      setClients(clientsRes.data || []);
      setProducts(productsRes.data || []);
      setMaterials(materialsRes.data || []);
      setCurrentPage(page);
      setTotalPages(Math.ceil((countRes.data.count || 0) / itemsPerPage));
    } catch (err) {
      console.error("Error loading:", err);
    }
    setLoading(false);
  };

  // ---- Items dinámicos (como Budget) ----

  const addProductItem = () => {
    setItems([...items, { type: "product", id: "", quantity: 1 }]);
  };

  const addMaterialItem = () => {
    setItems([...items, { type: "material", id: "", quantity: 1 }]);
  };

  const removeItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const updateItem = (index, field, value) => {
    const updated = [...items];
    updated[index][field] = value;
    setItems(updated);
  };

  // ---- Calcular total ----

  const calculateTotal = () => {
    return items.reduce((sum, item) => {
      if (item.type === "product") {
        const p = products.find((p) => p.id == item.id);
        return sum + (p ? p.price * (Number(item.quantity) || 0) : 0);
      } else {
        const m = materials.find((m) => m.id == item.id);
        return sum + (m ? (m.unit_price || 0) * (Number(item.quantity) || 0) : 0);
      }
    }, 0);
  };

  // ---- Crear venta ----

  const create = async () => {
    setError("");
    if (!client) {
      setError("Seleccioná un cliente");
      return;
    }

    const validItems = items
      .filter((i) => i.id && Number(i.quantity) > 0)
      .map((i) => ({
        ...(i.type === "product"
          ? { product_id: Number(i.id) }
          : { material_id: Number(i.id) }),
        quantity: Number(i.quantity),
      }));

    if (validItems.length === 0) {
      setError("Agregá al menos un producto o material");
      return;
    }

    try {
      const token = localStorage.getItem("token");
      await api.post(
        "/sales",
        {
          client_id: Number(client),
          items: validItems,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setClient("");
      setItems([]);
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

  // ---- Escaneo de código de barras ----

  const handleScan = async (e) => {
    if (e.key !== "Enter") return;
    const code = scanInput.trim();
    if (!code) return;

    setScanMessage("");
    try {
      const res = await api.get(`/barcodes/search/${encodeURIComponent(code)}`);
      const found = res.data;

      // Check if already in items — increment quantity
      const existingIndex = items.findIndex(
        (item) => item.type === found.type && String(item.id) === String(found.id)
      );

      if (existingIndex >= 0) {
        const updated = [...items];
        updated[existingIndex] = {
          ...updated[existingIndex],
          quantity: (updated[existingIndex].quantity || 0) + 1,
        };
        setItems(updated);
        setScanMessage(`✅ ${found.name} — cantidad actualizada a ${updated[existingIndex].quantity}`);
      } else {
        setItems([...items, { type: found.type, id: String(found.id), quantity: 1 }]);
        setScanMessage(`✅ ${found.type === "product" ? "Producto" : "Material"}: ${found.name} — $${found.price}`);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setScanMessage(`❌ Código "${code}" no encontrado en productos ni materiales`);
      } else {
        setScanMessage("❌ Error al buscar código");
      }
    }
    setScanInput("");
  };

  useEffect(() => {
    loadData(1);
  }, []);

  const getClientName = (id) => {
    const c = clients.find((c) => c.id === id);
    return c ? c.name : `Cliente #${id}`;
  };

  const handleExport = async () => {
    const token = localStorage.getItem("token");
    const url = `/export/sales?token=${token}`;
    await downloadFileFromBackend(url, "ventas.xlsx");
  };

  const total = calculateTotal();

  return (
    <div className="container">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "15px",
        }}
      >
        <h2 style={{ margin: 0 }}>Ventas</h2>
        <button className="btn" onClick={handleExport}>
          📥 Exportar Excel
        </button>
      </div>

      {error && <div style={{ color: "red", marginBottom: "15px" }}>{error}</div>}

      {/* FORMULARIO */}
      <div
        className="card"
        style={{ marginBottom: "40px", padding: "24px" }}
      >
        <h3 style={{ marginTop: 0, marginBottom: "20px" }}>Nueva Venta</h3>

        {/* Escáner de código de barras */}
        <div
          style={{
            background: "#f0f9ff",
            border: "2px dashed #3b82f6",
            borderRadius: "8px",
            padding: "12px 16px",
            marginBottom: "20px",
          }}
        >
          <label style={{ fontWeight: "bold", color: "#1e40af", display: "block", marginBottom: "6px" }}>
            📷 Escanear código de barras
          </label>
          <input
            type="text"
            value={scanInput}
            onChange={(e) => setScanInput(e.target.value)}
            onKeyDown={handleScan}
            autoFocus
            placeholder="Escaneá o escribí el código y presioná Enter..."
            style={{
              width: "100%",
              padding: "10px 12px",
              border: "2px solid #93c5fd",
              borderRadius: "6px",
              fontSize: "1rem",
              fontFamily: "monospace",
              letterSpacing: "2px",
              boxSizing: "border-box",
            }}
          />
          {scanMessage && (
            <div
              style={{
                marginTop: "8px",
                padding: "6px 10px",
                borderRadius: "4px",
                fontSize: "0.85rem",
                fontWeight: "bold",
                background: scanMessage.startsWith("✅") ? "#dcfce7" : "#fee2e2",
                color: scanMessage.startsWith("✅") ? "#166534" : "#991b1b",
              }}
            >
              {scanMessage}
            </div>
          )}
        </div>

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
              minWidth: "250px",
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

        {/* Items dinámicos */}
        <h4 style={{ marginBottom: "10px" }}>Productos / Materiales</h4>

        {items.map((item, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              gap: "10px",
              marginBottom: "10px",
              alignItems: "center",
            }}
          >
            {item.type === "product" ? (
              <select
                value={item.id}
                onChange={(e) => updateItem(i, "id", e.target.value)}
                style={{ flex: 2, padding: "8px", minWidth: "180px" }}
              >
                <option value="">-- Producto --</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} - ${p.price} (Stock: {p.stock})
                  </option>
                ))}
              </select>
            ) : (
              <select
                value={item.id}
                onChange={(e) => updateItem(i, "id", e.target.value)}
                style={{ flex: 2, padding: "8px", minWidth: "180px" }}
              >
                <option value="">-- Material --</option>
                {materials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} - ${m.unit_price || 0} (Stock: {m.current_stock || 0})
                  </option>
                ))}
              </select>
            )}
            <input
              type="number"
              min="1"
              placeholder="Cant"
              value={item.quantity}
              onChange={(e) => updateItem(i, "quantity", Number(e.target.value))}
              style={{ width: "80px", padding: "8px" }}
            />
            <span style={{ fontWeight: "bold", minWidth: "80px", color: "#22c55e" }}>
              $
              {item.type === "product"
                ? (
                    (products.find((p) => p.id == item.id)?.price || 0) *
                    (Number(item.quantity) || 0)
                  ).toLocaleString()
                : (
                    (materials.find((m) => m.id == item.id)?.unit_price || 0) *
                    (Number(item.quantity) || 0)
                  ).toLocaleString()}
            </span>
            <button className="btn btn-delete" onClick={() => removeItem(i)}>
              ❌
            </button>
          </div>
        ))}

        <div style={{ display: "flex", gap: "10px", marginBottom: "15px" }}>
          <button className="btn btn-edit" onClick={addProductItem}>
            ➕ Agregar Producto
          </button>
          <button className="btn btn-edit" onClick={addMaterialItem}>
            ➕ Agregar Material
          </button>
        </div>

        {/* Total */}
        <div
          style={{
            padding: "16px 20px",
            backgroundColor: "#22c55e",
            color: "white",
            borderRadius: "8px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "20px",
            fontWeight: "bold",
            marginBottom: "15px",
          }}
        >
          <span>TOTAL</span>
          <span>${total.toLocaleString()}</span>
        </div>

        <button className="btn btn-save" onClick={create} style={{ fontSize: "16px", padding: "12px 24px" }}>
          💰 Crear Venta
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: "10px" }}>Cargando...</div>
      )}

      <h3
        style={{
          marginTop: "30px",
          marginBottom: "15px",
          color: "#654321",
        }}
      >
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
                    <button className="btn btn-delete" onClick={() => del(s.id)}>
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
        <div
          className="pagination"
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: "10px",
            marginTop: "20px",
          }}
        >
          <button
            className="btn"
            onClick={() => loadData(currentPage - 1)}
            disabled={currentPage === 1}
          >
            ← Anterior
          </button>
          <span>
            Página {currentPage} de {totalPages}
          </span>
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
