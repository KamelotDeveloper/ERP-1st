import axios from "axios";

// URL de la API de suscripciones en Vercel (restaurado después del hack)
const suscripcionApi = axios.create({
  baseURL: "https://suscripcion-api-kc5t.vercel.app",
  timeout: 10000,
});

// Manejo de errores global
suscripcionApi.interceptors.response.use(
  response => response,
  error => {
    if (error.code === 'ECONNABORTED') {
      console.error('Timeout: El servidor no respondió en 10 segundos');
    } else if (!error.response) {
      console.error('Error de conexión: El backend no está disponible');
    } else {
      console.error('Error del servidor:', error.response.status + ' - ' + JSON.stringify(error.response.data));
    }
    return Promise.reject(error);
  }
);

// ==================== PLANES ====================

export async function obtenerPlanes() {
  const response = await suscripcionApi.get('/api/suscripcion/planes');
  return response.data;
}

// ==================== CREAR PREFERENCIA DE PAGO ====================

export async function crearPreferencia(client_id, plan, email, codigo_descuento = null) {
  const response = await suscripcionApi.post('/api/suscripcion/crear-preferencia', {
    client_id,
    plan,
    email,
    codigo_descuento
  });
  return response.data;
}

// ==================== VERIFICAR SUSCRIPCIÓN ====================

export async function verificarSuscripcion(client_id) {
  const response = await suscripcionApi.post('/api/suscripcion/verificar', {
    client_id
  });
  return response.data;
}

// ==================== VALIDAR CÓDIGO DE DESCUENTO ====================

export async function validarCodigo(codigo, plan = null) {
  const response = await suscripcionApi.post('/api/suscripcion/codigo-descuento', {
    codigo,
    plan
  });
  return response.data;
}

// ==================== INICIAR PRUEBA GRATIS ====================

export async function iniciarPruebaGratis(email) {
  // Obtener o generar client_id
  let clientId = localStorage.getItem("client_id");
  if (!clientId) {
    clientId = "user_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    localStorage.setItem("client_id", clientId);
  }
  
  const response = await suscripcionApi.post('/api/suscripcion/iniciar-prueba', {
    client_id: clientId,
    email
  });
  return response.data;
}

export default suscripcionApi;
