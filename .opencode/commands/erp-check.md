# ERP Check Command

Revisa el código modificado antes de guardar para asegurar cumplimiento con las guías del proyecto.

## Ejecución

```
/erp-check
```

## Reglas de Revisión

### 1. PROHIBIDO: TypeScript

Este proyecto es **Plain JavaScript/React ONLY**. No usar:
- Archivos `.ts`, `.tsx`
- `interface` o `type` para definir tipos (excepto de libraries)
- Anotaciones de tipos `: string`, `: number`, `: boolean`, etc.

**SÍ permitido en JavaScript:**
- `?.` optional chaining (ES2020) - Válido
- `??` nullish coalescing (ES2020) - Válido
- Destructuring `const { x } = y` - Válido
- Arrow functions `() => {}` - Válido

**Si detectas TypeScript:**
```
⚠️ TypeScript detectado. Este proyecto usa Plain JavaScript.
Prohibido: interface, type, : tipo
```

### 2. PROHIBIDO: TypeScript en Python

No usar sintaxis TypeScript en Python:
- No usar `?.` (optional chaining) - usar `if x is not None:`
- No usar `!` assertions - no aplica en Python

**Errores comunes de IA:**
```python
# ❌ INCORRECTO (TypeScript en Python)
return x?.y?.z
return x?.method()

# ✅ CORRECTO (Python)
return x.y.z if x and y else None
if x and hasattr(x, 'method'): return x.method()
```

### 3. Colores de Botones

Verificar que los botones usen las clases correctas del manual de estilo:

| Acción | Clase CSS | Color |
|--------|-----------|-------|
| Editar | `.btn-edit` | Amber `#f59e0b` |
| Eliminar | `.btn-delete` | Red `#ef4444` |
| Guardar | `.btn-save` | Green `#22c55e` |
| Reponer stock | `.btn-restock` | Blue `#3b82f6` |
| Default | `button` o `.btn` | Blue `#2e86de` |

**Si detectas color incorrecto:**
```
⚠️ Color de botón incorrecto. Usar clase '.btn-edit' (Amber) para editar.
```

### 4. Imports en Python

Verificar orden de imports según AGENTS.md:

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

### 5. Imports en JavaScript

```javascript
// Primero React hooks y libraries
import { useEffect, useState } from "react";
import { BrowserRouter } from "react-router-dom";

// Luego servicios locales
import api from "../services/api";

// Luego componentes
import Sidebar from "./components/Sidebar";
```

### 6. Convenciones de Nombres

**Python:**
- Classes: `PascalCase` → `ElectronicInvoiceConfig`
- Variables/Functions: `snake_case` → `get_db`, `client_id`
- Constants: `UPPER_SNAKE_CASE` → `DATABASE_URL`

**JavaScript:**
- Components: `PascalCase` → `Clients.jsx`
- Variables: `camelCase` → `data`, `formData`
- CSS Classes: `kebab-case` → `btn-edit`, `form-row`

### 7. SQLAlchemy Models

```python
class ElectronicInvoiceConfig(Base):
    __tablename__ = "electronic_invoice_config"

    id = Column(Integer, primary_key=True, index=True)
    razon_social = Column(String, nullable=True)
```

### 8. Verificación de Sintaxis

Antes de finalizar, verificar:

**Python:**
```bash
python -c "from main import app; print('OK')"
```

**JavaScript:**
- Sin errores de sintaxis obvios
- Llaves `{}` balanceadas
- Paréntesis `()` balanceados

## Output Esperado

```
═══════════════════════════════════════
  ERP CHECK - Revisión de Código
═══════════════════════════════════════

[✓] Sin TypeScript
[✓] Sin ?. en Python (solo JS)
[✓] Colores de botones correctos
[✓] Imports en orden correcto
[✓] Convenciones de nombres cumplidas
[✓] Archivos .jsx (no .tsx)

REVISADO: 3 archivos
ERRORES: 0
```

## Auto-Corrección

Si encuentras errores, aplica las correcciones automáticamente:
1. Renombrar `.tsx` → `.jsx`
2. Convertir `interface`/`type` a objetos
3. Eliminar `: type` annotations
4. Reemplazar `?.` en Python por checks tradicionales
5. Corregir colores de botones
6. Reordenar imports

Solo reporta si no puedes auto-corregir.
