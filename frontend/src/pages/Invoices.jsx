import { useEffect, useState } from "react";
import api from "../services/api";

export default function Invoices() {

  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState({
    client_id: "",
    tipo_factura: 6,
    items: []
  });
  const [loading, setLoading] = useState(false);

  const load = async () => {
    const [invRes, clientsRes, productsRes] = await Promise.all([
      api.get("/invoices"),
      api.get("/clients"),
      api.get("/products")
    ]);
    setInvoices(invRes.data);
    setClients(clientsRes.data);
    setProducts(productsRes.data);
  };

  const addItem = () => {
    setForm({
      ...form,
      items: [...form.items, { product_id: "", quantity: 1, unit_price: 0 }]
    });
  };

  const updateItem = (index, field, value) => {
    const newItems = [...form.items];
    newItems[index][field] = value;
    
    if (field === "product_id") {
      const product = products.find(p => p.id === parseInt(value));
      if (product) {
        newItems[index].unit_price = product.price;
      }
    }
    
    setForm({ ...form, items: newItems });
  };

  const removeItem = (index) => {
    const newItems = form.items.filter((_, i) => i !== index);
    setForm({ ...form, items: newItems });
  };

  const calculateTotal = () => {
    return form.items.reduce((sum, item) => {
      return sum + (item.quantity * item.unit_price);
    }, 0);
  };

  const calculateIVA = () => {
    return calculateTotal() * 0.21;
  };

  const calculateTotalFinal = () => {
    return calculateTotal() + calculateIVA();
  };

  const createInvoice = async () => {
    if (!form.client_id || form.items.length === 0) {
      alert("Completá cliente y al menos un producto");
      return;
    }

    setLoading(true);
    try {
      await api.post("/invoices", {
        client_id: parseInt(form.client_id),
        tipo_factura: parseInt(form.tipo_factura),
        items: form.items.map(item => ({
          product_id: parseInt(item.product_id),
          quantity: parseInt(item.quantity),
          unit_price: parseFloat(item.unit_price)
        }))
      });

      setForm({
        client_id: "",
        tipo_factura: 6,
        items: []
      });
      load();
      alert("Factura creada correctamente");
    } catch (error) {
      alert("Error al crear factura: " + (error.response?.data?.detail || error.message));
    }
    setLoading(false);
  };

  const getTipoFacturaLabel = (tipo) => {
    const labels = { 1: "A", 6: "B", 11: "C" };
    return labels[tipo] || tipo;
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="container">
      <h2>Facturación ARCA (AFIP)</h2>

      <div className="invoice-form">
        <div className="form-row">
          <select
            value={form.client_id}
            onChange={e => setForm({ ...form, client_id: e.target.value })}
          >
            <option value="">Seleccionar cliente</option>
            {clients.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          <select
            value={form.tipo_factura}
            onChange={e => setForm({ ...form, tipo_factura: parseInt(e.target.value) })}
          >
            <option value={1}>Factura A</option>
            <option value={6}>Factura B</option>
            <option value={11}>Factura C</option>
          </select>
        </div>

        <h3>Items de la Factura</h3>
        
        {form.items.map((item, index) => (
          <div key={index} className="form-row">
            <select
              value={item.product_id}
              onChange={e => updateItem(index, "product_id", e.target.value)}
            >
              <option value="">Producto</option>
              {products.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>

            <input
              type="number"
              placeholder="Cantidad"
              value={item.quantity}
              onChange={e => updateItem(index, "quantity", e.target.value)}
              min="1"
            />

            <input
              type="number"
              placeholder="Precio unit."
              value={item.unit_price}
              onChange={e => updateItem(index, "unit_price", e.target.value)}
              step="0.01"
            />

            <span style={{ padding: "8px", fontWeight: "bold" }}>
              ${(item.quantity * item.unit_price).toFixed(2)}
            </span>

            <button className="btn btn-delete" onClick={() => removeItem(index)}>
              X
            </button>
          </div>
        ))}

        <button onClick={addItem} style={{ marginBottom: "20px" }}>
          + Agregar Item
        </button>

        <div className="invoice-totals">
          <p>Subtotal: ${calculateTotal().toFixed(2)}</p>
          <p>IVA (21%): ${calculateIVA().toFixed(2)}</p>
          <p className="total">Total: ${calculateTotalFinal().toFixed(2)}</p>
        </div>

        <button 
          className="btn btn-save" 
          onClick={createInvoice}
          disabled={loading}
        >
          {loading ? "Generando..." : "Emitir Factura"}
        </button>
      </div>

      <h3>Facturas Emitidas</h3>

      <table className="table">
        <thead>
          <tr>
            <th>Número</th>
            <th>Cliente</th>
            <th>Tipo</th>
            <th>Total</th>
            <th>CAE</th>
            <th>Vto CAE</th>
            <th>Estado</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map(inv => (
            <tr key={inv.id}>
              <td>{inv.numero}</td>
              <td>{inv.cliente}</td>
              <td>Factura {getTipoFacturaLabel(inv.tipo_factura)}</td>
              <td>${inv.total?.toFixed(2)}</td>
              <td>{inv.cae || "-"}</td>
              <td>{inv.cae_vto ? new Date(inv.cae_vto).toLocaleDateString() : "-"}</td>
              <td>
                <span className={`status status-${inv.estado}`}>
                  {inv.estado === "issued" ? "Emitida" : inv.estado}
                </span>
              </td>
              <td>{new Date(inv.fecha).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <style>{`
        .invoice-form {
          background: white;
          padding: 20px;
          border-radius: 8px;
          margin-bottom: 30px;
        }
        
        .invoice-totals {
          background: #f8f9fa;
          padding: 15px;
          border-radius: 6px;
          margin: 20px 0;
        }
        
        .invoice-totals p {
          margin: 5px 0;
        }
        
        .invoice-totals .total {
          font-size: 18px;
          font-weight: bold;
          color: #22c55e;
        }
        
        .status {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
        }
        
        .status-issued {
          background: #dcfce7;
          color: #166534;
        }
        
        .status-draft {
          background: #fef3c7;
          color: #92400e;
        }
        
        .status-error {
          background: #fee2e2;
          color: #991b1b;
        }
      `}</style>
    </div>
  );
}
