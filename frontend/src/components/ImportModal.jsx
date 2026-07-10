import React, { useState, useRef, useCallback } from "react";
import api from "../services/api";

/* ------------------------------------------------------------------ */
/*  Styles (dark theme, inline <style> matching project pattern)      */
/* ------------------------------------------------------------------ */

const styles = `
.import-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.import-modal {
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 12px;
  width: 90%;
  max-width: 960px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  overflow: hidden;
}
.import-modal h2 {
  color: #f1f5f9;
  border-bottom: 2px solid #0ea5e9;
  padding: 20px 24px 12px;
  margin: 0;
  font-size: 1.25rem;
}
.import-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.import-footer {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid #334155;
  background: #0f172a;
}
.import-footer button,
.import-body button {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: 0.2s;
}
.btn-primary {
  background: linear-gradient(135deg, #0ea5e9, #0284c7);
  color: white;
}
.btn-primary:hover {
  background: linear-gradient(135deg, #0284c7, #0369a1);
  transform: translateY(-1px);
}
.btn-secondary {
  background: #334155;
  color: #e2e8f0;
}
.btn-secondary:hover {
  background: #475569;
}
.btn-danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: white;
}
.btn-success {
  background: linear-gradient(135deg, #22c55e, #16a34a);
  color: white;
}
.btn-success:hover {
  background: linear-gradient(135deg, #2dd46e, #26b44f);
  transform: translateY(-1px);
}
.btn-secondary:hover {
  background: #475569;
}
.import-footer button:disabled,
.import-body button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* Drop zone */
.drop-zone {
  border: 2px dashed #475569;
  border-radius: 12px;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #0f172a;
}
.drop-zone:hover,
.drop-zone.drag-over {
  border-color: #0ea5e9;
  background: #1a2a42;
}
.drop-zone p {
  margin: 8px 0;
  color: #94a3b8;
}
.drop-zone .drop-icon {
  font-size: 2.5rem;
  margin-bottom: 8px;
}
.drop-zone .browse-link {
  color: #0ea5e9;
  text-decoration: underline;
  cursor: pointer;
}
.file-info {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.file-info .file-name {
  font-weight: 600;
  color: #f1f5f9;
}
.file-info .file-size {
  color: #94a3b8;
  font-size: 0.8rem;
}
.file-info button {
  background: #ef4444;
}
.file-info button:hover {
  background: #dc2626;
}

/* Steps indicator */
.steps {
  display: flex;
  justify-content: center;
  gap: 0;
  padding: 16px 24px 0;
  margin-bottom: 8px;
}
.step-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  background: #334155;
  color: #94a3b8;
  transition: 0.2s;
}
.step-dot.active {
  background: #0ea5e9;
  color: white;
}
.step-dot.done {
  background: #22c55e;
  color: white;
}
.step-label {
  font-size: 0.8rem;
  color: #64748b;
}
.step-label.active {
  color: #f1f5f9;
  font-weight: 600;
}
.step-connector {
  width: 40px;
  height: 2px;
  background: #334155;
  margin: 0 8px;
}
.step-connector.done {
  background: #22c55e;
}

/* Preview table */
.import-table-wrap {
  overflow-x: auto;
  margin-top: 16px;
  border: 1px solid #334155;
  border-radius: 8px;
}
.import-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.import-table th {
  background: #0f172a;
  color: #94a3b8;
  font-weight: 600;
  text-align: left;
  padding: 10px 12px;
  white-space: nowrap;
  border-bottom: 2px solid #334155;
  position: sticky;
  top: 0;
  z-index: 2;
}
.import-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #1e293b;
  vertical-align: middle;
}
.import-table tr.row-skip td {
  opacity: 0.4;
  text-decoration: line-through;
}
.import-table tr.row-valid {
  background: #0d2818;
}
.import-table tr.row-error {
  background: #2d0a0a;
}
.import-table td.cell-error {
  background: rgba(239, 68, 68, 0.2);
  position: relative;
}
.import-table td.cell-error::after {
  content: "⚠";
  color: #ef4444;
  margin-left: 6px;
  cursor: help;
}
.import-table td input {
  background: #0f172a;
  border: 1px solid #475569;
  color: #e2e8f0;
  padding: 4px 8px;
  border-radius: 4px;
  width: 100%;
  min-width: 80px;
  font-size: 0.85rem;
}
.import-table td input:focus {
  outline: none;
  border-color: #0ea5e9;
}
.import-table .skip-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

/* Stats bar */
.stats-bar {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background: #0f172a;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 0.85rem;
  align-items: center;
}
.stats-bar .stat {
  display: flex;
  align-items: center;
  gap: 6px;
}
.stat-valid { color: #22c55e; }
.stat-error { color: #ef4444; }
.stat-skip  { color: #f59e0b; }
.stat-total { color: #94a3b8; }

/* Note banner */
.note-banner {
  background: #1a2a42;
  border: 1px solid #0ea5e9;
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 0.85rem;
  color: #93c5fd;
  margin-bottom: 12px;
}

/* Progress bar */
.progress-wrap {
  text-align: center;
  padding: 32px 24px;
}
.progress-bar-bg {
  width: 100%;
  height: 24px;
  background: #0f172a;
  border-radius: 12px;
  overflow: hidden;
  margin: 16px 0;
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #0ea5e9, #22c55e);
  border-radius: 12px;
  transition: width 0.3s ease;
}
.progress-text {
  font-size: 0.9rem;
  color: #94a3b8;
}

/* Result */
.result-summary {
  text-align: center;
  padding: 24px;
}
.result-summary .result-icon {
  font-size: 3rem;
  margin-bottom: 12px;
}
.result-summary .result-title {
  font-size: 1.25rem;
  font-weight: 700;
  margin-bottom: 8px;
}
.result-summary .result-detail {
  color: #94a3b8;
  font-size: 0.95rem;
}
.result-errors {
  margin-top: 20px;
  text-align: left;
}
.result-errors h4 {
  color: #ef4444;
  margin-bottom: 8px;
}
.result-errors ul {
  list-style: none;
  padding: 0;
  max-height: 200px;
  overflow-y: auto;
}
.result-errors li {
  padding: 6px 12px;
  background: #2d0a0a;
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 0.85rem;
}

/* Loading spinner */
.loading-spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid #475569;
  border-top-color: #0ea5e9;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  margin-right: 8px;
  vertical-align: middle;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Tooltip */
.tooltip-wrap {
  position: relative;
  cursor: help;
}
.tooltip-text {
  visibility: hidden;
  opacity: 0;
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: #0f172a;
  color: #f87171;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 0.75rem;
  white-space: nowrap;
  z-index: 10;
  border: 1px solid #ef4444;
  transition: 0.15s;
}
.tooltip-wrap:hover .tooltip-text {
  visibility: visible;
  opacity: 1;
}
`;

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

