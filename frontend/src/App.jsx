import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import SetupWizard from "./components/SetupWizard";
import ServerInfo from "./components/ServerInfo";
import ClientConfig from "./components/ClientConfig";
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
import Comprobantes from "./pages/Comprobantes";
import PlanSelection from "./pages/PlanSelection";
import { iniciarSesion } from "./services/suscripcion";
import { appDataDir } from "@tauri-apps/api/path";
import { readTextFile, writeTextFile } from "@tauri-apps/plugin-fs";
import { getApi } from "./services/api";

const isTauri = !!window.__TAURI_INTERNALS__;
const invoke = isTauri
  ? (cmd, args) => window.__TAURI_INTERNALS__.invoke(cmd, args)
  : null;

export default function App() {
  const [tieneAcceso, setTieneAcceso] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [clientId, setClientId] = useState(null);

  // LAN mode state
  const [lanMode, setLanMode] = useState(null); // null = checking, "none" = not Tauri, "server" | "client"
  const [apiReady, setApiReady] = useState(false);

  // 1) Resolve API base URL before anything else
  useEffect(() => {
    const init = async () => {
      await getApi();

      // Check LAN mode if in Tauri
      if (isTauri && invoke) {
        try {
          const mode = await invoke("get_mode");
          setLanMode(mode);
        } catch {
          // No mode set yet — show wizard
          setLanMode("none");
        }
      } else {
        setLanMode("none");
      }

      setApiReady(true);
    };
    init();
  }, []);

  // 2) License check — only runs after api is ready
  useEffect(() => {
    if (!apiReady) return;

    const verificarAcceso = async () => {
      try {
        let cid = localStorage.getItem("client_id");

        if (!cid) {
          try {
            const dir = await appDataDir();
            const stored = await readTextFile(dir + "client_id.txt");
            if (stored && stored.trim()) {
              cid = stored.trim();
            }
          } catch (_) {}
        }

        if (!cid) {
          cid =
            "user_" +
            Date.now() +
            "_" +
            Math.random().toString(36).substr(2, 9);
        }

        try {
          const dir = await appDataDir();
          await writeTextFile(dir + "client_id.txt", cid);
        } catch (_) {}
        localStorage.setItem("client_id", cid);
        setClientId(cid);

        const resultado = await iniciarSesion(cid);

        if (resultado.ok) {
          setTieneAcceso(true);
          if (resultado.tipo === "licencia") {
            console.log(
              "Licencia activa:",
              resultado.plan,
              "- días restantes:",
              resultado.dias_restantes
            );
          } else if (resultado.tipo === "trial") {
            console.log(
              "Trial activo - días restantes:",
              resultado.dias_restantes
            );
          }
        } else {
          setTieneAcceso(false);
          console.log("Sin acceso:", resultado.error || "No especificado");
        }
      } catch (error) {
        console.error("Error verificando licencia:", error);
        setTieneAcceso(false);
      } finally {
        setCargando(false);
      }
    };

    verificarAcceso();
  }, [apiReady]);

  const handleActivar = (fechaExpiracion) => {
    setTieneAcceso(true);
    console.log("Acceso activado hasta:", fechaExpiracion);
  };

  // Loading state — shows during API init + license check
  if (!apiReady || cargando) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#1f2937",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <p style={{ color: "white", fontSize: "1.5rem" }}>
          {apiReady ? "Verificando licencia..." : "Conectando..."}
        </p>
      </div>
    );
  }

  // Setup wizard — first run (no mode configured in Tauri store)
  if (isTauri && lanMode === "none") {
    return <SetupWizard onComplete={() => setLanMode("server")} />;
  }

  // License check — no access
  if (!tieneAcceso) {
    return <PlanSelection onActivar={handleActivar} clientId={clientId} />;
  }

  // Main app
  return (
    <BrowserRouter>
      {/* Server banner — only in server mode */}
      {lanMode === "server" && <ServerInfo />}
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
            <Route
              path="/electronic-invoicing"
              element={<ElectronicInvoicing />}
            />
            <Route path="/produccion" element={<Produccion />} />
            <Route path="/budget" element={<Budget />} />
            <Route path="/comprobantes" element={<Comprobantes />} />
            <Route path="/settings" element={<ClientConfig />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
