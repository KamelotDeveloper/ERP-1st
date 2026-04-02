import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import Clients from "./pages/Clients";
import Products from "./pages/Products";
import Materials from "./pages/Materials";
import Sales from "./pages/Sales";
import Invoices from "./pages/Invoices";
import ElectronicInvoicing from "./pages/ElectronicInvoicing";
import Profile from "./pages/Profile";
import Produccion from "./pages/Produccion";
import Budget from "./pages/Budget";

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <Sidebar />
        <div className="main">
          <Navbar />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/clients" element={<Clients />} />
            <Route path="/products" element={<Products />} />
            <Route path="/materials" element={<Materials />} />
            <Route path="/sales" element={<Sales />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/electronic-invoicing" element={<ElectronicInvoicing />} />
            <Route path="/produccion" element={<Produccion />} />
            <Route path="/budget" element={<Budget />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}