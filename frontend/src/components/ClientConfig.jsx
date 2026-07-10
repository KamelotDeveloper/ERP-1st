import { useState, useEffect } from "react";

const isTauri = !!window.__TAURI_INTERNALS__;
const invoke = isTauri
  ? (cmd, args) => window.__TAURI_INTERNALS__.invoke(cmd, args)
  : null;

export default function ClientConfig() {
  const [ip, setIp] = useState("");
  const [originalIp, setOriginalIp] = useState("");
  const [mode, setMode] = useState("server");
  const [testStatus, setTestStatus] = useState(""); // "" | "loading" | "success" | "error"
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!isTauri || !invoke) return;

    Promise.all([
      invoke("get_server_ip"),
      invoke("get_mode"),
    ])
      .then(([serverIp, currentMode]) => {
        setIp(serverIp);
        setOriginalIp(serverIp);
        setMode(currentMode);
      })
      .catch(() => {});
  }, []);

  const handleTestConnection = async () => {
    if (!ip.trim()) {
      setErrorMsg("Ingresá una IP válida");
      setTestStatus("error");
      return;
    }

    setTestStatus("loading");
    setErrorMsg("");

    try {
      const result = await invoke("test_connection", { ip: ip.trim() });
      if (result.success) {
        setTestStatus("success");
        setErrorMsg("");
      } else {
        setTestStatus("error");
        setErrorMsg("No se pudo conectar al servidor. Verificá la IP.");
      }
    } catch {
      setTestStatus("error");
      setErrorMsg("No se pudo conectar al servidor. Verificá la IP.");
    }
  };

  const handleSave = async () => {
    try {
      await invoke("set_client_ip", { ip: ip.trim() });
      setOriginalIp(ip.trim());
      alert("Configuración guardada. Reiniciá la aplicación para aplicar los cambios.");
    } catch (err) {
      setErrorMsg("Error al guardar: " + err);
    }
  };

  const handleSwitchMode = async (newMode) => {
    if (!confirm(`¿Cambiar a modo ${newMode === "server" ? "Servidor" : "Cliente"}? La aplicación se reiniciará.`)) {
      return;
    }
    try {
      await invoke("set_mode", { mode: newMode });
      window.location.reload();
    } catch (err) {
      setErrorMsg("Error al cambiar modo: " + err);
    }
  };

  const hasChanges = ip.trim() !== originalIp;
  const canSave = hasChanges && testStatus === "success";

  return (
    <div className="client-config">
      <h2>⚙️ Configuración de Red</h2>

      {/* Current mode */}
      <div className="cc-card">
        <h3>Modo actual</h3>
        <div className="cc-mode-badge">
          {mode === "server" ? "🖥️ Servidor" : "💻 Cliente"}
        </div>
        <div className="cc-mode-actions">
          {mode === "server" ? (
            <button
              className="cc-switch-btn"
              onClick={() => handleSwitchMode("client")}
            >
              Cambiar a Cliente
            </button>
          ) : (
            <button
              className="cc-switch-btn"
              onClick={() => handleSwitchMode("server")}
            >
              Cambiar a Servidor
            </button>
          )}
        </div>
      </div>

      {/* Server IP config (client mode) */}
      {mode === "client" && (
        <div className="cc-card">
          <h3>IP del Servidor</h3>
          <p className="cc-description">
            Dirección del PC servidor al que esta PC se conecta.
          </p>
          <div className="cc-input-row">
            <input
              type="text"
              value={ip}
              onChange={(e) => {
                setIp(e.target.value);
                setTestStatus("");
              }}
              placeholder="Ej: 192.168.1.42"
            />
            <button
              className={`cc-test-btn ${testStatus}`}
              onClick={handleTestConnection}
              disabled={testStatus === "loading"}
            >
              {testStatus === "loading"
                ? "Probando..."
                : testStatus === "success"
                ? "✓ OK"
                : "Probar conexión"}
            </button>
          </div>

          {testStatus === "success" && (
            <p className="cc-success-msg">Conexión exitosa con el servidor</p>
          )}
          {testStatus === "error" && (
            <p className="cc-error-msg">{errorMsg}</p>
          )}

          {hasChanges && (
            <button
              className="cc-save-btn"
              onClick={handleSave}
              disabled={!canSave}
            >
              Guardar
            </button>
          )}
        </div>
      )}

      {mode === "server" && (
        <div className="cc-card">
          <h3>Información</h3>
          <p className="cc-description">
            Esta PC funciona como servidor. Los datos se comparten con los
            clientes en la red local.
          </p>
        </div>
      )}

      <style>{`
        .client-config {
          padding: 30px;
          max-width: 640px;
        }
        .client-config h2 {
          margin-bottom: 24px;
        }
        .cc-card {
          background: white;
          border-radius: 12px;
          padding: 24px;
          margin-bottom: 20px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
        }
        .cc-card h3 {
          margin: 0 0 12px;
          font-size: 16px;
          color: #0f172a;
        }
        .cc-description {
          color: #64748b;
          font-size: 14px;
          margin: 0 0 16px;
        }
        .cc-mode-badge {
          display: inline-block;
          background: linear-gradient(135deg, #0f172a, #1e293b);
          color: #0ea5e9;
          padding: 8px 20px;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 600;
        }
        .cc-mode-actions {
          margin-top: 16px;
        }
        .cc-switch-btn {
          background: linear-gradient(135deg, #f59e0b, #d97706);
          color: white;
          border: none;
          padding: 10px 20px;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }
        .cc-switch-btn:hover {
          transform: translateY(-1px);
        }
        .cc-input-row {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        .cc-input-row input {
          flex: 1;
          padding: 10px 14px;
          border: 2px solid #e2e8f0;
          border-radius: 8px;
          font-size: 15px;
        }
        .cc-input-row input:focus {
          outline: none;
          border-color: #0ea5e9;
        }
        .cc-test-btn {
          padding: 10px 20px;
          border: 2px solid #0ea5e9;
          background: white;
          color: #0ea5e9;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          white-space: nowrap;
        }
        .cc-test-btn:hover {
          background: #f0f9ff;
        }
        .cc-test-btn.success {
          border-color: #22c55e;
          color: #22c55e;
        }
        .cc-test-btn.error {
          border-color: #ef4444;
          color: #ef4444;
        }
        .cc-test-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .cc-success-msg {
          color: #22c55e;
          font-size: 14px;
          font-weight: 600;
          margin: 12px 0 0;
        }
        .cc-error-msg {
          color: #ef4444;
          font-size: 14px;
          margin: 12px 0 0;
        }
        .cc-save-btn {
          margin-top: 16px;
          background: linear-gradient(135deg, #22c55e, #16a34a);
          color: white;
          border: none;
          padding: 10px 24px;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }
        .cc-save-btn:hover {
          transform: translateY(-1px);
        }
        .cc-save-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
          transform: none;
        }
      `}</style>
    </div>
  );
}
