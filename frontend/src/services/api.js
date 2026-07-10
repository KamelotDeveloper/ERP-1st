import axios from "axios";

const DEFAULT_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const isTauri = !!window.__TAURI_INTERNALS__;

let baseURL = null;
let apiInstance = null;

/**
 * Resolves the API base URL from Tauri store (server/client IP)
 * or falls back to env var / localhost for dev mode.
 * Only fetches once per session.
 */
async function resolveBaseURL() {
  if (baseURL) return baseURL;

  if (isTauri) {
    try {
      const ip = await window.__TAURI_INTERNALS__.invoke("get_server_ip");
      baseURL = `http://${ip}:8000`;
    } catch (err) {
      console.warn("Failed to get server IP from Tauri, using default:", err);
      baseURL = DEFAULT_URL;
    }
  } else {
    baseURL = DEFAULT_URL;
  }

  return baseURL;
}

/**
 * Returns a configured axios instance.
 * Must be awaited on first call; subsequent calls return the cached instance.
 */
export async function getApi() {
  if (apiInstance) return apiInstance;

  const url = await resolveBaseURL();
  apiInstance = axios.create({
    baseURL: url,
    timeout: 10000,
  });

  // Global error handler
  apiInstance.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.code === "ECONNABORTED") {
        console.error("Timeout: El servidor no respondió en 10 segundos");
      } else if (!error.response) {
        console.error("Error de conexión: El backend no está disponible");
      } else {
        console.error("Error del servidor:", error.response.status);
      }
      return Promise.reject(error);
    }
  );

  return apiInstance;
}

/**
 * Synchronous getter — returns the cached instance or a fallback.
 * Use only after getApi() has been called at least once.
 */
function getApiSync() {
  if (apiInstance) return apiInstance;

  // Fallback for modules that import api before async init completes
  apiInstance = axios.create({
    baseURL: DEFAULT_URL,
    timeout: 10000,
  });

  apiInstance.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.code === "ECONNABORTED") {
        console.error("Timeout: El servidor no respondió en 10 segundos");
      } else if (!error.response) {
        console.error("Error de conexión: El backend no está disponible");
      } else {
        console.error("Error del servidor:", error.response.status);
      }
      return Promise.reject(error);
    }
  );

  return apiInstance;
}

// Default export: sync getter for backward compatibility with existing imports.
// Components that need the correct URL (e.g. App.jsx startup) should use getApi().
export default getApiSync();
