import { useState, useEffect } from "react";
import api from "../services/api";

export default function ElectronicInvoicing() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    razon_social: "",
    CUIT: "",
    punto_venta: 1,
    ambiente: "testing"
  });
  const [files, setFiles] = useState({ certificado: null, clave_privada: null });
  const [message, setMessage] = useState(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const res = await api.get("/electronic-invoicing/status");
      setStatus(res.data);
      if (res.data.estado_habilitacion === "habilitado") {
        setStep(4);
      } else if (res.data.credenciales?.tiene_certificado) {
        setStep(3);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleFileChange = (e) => {
    setFiles({ ...files, [e.target.name]: e.target.files[0] });
  };

  const submitStep1 = async () => {
    if (!formData.razon_social || !formData.CUIT) {
      alert("Completá razón social y CUIT");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/electronic-invoicing/setup", formData);
      setMessage(res.data);
      setStep(2);
      loadStatus();
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || JSON.stringify(err);
      alert("Error: " + errorMsg);
    }
    setLoading(false);
  };

  const submitStep2 = async () => {
    if (!files.certificado || !files.clave_privada) {
      alert("Subí ambos archivos");
      return;
    }
    setLoading(true);
    try {
      const form = new FormData();
      form.append("certificado", files.certificado);
      form.append("clave_privada", files.clave_privada);
      
      const res = await api.post("/electronic-invoicing/upload-certificate", form, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setMessage(res.data);
      if (res.data.success) {
        setStep(3);
      }
      loadStatus();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al subir certificado");
    }
    setLoading(false);
  };

  const deleteCertificate = async () => {
    if (!confirm("¿Estás seguro de eliminar los certificados? Perderás la configuración de facturación electrónica.")) {
      return;
    }
    setLoading(true);
    try {
      const res = await api.delete("/electronic-invoicing/certificate");
      setMessage(res.data);
      if (res.data.success) {
        setStep(2);
        setFiles({ certificado: null, clave_privada: null });
      }
      loadStatus();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar certificados");
    }
    setLoading(false);
  };

  const testConnection = async () => {
    setLoading(true);
    try {
      const res = await api.post("/electronic-invoicing/test-connection");
      setMessage(res.data);
      if (res.data.success) {
        setStep(4);
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Error de conexión");
    }
    setLoading(false);
  };

  const toggleEnabled = async () => {
    setLoading(true);
    try {
      if (status?.habilitado) {
        await api.post("/electronic-invoicing/disable");
      } else {
        await api.post("/electronic-invoicing/enable");
      }
      loadStatus();
    } catch (err) {
      alert(err.response?.data?.detail || "Error");
    }
    setLoading(false);
  };

  const getStatusColor = (estado) => {
    const colors = {
      "no_iniciado": "#6b7280",
      "en_proceso": "#f59e0b",
      "habilitado": "#10b981",
      "error": "#ef4444"
    };
    return colors[estado] || "#6b7280";
  };

  return (
    <div className="container">
      <h2>Habilitación Facturación Electrónica ARCA</h2>
      
      {status && (
        <div className="status-card" style={{ 
          background: "#f8f9fa", 
          padding: "15px", 
          borderRadius: "8px",
          marginBottom: "20px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong>Estado:</strong> 
              <span style={{ 
                color: getStatusColor(status.estado_habilitacion),
                marginLeft: "8px",
                fontWeight: "bold"
              }}>
                {status.estado_habilitacion?.toUpperCase()}
              </span>
            </div>
            <div>
              <strong>Ambiente:</strong> {status.ambiente}
            </div>
            <div>
              <strong>Habilitado:</strong> 
              <span style={{ 
                color: status.habilitado ? "#10b981" : "#ef4444",
                marginLeft: "8px"
              }}>
                {status.habilitado ? "SÍ" : "NO"}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="wizard">
        <div className="step" style={{ opacity: step >= 1 ? 1 : 0.5 }}>
          <div className="step-num">1</div>
          <div className="step-content">
            <h4>Datos del Contribuyente</h4>
            <p>Razón social, CUIT y punto de venta</p>
          </div>
        </div>
        
        <div className="step" style={{ opacity: step >= 2 ? 1 : 0.5 }}>
          <div className="step-num">2</div>
          <div className="step-content">
            <h4>Certificado Digital</h4>
            <p>Subir certificado y clave de ARCA</p>
          </div>
        </div>
        
        <div className="step" style={{ opacity: step >= 3 ? 1 : 0.5 }}>
          <div className="step-num">3</div>
          <div className="step-content">
            <h4>Verificar Conexión</h4>
            <p>Probar conexión con ARCA</p>
          </div>
        </div>
        
        <div className="step" style={{ opacity: step >= 4 ? 1 : 0.5 }}>
          <div className="step-num">4</div>
          <div className="step-content">
            <h4>Habilitar</h4>
            <p>Activar facturación electrónica</p>
          </div>
        </div>
      </div>

      <div className="setup-form">
        {step === 1 && (
          <div className="step-form">
            <h3>Paso 1: Datos del Contribuyente</h3>
            
            <div className="form-group">
              <label>Razón Social</label>
              <input 
                type="text" 
                name="razon_social" 
                value={formData.razon_social}
                onChange={handleInputChange}
                placeholder="Nombre de la empresa"
              />
            </div>
            
            <div className="form-group">
              <label>CUIT (sin guiones)</label>
              <input 
                type="text" 
                name="CUIT" 
                value={formData.CUIT}
                onChange={handleInputChange}
                placeholder="20345678901"
                maxLength={11}
              />
            </div>
            
            <div className="form-group">
              <label>Punto de Venta</label>
              <select 
                name="punto_venta" 
                value={formData.punto_venta}
                onChange={handleInputChange}
              >
                {[1,2,3,4,5].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            
            <div className="form-group">
              <label>Ambiente</label>
              <select 
                name="ambiente" 
                value={formData.ambiente}
                onChange={handleInputChange}
              >
                <option value="testing">Testing (Pruebas)</option>
                <option value="production">Producción</option>
              </select>
            </div>
            
            <button 
              className="btn btn-primary" 
              onClick={submitStep1}
              disabled={loading}
            >
              {loading ? "Guardando..." : "Continuar"}
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="step-form">
            <h3>Paso 2: Certificado Digital</h3>
            <p style={{ color: "#6b7280", marginBottom: "15px" }}>
              Sube el certificado .pem y la clave privada que obtuviste de ARCA/AFIP
            </p>
            
            <button 
              className="btn" 
              onClick={() => setStep(1)}
              style={{ marginRight: "10px" }}
            >
              ← Volver
            </button>
            
            <div className="form-group">
              <label>Certificado (archivo .pem)</label>
              <input 
                type="file" 
                name="certificado"
                accept=".pem,.crt,.cer"
                onChange={handleFileChange}
              />
            </div>
            
            <div className="form-group">
              <label>Clave Privada (archivo .key)</label>
              <input 
                type="file" 
                name="clave_privada"
                accept=".key,.pem"
                onChange={handleFileChange}
              />
            </div>
            
            <button 
              className="btn btn-primary" 
              onClick={submitStep2}
              disabled={loading}
            >
              {loading ? "Validando..." : "Subir y Validar"}
            </button>
            
            <button 
              className="btn btn-delete" 
              onClick={deleteCertificate}
              disabled={loading}
              style={{ marginLeft: "10px" }}
            >
              Eliminar Certificados
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="step-form">
            <h3>Paso 3: Verificar Conexión</h3>
            <p style={{ color: "#6b7280", marginBottom: "15px" }}>
              Se probará la conexión con los servidores de ARCA
            </p>
            
            <button 
              className="btn" 
              onClick={() => setStep(2)}
              style={{ marginRight: "10px" }}
            >
              ← Volver
            </button>
            
            {status?.credenciales && (
              <div className="cred-check" style={{ 
                background: "#f3f4f6", 
                padding: "15px", 
                borderRadius: "6px",
                marginBottom: "15px"
              }}>
                <div>✓ Certificado: {status.credenciales.tiene_certificado ? "OK" : "Falta"}</div>
                <div>✓ Clave: {status.credenciales.tiene_key ? "OK" : "Falta"}</div>
                <div>✓ CUIT: {status.credenciales.tiene_cuit ? "OK" : "Falta"}</div>
              </div>
            )}
            
            <button 
              className="btn btn-primary" 
              onClick={testConnection}
              disabled={loading}
            >
              {loading ? "Probando..." : "Probar Conexión"}
            </button>
          </div>
        )}

        {step === 4 && (
          <div className="step-form">
            <h3>Paso 4: Habilitar Sistema</h3>
            
            <div style={{ 
              background: status?.habilitado ? "#d1fae5" : "#fef3c7",
              padding: "20px", 
              borderRadius: "8px",
              textAlign: "center",
              marginBottom: "20px"
            }}>
              {status?.habilitado ? (
                <>
                  <h4 style={{ color: "#065f46" }}>✓ Facturación Electrónica Habilitada</h4>
                  <p style={{ color: "#047857" }}>
                    Ya podés emitir facturas con CAE desde Facturación ARCA
                  </p>
                </>
              ) : (
                <>
                  <h4 style={{ color: "#92400e" }}>Sistema Listo para Habilitar</h4>
                  <p style={{ color: "#b45309" }}>
                    Todos los pasos completados. ¿Desea activar la facturación electrónica?
                  </p>
                </>
              )}
            </div>
            
            <button 
              className={`btn ${status?.habilitado ? "btn-delete" : "btn-primary"}`}
              onClick={toggleEnabled}
              disabled={loading}
            >
              {loading ? "Procesando..." : status?.habilitado ? "Deshabilitar" : "Habilitar Ahora"}
            </button>
          </div>
        )}
      </div>

      {message && (
        <div className="message" style={{ 
          marginTop: "20px",
          padding: "15px",
          background: message.success ? "#d1fae5" : "#fee2e2",
          borderRadius: "6px"
        }}>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
            {JSON.stringify(message, null, 2)}
          </pre>
        </div>
      )}

      <style>{`
        .wizard {
          display: flex;
          gap: 20px;
          margin-bottom: 30px;
        }
        .step {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 15px;
          background: #f3f4f6;
          border-radius: 8px;
        }
        .step-num {
          width: 32px;
          height: 32px;
          background: #3b82f6;
          color: white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
        }
        .step-content h4 {
          margin: 0 0 4px 0;
          font-size: 14px;
        }
        .step-content p {
          margin: 0;
          font-size: 12px;
          color: #6b7280;
        }
        .setup-form {
          background: white;
          padding: 25px;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
        }
        .form-group {
          margin-bottom: 15px;
        }
        .form-group label {
          display: block;
          margin-bottom: 5px;
          font-weight: 500;
          color: #374151;
        }
        .form-group input, 
        .form-group select {
          width: 100%;
          padding: 10px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
        }
        .btn {
          padding: 10px 20px;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 500;
        }
        .btn-primary {
          background: #3b82f6;
          color: white;
        }
        .btn-danger {
          background: #ef4444;
          color: white;
        }
        .btn-delete {
          background: #ef4444;
          color: white;
        }
        .btn:hover {
          opacity: 0.9;
        }
        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}