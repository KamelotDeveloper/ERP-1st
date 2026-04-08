import { useState, useEffect } from "react";
import api from "../services/api";

export default function Profile() {
  const [username, setUsername] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Load current user info
    const loadUser = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await api.get("/auth/me", {
          headers: { Authorization: `Bearer ${token}` }
        });
        setUsername(res.data.username);
      } catch (err) {
        console.error("Error loading user:", err);
      }
    };
    loadUser();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    // Check if new password fields are filled
    if (newPassword || oldPassword) {
      if (newPassword !== confirmPassword) {
        setError("Las contraseñas nuevas no coinciden");
        return;
      }
      if (newPassword && newPassword.length < 6) {
        setError("La contraseña debe tener al menos 6 caracteres");
        return;
      }
      if (oldPassword && !newPassword) {
        setError("Debe especificar la nueva contraseña");
        return;
      }
    }

    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      
      // Build the update data
      const updateData = {};
      if (username) updateData.username = username;
      if (oldPassword) updateData.old_password = oldPassword;
      if (newPassword) updateData.new_password = newPassword;

      const res = await api.put(
        "/auth/profile",
        updateData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      setMessage(res.data.message);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      
      // If username changed, update localStorage or redirect (optional)
      if (res.data.user) {
        console.log("Profile updated:", res.data.user);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Error al actualizar perfil");
    }
    setLoading(false);
  };

  return (
    <div className="page">
      <h2>Mi Perfil</h2>
      
      <div className="card" style={{ maxWidth: "500px" }}>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Usuario</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={{ width: "100%", padding: "8px" }}
            />
          </div>
          
          <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid #eee" }} />
          <h3 style={{ marginBottom: "15px", fontSize: "1rem" }}>Cambiar Contraseña (opcional)</h3>
          
          <div className="form-group">
            <label>Contraseña Actual</label>
            <input
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              placeholder="Dejar vacío si no quiere cambiar"
              style={{ width: "100%", padding: "8px" }}
            />
          </div>
          
          <div className="form-group">
            <label>Nueva Contraseña</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={6}
              placeholder="Mínimo 6 caracteres"
              style={{ width: "100%", padding: "8px" }}
            />
          </div>
          
          <div className="form-group">
            <label>Confirmar Nueva Contraseña</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirmar nueva contraseña"
              style={{ width: "100%", padding: "8px" }}
            />
          </div>
          
          {error && <div className="error" style={{ color: "#ef4444", marginBottom: "10px" }}>{error}</div>}
          {message && <div className="success" style={{ color: "#22c55e", marginBottom: "10px" }}>{message}</div>}
          
          <button type="submit" className="btn" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Guardando..." : "Guardar Cambios"}
          </button>
        </form>
      </div>
    </div>
  );
}