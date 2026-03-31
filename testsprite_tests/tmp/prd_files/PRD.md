# GA ERP - Carpintería El Menestral

## Product Requirements Document (PRD)

---

## 1. Product Overview

### What is GA ERP?

**GA ERP** (Gestión Administrativa ERP) is a full-stack enterprise resource planning system designed specifically for a carpentry business ("Carpintería El Menestral") in Argentina.

### Core Functionality

A web-based ERP system that manages the complete business operations of a carpentry workshop, including:
- **Client Management** with tax identification (CUIT) for electronic invoicing
- **Product Inventory** with stock tracking
- **Material Control** with stock movements (IN/OUT)
- **Sales Management** with automatic stock deduction
- **Electronic Invoicing** integrated with ARCA/AFIP (Argentine tax authority)
- **Dashboard** with business analytics

### Target Users

1. **Business Owner** - Manages all operations
2. **Administrative Staff** - Handles invoices and client data
3. **Warehouse Staff** - Tracks materials and inventory

---

## 2. Features Specification

### 2.1 Dashboard
- **Summary Cards**: Display total clients, products, materials, and sales revenue
- **Charts**: Visual representation of business metrics
- **Quick Stats**: Real-time business overview

### 2.2 Client Management
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-generated primary key |
| name | STRING | Client full name |
| email | STRING | Contact email |
| phone | STRING | Contact phone |
| address | STRING | Physical address (optional) |
| tax_id | STRING | CUIT for invoicing (optional) |

**CRUD Operations:**
- Create new client
- List all clients
- Edit client information
- Delete client

**Export:** Download client list as Excel file

### 2.3 Product Management
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-generated primary key |
| sku | STRING | Stock Keeping Unit code |
| name | STRING | Product name |
| price | FLOAT | Unit price (ARS) |
| stock | INTEGER | Current stock quantity |

**CRUD Operations:**
- Create new product
- List all products
- Edit product details
- Delete product
- **Restock**: Add stock to existing product

**Stock Logic:** Stock is manually managed (no automatic deduction on sales in this module)

### 2.4 Material Management
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-generated primary key |
| sku | STRING | Material SKU code |
| name | STRING | Material name |
| category | STRING | Material category |
| unit_cost | FLOAT | Cost per unit |
| stock | FLOAT | Calculated: (total IN) - (total OUT) |

**Stock Movement Tracking:**
- **IN**: Material enters warehouse (initial stock, purchases)
- **OUT**: Material leaves warehouse (usage in production)

**Features:**
- Automatic stock calculation
- Total value calculation (stock × unit_cost)
- Movement history per material

### 2.5 Sales Management
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-generated primary key |
| client_id | INTEGER | Foreign key to clients |
| total | FLOAT | Sale total amount |
| date | DATETIME | Sale timestamp |

**Sale Items:**
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-generated primary key |
| sale_id | INTEGER | Foreign key to sales |
| product_id | INTEGER | Foreign key to products |
| quantity | INTEGER | Units sold |
| price | FLOAT | Price at time of sale |

**Features:**
- Create sale with multiple products
- **Automatic stock deduction** when sale is created
- Stock validation (cannot sell more than available)

### 2.6 Electronic Invoicing (ARCA/AFIP)

#### Setup Wizard (4 Steps)
1. **Configure Contributor Data**
   - Business name (razón social)
   - CUIT (validated with official algorithm)
   - Point of sale number
   - Environment: Testing / Production

2. **Upload Certificate**
   - Digital certificate (.pem, .crt, .cer)
   - Private key (.key, .pem)
   - Certificate validation and expiration check

3. **Test Connection**
   - Connects to ARCA/AFIP WSAA service
   - Obtains authentication token
   - Validates credentials

4. **Enable System**
   - Activates electronic invoicing
   - System ready to emit real CAE

#### Invoice Emission
| Feature | Description |
|---------|-------------|
| Invoice Types | Factura A, B, C |
| CAE Request | Real CAE from ARCA (when configured) or simulated |
| Invoice Number | Auto-generated (PuntoVenta-Numero) |
| IVA Calculation | 21% automatic |
| Response Mode | "real" or "simulated" indicator |

