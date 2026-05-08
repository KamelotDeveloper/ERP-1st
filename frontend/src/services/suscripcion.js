import axios from "axios";

// URL del backend local (FastAPI en puerto 8000)
// En desarrollo: localhost:8000, en Tauri: http://127.0.0.1:8000
const getBaseURL = () => {
  // Si estamos en Tauri, usar la IP explícita
  if (window.__TAURI__) {
    return "http://127.0.0.1:8000";
  }
  // En navegador, usar la misma origin o localhost
  return "http://127.0.0.1:8000";
};

const suscripcionApi = axios.create({
  baseURL: getBaseURL(),
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

// ==================== PLANES (Links fijos de MercadoPago) ====================

export const PLANES = {
  mensual: {
    nombre: "Mensual",
    precio: 35000,
    periodo: "mes",
    mp_link: "https://mpago.la/1bumKHN",
    descripcion: "Ideal para probar el sistema"
  },
  semestral: {
    nombre: "Semestral",
    precio: 180000,
    periodo: "6 meses",
    mp_link: "https://mpago.la/247hTmc",
    descripcion: "Ahorro del 14% vs mensual"
  },
  anual: {
    nombre: "Anual",
    precio: 360000,
    periodo: "año",
    mp_link: "https://mpago.la/1VAdrEZ",
    descripcion: "El mejor valor, ahorro del 14% vs semestral"
  }
};

export function obtenerPlanes() {
  // Retorna los planes con links fijos (no necesita API call)
  return Promise.resolve({ ok: true, planes: PLANES });
}

// ==================== VERIFICAR LICENCIA ====================

export async function verificarSuscripcion(client_id) {
  // Usa el nuevo endpoint local /iniciar-sesion
  const response = await suscripcionApi.post('/iniciar-sesion', {
    client_id
  });
  return response.data;
}

// ==================== INICIAR SESIÓN (NUEVO ENDPOINT) ====================

export async function iniciarSesion(client_id) {
  const response = await suscripcionApi.post('/iniciar-sesion', {
    client_id
  });
  return response.data;
}

// ==================== VERIFICAR ACTIVACIÓN ====================

export async function verificarActivacion(client_id) {
  const response = await suscripcionApi.get('/verificar-activacion', {
    params: { client_id }
  });
  return response.data;
}

// ==================== YA NO USAMOS ESTOS (comentados para referencia) ====================
/*
export async function crearPreferencia(client_id, plan, email, codigo_descuento = null) {
  // YA NO SE USA - usamos links fijos de MP
  throw new Error("Función obsoleta - usar links fijos de MP");
}

export async function validarCodigo(codigo, plan = null) {
  // YA NO SE USA
  throw new Error("Función obsoleta");
}

export async function iniciarPruebaGratis(email) {
  // El trial ahora se maneja en el endpoint /iniciar-sesion del backend local
  let clientId = localStorage.getItem("client_id");
  if (!clientId) {
    clientId = "user_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    localStorage.setItem("client_id", clientId);
  }
  
  // Llamar al backend local para iniciar trial
  const response = await suscripcionApi.post('/iniciar-sesion', {
    client_id: clientId
  });
  return response.data;
}
*/

export default suscripcionApi;
