import { useState, useEffect } from "react";
import api from "../services/api";

export function useAlertasStock() {
  const [alertas, setAlertas] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAlertas = async () => {
    try {
      const res = await api.get("/materials/alertas");
      setAlertas(res.data);
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