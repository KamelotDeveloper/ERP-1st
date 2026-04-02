import { NavLink } from "react-router-dom";
import { downloadFileFromBackend, ensureDownloadFolder } from "../services/downloadService";

export default function Sidebar() {
  const handleDownload = async (url, filename) => {
    // Ensure download folder exists first
    await ensureDownloadFolder();
    // Then download
    await downloadFileFromBackend(url, filename);
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
        <NavLink to="/budget" className="nav-item">
          📝 Presupuestos
        </NavLink>
        <NavLink to="/produccion" className="nav-item">
          🏭 Producción
        </NavLink>
        <NavLink to="/invoices" className="nav-item invoice-link">
          🧾 Facturación ARCA
        </NavLink>
        <NavLink to="/electronic-invoicing" className="nav-item">
          ⚙️ Config. FE
        </NavLink>
      </nav>

      <div className="exports">
        <p className="export-title">Exportar</p>
        <button onClick={() => handleDownload("/export/clients", "clientes.xlsx")}>
          📥 Clientes Excel
        </button>
        <button onClick={() => handleDownload("/export/products", "productos.xlsx")}>
          📥 Productos Excel
        </button>
        <button onClick={() => handleDownload("/export/materials", "materiales.xlsx")}>
          📥 Materiales Excel
        </button>
      </div>

      <div className="sidebar-footer">
        <p>© 2026 El Menestral</p>
      </div>
    </div>
  );
}