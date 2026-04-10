import { useState, useEffect } from "react";
import api from "../services/api";

export function useAlertasStock() {
  const [alertas, setAlertas] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAlertas = async () => {
    try {
      const [matRes, prodRes] = await Promise.all([
        api.get("/materials/alertas"),
        api.get("/products/alertas")
      ]);
      
      const materialAlertas = matRes.data.map(m => ({ ...m, tipo: 'material' }));
      const productAlertas = prodRes.data.map(p => ({ ...p, tipo: 'producto' }));
      
      setAlertas([...materialAlertas, ...productAlertas]);
    } catch (err) {
      console.error("Error fetching alertas:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlertas();
    const interval = setInterval(fetchAlertas, 5 * 60 * 1000); // 5 minutes
    return () => clearInterval(interval);
  }, []);

  return { alertas, count: alertas.length };
}