import {useEffect,useState} from "react"
import api from "../services/api"

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

<h1>Dashboard</h1>

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