import { useState, useEffect } from "react";

const isTauri = !!window.__TAURI_INTERNALS__;
const invoke = isTauri
  ? (cmd, args) => window.__TAURI_INTERNALS__.invoke(cmd, args)
  : null;

export default function ServerInfo() {
  const [lanIp, setLanIp] = useState("");
  const [copied, setCopied] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!isTauri || !invoke) return;
    invoke("get_lan_ip")
      .then((ip) => setLanIp(ip))
      .catch(() => {});
  }, []);

  const url = `http://${lanIp}:8000`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = url;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (dismissed || !lanIp) return null;

  return (
    <div className="server-info-banner">
      <span className="server-info-text">
        🌐 Compartiendo en: <strong>{url}</strong>
      </span>
      <button className="server-info-copy-btn" onClick={handleCopy}>
        {copied ? "✓ Copiado" : "Copiar"}
      </button>
      <button
        className="server-info-dismiss"
        onClick={() => setDismissed(true)}
        title="Cerrar"
      >
        ✕
      </button>

      <style>{`
        .server-info-banner {
          background: linear-gradient(135deg, #0f172a, #1e293b);
          color: white;
          padding: 10px 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          font-size: 14px;
          border-bottom: 2px solid #0ea5e9;
        }
        .server-info-text {
          color: #e2e8f0;
        }
        .server-info-text strong {
          color: #0ea5e9;
        }
        .server-info-copy-btn {
          background: rgba(14, 165, 233, 0.15);
          border: 1px solid rgba(14, 165, 233, 0.4);
          color: #0ea5e9;
          padding: 4px 12px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }
        .server-info-copy-btn:hover {
          background: rgba(14, 165, 233, 0.25);
        }
        .server-info-dismiss {
          background: none;
          border: none;
          color: #64748b;
          font-size: 14px;
          cursor: pointer;
          padding: 2px 6px;
          border-radius: 4px;
          transition: color 0.2s;
        }
        .server-info-dismiss:hover {
          color: #ef4444;
        }
      `}</style>
    </div>
  );
}