#### Invoice Fields
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-generated primary key |
| sale_id | INTEGER | Optional link to sale |
| client_id | INTEGER | Foreign key to clients |
| cae | STRING | Electronic Authorization Code |
| cae_vto | DATETIME | CAE expiration date |
| punto_venta | INTEGER | Point of sale number |
| numero | INTEGER | Invoice sequence number |
| tipo_factura | INTEGER | 1=A, 6=B, 11=C |
| subtotal | FLOAT | Pre-tax amount |
| iva | FLOAT | 21% tax amount |
| total | FLOAT | Final amount |
| estado | STRING | draft, issued, error |
| fecha | DATETIME | Invoice creation date |

### 2.7 Global Search
- Search across all entities (clients, products, materials)
- Real-time search results
- Quick navigation to entity pages

### 2.8 Export Features
- Export clients to Excel
- Export products to Excel
- Export materials to Excel

---

## 3. Technical Architecture

### Backend (Python/FastAPI)
- **Framework**: FastAPI
- **ORM**: SQLAlchemy
- **Database**: SQLite
- **API Style**: RESTful

### Frontend (React)
- **Framework**: React 18
- **Build Tool**: Vite
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **Charts**: Recharts
- **Desktop**: Tauri 2.0

### Key Files Structure
```
backend/
├── main.py                    # FastAPI entry point
├── models.py                  # Database models
├── schemas.py                 # Pydantic schemas
├── routers/
│   ├── api.py                # CRUD endpoints
│   ├── invoices.py            # Invoice endpoints
│   └── electronic_invoicing.py # AFIP setup
└── services/
    ├── afip_service.py        # AFIP utilities
    └── wsfe_client.py        # WSFE integration

frontend/src/
├── pages/
│   ├── Dashboard.jsx
│   ├── Clients.jsx
│   ├── Products.jsx
│   ├── Materials.jsx
│   ├── Sales.jsx
│   ├── Invoices.jsx
│   └── ElectronicInvoicing.jsx
└── components/
    ├── Sidebar.jsx
    └── Navbar.jsx
```

---

## 4. TestSprite Testing Requirements

### 4.1 Backend Tests

#### Authentication & Health
- [ ] `GET /health` returns `{"status": "ok"}`

#### Client Management
- [ ] `POST /clients` creates a new client
- [ ] `GET /clients` returns list of clients
- [ ] `GET /clients/{id}` returns specific client
- [ ] `PUT /clients/{id}` updates client
- [ ] `DELETE /clients/{id}` removes client
- [ ] `GET /clients/{id}` returns 404 for non-existent

#### Product Management
- [ ] `POST /products` creates product
- [ ] `GET /products` returns all products
- [ ] `PUT /products/{id}` updates product
- [ ] `PUT /products/{id}/restock` adds stock
- [ ] `DELETE /products/{id}` removes product
- [ ] Stock validation on restock (positive numbers only)

#### Material Management
- [ ] `POST /materials` creates material with initial stock
- [ ] `GET /materials` returns materials with calculated stock
- [ ] `PUT /materials/{id}` updates and adjusts stock
- [ ] Stock calculation: (IN movements) - (OUT movements)

#### Sales Management
- [ ] `POST /sales` creates sale with items
- [ ] Stock is deducted when sale is created
- [ ] Returns error if insufficient stock
- [ ] `GET /sales` returns all sales

#### Invoices
- [ ] `POST /invoices` creates invoice
- [ ] `GET /invoices` returns all invoices
- [ ] `GET /invoices/{id}` returns specific invoice with client info
- [ ] CAE is generated (simulated if no certificate)
- [ ] Response includes `modo: "real"` or `modo: "simulado"`

#### Electronic Invoicing Setup
- [ ] `GET /electronic-invoicing/status` returns configuration
- [ ] `POST /electronic-invoicing/setup` configures basic data
- [ ] CUIT validation (11 digits, valid check digit)
- [ ] `POST /electronic-invoicing/upload-certificate` accepts files
- [ ] `POST /electronic-invoicing/test-connection` tests WSAA
- [ ] `POST /electronic-invoicing/enable` activates system
- [ ] `POST /electronic-invoicing/check-cert-expiry` returns cert status

