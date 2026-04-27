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
  Eye, EyeOff, RefreshCw, Sun, Moon, Edit, Loader2
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
  const [loadingApp, setLoadingApp] = useState(true)

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

  // Lógica de recuperación de contraseña y verificación
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const resetToken = urlParams.get('token');
    // Si la URL contiene un token de reset, disparamos el prompt
    if (window.location.pathname.includes('reset-password') || urlParams.has('token')) {
       // Si es un reset
       const esReset = window.location.pathname.includes('reset-password') || document.body.innerText.includes('Reset');
       // Por ahora lo manejamos simple con un prompt si detectamos el parámetro
       if (urlParams.has('token') && !token) {
          const nueva = prompt("Ingresá tu nueva contraseña (mín. 8 caracteres):");
          if (nueva) {
             handleResetPassword(urlParams.get('token'), nueva)
                .then(() => alert("¡Contraseña actualizada! Ya podés iniciar sesión."))
                .catch(e => alert(e.response?.data?.detail || "Error al resetear clave."));
          }
          window.history.replaceState({}, document.title, "/");
       }
    }
  }, []);

  const cargarUsuario = useCallback(async () => {
    try {
      const r = await api.get('/auth/me')
      setUsuario(r.data)
    } catch {
      handleLogout()
    } finally {
      setLoadingApp(false)
    }
  }, [])

  useEffect(() => {
    if (token) cargarUsuario()
    else setLoadingApp(false)
  }, [token, cargarUsuario])

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
      await handleLogin({ username, password })
      return true
    } catch (err) {
      setLoginError(err.response?.data?.detail || "Error al registrarse.")
      return false
    }
  }

  const handleForgotPassword = async (email) => {
    return axios.post(`${API_BASE_URL}/auth/olvide-password?username=${email}`)
  }

  const handleResetPassword = async (token, newPass) => {
    return axios.post(`${API_BASE_URL}/auth/reset-password?token=${token}&nueva_pass=${newPass}`)
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

  if (loadingApp) return <div className="h-screen w-full flex items-center justify-center bg-brand-dark"><Spinner texto="Iniciando ContaFlex..." /></div>

  if (!token || !usuario) {
    if (view === 'terminos') return <PlaceholderPage title="Términos y Condiciones" onBack={() => setView('dashboard')} />
    if (view === 'privacidad') return <PlaceholderPage title="Política de Privacidad" onBack={() => setView('dashboard')} />
    return <LandingPage onLogin={handleLogin} onRegister={handleRegister} authError={loginError} onForgotPassword={handleForgotPassword} setView={setView} />
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
             {!usuario?.email_verificado && esAdmin === false && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-1.5 flex items-center space-x-2 animate-pulse">
                  <span className="text-[10px] font-black text-amber-500 uppercase">Email sin verificar</span>
                </div>
             )}
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
        <div className="card-premium p-6 flex flex-col bg-brand-card/30 border-white/5">
          <h3 className="text-sm font-bold mb-4 flex items-center space-x-2">
            <Upload size={16} className="text-brand-blue" /><span>Extractos Bancarios</span>
          </h3>
          <div
            className="border-2 border-dashed border-brand-blue/20 rounded-2xl flex flex-col items-center justify-center p-8 hover:bg-brand-blue/5 transition-all min-h-[160px]"
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault()
              agregarArchivos(e.dataTransfer.files)
            }}>
            {extractos.length > 0 && (
              <div className="mb-4 space-y-1.5 w-full">
                {extractos.map((f, i) => <FileBadge key={`e${i}`} name={f.name} tag="PDF" color="blue" onRemove={() => setExtractos(p => p.filter((_, x) => x !== i))} />)}
              </div>
            )}
            <input type="file" multiple id="file_extractos" accept=".pdf,.xlsx,.xls" className="hidden"
              onChange={e => {
                agregarArchivos(e.target.files)
                e.target.value = ''
              }} />
            <label htmlFor="file_extractos" className="bg-brand-blue text-white px-8 py-3 rounded-2xl font-black text-xs hover:bg-blue-600 cursor-pointer transition-all shadow-xl shadow-brand-blue/20">
              SELECCIONAR ARCHIVOS
            </label>
          </div>
        </div>

        <div className="card-premium p-6 flex flex-col bg-brand-card/30 border-white/5">
          <h3 className="text-sm font-bold mb-4 flex items-center space-x-2">
            <Upload size={16} className="text-emerald-500" /><span>Mayores Contables</span>
          </h3>
          <div
            className="border-2 border-dashed border-emerald-500/20 rounded-2xl flex flex-col items-center justify-center p-8 hover:bg-emerald-500/5 transition-all min-h-[160px]"
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault()
              agregarArchivos(e.dataTransfer.files)
            }}>
            {mayores.length > 0 && (
              <div className="mb-4 space-y-1.5 w-full">
                {mayores.map((f, i) => <FileBadge key={`m${i}`} name={f.name} tag="XLS" color="green" onRemove={() => setMayores(p => p.filter((_, x) => x !== i))} />)}
              </div>
            )}
            <input type="file" multiple id="file_mayores" accept=".xlsx,.xls" className="hidden"
              onChange={e => {
                agregarArchivos(e.target.files)
                e.target.value = ''
              }} />
            <label htmlFor="file_mayores" className="bg-emerald-600 text-white px-8 py-3 rounded-2xl font-black text-xs hover:bg-emerald-700 cursor-pointer transition-all shadow-xl shadow-emerald-500/20">
              SELECCIONAR EXCEL
            </label>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <KPICard label="Conciliados" value={resultado?.summary ? `${resultado.summary.n_conc}` : "—"} icon={<CheckCircle2 className="text-brand-blue"/>} />
        <KPICard label="Diferencias" value={resultado?.summary ? `${resultado.summary.n_diff}` : "—"} icon={<AlertCircle className="text-amber-500"/>} />
        <KPICard label="Total Gastos" value={resultado?.summary ? `$${resultado.summary.total_gastos.toLocaleString('es-AR')}` : "—"} icon={<Layers className="text-emerald-500"/>} />
      </div>

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
            <div className="overflow-x-auto max-h-[500px]">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-brand-card border-b border-white/5 text-slate-500 font-bold">
                  <tr><th className="px-8 py-5">Fecha</th><th className="px-8 py-5">Concepto</th><th className="px-8 py-5 text-right">Monto</th></tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {tableData.map((row, i) => (
                    <tr key={i} className="hover:bg-white/2 transition-all">
                      <td className="px-8 py-5 text-slate-400">{row.fecha}</td>
                      <td className="px-8 py-5 font-bold">{row.concepto}</td>
                      <td className={`px-8 py-5 text-right font-black ${row.monto < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                        ${row.monto?.toLocaleString('es-AR')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
    if (!form.username.trim()) { setFormError("Usuario obligatorio."); return }
    setGuardando(true)
    try {
      if (editingUser) {
        await api.put(`/auth/usuarios/${editingUser}`, { password: form.password || undefined, rol: form.rol, plan: form.plan })
      } else {
        await api.post('/auth/usuarios', form)
      }
      setShowForm(false); setEditingUser(null); setForm({ username: '', password: '', rol: 'usuario', plan: 'Free' }); cargar()
    } catch (err) {
      setFormError(err.response?.data?.detail || "Error al guardar.")
    } finally { setGuardando(false) }
  }

  const prepararEdicion = (u) => {
    setEditingUser(u.username); setForm({ username: u.username, password: '', rol: u.rol, plan: u.plan || 'Free' }); setShowForm(true)
  }

  const toggleActivo = async (u) => {
    try { await api.put(`/auth/usuarios/${u.username}`, { activo: !u.activo }); cargar() } catch { setError("Error al actualizar.") }
  }

  const eliminar = async (username) => {
    if (!confirm(`¿Eliminar "${username}"?`)) return
    try { await api.delete(`/auth/usuarios/${username}`); cargar() } catch { setError("Error al eliminar.") }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-4xl font-black tracking-tight mb-2">Gestión de Usuarios</h2>
          <p className="text-slate-400">Administrá los accesos al sistema.</p>
        </div>
        <button onClick={() => setShowForm(s => !s)} className="bg-brand-blue hover:bg-blue-600 text-white px-6 py-3 rounded-2xl font-black text-sm transition-all"><Plus size={18}/></button>
      </div>

      {showForm && (
        <div className="card-premium p-8 border-brand-blue/20">
          <form onSubmit={guardarUsuario} className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <input type="text" placeholder="Usuario" value={form.username} onChange={e => setForm({...form, username: e.target.value})} className="bg-brand-dark border border-white/10 rounded-2xl py-3 px-5 font-bold outline-none" />
            <input type="password" placeholder="Pass" value={form.password} onChange={e => setForm({...form, password: e.target.value})} className="bg-brand-dark border border-white/10 rounded-2xl py-3 px-5 font-bold outline-none" />
            <select value={form.rol} onChange={e => setForm({...form, rol: e.target.value})} className="bg-brand-dark border border-white/10 rounded-2xl py-3 px-5 font-bold outline-none">
              <option value="usuario">Usuario</option><option value="admin">Admin</option>
            </select>
            <select value={form.plan} onChange={e => setForm({...form, plan: e.target.value})} className="bg-brand-dark border border-white/10 rounded-2xl py-3 px-5 font-bold outline-none">
              <option value="Free">Free</option><option value="Individual">Individual</option><option value="Estudio">Estudio</option>
            </select>
            <button type="submit" className="bg-brand-blue text-white px-8 py-3 rounded-2xl font-black text-sm">{editingUser ? 'ACTUALIZAR' : 'CREAR'}</button>
          </form>
        </div>
      )}

      <div className="card-premium overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-brand-card border-b border-white/5 text-slate-500 font-bold">
            <tr><th className="px-8 py-5 text-left">Usuario</th><th className="px-8 py-5 text-left">Rol</th><th className="px-8 py-5 text-left">Plan</th><th className="px-8 py-5 text-left">Uso</th><th className="px-8 py-5 text-right">Acciones</th></tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {usuarios.map(u => (
              <tr key={u.id} className="hover:bg-white/2 transition-all">
                <td className="px-8 py-5 font-black">{u.username}</td>
                <td className="px-8 py-5 text-xs uppercase">{u.rol}</td>
                <td className="px-8 py-5 text-xs font-bold text-brand-blue">{u.plan}</td>
                <td className="px-8 py-5 font-mono text-xs text-slate-400">{u.usos_mes_actual}/{u.limite_mensual}</td>
                <td className="px-8 py-5 text-right space-x-2">
                  <button onClick={() => prepararEdicion(u)} className="p-2 text-slate-400 hover:text-brand-blue"><Edit size={16}/></button>
                  <button onClick={() => toggleActivo(u)} className={`text-xs font-bold ${u.activo ? 'text-amber-500' : 'text-emerald-500'}`}>{u.activo ? 'Desactivar' : 'Activar'}</button>
                  <button onClick={() => eliminar(u.username)} className="p-2 text-slate-400 hover:text-rose-500"><Trash2 size={16}/></button>
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
  const [editando, setEditando] = useState(false)
  const [form, setForm] = useState({ new_username: usuario.username, password: '' })
  const [cargando, setCargando] = useState(false)

  const guardar = async (e) => {
    e.preventDefault()
    setCargando(true)
    try {
      await api.put(`/auth/usuarios/${usuario.username}`, form)
      const r = await api.get('/auth/me')
      setUsuario(r.data)
      setEditando(false)
      alert("Perfil actualizado.")
    } catch (err) {
      alert(err.response?.data?.detail || "Error al actualizar.")
    } finally { setCargando(false) }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
      <div className="flex items-center space-x-6">
        <div className="h-24 w-24 rounded-3xl bg-gradient-to-br from-brand-blue to-blue-600 flex items-center justify-center shadow-2xl shadow-brand-blue/20">
          <User size={48} className="text-white" />
        </div>
        <div>
          <h2 className="text-4xl font-black tracking-tight">{usuario.username}</h2>
          <p className="text-slate-400 font-medium">Miembro desde {new Date(usuario.creado_en).toLocaleDateString('es-AR')}</p>
        </div>
      </div>

      <div className="card-premium p-10 space-y-8">
        <h3 className="font-black text-lg border-b border-white/5 pb-4">Suscripción y Uso</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <p className="text-sm text-slate-400 font-medium">Plan Actual</p>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-black text-brand-blue">{usuario.plan}</span>
              {usuario.plan_pendiente ? (
                <span className="text-[10px] bg-amber-500/20 text-amber-400 px-3 py-1 rounded-full font-black animate-pulse">
                  PENDIENTE: {usuario.plan_pendiente.toUpperCase()}
                </span>
              ) : (
                <span className="text-xs bg-brand-blue/10 text-brand-blue px-3 py-1 rounded-full font-bold">Activo</span>
              )}
            </div>
            <p className="text-xs text-slate-500">
              {usuario.plan_pendiente 
                ? `Tu solicitud de plan ${usuario.plan_pendiente} está siendo procesada.` 
                : `Límite mensual: ${usuario.limite_mensual} conciliaciones.`}
            </p>
          </div>
          <div className="space-y-4">
            <p className="text-sm text-slate-400 font-medium">Uso del Mes</p>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-black text-white">{usuario.usos_mes_actual}</span>
              <span className="text-xs text-slate-500">de {usuario.limite_mensual}</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="bg-brand-blue h-full transition-all" style={{ width: `${Math.min(100, (usuario.usos_mes_actual / usuario.limite_mensual) * 100)}%` }}></div>
            </div>
          </div>
        </div>

        <div className="pt-6 border-t border-white/5">
          <p className="text-sm font-bold mb-4">Mejorar Plan</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {['Free', 'Individual', 'Estudio'].map(p => {
              const esActual = p === usuario.plan;
              const esPendiente = p === usuario.plan_pendiente;
              const planes = ['Free', 'Individual', 'Estudio'];
              const indiceActual = planes.indexOf(usuario.plan);
              const indiceP = planes.indexOf(p);
              const esInferior = indiceP < indiceActual;

              return (
                <button 
                  key={p}
                  onClick={async () => {
                    if (esActual || esPendiente || esInferior) return;
                    if (!confirm(`¿Solicitar cambio al plan ${p}? Se enviará una notificación para aprobación.`)) return;
                    try {
                      await api.post(`/auth/upgrade?plan_solicitado=${p}`);
                      const me = await api.get('/auth/me');
                      setUsuario(me.data);
                      alert(`Solicitud enviada para plan ${p}. Te avisaremos por mail.`);
                    } catch (err) {
                      alert(err.response?.data?.detail || "Error al solicitar plan.");
                    }
                  }}
                  disabled={esActual || esPendiente || esInferior}
                  className={`py-3 rounded-xl text-xs font-black transition-all ${
                    esActual ? 'bg-brand-blue/20 text-brand-blue cursor-default border border-brand-blue/30' : 
                    esPendiente ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30 animate-pulse' :
                    esInferior ? 'bg-slate-800 text-slate-600 cursor-not-allowed opacity-50' :
                    'bg-white/5 border border-white/10 hover:border-brand-blue hover:text-brand-blue'
                  }`}
                >
                  {p.toUpperCase()} {esActual && '✓'}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="card-premium p-10 space-y-8">
        <h3 className="font-black text-lg border-b border-white/5 pb-4">Ajustes de Cuenta</h3>
        <form onSubmit={guardar} className="space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase text-slate-500">Nombre de Usuario</label>
            <input type="text" value={form.new_username} onChange={e => setForm({...form, new_username: e.target.value})} className="w-full bg-brand-dark border border-white/10 rounded-2xl py-4 px-6 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none transition-all" />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase text-slate-500">Nueva Contraseña (dejar vacío para mantener)</label>
            <input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} className="w-full bg-brand-dark border border-white/10 rounded-2xl py-4 px-6 font-bold focus:ring-2 focus:ring-brand-blue/30 outline-none transition-all" />
          </div>
          <button type="submit" disabled={cargando} className="bg-brand-blue text-white px-10 py-4 rounded-2xl font-black text-sm tracking-widest shadow-xl transition-all hover:bg-blue-600 disabled:opacity-50">
            {cargando ? 'GUARDANDO...' : 'GUARDAR CAMBIOS'}
          </button>
        </form>
      </div>
    </div>
  )
}

// --- Componentes auxiliares ---
function SidebarLink({ active, icon, label, onClick }) {
  return (
    <button onClick={onClick} className={`flex items-center space-x-3 w-full px-6 py-3.5 rounded-2xl transition-all font-bold ${active ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}>
      {icon} <span className="text-sm">{label}</span>
    </button>
  )
}

function KPICard({ label, value, icon }) {
  return (
    <div className="card-premium p-6 flex items-center space-x-5">
      <div className="bg-brand-dark p-4 rounded-2xl border border-white/5">{icon}</div>
      <div>
        <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">{label}</p>
        <p className="text-2xl font-black">{value}</p>
      </div>
    </div>
  )
}

function FileBadge({ name, tag, color, onRemove }) {
  const colors = { blue: 'bg-brand-blue/10 text-brand-blue border-brand-blue/20', green: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' }
  return (
    <div className={`flex items-center justify-between px-4 py-2.5 rounded-xl border ${colors[color]} animate-fade-in`}>
      <div className="flex items-center space-x-3 overflow-hidden">
        <span className="text-[9px] font-black px-1.5 py-0.5 rounded bg-white/10">{tag}</span>
        <span className="text-xs font-bold truncate">{name}</span>
      </div>
      <button onClick={onRemove} className="ml-2 hover:text-white opacity-50 hover:opacity-100"><Trash2 size={14}/></button>
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div className="card-premium p-8">
      <h3 className="text-sm font-black text-slate-500 uppercase tracking-widest mb-6">{title}</h3>
      {children}
    </div>
  )
}

function TabBtn({ active, onClick, label, count }) {
  return (
    <button onClick={onClick} className={`px-6 py-3 rounded-2xl font-black text-xs transition-all border ${active ? 'bg-brand-blue border-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'bg-transparent border-white/10 text-slate-500 hover:border-white/20'}`}>
      {label.toUpperCase()} <span className="ml-2 opacity-50">{count}</span>
    </button>
  )
}

function Spinner({ texto }) {
  return (
    <div className="flex items-center space-x-3">
      <Loader2 className="animate-spin" size={20} />
      <span className="text-xs font-bold uppercase tracking-widest">{texto}</span>
    </div>
  )
}

function PlaceholderPage({ title, onBack }) {
  return (
    <div className="h-full flex flex-col items-center justify-center space-y-6">
      <h2 className="text-3xl font-black">{title}</h2>
      <p className="text-slate-400">Esta sección está en mantenimiento.</p>
      <button onClick={onBack} className="bg-brand-blue text-white px-8 py-3 rounded-2xl font-black text-xs">VOLVER</button>
    </div>
  )
}
