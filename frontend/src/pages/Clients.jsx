import React, { useEffect, useState } from "react";
import api from "../services/api";
import ImportModal from "../components/ImportModal";

const IMPORT_COLUMNS = [
  { key: "name", label: "Nombre", required: true },
  { key: "email", label: "Email", required: false },
  { key: "phone", label: "Teléfono", required: false },
  { key: "address", label: "Dirección", required: false },
  { key: "tax_id", label: "CUIT", required: false },
  { key: "condicion_iva_receptor_id", label: "Condición IVA ID", required: false },
];

export default function Clients() {
  const [data, setData] = useState([]);
  const [showImport, setShowImport] = useState(false);
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    tax_id: "",
  });
  const [editId, setEditId] = useState(null);
  const [error, setError] = useState("");
  
  // Paginación
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const itemsPerPage = 20;
  const [loading, setLoading] = useState(false);

  // Historial de compras expandible
  const [expandedClientId, setExpandedClientId] = useState(null);
  const [purchaseHistory, setPurchaseHistory] = useState({});
  const [purchasePage, setPurchasePage] = useState({});
  const [purchaseLoading, setPurchaseLoading] = useState({});
  const [purchaseTotalPages, setPurchaseTotalPages] = useState({});

  const loadData = async (page = 1) => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const skip = (page - 1) * itemsPerPage;
      
      const [clientsRes, countRes] = await Promise.all([
        api.get(`/clients?skip=${skip}&limit=${itemsPerPage}`, { headers: { Authorization: `Bearer ${token}` } }),
        api.get("/clients/count", { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setData(clientsRes.data || []);
      setCurrentPage(page);
      setTotalPages(Math.ceil((countRes.data.count || 0) / itemsPerPage));
    } catch (err) {
      console.error("Error loading clients:", err);
      setError("Error al cargar clientes");
    }
    setLoading(false);
  };

  const save = async () => {
    setError("");
    if (!form.name) {
      setError("El nombre es requerido");
      return;
    }
    try {
      if (editId) {
        await api.put("/clients/" + editId, form);
      } else {
        await api.post("/clients", form);
      }
      setForm({ name: "", email: "", phone: "", address: "", tax_id: "" });
      setEditId(null);
      loadData(currentPage);
    } catch (err) {
      console.error("Error saving client:", err);
      setError("Error al guardar: " + (err.response?.data?.detail || err.message));
    }
  };

  const edit = (c) => {
    setForm({
      name: c.name || "",
      email: c.email || "",
      phone: c.phone || "",
      address: c.address || "",
      tax_id: c.tax_id || "",
    });
    setEditId(c.id);
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar cliente?")) {
      return;
    }
    try {
      await api.delete("/clients/" + id);
      loadData(currentPage);
    } catch (err) {
      alert("Error al eliminar");
    }
  };

  const PAYMENT_LABELS = {
    efectivo: "Efectivo",
    transferencia: "Transferencia",
    tarjeta: "Tarjeta",
    cheque: "Cheque",
    otros: "Otros",
  };

  const togglePurchases = async (clientId, page = 1) => {
    if (expandedClientId === clientId) {
      setExpandedClientId(null);
      return;
    }
    setExpandedClientId(clientId);
    setPurchaseLoading((prev) => ({ ...prev, [clientId]: true }));
    try {
      const token = localStorage.getItem("token");
      const skip = (page - 1) * 10;
      const res = await api.get(`/clients/${clientId}/purchases?skip=${skip}&limit=10`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPurchaseHistory((prev) => ({ ...prev, [clientId]: res.data.purchases || [] }));
      setPurchasePage((prev) => ({ ...prev, [clientId]: page }));
      setPurchaseTotalPages((prev) => ({
        ...prev,
        [clientId]: Math.ceil((res.data.total_count || 0) / 10),
      }));
    } catch (err) {
      setPurchaseHistory((prev) => ({
        ...prev,
        [clientId]: { error: err.response?.data?.detail || "Error al cargar compras" },
      }));
    }
    setPurchaseLoading((prev) => ({ ...prev, [clientId]: false }));
  };

  useEffect(() => {
    loadData(1);
  }, []);

  return (
    <div className="container">
      <h2>Clientes</h2>

      {error && (
        <div style={{ color: "red", marginBottom: "10px" }}>{error}</div>
      )}

      <div className="form-row">
        <div className="form-group">
          <label>Nombre *:</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Nombre completo"
          />
        </div>

        <div className="form-group">
          <label>Email:</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="email@ejemplo.com"
          />
        </div>

        <div className="form-group">
          <label>Teléfono:</label>
          <input
            type="text"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="Teléfono"
          />
        </div>

        <div className="form-group">
          <label>Dirección:</label>
          <input
            type="text"
            value={form.address}
            onChange={(e) => setForm({ ...form, address: e.target.value })}
            placeholder="Dirección"
          />
        </div>

        <div className="form-group">
          <label>CUIT:</label>
          <input
            type="text"
            value={form.tax_id}
            onChange={(e) => setForm({ ...form, tax_id: e.target.value })}
            placeholder="XX-XXXXXXXX-X"
          />
        </div>

        <div className="form-group" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-save" onClick={save}>
            {editId ? "Actualizar" : "Crear"}
          </button>
          <button
            className="btn"
            onClick={() => setShowImport(true)}
            style={{ marginLeft: "5px" }}
          >
            Importar
          </button>
          {editId && (
            <button
              className="btn"
              onClick={() => {
                setEditId(null);
                setForm({ name: "", email: "", phone: "", address: "", tax_id: "" });
              }}
              style={{ marginLeft: "5px" }}
            >
              Cancelar
            </button>
          )}
        </div>
      </div>

      {showImport && (
        <ImportModal
          resource="clients"
          columns={IMPORT_COLUMNS}
          onImportComplete={() => loadData(currentPage)}
          onClose={() => setShowImport(false)}
        />
      )}

      {loading && <div style={{ textAlign: "center", padding: "10px" }}>Cargando...</div>}

      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Nombre</th>
            <th>Email</th>
            <th>Teléfono</th>
            <th>Dirección</th>
            <th>CUIT</th>
            <th>Acciones</th>
            <th>Compras</th>
          </tr>
        </thead>

        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan="8" style={{ textAlign: "center", padding: "20px" }}>
                No hay clientes. Agrega uno arriba.
              </td>
            </tr>
          ) : (
            data.map((i) => (
              <React.Fragment key={i.id}>
                <tr>
                  <td>{i.id}</td>
                  <td>{i.name}</td>
                  <td>{i.email || "-"}</td>
                  <td>{i.phone || "-"}</td>
                  <td>{i.address || "-"}</td>
                  <td>{i.tax_id || "-"}</td>
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
                  <td>
                    <button
                      className="btn"
                      onClick={() => togglePurchases(i.id)}
                    >
                      {expandedClientId === i.id ? "Ocultar" : "Ver Compras"}
                    </button>
                  </td>
                </tr>
                {expandedClientId === i.id && (
                  <tr>
                    <td colSpan="8" style={{ padding: "15px", background: "#f9f9f9" }}>
                      {purchaseLoading[i.id] ? (
                        <div style={{ textAlign: "center", padding: "10px" }}>Cargando...</div>
                      ) : purchaseHistory[i.id]?.error ? (
                        <div style={{ color: "red", textAlign: "center", padding: "10px" }}>
                          {purchaseHistory[i.id].error}
                        </div>
                      ) : !purchaseHistory[i.id] || purchaseHistory[i.id].length === 0 ? (
                        <div style={{ textAlign: "center", padding: "10px", color: "#888" }}>
                          Sin compras registradas
                        </div>
                      ) : (
                        <div>
                          <table className="table" style={{ background: "white" }}>
                            <thead>
                              <tr>
                                <th>Fecha</th>
                                <th>Producto</th>
                                <th>Cantidad</th>
                                <th>Precio</th>
                                <th>Total</th>
                                <th>Método de Pago</th>
                              </tr>
                            </thead>
                            <tbody>
                              {purchaseHistory[i.id].map((purchase) =>
                                purchase.items.map((item, idx) => (
                                  <tr key={`${purchase.sale_id}-${idx}`}>
                                    {idx === 0 ? (
                                      <td rowSpan={purchase.items.length}>
                                        {new Date(purchase.date).toLocaleDateString()}
                                      </td>
                                    ) : (
                                      <td></td>
                                    )}
                                    <td>{item.product_name}</td>
                                    <td>{item.quantity}</td>
                                    <td>${item.price.toFixed(2)}</td>
                                    {idx === 0 ? (
                                      <>
                                        <td rowSpan={purchase.items.length}>
                                          ${purchase.total.toFixed(2)}
                                        </td>
                                        <td rowSpan={purchase.items.length}>
                                          {PAYMENT_LABELS[purchase.payment_method] || "Efectivo"}
                                        </td>
                                      </>
                                    ) : (
                                      <>
                                        <td></td>
                                        <td></td>
                                      </>
                                    )}
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                          {purchaseTotalPages[i.id] > 1 && (
                            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "10px", marginTop: "10px" }}>
                              <button
                                className="btn"
                                onClick={() => togglePurchases(i.id, (purchasePage[i.id] || 1) - 1)}
                                disabled={purchasePage[i.id] <= 1}
                              >
                                ← Anterior
                              </button>
                              <span>Página {purchasePage[i.id] || 1} de {purchaseTotalPages[i.id]}</span>
                              <button
                                className="btn"
                                onClick={() => togglePurchases(i.id, (purchasePage[i.id] || 1) + 1)}
                                disabled={purchasePage[i.id] >= purchaseTotalPages[i.id]}
                              >
                                Siguiente →
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
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