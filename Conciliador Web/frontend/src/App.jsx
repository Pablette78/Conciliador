import { useState } from 'react'
import axios from 'axios'
import { 
  Upload, 
  FileCheck, 
  AlertCircle, 
  Download, 
  Settings, 
  History, 
  LayoutDashboard,
  CheckCircle2,
  AlertTriangle,
  Receipt,
  Building2,
  Trash2
} from 'lucide-react'

// --- Estilos Auxiliares ---
const BANCOS = [
  "— auto —", "Banco Santander", "Banco Galicia", "Banco BBVA", "Banco Bancor",
  "Banco Provincia", "Banco Nación", "Banco Credicoop", "Banco HSBC",
  "Banco ICBC", "Banco Macro", "Banco Ciudad", "Banco Comafi", "ARCA-Mis Retenciones"
]

function App() {
  const [banco, setBanco] = useState("— auto —")
  const [extractos, setExtractos] = useState([])
  const [mayores, setMayores] = useState([])
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)
  const [view, setView] = useState('dashboard') // Sidebar navigation state

  // --- Handlers ---
  const handleFileDrop = (e, setFiles) => {
    e.preventDefault()
    const droppedFiles = Array.from(e.dataTransfer.files)
    setFiles(prev => [...prev, ...droppedFiles])
  }

  const handleFileSelect = (e, setFiles) => {
    const selectedFiles = Array.from(e.target.files)
    setFiles(prev => [...prev, ...selectedFiles])
  }

  const removeFile = (index, setFiles) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleConciliar = async () => {
    if (extractos.length === 0 || mayores.length === 0) {
      setError("Debes cargar al menos un extracto y un mayor.")
      return
    }

    setLoading(true)
    setError(null)
    setResultado(null)

    const formData = new FormData()
    formData.append('banco', banco)
    extractos.forEach(file => formData.append('extractos', file))
    mayores.forEach(file => formData.append('mayores', file))

    try {
      const response = await axios.post('http://localhost:8000/api/conciliar', formData)
      
      if (response.data.success) {
        setResultado({
          summary: response.data.summary,
          fileId: response.data.fileId,
          filename: response.data.filename,
          bancoDetectado: response.data.banco
        })
      }
    } catch (err) {
      console.error(err)
      const msg = err.response?.data?.detail || "Error al procesar la conciliación. Asegúrate de que el backend esté corriendo."
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    if (!resultado?.fileId) return
    
    try {
      const response = await axios.get(`http://localhost:8000/api/download/${resultado.fileId}`, {
        responseType: 'blob'
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', resultado.filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      setError("Error al descargar el archivo.")
    }
  }

  return (
    <div className="flex h-screen bg-brand-dark text-slate-100 font-sans">
      {/* --- Sidebar --- */}
      <aside className="w-64 glass border-r border-slate-700 flex flex-col">
        <div className="p-8 text-center border-b border-slate-800">
          <div className="bg-brand-blue/20 p-3 rounded-2xl inline-block mb-3">
            <Building2 className="text-brand-blue" size={32} />
          </div>
          <h1 className="text-xl font-bold tracking-tight">Conciliador B10</h1>
          <span className="text-xs text-brand-blue font-semibold uppercase tracking-widest">SaaS Edition</span>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          <NavItem 
            active={view === 'dashboard'} 
            onClick={() => setView('dashboard')} 
            icon={<LayoutDashboard size={20} />} 
            label="Dashboard" 
          />
          <NavItem 
            active={view === 'history'} 
            onClick={() => setView('history')} 
            icon={<History size={20} />} 
            label="Historial" 
          />
          <NavItem 
            active={view === 'settings'} 
            onClick={() => setView('settings')} 
            icon={<Settings size={20} />} 
            label="Configuración" 
          />
        </nav>

        <div className="p-4 border-t border-slate-800">
          <div className="bg-slate-800/50 p-4 rounded-xl text-xs text-slate-400 text-center">
            &copy; 2026 Conciliador Pro
          </div>
        </div>
      </aside>

      {/* --- Main Content --- */}
      <main className="flex-1 overflow-y-auto p-8 relative">
        {view === 'dashboard' ? (
          <>
            <header className="mb-8 flex justify-between items-center">
              <div>
                <h2 className="text-3xl font-bold">Dashboard</h2>
                <p className="text-slate-400">Gestiona la conciliación bancaria de forma automática.</p>
              </div>
              <div className="flex items-center space-x-4 bg-slate-800/50 p-2 rounded-full px-4 border border-slate-700">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                <span className="text-xs font-medium text-slate-300">Servidor Online</span>
              </div>
            </header>

            {/* --- Upload Grid --- */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
              <DropZone 
                title="Extractos Bancarios" 
                hint="Arrastra tus PDFs o Excel aquí" 
                icon={<Upload className="text-slate-400 group-hover:text-brand-blue" size={32} />}
                files={extractos}
                onDrop={(e) => handleFileDrop(e, setExtractos)}
                onSelect={(e) => handleFileSelect(e, setExtractos)}
                onRemove={(idx) => removeFile(idx, setExtractos)}
                id="ext-input"
              />

              <DropZone 
                title="Mayor Contable" 
                hint="Sube los movimientos del sistema (.xlsx)" 
                icon={<FileCheck className="text-slate-400 group-hover:text-brand-blue" size={32} />}
                files={mayores}
                onDrop={(e) => handleFileDrop(e, setMayores)}
                onSelect={(e) => handleFileSelect(e, setMayores)}
                onRemove={(idx) => removeFile(idx, setMayores)}
                id="may-input"
              />
            </section>

            {/* --- Action Area --- */}
            <section className="flex flex-col items-center mb-12">
              <div className="flex items-center space-x-4 mb-4">
                <span className="text-sm text-slate-400 font-medium whitespace-nowrap">Banco:</span>
                <select 
                  className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-brand-blue outline-none transition-all"
                  value={banco}
                  onChange={(e) => setBanco(e.target.value)}
                >
                  {BANCOS.map(b => <option key={b} value={b}>{b}</option>)}
                </select>
                {resultado?.bancoDetectado && (
                  <span className="text-xs bg-brand-blue/10 text-brand-blue px-3 py-1 rounded-full border border-brand-blue/20">
                    Detectado: {resultado.bancoDetectado}
                  </span>
                )}
              </div>

              <button 
                disabled={loading}
                onClick={handleConciliar}
                className={`
                  w-full max-w-md py-4 rounded-2xl font-bold flex items-center justify-center space-x-3 transition-all transform active:scale-95
                  ${loading ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-brand-blue hover:bg-blue-600 text-white shadow-xl shadow-brand-blue/30'}
                `}
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-slate-500 border-t-white rounded-full animate-spin"></div>
                    <span>Procesando...</span>
                  </>
                ) : (
                  <>
                    <span>⚡</span>
                    <span>EJECUTAR CONCILIACIÓN</span>
                  </>
                )}
              </button>

              {error && (
                <div className="mt-4 flex items-center space-x-2 text-rose-400 bg-rose-500/10 p-3 rounded-xl border border-rose-500/20 text-sm">
                  <AlertCircle size={16} />
                  <span>{error}</span>
                </div>
              )}
            </section>

            {/* --- Results Section --- */}
            {resultado && (
              <section className="animate-in fade-in slide-in-from-bottom-5 duration-700">
                <h3 className="text-xl font-bold mb-6 flex items-center space-x-2">
                  <span>📊 Resultados: {resultado.summary?.titular}</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                  <ResultCard emoji="✅" label="Conciliados" value={resultado.summary?.n_conc} color="text-green-500" />
                  <ResultCard emoji="⚖️" label="Con Diferencia" value={resultado.summary?.n_diff} color="text-yellow-500" />
                  <ResultCard emoji="🏦" label="Solo Banco" value={resultado.summary?.n_banco} color="text-brand-blue" />
                  <ResultCard emoji="📋" label="Solo Sistema" value={resultado.summary?.n_sist} color="text-slate-400" />
                </div>

                <div className="glass p-10 rounded-3xl text-center mb-8 border border-emerald-500/20">
                  <div className="bg-emerald-500/10 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6">
                    <Receipt className="text-emerald-500" size={40} />
                  </div>
                  <h4 className="text-2xl font-bold mb-2">¡Conciliación Exitosa!</h4>
                  <p className="text-slate-400 mb-8 max-w-lg mx-auto">
                    Se han identificado <strong>{resultado.summary?.n_gastos}</strong> categorías de gastos e impuestos. 
                    El reporte detallado está listo para descargar.
                  </p>
                  <button 
                    onClick={handleDownload}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white px-10 py-4 rounded-2xl font-bold flex items-center space-x-3 mx-auto shadow-xl shadow-emerald-500/30 transition-all transform active:scale-95"
                  >
                    <Download size={20} />
                    <span>DESCARGAR REPORTE EXCEL</span>
                  </button>
                </div>
              </section>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-500">
            <LayoutDashboard size={64} className="mb-4 opacity-20" />
            <p className="text-xl font-medium">Esta sección estará disponible próximamente en la versión Cloud.</p>
            <button 
              onClick={() => setView('dashboard')}
              className="mt-6 text-brand-blue hover:underline font-medium"
            >
              Volver al Dashboard
            </button>
          </div>
        )}
      </main>
    </div>
  )
}

// --- Sub-componentes ---

function NavItem({ active, onClick, icon, label }) {
  return (
    <button 
      onClick={onClick}
      className={`flex items-center space-x-3 w-full p-3 rounded-xl transition-all ${
        active 
          ? 'bg-brand-blue text-white font-medium shadow-lg shadow-brand-blue/20' 
          : 'hover:bg-slate-800 text-slate-400'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

function DropZone({ title, hint, icon, files, onDrop, onSelect, onRemove, id }) {
  return (
    <div 
      className="glass p-8 rounded-3xl border-dashed border-2 border-slate-700 hover:border-brand-blue transition-colors group"
      onDragOver={(e) => e.preventDefault()}
      onDrop={onDrop}
    >
      <div className="flex flex-col items-center text-center">
        <div className="bg-slate-800 p-4 rounded-2xl mb-4 group-hover:scale-110 transition-transform">
          {icon}
        </div>
        <h3 className="text-lg font-semibold mb-1">{title}</h3>
        <p className="text-sm text-slate-400 mb-4">{hint}</p>
        <input 
          type="file" 
          multiple 
          className="hidden" 
          id={id} 
          onChange={onSelect} 
        />
        <label htmlFor={id} className="bg-slate-800 hover:bg-slate-700 px-6 py-2 rounded-xl text-sm font-medium cursor-pointer transition-colors border border-slate-700">
          Seleccionar archivos
        </label>
      </div>
      
      {files.length > 0 && (
        <div className="mt-6 space-y-2 border-t border-slate-800 pt-4">
          {files.map((f, i) => (
            <div key={i} className="flex items-center justify-between text-xs bg-brand-dark/50 p-2 rounded-lg border border-slate-800">
              <span className="truncate flex-1 pr-4">📄 {f.name}</span>
              <button onClick={() => onRemove(i)} className="text-rose-500 hover:bg-rose-500/10 p-1 rounded transition-colors">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ResultCard({ emoji, label, value, color }) {
  return (
    <div className="glass p-6 rounded-2xl flex flex-col items-center text-center border border-slate-700/50">
      <span className="text-2xl mb-2">{emoji}</span>
      <span className={`text-3xl font-bold ${color}`}>{value ?? '—'}</span>
      <span className="text-xs text-slate-500 uppercase font-bold tracking-widest">{label}</span>
    </div>
  )
}

export default App
