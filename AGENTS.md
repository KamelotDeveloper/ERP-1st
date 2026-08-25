# Ordo ERP System

## Project Overview

Full-stack ERP system for a carpentry business with electronic invoicing (ARCA/AFIP) for Argentina.

- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: React 18 + Vite + Tauri + React Router + Axios + Recharts
- **Desktop**: Tauri 2.0 for cross-platform installers

---

## Build, Lint & Test Commands

### Backend (Python/FastAPI)
```bash
cd backend

# Create & activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload

# Run on specific port
uvicorn main:app --reload --port 8000
```

### Frontend (React/Vite)
```bash
cd frontend

# Install dependencies
pnpm install

# Development
pnpm run dev

# Production build
pnpm run build
```

### Desktop App (Tauri)
```bash
cd frontend

# Install dependencies (first time)
pnpm install

# Build installers (Windows MSI, Mac DMG)
pnpm run tauri build
```

### Running All Services
```bash
# Terminal 1: Backend
cd backend && venv\Scripts\activate && uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend && pnpm run dev
```

---

## Code Style Guidelines

### Python (Backend)

**Imports Order**
```python
# 1. Standard library
import os
import json
from datetime import datetime

# 2. Third-party
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# 3. Local modules
from database import SessionLocal
import models, schemas
from services.afip_service import create_afip_service
```

**Naming Conventions**
| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `ElectronicInvoiceConfig` |
| Variables/Functions | snake_case | `get_db`, `client_id` |
| Constants | UPPER_SNAKE_CASE | `DATABASE_URL` |
| SQLAlchemy columns | snake_case | `fecha_creacion` |
| API Routes | snake_case or kebab-case | `/electronic-invoicing` |

**FastAPI Router Pattern**
```python
router = APIRouter(prefix="/resource", tags=["Category"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/items")
def create_item(data: schemas.ItemCreate, db: Session = Depends(get_db)):
    item = models.Item(**data.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.get("/items")
def list_items(db: Session = Depends(get_db)):
    return db.query(models.Item).all()

@router.get("/items/{id}")
def get_item(id: int, db: Session = Depends(get_db)):
    item = db.query(models.Item).filter(models.Item.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

**Error Handling**
- Use `HTTPException` with appropriate status codes (400, 404, 500)
- Always include `detail` message
- Return `{"ok": True}` for successful deletes

**File Upload Pattern**
```python
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    base_path = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(base_path, exist_ok=True)
    file_path = os.path.join(base_path, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"path": file_path}
```

---

### JavaScript/React (Frontend)

**Imports**
```javascript
import { useEffect, useState } from "react";
import api from "../services/api";
import Sidebar from "./components/Sidebar";
```

**Naming Conventions**
| Type | Convention | Example |
|------|------------|---------|
| Components | PascalCase | `Clients.jsx`, `ElectronicInvoicing` |
| Variables/Functions | camelCase | `data`, `formData`, `handleClick` |
| Constants | UPPER_SNAKE_CASE | `API_URL` |
| CSS Classes | kebab-case | `btn-edit`, `form-row`, `invoice-link` |

**Component Structure**
```javascript
export default function ComponentName() {
  const [data, setData] = useState([]);
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const res = await api.get("/endpoint");
      setData(res.data);
    } catch (error) {
      console.error(error);
    }
  };

  const save = async () => {
    setLoading(true);
    try {
      if (editId) {
        await api.put(`/resource/${editId}`, form);
      } else {
        await api.post("/resource", form);
      }
      load();
    } catch (error) {
      alert("Error: " + error.message);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="container">
      <h2>Title</h2>
      {/* JSX content */}
    </div>
  );
}
```

**API Service Pattern**
```javascript
import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000"
});

export default api;

// Usage in components:
// api.get("/endpoint")
// api.post("/endpoint", data)
// api.put("/endpoint/id", data)
// api.delete("/endpoint/id")
```

---

### CSS Styling

**Class Naming System**
| Pattern | Classes | Purpose |
|---------|---------|---------|
| Layout | `.layout`, `.container`, `.main`, `.sidebar`, `.navbar` | Page structure |
| Tables | `.table`, `.table th`, `.table td` | Data tables |
| Forms | `.form-row`, `.form-group` | Form inputs |
| Buttons | `.btn`, `.btn-edit`, `.btn-delete`, `.btn-save`, `.btn-restock` | Actions |
| Cards | `.card`, `.chart-card`, `.dashboard-grid` | Dashboard widgets |
| Status | `.status`, `.status-issued`, `.status-draft`, `.status-error` | State indicators |

**Button Colors**
- Edit: `.btn-edit` → Amber `#f59e0b`
- Delete: `.btn-delete` → Red `#ef4444`
- Save: `.btn-save` → Green `#22c55e`
- Default: `button` or `.btn` → Blue `#2e86de`
- Restock: `.btn-restock` → Blue `#3b82f6`

**Inline Styles**
- Use inline `style={{}}` for dynamic values
- Use `<style>{...}</style>` for component-specific styles

---

## Project Structure

