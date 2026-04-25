import { useState, useMemo, useEffect, useCallback } from 'react'
import axios from 'axios'
import LandingPage from './LandingPage'
import {
  PieChart, Pie, Cell, Legend, ResponsiveContainer
} from 'recharts'
import {
  Upload, AlertCircle, Download, LayoutDashboard,
  CheckCircle2, Layers, Lock, LogOut, FileText,
  Activity, User, Trash2, Users, Plus, Shield,
  Eye, EyeOff, RefreshCw, Sun, Moon, Edit
} from 'lucide-react'

// --- Config ---
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

const BANCOS = [
  "— auto —",
  "Banco Santander", "Banco Galicia", "Banco BBVA", "Banco Bancor",
  "Banco Provincia", "Banco Nación", "Banco Credicoop", "Banco HSBC",
  "Banco ICBC", "Banco Macro", "Banco Patagonia", "Banco Supervielle",
  "Banco Ciudad", "Banco Comafi",
  "ARCA-Mis Retenciones", "American Express", "Tarjeta VISA",
]

const ALLOWED_EXTENSIONS = ['.pdf', '.xlsx', '.xls']
const MAX_FILE_SIZE_MB = 50
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
const COLORS = ['#3B82F6', '#F59E0B', '#10B981', '#6366F1']

function validarArchivo(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  if (!ALLOWED_EXTENSIONS.includes(ext))
    return `Tipo no permitido: "${file.name}". Solo PDF, XLSX y XLS.`
  if (file.size > MAX_FILE_SIZE_BYTES)
    return `"${file.name}" supera el límite de ${MAX_FILE_SIZE_MB} MB.`
  return null
}

// Axios con token automático
const api = axios.create({ baseURL: API_BASE_URL })
api.interceptors.request.use(cfg => {
  const token = sessionStorage.getItem('token')
  if (token) cfg.headers['Authorization'] = `Bearer ${token}`
  return cfg
})

