# GA Software - Carpintería El Menestral

Sistema ERP para gestión de carpintería con facturación AFIP/ARCA.

## Requisitos

- Python 3.8+
- Node.js 18+
- Rust (para compilar instaladores)

## Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows | source venv/bin/activate  # Mac
pip install -r requirements.txt
uvicorn main:app --reload
```

## Frontend (Desarrollo)

```bash
cd frontend
npm install
npm run dev
```

## Compilar instaladores (Windows/Mac)

### Windows
```bash
cd frontend
npm install
npm run tauri build
# Genera: src-tauri/target/release/bundle/msi/*.msi
```

### Mac
```bash
cd frontend
npm install
npm run tauri build
# Genera: src-tauri/target/release/bundle/dmg/*.dmg
```

## Funcionalidades

- Dashboard con estadísticas
- Gestión de clientes (con CUIT para facturación)
- Gestión de productos
- Control de materiales
- Ventas
- **Facturación ARCA/AFIP** (Facturas A, B, C)
- Buscador global integrado en el navbar

## Facturación AFIP

Para usar facturación real con AFIP/ARCA necesitas:

1. Obtener un certificado digital de ARCA (https://www.afip.gob.ar/)
2. Colocar el certificado en la carpeta del backend
3. Configurar el CUIT de la empresa en el sistema

El sistema actualmente usa simulación de CAE para pruebas.