#### Dashboard & Search
- [ ] `GET /dashboard` returns summary statistics
- [ ] `GET /search?q=term` returns search results

### 4.2 Frontend Tests

#### Navigation
- [ ] Sidebar displays all menu items
- [ ] Navigation links work correctly
- [ ] Global search in navbar works

#### Client Page
- [ ] Client form creates new client
- [ ] Client list displays all clients
- [ ] Edit button populates form
- [ ] Delete removes client
- [ ] Export button downloads Excel

#### Product Page
- [ ] Product form creates product
- [ ] Stock display updates after restock
- [ ] Edit and delete work correctly

#### Material Page
- [ ] Material form with initial stock
- [ ] Stock movements display correctly
- [ ] Calculated values shown

#### Sales Page
- [ ] Sale form with multiple items
- [ ] Total calculation correct
- [ ] Sale creates successfully
- [ ] Stock deducted after sale

#### Invoice Page
- [ ] Invoice form with item selection
- [ ] IVA calculation (21%)
- [ ] Invoice creates with CAE
- [ ] Invoice list displays all
- [ ] Status badges display correctly

#### Electronic Invoicing Page
- [ ] Setup wizard renders correctly
- [ ] Step navigation works
- [ ] Status display shows current state
- [ ] Certificate upload form works
- [ ] Test connection button works
- [ ] Enable/disable toggle works

#### Dashboard
- [ ] Stats cards display correctly
- [ ] Charts render
- [ ] Data updates when entities change

### 4.3 Integration Tests

- [ ] Create client → Create invoice → Invoice shows client name
- [ ] Create product → Create sale → Stock decreases
- [ ] Full invoicing flow (client + products → invoice)
- [ ] Export generates downloadable file

---

## 5. Test Data Requirements

### Required Test Entities

#### Client
```json
{
  "name": "Cliente de Prueba SRL",
  "email": "test@cliente.com",
  "phone": "1155551234",
  "address": "Calle Falsa 123",
  "tax_id": "30678765438"
}
```

#### Products (minimum 3)
```json
[
  {"sku": "MAD-001", "name": "Puerta de madera", "price": 15000, "stock": 10},
  {"sku": "MAD-002", "name": "Ventana corrediza", "price": 8500, "stock": 15},
  {"sku": "MAD-003", "name": "Mesa de madera", "price": 22000, "stock": 5}
]
```

#### Materials (minimum 2)
```json
[
  {"sku": "MAT-001", "name": "Madera pine", "category": "Madera", "stock": 100, "unit_cost": 500},
  {"sku": "MAT-002", "name": "Clavos 2 pulgadas", "category": "Herrajes", "stock": 500, "unit_cost": 50}
]
```

---

## 6. Environment Setup

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Test Sprite Configuration
```javascript
{
  "projectPath": "C:\\Users\\Giuliano\\Desktop\\GA_ERP_FIXED",
  "localPort": 8000,
  "backendPort": 8000,
  "frontendPort": 5173,
  "apiBaseUrl": "http://127.0.0.1:8000"
}
```

---

## 7. Success Criteria

The application is considered complete when:

1. ✅ All CRUD operations work for all entities
2. ✅ Stock calculations are accurate
3. ✅ Electronic invoicing setup wizard completes successfully
4. ✅ Invoices generate with CAE (real or simulated)
5. ✅ Dashboard displays accurate statistics
6. ✅ All pages render without errors
7. ✅ Export features generate downloadable files
8. ✅ Search functionality returns correct results

---

## 8. Known Limitations

1. **No User Authentication** - Currently no login system
2. **No Role-Based Access** - All users have full access
3. **SQLite Database** - Single-user, no concurrent writes
4. **CAE Simulation** - Without certificate, CAE is simulated
5. **Manual Stock** - Product stock requires manual restocking

---

*Document Version: 1.0*
*Last Updated: 2026-03-21*