// ============================================================
// APP
// ============================================================
export default function App() {
  const [token, setToken]       = useState(() => sessionStorage.getItem('token'))
  const [usuario, setUsuario]   = useState(null)
  const [loginError, setLoginError] = useState(null)
  const [theme, setTheme]       = useState(() => localStorage.getItem('theme') || 'dark')

  const [view, setView]         = useState('dashboard')
  const [banco, setBanco]       = useState("— auto —")
  const [extractos, setExtractos] = useState([])
  const [mayores, setMayores]   = useState([])
  const [loading, setLoading]   = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error, setError]       = useState(null)
  const [tableTab, setTableTab] = useState('banco')

  useEffect(() => {
    document.documentElement.className = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  // Cargar datos del usuario al tener token
  useEffect(() => {
    if (!token) return
    api.get('/auth/me')
      .then(r => setUsuario(r.data))
      .catch(() => handleLogout())
  }, [token])

  const handleLogin = async ({ username, password }) => {
    setLoginError(null)
    try {
      const r = await axios.post(`${API_BASE_URL}/auth/login`, { username, password })
      sessionStorage.setItem('token', r.data.access_token)
      setToken(r.data.access_token)
      setUsuario(r.data.usuario)
    } catch (err) {
      setLoginError(err.response?.data?.detail || "Error de conexión.")
    }
  }

  const handleRegister = async ({ username, password, rol, plan }) => {
    setLoginError(null)
    try {
      await axios.post(`${API_BASE_URL}/auth/usuarios`, { username, password, rol, plan })
      // Auto-login tras registro
      await handleLogin({ username, password })
      return true
    } catch (err) {
      setLoginError(err.response?.data?.detail || "Error al crear cuenta.")
      return false
    }
  }

  const handleLogout = () => {
    sessionStorage.removeItem('token')
    setToken(null)
    setUsuario(null)
    setResultado(null)
    setError(null)
    setView('dashboard')
  }

  const agregarArchivos = (files) => {
    const errores = [], pdfs = [], excels = []
    for (const f of files) {
      const err = validarArchivo(f)
      if (err) { errores.push(err); continue }
      const ext = '.' + f.name.split('.').pop().toLowerCase()
      ext === '.pdf' ? pdfs.push(f) : excels.push(f)
    }
    if (errores.length) setError(errores.join(' | '))
    else setError(null)
    if (pdfs.length) setExtractos(p => [...p, ...pdfs])
    if (excels.length) setMayores(p => [...p, ...excels])
  }

  const handleConciliar = async () => {
    if (!extractos.length || !mayores.length) {
      setError("Cargá al menos un extracto (PDF) y un mayor (Excel).")
      return
    }
    setLoading(true); setError(null)
    const fd = new FormData()
    fd.append('banco', banco)
    extractos.forEach(f => fd.append('extractos', f))
    mayores.forEach(f => fd.append('mayores', f))
    try {
      const r = await api.post('/api/conciliar', fd)
      if (r.data.success) { setResultado(r.data); setTableTab('banco') }
    } catch (err) {
      if (err.response?.status === 401) handleLogout()
      else setError(err.response?.data?.detail || "Error en el servidor.")
    } finally { setLoading(false) }
  }

  const handleDownload = async () => {
    if (!resultado?.fileId || downloading) return
    setDownloading(true)
    try {
      const r = await api.get(`/api/download/${resultado.fileId}`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([r.data]))
      const a = document.createElement('a')
      a.href = url; a.download = resultado.filename
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
    } catch { setError("Error al descargar.") }
    finally { setDownloading(false) }
  }

  const pieData = useMemo(() => {
    if (!resultado?.summary) return []
    const { n_conc, n_banco, n_sist, n_diff } = resultado.summary
    return [
      { name: 'Conciliados', value: n_conc },
      { name: 'Solo Banco', value: n_banco },
      { name: 'Solo Sistema', value: n_sist },
      { name: 'Diferencias', value: n_diff },
    ]
  }, [resultado])

  const tableData = useMemo(() => {
    if (!resultado?.summary) return []
    if (tableTab === 'banco') return resultado.summary.solo_banco
    if (tableTab === 'sistema') return resultado.summary.solo_sistema
    return []
  }, [resultado, tableTab])

  // --- Login screen ---
  if (!token || !usuario) {
    if (view === 'terminos') return <PlaceholderPage title="Términos y Condiciones" onBack={() => setView('dashboard')} />
    if (view === 'privacidad') return <PlaceholderPage title="Política de Privacidad" onBack={() => setView('dashboard')} />
    return <LandingPage onLogin={handleLogin} onRegister={handleRegister} authError={loginError} setView={setView} />
  }

  const esAdmin = usuario?.rol === 'admin'



  return (
    <div className={`flex h-screen bg-brand-dark text-[var(--text-primary)] font-sans overflow-hidden transition-colors duration-300 ${theme === 'light' ? 'light' : ''}`}>
      {/* Sidebar */}
      <aside className="w-68 glass-sidebar flex flex-col z-30 shadow-2xl">
        <div className="p-8 flex items-center space-x-4 mb-8">
          <div className="bg-brand-blue p-2.5 rounded-2xl shadow-lg shadow-brand-blue/30">
            <Activity className="text-white" size={26} />
          </div>
          <span className="text-xl font-extrabold tracking-tight">
            Conta<span className="text-brand-blue">Flex</span>
          </span>
        </div>
        <nav className="flex-1 px-4 space-y-2">
          <SidebarLink active={view === 'dashboard'} icon={<LayoutDashboard size={20}/>} label="Dashboard" onClick={() => setView('dashboard')} />
          <SidebarLink active={view === 'perfil'} icon={<User size={20}/>} label="Mi Perfil" onClick={() => setView('perfil')} />
          {esAdmin && (
            <SidebarLink active={view === 'usuarios'} icon={<Users size={20}/>} label="Usuarios" onClick={() => setView('usuarios')} />
          )}
        </nav>
        <div className="px-4 pb-8 border-t border-white/5 mt-4 pt-4">
          <div className="px-6 py-3 mb-2">
            <p className="text-xs font-black text-slate-300">{usuario?.username ?? 'Usuario'}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full ${esAdmin ? 'bg-brand-blue/20 text-brand-blue' : 'bg-slate-700 text-slate-400'}`}>
                {usuario?.plan ?? (esAdmin ? 'Admin' : 'Free')}
              </span>
              {!esAdmin && (
                <span className="text-[10px] text-slate-500 font-mono">
                  {usuario?.usos_mes_actual}/{usuario?.limite_mensual}
                </span>
              )}
            </div>
            {!esAdmin && (
              <div className="w-full bg-slate-800 h-1 rounded-full mt-2 overflow-hidden">
                <div 
                  className="bg-brand-blue h-full transition-all" 
                  style={{ width: `${Math.min(100, (usuario?.usos_mes_actual / usuario?.limite_mensual) * 100)}%` }}
                ></div>
              </div>
            )}
          </div>
          <button onClick={handleLogout} className="flex items-center space-x-3 w-full px-6 py-3 rounded-2xl text-rose-500 hover:bg-rose-500/10 transition-all font-bold">
            <LogOut size={18}/> <span className="text-sm">Cerrar sesión</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-20 flex items-center justify-between px-10 border-b border-white/5 bg-brand-dark/40 backdrop-blur-xl z-20 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-1.5 flex items-center space-x-2">
              <span className="text-[10px] font-black text-emerald-500 uppercase">Online</span>
              <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></div>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <button
               onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
               className="p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all text-slate-400 hover:text-brand-blue"
               title={theme === 'dark' ? 'Modo día' : 'Modo noche'}
            >
              {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </button>
            <div className="h-8 w-px bg-white/5 mx-2"></div>
            <p className="text-sm font-black text-[var(--text-primary)]">{usuario?.username ?? 'Usuario'}</p>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-10 space-y-10 scrollbar-hide bg-[var(--bg-dark)]">
          {view === 'dashboard' && (
            <Dashboard
              banco={banco} setBanco={setBanco}
              extractos={extractos} setExtractos={setExtractos}
              mayores={mayores} setMayores={setMayores}
              agregarArchivos={agregarArchivos}
              loading={loading} downloading={downloading}
              resultado={resultado} error={error}
              tableTab={tableTab} setTableTab={setTableTab}
              tableData={tableData} pieData={pieData}
              onConciliar={handleConciliar}
              onDownload={handleDownload}
            />
          )}
          {view === 'perfil' && (
            <PanelPerfil usuario={usuario} setUsuario={setUsuario} onLogout={handleLogout} />
          )}
          {view === 'usuarios' && esAdmin && (
            <PanelUsuarios usuario={usuario} />
          )}
        </main>
      </div>
    </div>
  )
}

// ============================================================
// LOGIN
// ============================================================
function LoginScreen({ onLogin, error }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)

  const submit = (e) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    onLogin({ username: username.trim(), password })
  }

  return (
    <div className="h-screen w-full bg-brand-dark flex items-center justify-center p-6">
      <div className="card-premium p-10 max-w-md w-full animate-fade-in bg-brand-card/80 backdrop-blur-xl">
        <div className="flex justify-center mb-8">
          <div className="bg-brand-blue/20 p-4 rounded-3xl border border-brand-blue/30">
            <Lock className="text-brand-blue" size={40} />
          </div>
        </div>
        <h1 className="text-2xl font-black text-center mb-1 tracking-tight">Conta<span className="text-brand-blue">Flex</span></h1>
        <p className="text-slate-400 text-sm text-center mb-8">Ingresá con tu usuario y contraseña.</p>
        <form onSubmit={submit} className="space-y-4">
          <input
            type="text" placeholder="Usuario" value={username}
            onChange={e => setUsername(e.target.value)}
            className="w-full bg-brand-dark border border-white/10 rounded-2xl py-4 px-6 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none transition-all"
          />
          <div className="relative">
            <input
              type={showPass ? 'text' : 'password'} placeholder="Contraseña" value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-brand-dark border border-white/10 rounded-2xl py-4 px-6 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none transition-all pr-14"
            />
            <button type="button" onClick={() => setShowPass(p => !p)}
              className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
              {showPass ? <EyeOff size={18}/> : <Eye size={18}/>}
            </button>
          </div>
          <button type="submit"
            className="w-full bg-brand-blue hover:bg-blue-600 text-white py-4 rounded-2xl font-black text-sm tracking-widest shadow-xl transition-all active:scale-95">
            INGRESAR
          </button>
        </form>
        {error && <p className="text-rose-500 text-xs text-center mt-4 font-bold">{error}</p>}
        <p className="text-[10px] text-slate-600 text-center mt-8">Mantenido por Pablo Ponti</p>
      </div>
    </div>
  )
}

// ============================================================
// DASHBOARD
// ============================================================
function Dashboard({
  banco, setBanco, extractos, setExtractos, mayores, setMayores,
  agregarArchivos, loading, downloading, resultado, error,
  tableTab, setTableTab, tableData, pieData, onConciliar, onDownload
}) {
  return (
    <>
      <div>
        <h2 className="text-4xl font-black tracking-tight mb-2 text-[var(--text-primary)]">Conciliación Bancaria</h2>
        <p className="text-[var(--text-secondary)] font-medium">Procesá extractos y mayores para detectar diferencias.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Upload - Extractos */}
        <div className="card-premium p-6 flex flex-col bg-brand-card/30 border-white/5">
          <h3 className="text-sm font-bold mb-4 flex items-center space-x-2">
            <Upload size={16} className="text-brand-blue" /><span>Extractos Bancarios</span>
            <div className="ml-auto flex gap-1">
              <span className="text-[9px] font-black text-slate-600 bg-brand-blue/10 text-brand-blue px-2 py-0.5 rounded-full">PDF</span>
              <span className="text-[9px] font-black text-slate-600 bg-emerald-500/10 text-emerald-500 px-2 py-0.5 rounded-full">EXCEL</span>
            </div>
          </h3>
          <div
            className="border-2 border-dashed border-brand-blue/20 rounded-2xl flex flex-col items-center justify-center p-8 hover:bg-brand-blue/5 transition-all min-h-[160px]"
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault()
              const allowed = Array.from(e.dataTransfer.files).filter(f => /\.(pdf|xlsx|xls)$/i.test(f.name))
              if (allowed.length) setExtractos(p => [...p, ...allowed])
            }}>
            {extractos.length > 0 && (
              <div className="mb-4 space-y-1.5 w-full">
                {extractos.map((f, i) => {
                  const isPdf = f.name.toLowerCase().endsWith('.pdf')
                  return <FileBadge key={`e${i}`} name={f.name} tag={isPdf ? 'PDF' : 'XLS'} color={isPdf ? 'blue' : 'green'} onRemove={() => setExtractos(p => p.filter((_, x) => x !== i))} />
                })}
              </div>
            )}
            <input type="file" multiple id="file_extractos" accept=".pdf,.xlsx,.xls" className="hidden"
              onChange={e => {
                const allowed = Array.from(e.target.files)
                if (allowed.length) setExtractos(p => [...p, ...allowed])
                e.target.value = ''
              }} />
            <label htmlFor="file_extractos" className="bg-brand-blue text-white px-8 py-3 rounded-2xl font-black text-xs hover:bg-blue-600 cursor-pointer transition-all shadow-xl shadow-brand-blue/20">
              SELECCIONAR ARCHIVOS
            </label>
            <p className="text-[10px] text-[var(--text-secondary)] mt-3 text-center">PDF o Excel · Máx. {MAX_FILE_SIZE_MB} MB</p>
          </div>
        </div>

        {/* Upload - Mayores */}
        <div className="card-premium p-6 flex flex-col bg-brand-card/30 border-white/5">
          <h3 className="text-sm font-bold mb-4 flex items-center space-x-2">
            <Upload size={16} className="text-emerald-500" /><span>Mayores Contables</span>
            <span className="ml-auto text-[9px] font-black bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full">XLSX</span>
          </h3>
          <div
            className="border-2 border-dashed border-emerald-500/20 rounded-2xl flex flex-col items-center justify-center p-8 hover:bg-emerald-500/5 transition-all min-h-[160px]"
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault()
              const excels = Array.from(e.dataTransfer.files).filter(f => /\.(xlsx|xls)$/i.test(f.name))
              if (excels.length) setMayores(p => [...p, ...excels])
            }}>
            {mayores.length > 0 && (
              <div className="mb-4 space-y-1.5 w-full">
                {mayores.map((f, i) => <FileBadge key={`m${i}`} name={f.name} tag="XLS" color="green" onRemove={() => setMayores(p => p.filter((_, x) => x !== i))} />)}
              </div>
            )}
            <input type="file" multiple id="file_mayores" accept=".xlsx,.xls" className="hidden"
              onChange={e => {
                const excels = Array.from(e.target.files)
                if (excels.length) setMayores(p => [...p, ...excels])
                e.target.value = ''
              }} />
            <label htmlFor="file_mayores" className="bg-emerald-600 text-white px-8 py-3 rounded-2xl font-black text-xs hover:bg-emerald-700 cursor-pointer transition-all shadow-xl shadow-emerald-500/20">
              SELECCIONAR EXCEL
            </label>
            <p className="text-[10px] text-[var(--text-secondary)] mt-3 text-center">Arrastrá tus archivos Excel aquí</p>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <KPICard label="Conciliados" value={resultado?.summary ? `${resultado.summary.n_conc}` : "—"} icon={<CheckCircle2 className="text-brand-blue"/>} />
        <KPICard label="Diferencias" value={resultado?.summary ? `${resultado.summary.n_diff}` : "—"} icon={<AlertCircle className="text-amber-500"/>} />
        <KPICard label="Total Gastos" value={resultado?.summary ? `$${resultado.summary.total_gastos.toLocaleString('es-AR')}` : "—"} icon={<Layers className="text-emerald-500"/>} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Gráfico */}
        <div className="lg:col-span-12">
          <Card title="Distribución de Resultados">
            <div className="h-64 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                    {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Legend iconType="circle" />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      </div>

      {/* Controles */}
      <div className="flex flex-col items-center space-y-6">
        <div className="flex bg-brand-card/50 p-2 rounded-2xl border border-white/5 px-6">
          <select value={banco} onChange={e => setBanco(e.target.value)} className="bg-transparent text-sm font-black focus:outline-none focus:text-brand-blue cursor-pointer">
            {BANCOS.map(b => <option key={b} value={b} className="bg-brand-card">{b}</option>)}
          </select>
        </div>
        <button onClick={onConciliar} disabled={loading}
          className={`w-full max-w-xl py-5 rounded-3xl font-black text-xl flex items-center justify-center space-x-4 shadow-2xl transition-all active:scale-95 ${loading ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-brand-blue hover:bg-blue-600 shadow-brand-blue/30'}`}>
          {loading ? <Spinner texto="Procesando..." /> : <><CheckCircle2 size={24}/><span>INICIAR CONCILIACIÓN</span></>}
        </button>
        {error && <p className="text-rose-400 font-bold text-sm text-center max-w-xl">{error}</p>}
      </div>

      {/* Resultado */}
      {resultado && (
        <div className="animate-fade-in space-y-10">
          <div className="card-premium p-10 bg-gradient-to-br from-emerald-500/10 to-transparent border-emerald-500/20 text-center">
            <h3 className="text-3xl font-black mb-2">Reporte Generado</h3>
            <p className="text-slate-400 text-sm mb-6">{resultado.banco} · {resultado.summary.titular}</p>
            <button onClick={onDownload} disabled={downloading}
              className={`px-12 py-5 rounded-3xl font-black text-xl flex items-center space-x-4 mx-auto shadow-2xl transition-all ${downloading ? 'bg-slate-700 text-slate-400 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/30 hover:scale-105'}`}>
              {downloading ? <Spinner texto="Descargando..." /> : <><Download size={24}/><span>DESCARGAR EXCEL</span></>}
            </button>
          </div>

          <div className="card-premium overflow-hidden">
            <div className="p-8 border-b border-white/5 flex gap-4">
              <TabBtn active={tableTab === 'banco'} onClick={() => setTableTab('banco')} label="Solo en Banco" count={resultado.summary.n_banco} />
              <TabBtn active={tableTab === 'sistema'} onClick={() => setTableTab('sistema')} label="Solo en Sistema" count={resultado.summary.n_sist} />
            </div>
            {tableData.length === 0 ? (
              <p className="text-slate-500 text-center py-16 font-bold">Sin movimientos sin conciliar ✓</p>
            ) : (
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
                    {tableData.map((row, i) => {
                      const monto = typeof row.monto === 'number' ? row.monto : 0
                      return (
                        <tr key={i} className="hover:bg-white/2 transition-all">
                          <td className="px-8 py-5 text-slate-400">{row.fecha}</td>
                          <td className="px-8 py-5 font-bold">{row.concepto}</td>
                          <td className={`px-8 py-5 text-right font-black ${monto < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                            ${monto.toLocaleString('es-AR')}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {tableData.length >= 100 && (
                  <p className="text-center text-slate-600 text-xs py-4">Mostrando primeros 100. Descargá el Excel para ver todos.</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}

// ============================================================
// PANEL USUARIOS (admin)
// ============================================================
function PanelUsuarios({ usuario: adminActual }) {
  const [usuarios, setUsuarios] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ username: '', password: '', rol: 'usuario', plan: 'Free' })
  const [editingUser, setEditingUser] = useState(null)
  const [formError, setFormError] = useState(null)
  const [guardando, setGuardando] = useState(false)

  const cargar = useCallback(async () => {
    setCargando(true); setError(null)
    try {
      const r = await api.get('/auth/usuarios')
      setUsuarios(r.data)
    } catch { setError("Error al cargar usuarios.") }
    finally { setCargando(false) }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  const guardarUsuario = async (e) => {
    e.preventDefault()
    setFormError(null)
    if (!form.username.trim()) {
      setFormError("El nombre de usuario es obligatorio.")
      return
    }
    
    setGuardando(true)
    try {
      if (editingUser) {
        // Editar existente
        await api.put(`/auth/usuarios/${editingUser}`, {
          password: form.password ? form.password : undefined,
          rol: form.rol,
          plan: form.plan
        })
      } else {
        // Crear nuevo
        if (form.password.length < 6) {
          setFormError("La contraseña debe tener al menos 6 caracteres.")
          setGuardando(false)
          return
        }
        await api.post('/auth/usuarios', form)
      }
      
      setShowForm(false)
      setEditingUser(null)
      setForm({ username: '', password: '', rol: 'usuario', plan: 'Free' })
      cargar()
    } catch (err) {
      setFormError(err.response?.data?.detail || "Error al guardar usuario.")
    } finally { setGuardando(false) }
  }

  const prepararEdicion = (u) => {
    setEditingUser(u.username)
    setForm({ 
      username: u.username, 
      password: '', 
      rol: u.rol, 
      plan: u.plan || 'Free'
    })
    setShowForm(true)
  }

  const toggleActivo = async (u) => {
    try {
      await api.put(`/auth/usuarios/${u.username}`, { activo: !u.activo })
      cargar()
    } catch (err) {
      setError(err.response?.data?.detail || "Error al actualizar usuario.")
    }
  }

  const eliminar = async (username) => {
    if (!confirm(`¿Eliminar usuario "${username}"?`)) return
    try {
      await api.delete(`/auth/usuarios/${username}`)
      cargar()
    } catch (err) {
      setError(err.response?.data?.detail || "Error al eliminar.")
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-4xl font-black tracking-tight mb-2">Gestión de Usuarios</h2>
          <p className="text-slate-400">Administrá los accesos al sistema.</p>
        </div>
        <div className="flex gap-3">
          <button onClick={cargar} className="p-3 rounded-2xl bg-brand-card/50 border border-white/10 hover:bg-white/5 transition-all text-slate-400">
            <RefreshCw size={18} />
          </button>
          <button onClick={() => setShowForm(s => !s)}
            className="flex items-center space-x-2 bg-brand-blue hover:bg-blue-600 text-white px-6 py-3 rounded-2xl font-black text-sm transition-all">
            <Plus size={18}/><span>NUEVO USUARIO</span>
          </button>
        </div>
      </div>

      {/* Formulario nuevo usuario */}
      {showForm && (
        <div className="card-premium p-8 border-brand-blue/20">
          <h3 className="font-black text-lg mb-6">{editingUser ? `Editar usuario: ${editingUser}` : 'Crear usuario' }</h3>
          <form onSubmit={guardarUsuario} className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input type="text" placeholder="Nombre de usuario" value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
              className="bg-brand-dark border border-white/10 rounded-2xl py-3 px-5 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none" />
            <input type="password" placeholder={editingUser ? "Nueva contraseña (opcional)" : "Contraseña (mín. 6 caracteres)"} value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              className="bg-brand-dark border border-white/10 rounded-2xl py-3 px-5 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none" />
            <select value={form.rol} onChange={e => setForm(f => ({ ...f, rol: e.target.value }))}
              className="bg-brand-dark border border-white/10 rounded-2xl py-3 px-5 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none cursor-pointer">
              <option value="usuario">Usuario</option>
              <option value="admin">Administrador</option>
            </select>
            <select value={form.plan} onChange={e => setForm(f => ({ ...f, plan: e.target.value }))}
              className="bg-brand-dark border border-white/10 rounded-2xl py-3 px-5 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none cursor-pointer">
              <option value="Free">Plan Free (5)</option>
              <option value="Individual">Plan Individual (20)</option>
              <option value="Estudio">Plan Estudio (100)</option>
            </select>
            {formError && <p className="text-rose-400 text-sm font-bold md:col-span-3">{formError}</p>}
            <div className="md:col-span-3 flex gap-3">
              <button type="submit" disabled={guardando}
                className="bg-brand-blue hover:bg-blue-600 text-white px-8 py-3 rounded-2xl font-black text-sm transition-all disabled:opacity-50">
                {guardando ? 'Guardando...' : (editingUser ? 'ACTUALIZAR' : 'CREAR')}
              </button>
              <button type="button" onClick={() => { setShowForm(false); setEditingUser(null); }}
                className="px-8 py-3 rounded-2xl font-black text-sm text-slate-400 hover:text-white border border-white/10 transition-all">
                CANCELAR
              </button>
            </div>
          </form>
        </div>
      )}

      {error && <p className="text-rose-400 font-bold">{error}</p>}

      {/* Tabla de usuarios */}
      <div className="card-premium overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-brand-card border-b border-white/5 text-slate-500 font-bold">
            <tr>
              <th className="px-8 py-5 text-left">Usuario</th>
              <th className="px-8 py-5 text-left">Rol</th>
              <th className="px-8 py-5 text-left">Plan</th>
              <th className="px-8 py-5 text-left">Uso Mensual</th>
              <th className="px-8 py-5 text-left">Estado</th>
              <th className="px-8 py-5 text-left">Último login</th>
              <th className="px-8 py-5 text-left">Creado</th>
              <th className="px-8 py-5 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {cargando ? (
              <tr><td colSpan={7} className="text-center py-12 text-slate-500">Cargando...</td></tr>
            ) : usuarios.map(u => (
              <tr key={u.id} className="hover:bg-white/2 transition-all">
                <td className="px-8 py-5 font-black flex items-center space-x-3">
                  <User size={16} className="text-slate-500" />
                  <span>{u.username}</span>
                  {u.username === adminActual.username && (
                    <span className="text-[9px] bg-brand-blue/20 text-brand-blue px-2 py-0.5 rounded-full font-black">TÚ</span>
                  )}
                </td>
                <td className="px-8 py-5">
                  <span className={`text-[10px] font-black uppercase px-3 py-1 rounded-full ${u.rol === 'admin' ? 'bg-brand-blue/20 text-brand-blue' : 'bg-slate-700 text-slate-400'}`}>
                    {u.rol}
                  </span>
                </td>
                <td className="px-8 py-5">
                  <span className={`text-[10px] font-black uppercase px-3 py-1 rounded-full ${u.plan === 'Estudio' ? 'bg-brand-blue/20 text-brand-blue' : 'bg-slate-700 text-slate-400'}`}>
                    {u.plan}
                  </span>
                </td>
                <td className="px-8 py-5 font-mono text-xs">
                  <span className={u.usos_mes_actual >= u.limite_mensual ? 'text-rose-400 font-bold' : 'text-slate-300'}>
                    {u.usos_mes_actual} / {u.limite_mensual}
                  </span>
                </td>
                <td className="px-8 py-5">
                  <span className={`text-[10px] font-black uppercase px-3 py-1 rounded-full ${u.activo ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                    {u.activo ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="px-8 py-5 text-slate-400 text-xs">
                  {u.ultimo_login ? new Date(u.ultimo_login).toLocaleString('es-AR') : '—'}
                </td>
                <td className="px-8 py-5 text-slate-400 text-xs">
                  {new Date(u.creado_en).toLocaleDateString('es-AR')}
                </td>
                <td className="px-8 py-5 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button onClick={() => prepararEdicion(u)}
                      className="p-2 rounded-xl text-slate-600 hover:text-brand-blue hover:bg-brand-blue/10 transition-all">
                      <Edit size={15}/>
                    </button>
                    {u.username !== adminActual.username && (
                      <>
                        <button onClick={() => toggleActivo(u)}
                          className={`text-xs font-black px-4 py-1.5 rounded-xl transition-all ${u.activo ? 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20' : 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'}`}>
                          {u.activo ? 'Desactivar' : 'Activar'}
                        </button>
                        <button onClick={() => eliminar(u.username)}
                          className="p-2 rounded-xl text-slate-600 hover:text-rose-500 hover:bg-rose-500/10 transition-all">
                          <Trash2 size={15}/>
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ============================================================
// PANEL PERFIL
// ============================================================
function PanelPerfil({ usuario, setUsuario, onLogout }) {
  const [form, setForm] = useState({ username: usuario.username, password: '' })
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [guardando, setGuardando] = useState(false)

  const guardar = async (e) => {
    e.preventDefault()
    setError(null); setSuccess(null)
    if (!form.username.trim()) return setError("El nombre es requerido.")
    
    setGuardando(true)
    try {
      await api.put(`/auth/usuarios/${usuario.username}`, {
        new_username: form.username !== usuario.username ? form.username : undefined,
        password: form.password ? form.password : undefined
      })
      
      setSuccess("Perfil actualizado.")
      // Si cambió el nombre, hay que cerrar sesión o actualizar el token
      if (form.username !== usuario.username) {
        setTimeout(() => onLogout(), 2000)
      } else {
        setUsuario(u => ({ ...u, username: form.username }))
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Error al actualizar.")
    } finally { setGuardando(false) }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8 animate-fade-in">
      <div>
        <h2 className="text-4xl font-black tracking-tight mb-2 text-[var(--text-primary)]">Mi Perfil</h2>
        <p className="text-[var(--text-secondary)]">Gestioná tu información personal y contraseña.</p>
      </div>

      <div className="card-premium p-10 space-y-8">
        <h3 className="font-black text-lg border-b border-white/5 pb-4">Suscripción y Uso</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <p className="text-sm text-slate-400 font-medium">Plan Actual</p>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-black text-brand-blue">{usuario.plan}</span>
              <span className="text-xs bg-brand-blue/10 text-brand-blue px-3 py-1 rounded-full font-bold">Activo</span>
            </div>
            <p className="text-xs text-slate-500">Límite mensual: {usuario.limite_mensual} conciliaciones.</p>
          </div>
          <div className="space-y-4">
            <p className="text-sm text-slate-400 font-medium">Uso del Mes</p>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-black text-white">{usuario.usos_mes_actual}</span>
              <span className="text-xs text-slate-500">de {usuario.limite_mensual}</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div 
                className="bg-brand-blue h-full transition-all" 
                style={{ width: `${Math.min(100, (usuario.usos_mes_actual / usuario.limite_mensual) * 100)}%` }}
              ></div>
            </div>
          </div>
        </div>

        <div className="pt-6 border-t border-white/5">
          <p className="text-sm font-bold mb-4">Mejorar Plan</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {['Free', 'Individual', 'Estudio'].map(p => (
              <button 
                key={p}
                onClick={async () => {
                  if (p === usuario.plan) return;
                  if (!confirm(`¿Cambiar al plan ${p}?`)) return;
                  try {
                    await api.post(`/auth/upgrade?plan_solicitado=${p}`);
                    // Actualizar usuario localmente
                    const me = await api.get('/auth/me');
                    setUsuario(me.data);
                    alert(`¡Plan actualizado a ${p}!`);
                  } catch (err) {
                    alert("Error al actualizar plan.");
                  }
                }}
                disabled={p === usuario.plan}
                className={`py-3 rounded-xl text-xs font-black transition-all ${p === usuario.plan ? 'bg-slate-800 text-slate-500 cursor-default' : 'bg-white/5 border border-white/10 hover:border-brand-blue hover:text-brand-blue'}`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="card-premium p-10 space-y-8">
        <h3 className="font-black text-lg border-b border-white/5 pb-4">Ajustes de Cuenta</h3>
        <form onSubmit={guardar} className="space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase text-slate-500">Nombre de Usuario</label>
            <input type="text" value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
              className="w-full bg-brand-dark border border-white/10 rounded-2xl py-4 px-6 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none" />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase text-slate-500">Nueva Contraseña (dejar en blanco para mantener)</label>
            <input type="password" value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              className="w-full bg-brand-dark border border-white/10 rounded-2xl py-4 px-6 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none" />
          </div>
          
          {error && <p className="text-rose-400 text-sm font-bold">{error}</p>}
          {success && <p className="text-emerald-400 text-sm font-bold">{success}</p>}
          {success && form.username !== usuario.username && <p className="text-amber-400 text-xs italic">Cerrando sesión para aplicar cambios...</p>}

          <button type="submit" disabled={guardando}
            className="bg-brand-blue hover:bg-blue-600 text-white px-10 py-4 rounded-2xl font-black text-sm transition-all shadow-xl disabled:opacity-50">
            {guardando ? 'GUARDANDO...' : 'ACTUALIZAR PERFIL'}
          </button>
        </form>
      </div>
    </div>
  )
}

function KPICard({ label, value, icon }) {
  return (
    <div className="card-premium p-8 hover:border-brand-blue/30 transition-all">
      <div className="bg-emerald-500/5 p-3 rounded-2xl border border-white/5 mb-6 w-fit">{icon}</div>
      <p className="text-[10px] font-black text-[var(--text-secondary)] uppercase tracking-widest mb-1">{label}</p>
      <p className="text-3xl font-black tracking-tighter text-[var(--text-primary)]">{value}</p>
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
      <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-[var(--text-secondary)] mb-4">{title}</h3>
      <div className="flex-1">{children}</div>
    </div>
  )
}
function FileBadge({ name, tag, onRemove, color = 'blue' }) {
  const iconColor = color === 'green' ? 'text-emerald-500' : 'text-brand-blue'
  return (
    <div className="flex items-center justify-between bg-white/5 border border-white/5 rounded-xl px-4 py-2">
      <div className="flex items-center space-x-3 overflow-hidden">
        <FileText size={14} className={`${iconColor} shrink-0`} />
        <span className="text-[10px] font-bold truncate text-slate-400">{name}</span>
        <span className="text-[9px] font-black text-slate-600 shrink-0">{tag}</span>
      </div>
      <button onClick={onRemove} className="text-slate-600 hover:text-rose-500 ml-4 shrink-0"><Trash2 size={12}/></button>
    </div>
  )
}
function TabBtn({ active, onClick, label, count }) {
  return (
    <button onClick={onClick} className={`px-5 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${active ? 'bg-brand-blue text-white' : 'text-slate-500 hover:text-slate-300'}`}>
      {label} <span className="ml-2 opacity-50">{count}</span>
    </button>
  )
}
function Spinner({ texto }) {
  return (
    <div className="flex items-center space-x-4">
      <div className="w-6 h-6 border-4 border-slate-700 border-t-white rounded-full animate-spin"></div>
      <span className="text-xs font-black tracking-widest uppercase">{texto}</span>
    </div>
  )
}

function PlaceholderPage({ title, onBack }) {
  return (
    <div className="h-screen w-full bg-brand-dark flex flex-col items-center justify-center p-10 text-center">
      <h1 className="text-4xl font-black mb-4">{title}</h1>
      <p className="text-slate-400 max-w-lg mb-8">Esta página está en construcción. Próximamente incluiremos toda la información legal y operativa de ContaFlex.</p>
      <button onClick={onBack} className="bg-brand-blue text-white px-10 py-4 rounded-2xl font-black text-sm">
        VOLVER AL INICIO
      </button>
    </div>
  )
}
