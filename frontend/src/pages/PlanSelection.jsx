import { useState, useEffect } from "react";
import { iniciarPruebaGratis } from "../services/suscripcion";

const SUSCRIPCION_API_URL = "https://suscripcion-api-kc5t.vercel.app";

export default function PlanSelection({ onActivar }) {
  const [planes, setPlanes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [codigoDev, setCodigoDev] = useState("");

  // Cargar planes desde la API (Supabase)
  useEffect(() => {
    const cargarPlanes = async () => {
      try {
        const res = await fetch(`${SUSCRIPCION_API_URL}/api/planes`);
        const data = await res.json();
        if (data.ok) {
          setPlanes(data.planes);
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
    setLoading(true);
    setError("");
    
    try {
      // Obtener o generar client_id
      let clientId = localStorage.getItem("client_id");
      if (!clientId) {
        clientId = "user_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
        localStorage.setItem("client_id", clientId);
      }
      
      const result = await iniciarPruebaGratis(clientId + "@demo.com");
      
      if (result.ok || result.activo) {
        const fechaExpira = result.fecha_expiracion || new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
        onActivar(fechaExpira);
      } else {
        setError(result.mensaje || result.error || "Error al activar prueba");
      }
    } catch (err) {
      setError("Error de conexión");
    }
    setLoading(false);
  };

  const handlePago = async (planId) => {
    try {
      setLoading(true);
      setError("");
      
      // Obtener o generar client_id
      let clientId = localStorage.getItem("client_id");
      if (!clientId) {
        clientId = "user_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
        localStorage.setItem("client_id", clientId);
      }
      
      // Llamar a API de preferencias
      const res = await fetch("https://suscripcion-api-kc5t.vercel.app/api/crear-preferencia", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          plan: planId,
          email: clientId + "@demo.com"
        })
      });
      
      const data = await res.json();
      
      if (data.ok && data.init_point) {
        // Redirigir a MercadoPago
        window.location.href = data.init_point;
      } else {
        setError(data.error || "Error al crear preferencia");
      }
    } catch (err) {
      setError("Error de conexión con MercadoPago");
    }
    setLoading(false);
  };

  const handleCodigoDev = async () => {
    if (!codigoDev.trim()) return;
    
    try {
      setLoading(true);
      setError("");
      
      let clientId = localStorage.getItem("client_id");
      if (!clientId) {
        clientId = "user_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
        localStorage.setItem("client_id", clientId);
      }
      
      // Validar código desde la API
      const res = await fetch("https://suscripcion-api-kc5t.vercel.app/api/codigo-descuento", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          codigo: codigoDev.toUpperCase(),
          client_id: clientId
        })
      });
      
      const data = await res.json();
      
      if (data.valido) {
        // Código válido - dar acceso
        const fechaExpira = new Date();
        fechaExpira.setDate(fechaExpira.getDate() + 30);
        onActivar(fechaExpira.toISOString());
      } else {
        setError(data.error || "Código inválido");
      }
    } catch (err) {
      setError("Error al validar código");
    }
    setLoading(false);
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

       {/* Planes - dinámicos desde Supabase */}
       {planes.length === 0 ? (
         <p style={{ color: "#9ca3af", fontSize: "1.2rem" }}>No hay planes disponibles</p>
       ) : (
         <div style={{ display: "flex", gap: "20px", justifyContent: "center", marginBottom: "2rem", flexWrap: "wrap" }}>
           {planes.map((plan, index) => {
             // Colores dinámicos según el orden (o podés agregar campo 'color' en Supabase)
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
                     {plan.precio === 0 ? (
                       <span style={{ fontSize: "1.3rem", fontWeight: "bold", color: "#22c55e" }}>¡GRATIS!</span>
                     ) : (
                       <>
                         <span style={{ fontSize: "2rem", fontWeight: "bold" }}>${plan.precio.toLocaleString()}</span>
                         <span style={{ color: "#6b7280" }}> / {plan.dias} días</span>
                       </>
                     )}
                   </div>

                   {/* Características básicas según el plan */}
                   <ul style={{ listStyle: "none", padding: 0, textAlign: "left", fontSize: "0.9rem" }}>
                     <li style={{ padding: "0.25rem 0", color: "#374151" }}>✓ Acceso completo</li>
                     <li style={{ padding: "0.25rem 0", color: "#374151" }}>✓ {plan.dias} días de uso</li>
                     {plan.precio > 0 && (
                       <li style={{ padding: "0.25rem 0", color: "#374151" }}>✓ Soporte técnico</li>
                     )}
                   </ul>
                 </div>

                 <button
                   onClick={() => plan.id === "prueba" ? handlePruebaGratis() : handlePago(plan.id)}
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
                   {loading ? "Activando..." : plan.id === "prueba" ? "🎁 Activar Gratis" : "💳 Comprar"}
                 </button>
               </div>
             );
           })}
         </div>
       )}

      {/* Acceso Developer */}
      <div style={{ 
        backgroundColor: "#374151", 
        padding: "1.5rem", 
        borderRadius: "12px",
        marginTop: "1rem",
        border: "1px solid #4b5563"
      }}>
        <p style={{ color: "#9ca3af", fontSize: "0.9rem", marginBottom: "1rem", textAlign: "center" }}>
          Acceso Developer
        </p>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={codigoDev}
            onChange={(e) => setCodigoDev(e.target.value.toUpperCase())}
            placeholder="Código developer"
            style={{ 
              padding: "0.75rem 1rem", 
              borderRadius: "8px", 
              border: "none", 
              width: "200px", 
              fontSize: "1rem",
              backgroundColor: "#1f2937",
              color: "white"
            }}
          />
          <button
            onClick={handleCodigoDev}
            disabled={loading || !codigoDev.trim()}
            style={{
              padding: "0.75rem 1.5rem",
              backgroundColor: "#ef4444",
              color: "white",
              border: "none",
              borderRadius: "8px",
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: "1rem"
            }}
          >
            Acceder
          </button>
        </div>
      </div>

      {/* Footer */}
      <p style={{ marginTop: "2rem", color: "#6b7280", fontSize: "0.9rem" }}>
        © 2026 GA Software
      </p>
    </div>
  );
}
