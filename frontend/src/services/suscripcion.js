// URL de la API de suscripción en Vercel
const SUSCRIPCION_API_URL = "https://suscripcion-api-kc5t.vercel.app";

// Generar ID único desde el dispositivo
function generateClientId() {
  // Usar nombre de usuario + fecha como ID temporal
  const stored = localStorage.getItem("client_id");
  if (stored) return stored;
  
  const newId = "user_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
  localStorage.setItem("client_id", newId);
  return newId;
}

// Verificar suscripción
export async function verificarSuscripcion() {
  const clientId = generateClientId();
  
  try {
    const res = await fetch(`${SUSCRIPCION_API_URL}/api/verificar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId })
    });
    
    const data = await res.json();
    return data;
  } catch (error) {
    console.error("Error verificando suscripción:", error);
    return { activo: true, estado: "offline", mensaje: "Sin conexión" };
  }
}

// Iniciar prueba gratis de 7 días
export async function iniciarPruebaGratis(email) {
  const clientId = generateClientId();
  
  try {
    const res = await fetch(`${SUSCRIPCION_API_URL}/api/iniciar-prueba`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId, email: email })
    });
    
    const data = await res.json();
    return data;
  } catch (error) {
    console.error("Error iniciando prueba:", error);
    return { ok: false, error: "Sin conexión" };
  }
}

// Validar código de descuento
export async function validarCodigo(codigo) {
  try {
    const res = await fetch(`${SUSCRIPCION_API_URL}/api/codigo-descuento`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo })
    });
    
    const data = await res.json();
    return data;
  } catch (error) {
    console.error("Error validando código:", error);
    return { valido: false, error: "Sin conexión" };
  }
}

export { generateClientId, SUSCRIPCION_API_URL };