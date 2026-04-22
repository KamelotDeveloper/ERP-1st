import { useState, useEffect } from "react";
import api from "../services/api";
import { verificarSuscripcion, iniciarPruebaGratis, validarCodigo } from "../services/suscripcion";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
  // Estados de suscripción
  const [suscrito, setSuscrito] = useState(null);
  const [codigoDescuento, setCodigoDescuento] = useState("");
  const [aplicandoCodigo, setAplicandoCodigo] = useState(false);
  const [mostrarSuscripcion, setMostrarSuscripcion] = useState(false);

  // Al cargar, verificar suscripción
  useEffect(() => {
    verificarSuscripcion().then(data => {
      setSuscrito(data);
      if (!data.activo) {
        setMostrarSuscripcion(true);
      }
    });
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append("username", username);
      formData.append("password", password);

      const res = await api.post("/auth/login", formData, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      onLogin(res.data.access_token);
    } catch (err) {
      setError(err.response?.data?.detail || "Error al iniciar sesión");
    }
    setLoading(false);
  };

  const handleIniciarPrueba = async () => {
    if (!username) {
      setError("Ingresá un usuario primero");
      return;
    }
    
    setLoading(true);
    const result = await iniciarPruebaGratis(username + "@demo.com");
    
    if (result.ok) {
      setSuscrito({ activo: true, estado: "prueba", mensaje: result.mensaje });
      setMostrarSuscripcion(false);
    } else {
      setError(result.error || "Error al iniciar prueba");
    }
    setLoading(false);
  };

  const handleAplicarCodigo = async () => {
    if (!codigoDescuento) return;
    
    setAplicandoCodigo(true);
    const result = await validarCodigo(codigoDescuento);
    
    if (result.valido) {
      alert(`¡Código aplicado! ${result.descuento}% de descuento`);
    } else {
      setError(result.error || "Código inválido");
    }
    setAplicandoCodigo(false);
  };

  const planes = [
    { id: "1_mes", nombre: "Mensual", precio: 35000 },
    { id: "6_meses", nombre: "Semestral", precio: 180000, precioMensual: 30000 },
    { id: "1_anio", nombre: "Anual", precio: 300000, precioMensual: 25000 }
  ];

  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      minHeight: "100vh",
      backgroundColor: "#f3f4f6"
    }}>
      <div style={{
        backgroundColor: "white",
        padding: "2rem",
        borderRadius: "8px",
        boxShadow: "0 4px 6px rgba(0,0,0,0.1)",
        width: "100%",
        maxWidth: "400px"
      }}>
        <h1 style={{
          textAlign: "center",
          marginBottom: "1.5rem",
          color: "#1f2937",
          fontSize: "1.5rem"
        }}>
          El Menestral ERP
        </h1>

        {/* Si no está suscrito, mostrar pantalla de suscripción */}
        {mostrarSuscripcion && !suscrito?.activo ? (
          <div>
            <div style={{
              backgroundColor: "#fef3c7",
              padding: "1rem",
              borderRadius: "8px",
              marginBottom: "1rem",
              textAlign: "center"
            }}>
              <h3 style={{ margin: 0, color: "#92400e" }}>Suscripción requerida</h3>
              <p style={{ margin: "0.5rem 0 0", color: "#92400e", fontSize: "0.9rem" }}>
                {suscrito?.mensaje || "Iniciá tu prueba gratis de 7 días"}
              </p>
            </div>

            {/* Botón prueba gratis */}
            <button
              onClick={handleIniciarPrueba}
              disabled={loading}
              style={{
                width: "100%",
                padding: "0.75rem",
                marginBottom: "1rem",
                backgroundColor: "#22c55e",
                color: "white",
                border: "none",
                borderRadius: "4px",
                fontSize: "1rem",
                cursor: loading ? "not-allowed" : "pointer"
              }}
            >
              {loading ? "Activando..." : "🎁 Activar prueba gratis (7 días)"}
            </button>

            {/* códigos de descuento */}
            <div style={{ marginBottom: "1rem" }}>
              <label style={{ display: "block", marginBottom: "0.5rem", color: "#374151" }}>
                ¿Tenés código de descuento?
              </label>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <input
                  type="text"
                  value={codigoDescuento}
                  onChange={(e) => setCodigoDescuento(e.target.value.toUpperCase())}
                  placeholder="Código"
                  style={{
                    flex: 1,
                    padding: "0.75rem",
                    border: "1px solid #d1d5db",
                    borderRadius: "4px",
                    fontSize: "1rem"
                  }}
                />
                <button
                  onClick={handleAplicarCodigo}
                  disabled={aplicandoCodigo || !codigoDescuento}
                  style={{
                    padding: "0.75rem",
                    backgroundColor: "#6b7280",
                    color: "white",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer"
                  }}
                >
                  {aplicandoCodigo ? "..." : "Aplicar"}
                </button>
              </div>
            </div>

            {/* Plans */}
            <div style={{ marginTop: "1.5rem" }}>
              <h3 style={{ textAlign: "center", marginBottom: "1rem" }}>Planes</h3>
              
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div style={{
                  padding: "1rem",
                  border: "2px solid #22c55e",
                  borderRadius: "8px",
                  cursor: "pointer"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontWeight: "bold" }}>Mensual</span>
                    <span style={{ fontWeight: "bold", color: "#22c55e" }}>$35.000/mes</span>
                  </div>
                </div>
                
                <div style={{
                  padding: "1rem",
                  border: "2px solid #3b82f6",
                  borderRadius: "8px",
                  cursor: "pointer"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontWeight: "bold" }}>Semestral</span>
                    <div>
                      <span style={{ fontWeight: "bold", color: "#3b82f6" }}>$30.000/mes</span>
                      <span style={{ fontSize: "0.8rem", display: "block", color: "#22c55e" }}>Ahorrás $30.000</span>
                    </div>
                  </div>
                </div>
                
                <div style={{
                  padding: "1rem",
                  border: "2px solid #8b5cf6",
                  borderRadius: "8px",
                  cursor: "pointer"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontWeight: "bold" }}>Anual</span>
                    <div>
                      <span style={{ fontWeight: "bold", color: "#8b5cf6" }}>$25.000/mes</span>
                      <span style={{ fontSize: "0.8rem", display: "block", color: "#22c55e" }}>Ahorrás $120.000</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {error && (
              <div style={{
                color: "#ef4444",
                marginTop: "1rem",
                padding: "0.5rem",
                backgroundColor: "#fee2e2",
                borderRadius: "4px"
              }}>
                {error}
              </div>
            )}
          </div>
        ) : (
          /* Login normal si está suscrito */
          <form onSubmit={handleSubmit}>
            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label style={{ display: "block", marginBottom: "0.5rem", color: "#374151" }}>
                Usuario
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: "0.75rem",
                  border: "1px solid #d1d5db",
                  borderRadius: "4px",
                  fontSize: "1rem"
                }}
              />
            </div>

            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label style={{ display: "block", marginBottom: "0.5rem", color: "#374151" }}>
                Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: "0.75rem",
                  border: "1px solid #d1d5db",
                  borderRadius: "4px",
                  fontSize: "1rem"
                }}
              />
            </div>

            {error && (
              <div style={{
                color: "#ef4444",
                marginBottom: "1rem",
                padding: "0.5rem",
                backgroundColor: "#fee2e2",
                borderRadius: "4px"
              }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn"
              disabled={loading}
              style={{
                width: "100%",
                padding: "0.75rem",
                backgroundColor: "#2e86de",
                color: "white",
                border: "none",
                borderRadius: "4px",
                fontSize: "1rem",
                cursor: loading ? "not-allowed" : "pointer"
              }}
            >
              {loading ? "Iniciando sesión..." : "Iniciar Sesión"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}