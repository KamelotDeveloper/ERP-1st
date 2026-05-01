import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import Clients from "./pages/Clients";
import Products from "./pages/Products";
import Materials from "./pages/Materials";
import Sales from "./pages/Sales";
import Invoices from "./pages/Invoices";
import ElectronicInvoicing from "./pages/ElectronicInvoicing";
import Profile from "./pages/Profile";
import Produccion from "./pages/Produccion";
import Budget from "./pages/Budget";
import PlanSelection from "./pages/PlanSelection";
import { verificarSuscripcion } from "./services/suscripcion";

export default function App() {
  const [tieneAcceso, setTieneAcceso] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [clientId, setClientId] = useState(null);

  useEffect(() => {
    const verificarAcceso = async () => {
      try {
        // Generar o recuperar client_id
        let cid = localStorage.getItem("client_id");
        if (!cid) {
          cid = "user_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
          localStorage.setItem("client_id", cid);
        }
        setClientId(cid);

        // Verificar suscripción en el backend local (:8000)
        const resultado = await verificarSuscripcion(cid);
        
        if (resultado.activo) {
          setTieneAcceso(true);
        } else {
          setTieneAcceso(false);
        }
      } catch (error) {
        console.error("Error verificando suscripción:", error);
        // Si hay error de conexión, asumir que no tiene acceso
        setTieneAcceso(false);
      } finally {
        setCargando(false);
      }
    };

    verificarAcceso();
  }, []);

  const handleActivar = (fechaExpiracion) => {
    setTieneAcceso(true);
    // Podés guardar la fecha de expiración si querés
    console.log("Acceso activado hasta:", fechaExpiracion);
  };

  if (cargando) {
    return (
      <div style={{
        minHeight: "100vh",
        backgroundColor: "#1f2937",
        display: "flex",
        alignItems: "center",
        justifyContent: "center"
      }}>
        <p style={{ color: "white", fontSize: "1.5rem" }}>Verificando suscripción...</p>
      </div>
    );
  }

  // Si NO tiene acceso, mostrar PlanSelection
  if (!tieneAcceso) {
    return <PlanSelection onActivar={handleActivar} />;
  }

  // Si SÍ tiene acceso, mostrar la app normal
  return (
    <BrowserRouter>
      <div className="layout">
        <Sidebar />
        <div className="main">
          <Navbar />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/clients" element={<Clients />} />
            <Route path="/products" element={<Products />} />
            <Route path="/materials" element={<Materials />} />
            <Route path="/sales" element={<Sales />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/electronic-invoicing" element={<ElectronicInvoicing />} />
            <Route path="/produccion" element={<Produccion />} />
            <Route path="/budget" element={<Budget />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}