```
GA_ERP_FIXED/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── models.py                  # SQLAlchemy models
│   ├── schemas.py                 # Pydantic schemas
│   ├── database.py                # DB connection
│   ├── requirements.txt           # Python dependencies
│   ├── routers/
│   │   ├── api.py                 # Main CRUD routes
│   │   ├── invoices.py            # Invoice routes
│   │   └── electronic_invoicing.py # AFIP setup wizard
 │   └── services/
│       ├── __init__.py
│       ├── afip_service.py        # ARCA/AFIP utilities
│       └── wsfe_client.py        # WSFE real integration
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Router setup
│   │   ├── main.jsx               # Entry point
│   │   ├── styles.css             # Global styles
│   │   ├── pages/                 # Page components
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Clients.jsx
│   │   │   ├── Products.jsx
│   │   │   ├── Materials.jsx
│   │   │   ├── Sales.jsx
│   │   │   ├── Invoices.jsx
│   │   │   └── ElectronicInvoicing.jsx
│   │   ├── components/             # Shared components
│   │   │   ├── Sidebar.jsx
│   │   │   ├── Navbar.jsx
│   │   │   └── GlobalSearch.jsx
│   │   └── services/
│   │       └── api.js             # Axios instance
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## Database

- **Type**: SQLite
- **Location**: `backend/carpinteria.db`
- **Auto-create**: Tables created on `uvicorn` startup via `Base.metadata.create_all()`
- **No migrations**: Schema changes require DB recreation

---

## API Conventions

### Response Patterns
```javascript
// Success
{ "id": 1, "name": "..." }

// Delete success
{ "ok": true }

// Error
{ "detail": "Error message" }

// List
[{ "id": 1 }, { "id": 2 }]

// Success flag
{ "success": true, "message": "..." }
```

### CRUD Endpoints (per entity)
```
GET    /resource          → List all
POST   /resource          → Create new
GET    /resource/{id}     → Get single
PUT    /resource/{id}     → Update
DELETE /resource/{id}     → Delete
```

---

## Key Notes for AI Agents

1. **No TypeScript** - Plain JavaScript/React only
2. **CSS Location** - Global in `styles.css`, component-specific in `<style>` tags
3. **Backend-First** - All business logic and validation in FastAPI
4. **SQLite Auto-Schema** - No migration system; tables auto-create
5. **Spanish UI** - Interface text in Spanish
6. **Argentinian Context** - ARCA/AFIP for electronic invoicing
7. **Facturación Electrónica** - Sistema completo con WSAA + WSFE para CAE real

## ARCA/AFIP Integration

### Flujo de Habilitación
1. `POST /electronic-invoicing/setup` - Configurar CUIT y datos
2. `POST /electronic-invoicing/upload-certificate` - Subir certificado .pem y clave .key
3. `POST /electronic-invoicing/test-connection` - Probar conexión WSAA
4. `POST /electronic-invoicing/enable` - Habilitar facturación

### Facturación Automática
- Si hay certificado configurado y habilitado → CAE real via WSFE
- Si no hay certificado → CAE simulado (para testing)
- La respuesta incluye `"modo": "real"` o `"modo": "simulado"`

### Validación de CUIT
- Usa algoritmo oficial de ARCA para verificar dígito verificador
- Valida formato (11 dígitos) y código de barras

---

## Adding New Features

### Backend
1. Add model to `models.py`
2. Add schema to `schemas.py`
3. Add routes to `routers/` or `main.py`
4. Test with curl/Postman

### Frontend
1. Create page in `pages/`
2. Add route to `App.jsx`
3. Add NavLink to `Sidebar.jsx`
4. Add styles to `styles.css`

---

## Common Patterns

### Create with Validation
```python
@router.post("/items")
def create_item(data: schemas.ItemCreate, db: Session = Depends(get_db)):
    item = models.Item(**data.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
```

### Update with Partial Data
```python
@router.put("/items/{id}")
def update_item(id: int, data: schemas.ItemUpdate, db: Session = Depends(get_db)):
    item = db.query(models.Item).filter(models.Item.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.dict().items():
        if value is not None:
            setattr(item, key, value)
    db.commit()
    return item
```

### React CRUD with State
```javascript
const [data, setData] = useState([]);
const [form, setForm] = useState({});
const [editId, setEditId] = useState(null);

const load = async () => {
  const res = await api.get("/resource");
  setData(res.data);
};

const save = async () => {
  if (editId) {
    await api.put(`/resource/${editId}`, form);
  } else {
    await api.post("/resource", form);
  }
  setForm({});
  setEditId(null);
  load();
};
```
## Agent Orchestration Rules
- **Lógica Fiscal:** Siempre que la tarea involucre archivos en `backend/routers/electronic_invoicing` o mencione "ARCA", "AFIP", "CAE" o "Factura", invoca automáticamente al sub-agente `@fiscal_expert`. [2]
- **Entorno de Escritorio:** Si el cambio afecta la carpeta `src-tauri` o la configuración de empaquetado, delega la revisión al sub-agente `@tauri_specialist`. [2]
- **Auditoría de Seguridad:** Antes de finalizar cualquier cambio que modifique la base de datos SQLite o maneje certificados, llama al `@security_auditor` para verificar vulnerabilidades. [2, 4]
- **Restricción de Lenguaje:** Bajo ninguna circunstancia permitas el uso de TypeScript; si detectas un intento de uso, rechaza el cambio y solicita conversión a Plain JavaScript. [5]