function downloadCSV(filename, rows, columns) {
  const headers = columns.map((c) => c.label || c.key).join(",");
  const lines = rows.map((r) =>
    columns.map((c) => {
      const val = r.data?.[c.key] ?? "";
      return typeof val === "string" && (val.includes(",") || val.includes('"'))
        ? `"${val.replace(/"/g, '""')}"`
        : val;
    }).join(",")
  );
  const csv = [headers, ...lines].join("\n");
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadJSON(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/* ------------------------------------------------------------------ */
/*  Sub-steps                                                         */
/* ------------------------------------------------------------------ */

function StepFileSelect({ resource, onFileSelected, loading, setLoading, error, setError }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [processing, setProcessing] = useState(false);

  const validateAndSelect = useCallback(
    async (file) => {
      if (!file) return;
      // Validate size (< 10MB)
      if (file.size > 10 * 1024 * 1024) {
        setError("El archivo supera el límite de 10MB");
        return;
      }
      // Validate extension
      const ext = file.name.split(".").pop().toLowerCase();
      if (!["csv", "xlsx"].includes(ext)) {
        setError("Solo se permiten archivos .csv y .xlsx");
        return;
      }
      setError("");
      setSelectedFile(file);
      setProcessing(true);
      setLoading(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await api.post(`/${resource}/import/preview`, fd);
        onFileSelected(file, res.data);
      } catch (err) {
        setError(
          "Error al procesar el archivo: " +
            (err.response?.data?.detail || err.message)
        );
      }
      setLoading(false);
      setProcessing(false);
    },
    [resource, onFileSelected, setLoading, setError]
  );

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      validateAndSelect(file);
    },
    [validateAndSelect]
  );

  const handleFileInput = useCallback(
    (e) => {
      const file = e.target.files[0];
      if (file) validateAndSelect(file);
    },
    [validateAndSelect]
  );

  const downloadTemplate = async () => {
    try {
      const res = await api.get(`/${resource}/import/template`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      triggerDownload(url, `${resource}_template.xlsx`);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError("Error al descargar plantilla: " + err.message);
    }
  };

  return (
    <div>
      <div
        className={`drop-zone${dragOver ? " drag-over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="drop-icon">📂</div>
        <p>
          Arrastrá tu archivo .csv o .xlsx acá, o{" "}
          <span
            className="browse-link"
            onClick={(e) => {
              e.stopPropagation();
              inputRef.current?.click();
            }}
          >
            seleccioná uno
          </span>
        </p>
        <p style={{ fontSize: "0.8rem", color: "#64748b" }}>
          Máximo 10MB · Formatos: CSV, XLSX
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx"
          style={{ display: "none" }}
          onChange={handleFileInput}
        />
      </div>

      {processing && (
        <div style={{ textAlign: "center", marginTop: "16px" }}>
          <span className="loading-spinner" />
          Procesando archivo...
        </div>
      )}

      {selectedFile && !processing && (
        <div className="file-info">
          <div>
            <div className="file-name">{selectedFile.name}</div>
            <div className="file-size">{formatFileSize(selectedFile.size)}</div>
          </div>
          <button onClick={() => { setSelectedFile(null); setError(""); }}>Quitar</button>
        </div>
      )}

      {error && (
        <div
          style={{
            color: "#f87171",
            background: "#2d0a0a",
            padding: "10px 16px",
            borderRadius: "8px",
            marginTop: "12px",
            fontSize: "0.85rem",
          }}
        >
          {error}
        </div>
      )}

      <div style={{ marginTop: "20px", textAlign: "center" }}>
        <button className="btn-secondary" onClick={downloadTemplate}>
          📥 Descargar plantilla
        </button>
      </div>
    </div>
  );
}

function StepPreviewEdit({
  previewData,
  columns,
  editedRows,
  setEditedRows,
  skippedRows,
  setSkippedRows,
  onBack,
  onConfirm,
  loading,
}) {
  const rows = previewData?.rows || [];
  const columnsMapped = previewData?.columns_mapped || [];
  const columnsIgnored = previewData?.columns_ignored || [];
  const totalRows = previewData?.total_rows || 0;

  // Compute stats
  const validRows = rows.filter((r) => r.valid);
  const errorRows = rows.filter((r) => !r.valid);
  const skippedCount = skippedRows.size;
  const validCount = validRows.length;

  // Determine display columns: only mapped columns that are in our columns prop
  const displayColumns = columns.filter((c) => columnsMapped.includes(c.key));

  // Editable cell handler
  const handleCellEdit = (rowIndex, field, value) => {
    setEditedRows((prev) => ({
      ...prev,
      [rowIndex]: { ...(prev[rowIndex] || {}), [field]: value },
    }));
  };

  // Get the merged data for a row (original + edited)
  const getRowData = (row) => {
    const edits = editedRows[row.index] || {};
    return { ...row.data, ...edits };
  };

  // Get errors for a row considering edits might have fixed some
  const getRowErrors = (row) => {
    if (row.valid) return {};
    // Re-compute locally: if edited, clear the error for that field
    const edits = editedRows[row.index] || {};
    const rowErrors = { ...row.errors };
    Object.keys(edits).forEach((f) => {
      if (edits[f] !== undefined && edits[f] !== null) {
        delete rowErrors[f];
      }
    });
    return rowErrors;
  };

  const isRowValid = (row) => {
    const errors = getRowErrors(row);
    return row.valid && Object.keys(errors).length === 0;
  };

  const toggleSkip = (rowIndex) => {
    setSkippedRows((prev) => {
      const next = new Set(prev);
      if (next.has(rowIndex)) next.delete(rowIndex);
      else next.add(rowIndex);
      return next;
    });
  };

  // Download errors CSV
  const handleDownloadErrors = () => {
    const errorRowsOnly = rows.filter((r) => !r.valid);
    downloadCSV("errores_importacion.csv", errorRowsOnly, columns);
  };

  const isFieldRequired = (field) => {
    const col = columns.find((c) => c.key === field);
    return col?.required || false;
  };

  return (
    <div>
      {columnsIgnored.length > 0 && (
        <div className="note-banner">
          Columnas ignoradas: {columnsIgnored.join(", ")}
        </div>
      )}

      {previewData?.warnings?.length > 0 &&
        previewData.warnings.map((w, i) => (
          <div
            key={i}
            style={{
              background: "#1a2a42",
              border: "1px solid #f59e0b",
              borderRadius: "8px",
              padding: "10px 16px",
              fontSize: "0.85rem",
              color: "#fbbf24",
              marginBottom: "8px",
            }}
          >
            {w}
          </div>
        ))}

      <div className="stats-bar">
        <span className="stat stat-total">Total: {totalRows} filas</span>
        <span className="stat stat-valid">✓ {validCount} válidas</span>
        {errorRows.length > 0 && (
          <span className="stat stat-error">✗ {errorRows.length} con errores</span>
        )}
        {skippedCount > 0 && (
          <span className="stat stat-skip">— {skippedCount} a saltar</span>
        )}
      </div>

      {errorRows.length > 0 && (
        <div style={{ marginBottom: "12px" }}>
          <button className="btn-secondary" onClick={handleDownloadErrors}>
            ⬇ Descargar errores
          </button>
        </div>
      )}

      <div className="import-table-wrap">
        <table className="import-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>#</th>
              <th style={{ width: 50 }}>Saltar</th>
              {displayColumns.map((col) => (
                <th key={col.key}>
                  {col.label}
                  {col.required && (
                    <span style={{ color: "#ef4444", marginLeft: 2 }}>*</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const rowErrors = getRowErrors(row);
              const rowData = getRowData(row);
              const skip = skippedRows.has(row.index);
              const rowValid = isRowValid(row);

              let rowClass = "";
              if (skip) rowClass = "row-skip";
              else if (rowValid) rowClass = "row-valid";
              else rowClass = "row-error";

              return (
                <tr key={row.index} className={rowClass}>
                  <td style={{ color: "#64748b", fontSize: "0.8rem" }}>
                    {row.index + 1}
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      className="skip-checkbox"
                      checked={skip}
                      onChange={() => toggleSkip(row.index)}
                    />
                  </td>
                  {displayColumns.map((col) => {
                    const val = rowData[col.key] ?? "";
                    const hasError = !!rowErrors[col.key];

                    return (
                      <td
                        key={col.key}
                        className={hasError ? "cell-error" : ""}
                      >
                        {hasError ? (
                          <span className="tooltip-wrap">
                            <EditableCell
                              value={val}
                              onChange={(v) =>
                                handleCellEdit(row.index, col.key, v)
                              }
                            />
                            <span className="tooltip-text">
                              {rowErrors[col.key]}
                            </span>
                          </span>
                        ) : (
                          <EditableCell
                            value={val}
                            onChange={(v) =>
                              handleCellEdit(row.index, col.key, v)
                            }
                          />
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EditableCell({ value, onChange }) {
  const [editing, setEditing] = useState(false);
  const [localVal, setLocalVal] = useState(value);
  const inputRef = useRef(null);

  const startEdit = () => {
    setLocalVal(value);
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  };

  const finishEdit = () => {
    setEditing(false);
    if (localVal !== value) {
      onChange(localVal);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") finishEdit();
    if (e.key === "Escape") {
      setLocalVal(value);
      setEditing(false);
    }
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="text"
        value={localVal}
        onChange={(e) => setLocalVal(e.target.value)}
        onBlur={finishEdit}
        onKeyDown={handleKeyDown}
        autoFocus
      />
    );
  }

  return (
    <span
      onClick={startEdit}
      style={{
        cursor: "pointer",
        minHeight: "20px",
        display: "inline-block",
        width: "100%",
      }}
      title="Hacé clic para editar"
    >
      {value === null || value === undefined || value === "" ? (
        <span style={{ color: "#475569", fontStyle: "italic" }}>vacío</span>
      ) : (
        String(value)
      )}
    </span>
  );
}

function StepConfirmResult({
  resource,
  rows,
  editedRows,
  skippedRows,
  columns,
  onDone,
}) {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("uploading"); // uploading | done
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  // Build the rows payload with merged data
  const buildPayload = useCallback(() => {
    return rows.map((row) => {
      const edits = editedRows[row.index] || {};
      const merged = { ...row.data, ...edits };
      return {
        index: row.index,
        data: merged,
        skip: skippedRows.has(row.index),
      };
    });
  }, [rows, editedRows, skippedRows]);

  // Simulate progress while uploading
  const executeImport = useCallback(async () => {
    // Animate progress to 90% while waiting
    const interval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 5, 90));
    }, 200);

    try {
      const payload = { rows: buildPayload() };
      const res = await api.post(`/${resource}/import/execute`, payload);
      clearInterval(interval);
      setProgress(100);
      setResult(res.data);
      setStatus("done");
    } catch (err) {
      clearInterval(interval);
      setProgress(100);
      setError(
        "Error al importar: " +
          (err.response?.data?.detail || err.message)
      );
      setStatus("done");
    }
  }, [resource, buildPayload]);

  React.useEffect(() => {
    executeImport();
  }, [executeImport]);

  // Download detailed log
  const handleDownloadLog = () => {
    downloadJSON(`importe_${resource}_log.json`, {
      resource,
      imported_at: new Date().toISOString(),
      ...result,
    });
  };

  if (status === "uploading") {
    return (
      <div className="progress-wrap">
        <h3 style={{ color: "#f1f5f9", marginBottom: "16px" }}>
          Importando datos...
        </h3>
        <div className="progress-bar-bg">
          <div
            className="progress-bar-fill"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="progress-text">{progress}%</div>
        {error && (
          <div
            style={{
              color: "#f87171",
              marginTop: "12px",
              fontSize: "0.85rem",
            }}
          >
            {error}
          </div>
        )}
      </div>
    );
  }

  if (error) {
    return (
      <div className="result-summary">
        <div className="result-icon" style={{ color: "#ef4444" }}>
          ✗
        </div>
        <div className="result-title" style={{ color: "#ef4444" }}>
          Error en la importación
        </div>
        <div className="result-detail">{error}</div>
        <div style={{ marginTop: "20px" }}>
          <button className="btn-primary" onClick={onDone}>
            Cerrar
          </button>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const hasErrors = result.failed > 0 || (result.errors && result.errors.length > 0);
  const allOk = result.imported > 0 && !hasErrors;

  return (
    <div className="result-summary">
      {allOk ? (
        <>
          <div className="result-icon" style={{ color: "#22c55e" }}>
            ✓
          </div>
          <div className="result-title" style={{ color: "#22c55e" }}>
            Importación exitosa
          </div>
          <div className="result-detail">
            Se importaron {result.imported} registros correctamente
          </div>
        </>
      ) : (
        <>
          <div className="result-icon" style={{ color: "#f59e0b" }}>
            ⚠
          </div>
          <div className="result-title" style={{ color: "#f59e0b" }}>
            Importación parcial
          </div>
          <div className="result-detail">
            {result.imported} importados, {result.failed} con errores
          </div>
        </>
      )}

      {result.errors && result.errors.length > 0 && (
        <div className="result-errors">
          <h4>Errores ({result.errors.length})</h4>
          <ul>
            {result.errors.map((e, i) => (
              <li key={i}>
                <strong>Fila {e.row + 1}:</strong>{" "}
                {e.field && `[${e.field}] `}
                {e.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.results && result.results.length > 0 && (
        <div style={{ marginTop: "16px" }}>
          <button className="btn-secondary" onClick={handleDownloadLog}>
            ⬇ Descargar log
          </button>
        </div>
      )}

      <div style={{ marginTop: "24px", display: "flex", gap: "10px", justifyContent: "center" }}>
        <button className="btn-success" onClick={onDone}>
          Cerrar
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                    */
/* ------------------------------------------------------------------ */

export default function ImportModal({
  resource,
  columns,
  onImportComplete,
  onClose,
}) {
  const [step, setStep] = useState(1); // 1=FileSelect, 2=Preview, 3=Result
  const [file, setFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [editedRows, setEditedRows] = useState({});
  const [skippedRows, setSkippedRows] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFileSelected = (selectedFile, preview) => {
    setFile(selectedFile);
    setPreviewData(preview);
    setEditedRows({});
    setSkippedRows(new Set());
    setError("");
    setStep(2);
  };

  const handleBack = () => {
    setStep(1);
    setError("");
  };

  const handleConfirm = () => {
    setStep(3);
  };

  const handleDone = () => {
    onImportComplete();
    onClose();
  };

  const handleOverlayClick = (e) => {
    if (e.target.classList.contains("import-overlay")) {
      onClose();
    }
  };

  return (
    <>
      <style>{styles}</style>
      <div className="import-overlay" onClick={handleOverlayClick}>
        <div className="import-modal">
          <h2>
            Importar{" "}
            {resource === "clients"
              ? "Clientes"
              : resource === "products"
              ? "Productos"
              : "Materiales"}
          </h2>

          {/* Steps indicator */}
          <div className="steps">
            <div className="step-indicator">
              <div className={`step-dot ${step >= 1 ? (step > 1 ? "done" : "active") : ""}`}>
                {step > 1 ? "✓" : "1"}
              </div>
              <span className={`step-label ${step >= 1 ? "active" : ""}`}>
                Archivo
              </span>
            </div>
            <div className={`step-connector ${step > 1 ? "done" : ""}`} />
            <div className="step-indicator">
              <div className={`step-dot ${step >= 2 ? (step > 2 ? "done" : "active") : ""}`}>
                {step > 2 ? "✓" : "2"}
              </div>
              <span className={`step-label ${step >= 2 ? "active" : ""}`}>
                Vista previa
              </span>
            </div>
            <div className={`step-connector ${step > 2 ? "done" : ""}`} />
            <div className="step-indicator">
              <div className={`step-dot ${step >= 3 ? "active" : ""}`}>
                3
              </div>
              <span className={`step-label ${step >= 3 ? "active" : ""}`}>
                Resultado
              </span>
            </div>
          </div>

          <div className="import-body">
            {step === 1 && (
              <StepFileSelect
                resource={resource}
                onFileSelected={handleFileSelected}
                loading={loading}
                setLoading={setLoading}
                error={error}
                setError={setError}
              />
            )}

            {step === 2 && previewData && (
              <StepPreviewEdit
                previewData={previewData}
                columns={columns}
                editedRows={editedRows}
                setEditedRows={setEditedRows}
                skippedRows={skippedRows}
                setSkippedRows={setSkippedRows}
                onBack={handleBack}
                onConfirm={handleConfirm}
                loading={loading}
              />
            )}

            {step === 3 && (
              <StepConfirmResult
                resource={resource}
                rows={previewData?.rows || []}
                editedRows={editedRows}
                skippedRows={skippedRows}
                columns={columns}
                onDone={handleDone}
              />
            )}
          </div>

          {step === 2 && (
            <div className="import-footer">
              <button className="btn-secondary" onClick={handleBack}>
                ← Atrás
              </button>
              <button className="btn-success" onClick={handleConfirm}>
                Confirmar importación
              </button>
            </div>
          )}

          {step === 1 && (
            <div className="import-footer">
              <button className="btn-secondary" onClick={onClose}>
                Cancelar
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

