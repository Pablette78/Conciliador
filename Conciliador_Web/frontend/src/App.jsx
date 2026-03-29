import { useState, useMemo, useEffect } from 'react'
import axios from 'axios'
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'
import { 
  Upload, FileCheck, AlertCircle, Download, Settings, History, 
  LayoutDashboard, Building2, Trash2, Search, Bell, User,
  TrendingUp, Clock, CheckCircle2, CreditCard, ChevronDown, ListCheck,
  FileText, Activity, Layers, Lock, LogOut, ExternalLink
} from 'lucide-react'

// --- Configuración Global ---
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const BANCOS = [
  "— auto —", "Banco Santander", "Banco Galicia", "Banco BBVA", "Banco Bancor",
  "Banco Provincia", "Banco Nación", "Banco Credicoop", "Banco HSBC",
  "Banco ICBC", "Banco Macro", "Banco Ciudad", "Banco Comafi", "ARCA-Mis Retenciones"
]

const COLORS = ['#3B82F6', '#F59E0B', '#10B981', '#6366F1']

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [apiKey, setApiKey] = useState("")
  const [loginError, setLoginError] = useState(null)
  
  const [banco, setBanco] = useState("— auto —")
  const [extractos, setExtractos] = useState([])
  const [mayores, setMayores] = useState([])
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)
  const [view, setView] = useState('dashboard')
  const [tableTab, setTableTab] = useState('banco')

  // Cargar sesión
  useEffect(() => {
    const savedKey = localStorage.getItem('conciliador_key')
    if (savedKey) {
      setApiKey(savedKey)
      setIsAuthenticated(true)
    }
  }, [])

  const handleLogin = (e) => {
    e.preventDefault()
    if (apiKey.length < 5) {
      setLoginError("La clave es demasiado corta.")
      return
    }
    localStorage.setItem('conciliador_key', apiKey)
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    localStorage.removeItem('conciliador_key')
    setIsAuthenticated(false)
    setApiKey("")
    setResultado(null)
  }

  // --- Handlers Operativos ---
  const handleConciliar = async () => {
    if (extractos.length === 0 || mayores.length === 0) {
      setError("Debes cargar al menos un extracto y un mayor.")
      return
    }
    setLoading(true)
    setError(null)
    const formData = new FormData()
    formData.append('banco', banco)
    extractos.forEach(f => formData.append('extractos', f))
    mayores.forEach(f => formData.append('mayores', f))

    try {
      const resp = await axios.post(`${API_BASE_URL}/api/conciliar`, formData, {
        headers: { 'X-API-KEY': apiKey }
      })
      if (resp.data.success) {
        setResultado(resp.data)
        setTableTab('banco')
      }
    } catch (err) {
      setError(err.response?.status === 403 ? "Error de autenticación. Verifica tu clave." : (err.response?.data?.detail || "Error en el servidor"))
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    if (!resultado?.fileId) return
    try {
      const resp = await axios.get(`${API_BASE_URL}/api/download/${resultado.fileId}`, { 
        responseType: 'blob',
        headers: { 'X-API-KEY': apiKey }
      })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', resultado.filename)
      document.body.appendChild(link)
      link.click()
    } catch (err) {
      setError("Error al descargar el archivo.")
    }
  }

  // --- Datos Visuales ---
  const pieData = useMemo(() => {
    if (!resultado?.summary) return []
    const { n_conc, n_banco, n_sist, n_diff } = resultado.summary
    return [
      { name: 'Conciliados', value: n_conc },
      { name: 'Solo Banco', value: n_banco },
      { name: 'Solo Sistema', value: n_sist },
      { name: 'Diferencias', value: n_diff }
    ]
  }, [resultado])

  const tableData = useMemo(() => {
    if (!resultado?.summary) return []
    if (tableTab === 'banco') return resultado.summary.solo_banco
    if (tableTab === 'sistema') return resultado.summary.solo_sistema
    if (tableTab === 'gastos') return resultado.summary.gastos
    return []
  }, [resultado, tableTab])

  // --- Vistas ---
  if (!isAuthenticated) {
    return (
      <div className="h-screen w-full bg-brand-dark flex items-center justify-center p-6 bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')]">
        <div className="card-premium p-10 max-w-md w-full animate-fade-in border-brand-blue/20 bg-brand-card/80 backdrop-blur-xl">
           <div className="flex justify-center mb-8">
              <div className="bg-brand-blue/20 p-4 rounded-3xl border border-brand-blue/30 shadow-2xl shadow-brand-blue/20">
                <Lock className="text-brand-blue" size={40} />
              </div>
           </div>
           <h1 className="text-2xl font-black text-center mb-2 tracking-tight">Acceso Seguro</h1>
           <p className="text-slate-400 text-sm text-center mb-8">Introduce tu clave de acceso proporcionada para las pruebas del Conciliador Flow.</p>
           
           <form onSubmit={handleLogin} className="space-y-4">
              <input 
                type="password" 
                placeholder="Clave de acceso" 
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full bg-brand-dark border border-white/10 rounded-2xl py-4 px-6 text-center text-lg font-bold tracking-widest focus:ring-2 focus:ring-brand-blue/30 outline-none transition-all"
              />
              <button type="submit" className="w-full bg-brand-blue hover:bg-blue-600 text-white py-4 rounded-2xl font-black text-sm tracking-widest shadow-xl shadow-brand-blue/20 transition-all active:scale-95">
                 ENTRAR AL SISTEMA
              </button>
           </form>
           {loginError && <p className="text-rose-500 text-xs text-center mt-4 font-bold uppercase tracking-widest">{loginError}</p>}
           
           <div className="mt-10 pt-8 border-t border-white/5 flex flex-col items-center">
              <p className="text-[10px] text-slate-600 font-black uppercase tracking-widest mb-4">Mantenido por Pablo Ponti</p>
              <div className="flex space-x-4">
                 <div className="h-1.5 w-1.5 bg-emerald-500 rounded-full"></div>
                 <div className="h-1.5 w-1.5 bg-brand-blue rounded-full"></div>
              </div>
           </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-brand-dark text-slate-100 font-sans overflow-hidden">
      {/* --- Sidebar --- */}
      <aside className="w-68 glass-sidebar flex flex-col z-30 shadow-2xl">
        <div className="p-8 flex items-center space-x-4 mb-8">
          <div className="bg-brand-blue p-2.5 rounded-2xl shadow-lg shadow-brand-blue/30">
            <Activity className="text-white" size={26} />
          </div>
          <span className="text-xl font-extrabold tracking-tight">Conciliador <span className="text-brand-blue">Flow</span></span>
        </div>

        <nav className="flex-1 px-4 space-y-2">
          <SidebarLink active={view === 'dashboard'} icon={<LayoutDashboard size={20}/>} label="Dashboard" onClick={() => setView('dashboard')}/>
          <SidebarLink icon={<History size={20}/>} label="Historial Cloud" />
          <SidebarLink icon={<Settings size={20}/>} label="Configuración" />
          <button onClick={handleLogout} className="flex items-center space-x-4 w-full px-6 py-4 rounded-2xl text-rose-500 hover:bg-rose-500/10 transition-all font-bold mt-auto border-t border-white/5 pt-8">
             <LogOut size={20}/> <span className="text-sm">Salir</span>
          </button>
        </nav>
      </aside>

      {/* --- Main --- */}
      <div className="flex-1 flex flex-col">
        {/* --- Top Bar --- */}
        <header className="h-20 flex items-center justify-between px-10 border-b border-white/5 bg-brand-dark/40 backdrop-blur-xl z-20">
          <div className="flex items-center space-x-4">
             <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-1.5 flex items-center space-x-2">
                <span className="text-[10px] font-black text-emerald-500 uppercase">Producción</span>
                <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full shadow-lg shadow-emerald-500/50"></div>
             </div>
             <p className="text-xs text-slate-500 font-bold hidden md:block">{API_BASE_URL}</p>
          </div>
          
          <div className="flex items-center space-x-6">
            <UserProfile name="P. Ponti" role="Testing Mode" />
          </div>
        </header>

        {/* --- Content --- */}
        <main className="flex-1 overflow-y-auto p-10 space-y-10 scrollbar-hide">
          <div className="flex justify-between items-end">
            <div>
              <h2 className="text-4xl font-black tracking-tight mb-2">Operación en Nube</h2>
              <p className="text-slate-400 font-medium tracking-wide">Procesando datos en servidores distribuidos (Phase 7: Cloud Beta).</p>
            </div>
          </div>

          {/* --- KPI Cards --- */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <KPICard label="Items Conciliados" value={resultado?.summary ? `${resultado.summary.n_conc}` : "0"} icon={<CheckCircle2 className="text-brand-blue"/>} />
            <KPICard label="Diferencias" value={resultado?.summary ? `${resultado.summary.n_diff}` : "0"} icon={<AlertCircle className="text-amber-500"/>} />
            <KPICard label="Gastos" value={resultado?.summary ? `$${resultado.summary.total_gastos.toLocaleString()}` : "$0"} icon={<Layers className="text-emerald-500"/>} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <div className="lg:col-span-8 flex flex-col space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 flex-1">
                <Card title="Resultados">
                  <div className="h-64 mt-4">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                          {pieData.map((_, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                        </Pie>
                        <Legend iconType="circle" />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
                <div className="card-premium p-8 flex flex-col justify-center items-center text-center space-y-4">
                   <div className="bg-brand-blue/10 p-4 rounded-3xl">
                      <ExternalLink className="text-brand-blue" size={32} />
                   </div>
                   <h4 className="font-black text-sm uppercase tracking-widest">Servidor Activo</h4>
                   <p className="text-xs text-slate-500 font-medium">Conectado a Render.com vía WebSockets y REST. Latencia medida: <span className="text-emerald-400 font-bold">120ms</span></p>
                </div>
              </div>
            </div>

            {/* Upload Widget */}
            <div className="lg:col-span-4 card-premium p-8 flex flex-col bg-brand-card/30 border-white/5">
              <h3 className="text-lg font-bold mb-6 flex items-center space-x-2">
                 <Upload size={20} className="text-brand-blue" />
                 <span>Subida en Nube</span>
              </h3>
              <div 
                className="flex-1 border-2 border-dashed border-white/10 rounded-3xl flex flex-col items-center justify-center p-6 hover:bg-white/2 transition-all group"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                   e.preventDefault()
                   const files = Array.from(e.dataTransfer.files)
                   const p_ext = files.filter(f => f.name.toLowerCase().endsWith('.pdf'))
                   const p_may = files.filter(f => !f.name.toLowerCase().endsWith('.pdf'))
                   if (p_ext.length) setExtractos(prev => [...prev, ...p_ext])
                   if (p_may.length) setMayores(prev => [...prev, ...p_may])
                }}
              >
                <div className="mb-6 space-y-2 w-full">
                   {extractos.map((f, i) => <FileBadge key={i} name={f.name} onRemove={() => setExtractos(prev => prev.filter((_, idx) => idx !== i))} />)}
                   {mayores.map((f, i) => <FileBadge key={i} name={f.name} onRemove={() => setMayores(prev => prev.filter((_, idx) => idx !== i))} />)}
                </div>
                <input type="file" multiple id="file_btn" className="hidden" 
                   onChange={(e) => {
                      const files = Array.from(e.target.files)
                      setExtractos(prev => [...prev, ...files.filter(f => f.name.toLowerCase().endsWith('.pdf'))])
                      setMayores(prev => [...prev, ...files.filter(f => !f.name.toLowerCase().endsWith('.pdf'))])
                   }} 
                />
                <label htmlFor="file_btn" className="bg-brand-blue text-white px-8 py-3 rounded-2xl font-black text-xs hover:bg-blue-600 cursor-pointer transition-all shadow-xl shadow-brand-blue/30">
                  CARGAR ARCHIVOS
                </label>
              </div>
            </div>
          </div>

          {/* --- Controls --- */}
          <div className="flex flex-col items-center space-y-6">
             <div className="flex bg-brand-card/50 p-2 rounded-2xl border border-white/5 px-6">
                <select value={banco} onChange={(e) => setBanco(e.target.value)} className="bg-transparent text-sm font-black focus:outline-none focus:text-brand-blue cursor-pointer">
                   {BANCOS.map(b => <option key={b} value={b} className="bg-brand-card">{b}</option>)}
                </select>
             </div>
             <button onClick={handleConciliar} disabled={loading} className={`w-full max-w-xl py-5 rounded-3xl font-black text-xl flex items-center justify-center space-x-4 shadow-2xl transition-all active:scale-95 ${loading ? 'bg-slate-800 text-slate-500' : 'bg-brand-blue hover:bg-blue-600 shadow-brand-blue/30'}`}>
                {loading ? <LoadingSpinner /> : <><CheckCircle2 size={24}/><span>INICIAR CONCILIACIÓN</span></>}
             </button>
             {error && <p className="text-rose-400 font-bold text-sm tracking-widest uppercase">{error}</p>}
          </div>

          {/* --- Results --- */}
          {resultado && (
            <div className="animate-fade-in space-y-10">
               <div className="card-premium p-10 bg-gradient-to-br from-emerald-500/10 to-transparent border-emerald-500/20 text-center relative">
                  <h3 className="text-3xl font-black mb-4">Reporte Generado</h3>
                  <button onClick={handleDownload} className="bg-emerald-600 hover:bg-emerald-500 text-white px-12 py-5 rounded-3xl font-black text-xl flex items-center space-x-4 mx-auto shadow-2xl shadow-emerald-500/30 transition-all hover:scale-105">
                    <Download size={24}/> <span>DESCARGAR EXCEL DE PRODUCCIÓN</span>
                  </button>
               </div>

               <div className="card-premium overflow-hidden">
                  <div className="p-8 border-b border-white/5 flex gap-4">
                     <TabBtn active={tableTab === 'banco'} onClick={() => setTableTab('banco')} label="En Banco" count={resultado.summary.n_banco} />
                     <TabBtn active={tableTab === 'sistema'} onClick={() => setTableTab('sistema')} label="En Sistema" count={resultado.summary.n_sist} />
                  </div>
                  <div className="overflow-x-auto max-h-[500px]">
                     <table className="w-full text-left text-sm">
                        <thead className="sticky top-0 bg-brand-card border-b border-white/5 text-slate-500 font-bold">
                           <tr>
                              <th className="px-8 py-5">Fecha</th>
                              <th className="px-8 py-5">Concepto</th>
                              <th className="px-8 py-5 text-right">Monto</th>
                           </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                           {tableData.map((row, i) => (
                              <tr key={i} className="hover:bg-white/2 transition-all">
                                 <td className="px-8 py-5 text-slate-400">{row.fecha}</td>
                                 <td className="px-8 py-5 font-bold">{row.concepto}</td>
                                 <td className={`px-8 py-5 text-right font-black ${row.monto < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>${row.monto.toLocaleString()}</td>
                              </tr>
                           ))}
                        </tbody>
                     </table>
                  </div>
               </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

// --- Sub-componentes ---
function KPICard({ label, value, icon }) {
  return (
    <div className="card-premium p-8 group hover:border-brand-blue/30 transition-all">
       <div className="bg-brand-dark/40 p-3 rounded-2xl border border-white/5 mb-6 w-fit">{icon}</div>
       <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">{label}</p>
       <p className="text-3xl font-black tracking-tighter">{value}</p>
    </div>
  )
}
function SidebarLink({ icon, label, active, onClick }) {
  return (
    <button onClick={onClick} className={`flex items-center space-x-4 w-full px-6 py-4 rounded-2xl transition-all ${active ? 'bg-brand-blue/10 text-brand-blue font-black' : 'text-slate-500 hover:text-slate-300'}`}>
      {icon} <span className="text-xs uppercase tracking-widest">{label}</span>
    </button>
  )
}
function Card({ title, children }) {
  return (
    <div className="card-premium p-8 bg-brand-card/30 flex flex-col">
       <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-4">{title}</h3>
       <div className="flex-1">{children}</div>
    </div>
  )
}
function FileBadge({ name, onRemove }) {
  return (
    <div className="flex items-center justify-between bg-white/5 border border-white/5 rounded-xl px-4 py-2">
       <div className="flex items-center space-x-3 overflow-hidden">
          <FileText size={14} className="text-brand-blue" />
          <span className="text-[10px] font-bold truncate text-slate-400">{name}</span>
       </div>
       <button onClick={onRemove} className="text-slate-600 hover:text-rose-500 ml-4"><Trash2 size={12}/></button>
    </div>
  )
}
function TabBtn({ active, onClick, label, count }) {
  return (
    <button onClick={onClick} className={`px-5 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${active ? 'bg-brand-blue text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}>
       {label} <span className="ml-2 opacity-50">{count}</span>
    </button>
  )
}
function UserProfile({ name, role }) {
  return (
    <div className="flex items-center space-x-4 cursor-pointer group">
      <div className="text-right">
        <p className="text-sm font-black group-hover:text-brand-blue transition-colors leading-tight">{name}</p>
        <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{role}</p>
      </div>
      <div className="h-10 w-10 rounded-2xl bg-brand-blue/20 border border-brand-blue/20 flex items-center justify-center group-hover:scale-105 transition-transform"><User className="text-brand-blue" size={24}/></div>
    </div>
  )
}
function LoadingSpinner() {
  return (
    <div className="flex items-center space-x-4">
       <div className="w-6 h-6 border-4 border-slate-700 border-t-white rounded-full animate-spin"></div>
       <span className="text-xs font-black tracking-widest uppercase">Procesando en Render...</span>
    </div>
  )
}

export default App
