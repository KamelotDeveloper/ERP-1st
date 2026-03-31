import { NavLink } from "react-router-dom";

export default function Sidebar() {
  const download = (url) => {
    window.open("http://127.0.0.1:8000" + url);
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <img src="/em.jpg" alt="El Menestral" />
        </div>
        <h2>El Menestral</h2>
      </div>

      <nav>
        <NavLink to="/" className="nav-item">
          📊 Dashboard
        </NavLink>
        <NavLink to="/clients" className="nav-item">
          👥 Clientes
        </NavLink>
        <NavLink to="/products" className="nav-item">
          📦 Productos
        </NavLink>
        <NavLink to="/materials" className="nav-item">
          🪵 Materiales
        </NavLink>
        <NavLink to="/sales" className="nav-item">
          💰 Ventas
        </NavLink>
        <NavLink to="/invoices" className="nav-item invoice-link">
          🧾 Facturación ARCA
        </NavLink>
        <NavLink to="/electronic-invoicing" className="nav-item">
          ⚙️ Config. FE
        </NavLink>
        <NavLink to="/profile" className="nav-item">
          🔐 Cambiar Contraseña
        </NavLink>
      </nav>

      <div className="exports">
        <p className="export-title">Exportar</p>
        <button onClick={() => download("/export/clients")}>
          📥 Clientes Excel
        </button>
        <button onClick={() => download("/export/products")}>
          📥 Productos Excel
        </button>
        <button onClick={() => download("/export/materials")}>
          📥 Materiales Excel
        </button>
      </div>

      <div className="sidebar-footer">
        <p>© 2026 El Menestral</p>
      </div>
    </div>
  );
}