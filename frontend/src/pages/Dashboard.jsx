import {useEffect,useState} from "react"
import api from "../services/api"
import {useAlertasStock} from "../services/useAlertasStock"

import{
BarChart,
Bar,
LineChart,
Line,
CartesianGrid,
XAxis,
YAxis,
Tooltip,
ResponsiveContainer
}from"recharts"

export default function Dashboard(){

const [data,setData]=useState(null)
const [showAlertas, setShowAlertas] = useState(false)
const { alertas, count } = useAlertasStock();

const load=async()=>{
const r=await api.get("/dashboard")
setData(r.data)
}

useEffect(()=>{load()},[])

if(!data){
return <div className="container">Cargando dashboard...</div>
}

const systemData=[
{name:"Clientes",value:data.clients},
{name:"Productos",value:data.products},
{name:"Materiales",value:data.materials}
]

const monthly=data.monthly_sales || []

const top=data.top_products || []

return(

<div className="container">

<h1>Dashboard {count > 0 && (
  <span 
    onClick={() => setShowAlertas(!showAlertas)}
    style={{ 
      cursor: "pointer", 
      marginLeft: "15px",
      padding: "5px 12px",
      background: "#ef4444",
      color: "white",
      borderRadius: "12px",
      fontSize: "14px"
    }}
  >
    ⚠ {count} alerta{count !== 1 ? 's' : ''}
  </span>
)}

{showAlertas && count > 0 && (
  <div style={{ 
    marginTop: "15px", 
    padding: "15px", 
    background: "#fef2f2", 
    border: "1px solid #fecaca",
    borderRadius: "8px"
  }}>
    <h4 style={{ margin: "0 0 10px 0", color: "#991b1b" }}>Materiales con stock bajo:</h4>
    {alertas.map(a => (
      <div key={a.id} style={{ 
        display: "flex", 
        alignItems: "center", 
        gap: "8px", 
        padding: "8px 0",
        borderBottom: "1px solid #fecaca"
      }}>
        <span style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: a.stock === 0 ? "#ef4444" : "#f59e0b"
        }}></span>
        <span style={{ flex: 1 }}>{a.nombre}</span>
        <span style={{ color: "#666" }}>Stock: {a.stock} / Min: {a.stock_minimo}</span>
      </div>
    ))}
  </div>
)}
</h1>

<div className="dashboard-grid">

<div className="card">
<h3>Clientes</h3>
<p>{data.clients}</p>
</div>

<div className="card">
<h3>Productos</h3>
<p>{data.products}</p>
</div>

<div className="card">
<h3>Materiales</h3>
<p>{data.materials}</p>
</div>

<div className="card">
<h3>Ventas</h3>
<p>${data.sales}</p>
</div>

</div>


<div className="charts-grid">

<div className="chart-card">

<h3>Distribución del sistema</h3>

<ResponsiveContainer width="100%" height={300}>

<BarChart data={systemData}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="name"/>

<YAxis/>

<Tooltip/>

<Bar dataKey="value" fill="#22382c"/>

</BarChart>

</ResponsiveContainer>

</div>


<div className="chart-card">

<h3>Ventas por mes</h3>

<ResponsiveContainer width="100%" height={300}>

<LineChart data={monthly}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="month"/>

<YAxis/>

<Tooltip/>

<Line
type="monotone"
dataKey="total"
stroke="#22382c"
strokeWidth={3}
/>

</LineChart>

</ResponsiveContainer>

</div>


<div className="chart-card">

<h3>Productos más vendidos</h3>

<ResponsiveContainer width="100%" height={300}>

<BarChart data={top}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="product"/>

<YAxis/>

<Tooltip/>

<Bar dataKey="qty" fill="#f59e0b"/>

</BarChart>

</ResponsiveContainer>

</div>

</div>

</div>

)

}