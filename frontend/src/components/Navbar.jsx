import {useState} from "react";
import api from "../services/api";
import {useNavigate} from "react-router-dom";

export default function Navbar(){

const [q,setQ]=useState("");
const [results,setResults]=useState([]);
const navigate = useNavigate();

const search = async (value)=>{
setQ(value);

if(value.length<2){
setResults([]);
return;
}

const r = await api.get(`/search?q=${value}`);
setResults(r.data);
}

const go = (r)=>{
setResults([]);
setQ("");
navigate(`${r.page}?highlight=${r.id}`);
}

return (
<div className="navbar">
  <div className="navbar-title">El Menestral</div>
  
  <div className="navbar-search">
    <input
      placeholder="Buscar cliente, producto, material..."
      value={q}
      onChange={e=>search(e.target.value)}
    />
    
    {results.length>0 && (
      <div className="search-results">
        {results.map((r,i)=>(
          <div
            key={i}
            className="search-item"
            onClick={()=>go(r)}
          >
            {r.label}
          </div>
        ))}
      </div>
    )}
  </div>
  
  <div></div>
</div>
)}
