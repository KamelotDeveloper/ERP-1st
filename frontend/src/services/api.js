import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
  timeout: 10000, // 10 segundos - evita que la app se congele si el backend no responde
});

// Manejo de errores global
api.interceptors.response.use(
  response => response,
  error => {
    if (error.code === 'ECONNABORTED') {
      console.error('Timeout: El servidor no respondió en 10 segundos');
    } else if (!error.response) {
      console.error('Error de conexión: El backend no está disponible');
    } else {
      console.error('Error del servidor:', error.response.status);
    }
    return Promise.reject(error);
  }
);

// No authentication required - direct access
export default api;