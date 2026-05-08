import { useState, useEffect } from "react";
import { obtenerPlanes, iniciarSesion } from "../services/suscripcion";

export default function PlanSelection({ onActivar, clientId }) {
  const [planes, setPlanes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [iniciandoTrial, setIniciandoTrial] = useState(false);

  // Cargar planes (links fijos desde el servicio)
  useEffect(() => {
    const cargarPlanes = async () => {
      try {
        const data = await obtenerPlanes();
        if (data.ok) {
          // Convertir objeto de planes a array para mapear
          const planesArray = Object.entries(data.planes).map(([key, val]) => ({
            id: key,
            ...val
          }));
          setPlanes(planesArray);
        } else {
          setError("Error cargando planes");
        }
      } catch (err) {
        console.error("Error:", err);
        setError("Error de conexión");
      } finally {
        setLoading(false);
      }
    };
    cargarPlanes();
  }, []);

  const handlePruebaGratis = async () => {
    setIniciandoTrial(true);
    setError("");
    
    try {
      if (!clientId) {
        setError("No se encontró client_id");
        setIniciandoTrial(false);
        return;
      }
      
      // Llamar al backend local para INICIAR el trial
      const result = await iniciarSesion(clientId);
      
      if (result.ok && result.tipo === "trial") {
        onActivar(result.fecha_fin);
      } else {
        setError(result.mensaje || "No se pudo activar el trial. Contactá soporte.");
      }
    } catch (err) {
      console.error("Error iniciando trial:", err);
      setError("Error de conexión con el servidor local");
    }
    setIniciandoTrial(false);
  };

  const handlePago = async (plan) => {
    try {
      setError("");
      
      // Verificar que estamos en Tauri
      if (!window.__TAURI__) {
        setError("Los pagos requieren la aplicación de escritorio (Tauri)");
        return;
      }
      
      // Abrir link de MercadoPago usando Tauri shell
      const { open } = window.__TAURI__.shell;
      await open(plan.mp_link);
      
      alert(`Pago iniciado para ${plan.nombre}.\nCompletá el pago en el navegador.\n\nUna vez pagado, reiniciá la aplicación para verificar la licencia.`);
      
    } catch (err) {
      console.error("Error abriendo pago:", err);
      setError("Error abriendo enlace de pago");
    }
  };

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh",
        backgroundColor: "#1f2937",
        display: "flex",
        alignItems: "center",
        justifyContent: "center"
      }}>
        <p style={{ color: "white", fontSize: "1.5rem" }}>Cargando planes...</p>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: "100vh",
      backgroundColor: "#1f2937",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "3rem 1rem"
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: "3rem" }}>
        <h1 style={{ color: "white", fontSize: "2.5rem", marginBottom: "0.5rem" }}>
          GA Software ERP
        </h1>
        <p style={{ color: "#9ca3af", fontSize: "1.1rem" }}>
          Sistema de gestión para tu empresa
        </p>
      </div>

      {/* Error */}
      {error && (
        <div style={{ 
          backgroundColor: "#fee2e2", 
          color: "#ef4444", 
          padding: "1rem", 
          borderRadius: "8px", 
          marginBottom: "2rem",
          maxWidth: "400px",
          textAlign: "center"
        }}>
          {error}
        </div>
      )}

      {/* Planes */}
      {planes.length === 0 ? (
        <p style={{ color: "#9ca3af", fontSize: "1.2rem" }}>No hay planes disponibles</p>
      ) : (
        <div style={{ display: "flex", gap: "20px", justifyContent: "center", marginBottom: "2rem", flexWrap: "wrap" }}>
          {planes.map((plan, index) => {
            const colors = ["#22c55e", "#3b82f6", "#8b5cf6"];
            const color = colors[index] || "#6b7280";
            
            return (
              <div
                key={plan.id}
                style={{
                  backgroundColor: "white",
                  borderRadius: "16px",
                  padding: "1.5rem",
                  textAlign: "center",
                  border: `4px solid ${color}`,
                  width: "220px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}
              >
                <div>
                  <h3 style={{ color: color, fontSize: "1.3rem", marginBottom: "0.5rem", fontWeight: "bold" }}>
                    {plan.nombre}
                  </h3>
                 
                  <div style={{ marginBottom: "1rem" }}>
                    <span style={{ fontSize: "2rem", fontWeight: "bold" }}>${plan.precio.toLocaleString()}</span>
                    <span style={{ color: "#6b7280" }}> / {plan.periodo}</span>
                  </div>

                  <p style={{ color: "#6b7280", fontSize: "0.9rem", marginBottom: "1rem" }}>
                    {plan.descripcion}
                  </p>

                  <ul style={{ listStyle: "none", padding: 0, textAlign: "left", fontSize: "0.9rem" }}>
                    <li style={{ padding: "0.25rem 0", color: "#374151" }}>✓ Acceso completo</li>
                    <li style={{ padding: "0.25rem 0", color: "#374151" }}>✓ {plan.periodo} de uso</li>
                    {plan.precio > 0 && (
                      <li style={{ padding: "0.25rem 0", color: "#374151" }}>✓ Soporte técnico</li>
                    )}
                  </ul>
                </div>

                <button
                  onClick={() => handlePago(plan)}
                  disabled={loading}
                  style={{
                    width: "100%",
                    padding: "0.75rem",
                    marginTop: "1rem",
                    backgroundColor: color,
                    color: "white",
                    border: "none",
                    borderRadius: "8px",
                    fontSize: "1rem",
                    fontWeight: "bold",
                    cursor: loading ? "not-allowed" : "pointer"
                  }}
                >
                  {loading ? "Procesando..." : `💳 Comprar ${plan.nombre}`}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Botón de Prueba Gratis */}
      <button
        onClick={handlePruebaGratis}
        disabled={iniciandoTrial || !clientId}
        style={{
          padding: "1rem 2rem",
          backgroundColor: "#22c55e",
          color: "white",
          border: "none",
          borderRadius: "8px",
          fontSize: "1.1rem",
          fontWeight: "bold",
          cursor: iniciandoTrial ? "not-allowed" : "pointer",
          marginBottom: "2rem"
        }}
      >
        {iniciandoTrial ? "Iniciando..." : "🎁 Activar Prueba Gratis (15 días)"}
      </button>

      {/* Footer */}
      <p style={{ marginTop: "2rem", color: "#6b7280", fontSize: "0.9rem" }}>
        © 2026 GA Software
      </p>
    </div>
  );
}
