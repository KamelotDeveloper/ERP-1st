import { useState } from "react";

const isTauri = !!window.__TAURI_INTERNALS__;
const invoke = isTauri
  ? (cmd, args) => window.__TAURI_INTERNALS__.invoke(cmd, args)
  : null;

export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState("start"); // start | server | client-ip | client-testing | client-success | client-error
  const [ip, setIp] = useState("");
  const [serverLanIp, setServerLanIp] = useState("");
  const [error, setError] = useState("");

  const handleServidor = async () => {
    try {
      await invoke("set_mode", { mode: "server" });
      const lanIp = await invoke("get_lan_ip");
      setServerLanIp(lanIp);
      setStep("server");
    } catch (err) {
      setError("Error al configurar modo servidor: " + err);
    }
  };

  const handleCliente = () => {
    setStep("client-ip");
  };

  const handleTestConnection = async () => {
    if (!ip.trim()) {
      setError("Ingresá una IP válida");
      return;
    }
    setStep("client-testing");
    setError("");

    try {
      const result = await invoke("test_connection", { ip: ip.trim() });
      if (result.success) {
        await invoke("set_client_ip", { ip: ip.trim() });
        setStep("client-success");
      } else {
        setError(
          "No se pudo conectar al servidor. Verificá la IP."
        );
        setStep("client-ip");
      }
    } catch (err) {
      setError("No se pudo conectar al servidor. Verificá la IP.");
      setStep("client-ip");
    }
  };

  const handleFinish = () => {
    if (onComplete) onComplete();
    // Reload to re-init api with the new URL
    window.location.reload();
  };

  return (
    <div className="setup-wizard">
      <div className="setup-wizard-card">
        {/* Logo */}
        <div className="setup-wizard-logo">
          <img src="/GA logo.png" alt="Ordo ERP" />
        </div>

        <h1>Ordo ERP</h1>

        {/* Step: Start */}
        {step === "start" && (
          <>
            <p className="setup-wizard-subtitle">
              Bienvenido. Elegí cómo funciona esta PC en la red.
            </p>
            <div className="setup-wizard-options">
              <button
                className="setup-wizard-option"
                onClick={handleServidor}
              >
                <span className="setup-wizard-option-icon">🖥️</span>
                <span className="setup-wizard-option-title">Servidor</span>
                <span className="setup-wizard-option-desc">
                  Esta PC comparte los datos con otras en la red
                </span>
              </button>
              <button
                className="setup-wizard-option"
                onClick={handleCliente}
              >
                <span className="setup-wizard-option-icon">💻</span>
                <span className="setup-wizard-option-title">Cliente</span>
                <span className="setup-wizard-option-desc">
                  Esta PC se conecta a otro servidor en la red
                </span>
              </button>
            </div>
          </>
        )}

        {/* Step: Server — show LAN IP */}
        {step === "server" && (
          <>
            <p className="setup-wizard-subtitle">
              Modo Servidor activado. Compartí esta dirección con las otras PCs:
            </p>
            <div className="setup-wizard-ip-display">
              <code>http://{serverLanIp}:8000</code>
            </div>
            <button
              className="setup-wizard-primary-btn"
              onClick={handleFinish}
            >
              Ir al Dashboard
            </button>
          </>
        )}

        {/* Step: Client — enter IP */}
        {step === "client-ip" && (
          <>
            <p className="setup-wizard-subtitle">
              Ingresá la IP del servidor al que querés conectarte:
            </p>
            <div className="setup-wizard-input-group">
              <input
                type="text"
                placeholder="Ej: 192.168.1.42"
                value={ip}
                onChange={(e) => setIp(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleTestConnection()}
              />
              <button
                className="setup-wizard-primary-btn"
                onClick={handleTestConnection}
              >
                Probar conexión
              </button>
            </div>
            {error && (
              <p className="setup-wizard-error">{error}</p>
            )}
          </>
        )}

        {/* Step: Client — testing */}
        {step === "client-testing" && (
          <div className="setup-wizard-loading">
            <div className="setup-wizard-spinner"></div>
            <p>Probando conexión...</p>
          </div>
        )}

        {/* Step: Client — success */}
        {step === "client-success" && (
          <>
            <p className="setup-wizard-success">
              ✓ Conexión exitosa con el servidor
            </p>
            <button
              className="setup-wizard-primary-btn"
              onClick={handleFinish}
            >
              Ir al Dashboard
            </button>
          </>
        )}

        {error && step === "start" && (
          <p className="setup-wizard-error">{error}</p>
        )}
      </div>

      <style>{`
        .setup-wizard {
          position: fixed;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
          z-index: 9999;
        }
        .setup-wizard-card {
          background: white;
          border-radius: 16px;
          padding: 48px 40px;
          max-width: 520px;
          width: 90%;
          text-align: center;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }
        .setup-wizard-logo {
          width: 80px;
          height: 80px;
          margin: 0 auto 20px;
          background: linear-gradient(135deg, #0ea5e9, #0f172a);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
        }
        .setup-wizard-logo img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
        .setup-wizard-card h1 {
          margin: 0 0 8px;
          font-size: 28px;
          color: #0f172a;
          border: none;
          padding-bottom: 0;
        }
        .setup-wizard-subtitle {
          color: #64748b;
          font-size: 15px;
          margin-bottom: 28px;
        }
        .setup-wizard-options {
          display: flex;
          gap: 16px;
          justify-content: center;
        }
        .setup-wizard-option {
          flex: 1;
          padding: 24px 16px;
          border: 2px solid #e2e8f0;
          border-radius: 12px;
          background: white;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          text-align: center;
        }
        .setup-wizard-option:hover {
          border-color: #0ea5e9;
          background: #f0f9ff;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(14, 165, 233, 0.15);
        }
        .setup-wizard-option-icon {
          font-size: 32px;
        }
        .setup-wizard-option-title {
          font-size: 16px;
          font-weight: 600;
          color: #0f172a;
        }
        .setup-wizard-option-desc {
          font-size: 13px;
          color: #64748b;
          line-height: 1.4;
        }
        .setup-wizard-ip-display {
          background: #f1f5f9;
          border: 2px dashed #0ea5e9;
          border-radius: 10px;
          padding: 16px;
          margin: 20px 0;
        }
        .setup-wizard-ip-display code {
          font-size: 18px;
          font-weight: 600;
          color: #0f172a;
          word-break: break-all;
        }
        .setup-wizard-input-group {
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin: 20px 0;
        }
        .setup-wizard-input-group input {
          padding: 12px 16px;
          border: 2px solid #e2e8f0;
          border-radius: 8px;
          font-size: 16px;
          text-align: center;
          transition: border-color 0.2s;
        }
        .setup-wizard-input-group input:focus {
          outline: none;
          border-color: #0ea5e9;
        }
        .setup-wizard-primary-btn {
          background: linear-gradient(135deg, #0ea5e9, #0284c7);
          color: white;
          border: none;
          padding: 12px 32px;
          border-radius: 8px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          margin-top: 8px;
        }
        .setup-wizard-primary-btn:hover {
          background: linear-gradient(135deg, #0284c7, #0369a1);
          transform: translateY(-1px);
        }
        .setup-wizard-error {
          color: #ef4444;
          font-size: 14px;
          margin-top: 12px;
        }
        .setup-wizard-success {
          color: #22c55e;
          font-size: 16px;
          font-weight: 600;
          margin: 20px 0;
        }
        .setup-wizard-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          padding: 40px 0;
        }
        .setup-wizard-spinner {
          width: 36px;
          height: 36px;
          border: 3px solid #e2e8f0;
          border-top-color: #0ea5e9;
          border-radius: 50%;
          animation: setup-spin 0.8s linear infinite;
        }
        @keyframes setup-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
