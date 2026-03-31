import { useEffect, useState } from "react";
import api from "../services/api";

export default function Clients() {
  const [data, setData] = useState([]);
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    tax_id: "",
  });
  const [editId, setEditId] = useState(null);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const r = await api.get("/clients");
      setData(r.data || []);
    } catch (err) {
      console.error("Error loading clients:", err);
      setError("Error al cargar clientes");
    }
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
      load();
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
    if (!confirm("¿Eliminar cliente?")) return;
    try {
      await api.delete("/clients/" + id);
      load();
    } catch (err) {
      alert("Error al eliminar");
    }
  };

  useEffect(() => {
    load();
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
          </tr>
        </thead>

        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan="7" style={{ textAlign: "center", padding: "20px" }}>
                No hay clientes. Agrega uno arriba.
              </td>
            </tr>
          ) : (
            data.map((i) => (
              <tr key={i.id}>
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
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}