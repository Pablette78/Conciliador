import React, { useState } from 'react';
import { Lock, Check, Activity } from 'lucide-react';
import { GoogleLogin } from '@react-oauth/google';

export default function LandingPage({ onLogin, onRegister, onGoogleLogin, authError, onForgotPassword, setView }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [authTab, setAuthTab] = useState('login'); // 'login' | 'register' | 'forgot'
  const [successMode, setSuccessMode] = useState(false); // false | 'login' | 'registered' | 'forgot'

  // Form states
  const [loginForm, setLoginForm]   = useState({ user: '', pass: '' });
  const [regForm, setRegForm]       = useState({ username: '', email: '', pass: '', plan: 'Free' });
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);

  const openModal = (tab) => {
    setAuthTab(tab);
    setModalOpen(true);
    setSuccessMode(false);
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    if (!loginForm.user || !loginForm.pass) return alert('Completá todos los campos');
    const success = await onLogin({ username: loginForm.user, password: loginForm.pass });
    if (success) setSuccessMode('login');
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    if (!regForm.username || !regForm.email || !regForm.pass) return alert('Completá todos los campos');
    if (regForm.pass.length < 8) return alert('La contraseña debe tener al menos 8 caracteres');
    const result = await onRegister({
      username: regForm.username,
      email: regForm.email,
      password: regForm.pass,
      rol: 'usuario',
      plan: regForm.plan
    });
    if (result === 'registered') setSuccessMode('registered');
  };

  const handleForgotSubmit = async (e) => {
    e.preventDefault();
    if (!forgotEmail) return;
    setForgotLoading(true);
    try {
      await onForgotPassword(forgotEmail);
      setSuccessMode('forgot');
    } catch { alert('Error al procesar la solicitud.'); }
    finally { setForgotLoading(false); }
  };

  return (
    <div className="bg-[#0a0e1a] text-[#f1f5f9] min-h-screen font-landing overflow-x-hidden">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-[100] flex items-center justify-between px-6 md:px-12 h-[68px] bg-[#0a0e1a]/85 backdrop-blur-xl border-b border-white/5">
        <div className="font-mono text-xl font-medium tracking-tight">
          Conta<span className="text-[#60a5fa]">Flex</span>
        </div>
        <div className="hidden md:flex gap-8 items-center">
          <a href="#features" className="text-sm text-[#94a3b8] hover:text-white transition-colors">Funciones</a>
          <a href="#como-funciona" className="text-sm text-[#94a3b8] hover:text-white transition-colors">Cómo funciona</a>
          <a href="#precios" className="text-sm text-[#94a3b8] hover:text-white transition-colors">Precios</a>
          <button 
            onClick={() => openModal('login')}
            className="bg-[#3b82f6] text-white px-5 py-2 rounded-lg text-sm font-semibold hover:bg-[#60a5fa] transition-all transform hover:-translate-y-px"
          >
            Iniciar sesión
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative min-h-screen flex flex-col items-center justify-center px-6 text-center pt-24 pb-20 overflow-hidden">
        <div className="lp-hero-bg absolute inset-0 z-0"></div>
        <div className="lp-grid-lines absolute inset-0 z-0"></div>
        
        <div className="relative z-10 lp-animate-fadeUp">
          <div className="inline-flex items-center gap-2 bg-[#3b82f6]/10 border border-[#3b82f6]/30 rounded-full px-4 py-1.5 text-[11px] font-mono text-[#60a5fa] mb-8">
            <div className="w-1.5 h-1.5 rounded-full bg-[#10b981] lp-animate-pulse shadow-[0_0_8px_#10b981]"></div>
            Sistema contable 100% argentino
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold leading-[1.1] tracking-tight mb-6">
            Automatiza tu conciliación en <br />
            <em className="not-italic bg-gradient-to-r from-[#60a5fa] to-[#10b981] bg-clip-text text-transparent">minutos, no en horas</em>
          </h1>
          
          <p className="text-[#94a3b8] text-lg max-w-xl mx-auto font-light leading-relaxed mb-10">
            Recuperá tu tiempo, evitá errores ante AFIP y mantené el orden financiero de tu empresa o estudio sin depender de Excel manuales.
          </p>
          
          <div className="flex flex-wrap justify-center gap-4">
            <button onClick={() => openModal('register')} className="lp-btn-primary px-8 py-3.5 rounded-xl text-base font-semibold">
              Empezar ahora — Gratis
            </button>
            <button onClick={() => openModal('login')} className="bg-transparent border border-white/10 hover:border-[#3b82f6] hover:text-[#60a5fa] text-white px-8 py-3.5 rounded-xl transition-all">
              Ya tengo cuenta →
            </button>
          </div>

          <div className="flex flex-wrap justify-center gap-12 mt-16">
            <div className="text-center">
              <div className="font-mono text-2xl font-medium"><span className="text-[#60a5fa]">+17</span></div>
              <div className="text-[11px] text-[#94a3b8] uppercase tracking-wider mt-1">bancos e instituciones</div>
            </div>
            <div className="text-center">
              <div className="font-mono text-2xl font-medium"><span className="text-[#60a5fa]">MULTI</span></div>
              <div className="text-[11px] text-[#94a3b8] uppercase tracking-wider mt-1">extractos en simultáneo</div>
            </div>
            <div className="text-center">
              <div className="font-mono text-2xl font-medium"><span className="text-[#60a5fa]">100</span>%</div>
              <div className="text-[11px] text-[#94a3b8] uppercase tracking-wider mt-1">proceso automatizado</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-24" id="features">
        <div className="font-mono text-[10px] text-[#60a5fa] uppercase tracking-[3px] mb-4">// funcionalidades</div>
        <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-12">
          Todo lo que tu estudio<br />necesita, en un lugar
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <FeatureCard icon="🏦" title="Parsers Multibanco" desc="Lectura inteligente de extractos PDF y Excel de Santander, Galicia, BBVA, Ciudad, Comafi y más." />
          <FeatureCard icon="🎯" title="Conciliación Inteligente" desc="Cruce automático de movimientos bancarios contra tus mayores contables (XLSX) en segundos." />
          <FeatureCard icon="📑" title="Reportes de Auditoría" desc="Generación de planillas Excel con fórmulas automáticas, listas para presentar al contador." />
          <FeatureCard icon="🔍" title="Detección de Faltantes" desc="Identifica instantáneamente qué movimientos están solo en el banco o solo en tu sistema." />
          <FeatureCard icon="⚡" title="Procesamiento Cloud" desc="Sin instalaciones pesadas. Subí tus archivos y obtené el resultado desde cualquier lugar." />
          <FeatureCard icon="🛡️" title="Control de Integridad" desc="Validación matemática de saldos iniciales y finales para asegurar que no falte ni un centavo." />
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-6xl mx-auto px-6 py-24 border-t border-white/5" id="como-funciona">
        <div className="text-center mb-16">
          <div className="font-mono text-[10px] text-[#60a5fa] uppercase tracking-[3px] mb-4">// simple y rápido</div>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight">Conciliación en 3 simples pasos</h2>
          <p className="text-[#94a3b8] mt-4">Olvídate de cruzar filas a mano. Nuestra plataforma lo hace por vos.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20">
          <div className="bg-[#141c2e] border border-white/5 rounded-2xl p-8 text-center relative hover:border-[#3b82f6]/30 transition-all hover:-translate-y-1">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-[#3b82f6] text-white flex items-center justify-center font-bold font-mono shadow-[0_0_15px_rgba(59,130,246,0.5)]">1</div>
            <div className="text-3xl mb-4 mt-2">📥</div>
            <h3 className="text-xl font-bold mb-3">Subí tus datos</h3>
            <p className="text-[#94a3b8] text-sm leading-relaxed">Carga el extracto del banco (PDF/Excel) y tu mayor contable. Leemos cualquier formato.</p>
          </div>
          <div className="bg-[#141c2e] border border-white/5 rounded-2xl p-8 text-center relative hover:border-[#10b981]/30 transition-all hover:-translate-y-1">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-[#10b981] text-white flex items-center justify-center font-bold font-mono shadow-[0_0_15px_rgba(16,185,129,0.5)]">2</div>
            <div className="text-3xl mb-4 mt-2">🧠</div>
            <h3 className="text-xl font-bold mb-3">Cruce Inteligente</h3>
            <p className="text-[#94a3b8] text-sm leading-relaxed">El algoritmo empareja movimientos y detecta diferencias al instante con precisión matemática.</p>
          </div>
          <div className="bg-[#141c2e] border border-white/5 rounded-2xl p-8 text-center relative hover:border-[#60a5fa]/30 transition-all hover:-translate-y-1">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-[#60a5fa] text-white flex items-center justify-center font-bold font-mono shadow-[0_0_15px_rgba(96,165,250,0.5)]">3</div>
            <div className="text-3xl mb-4 mt-2">📊</div>
            <h3 className="text-xl font-bold mb-3">Reporte Listo</h3>
            <p className="text-[#94a3b8] text-sm leading-relaxed">Descarga un Excel auditado, con fórmulas armadas y listo para presentar sin miedo a errores.</p>
          </div>
        </div>

        {/* Dashboard Preview */}
        <div className="text-center mb-10">
          <h3 className="text-2xl md:text-3xl font-bold tracking-tight">Así se ve la plataforma</h3>
        </div>

        <div className="relative mx-auto max-w-4xl rounded-2xl border border-white/10 bg-[#0f172a] shadow-2xl overflow-hidden group">
          {/* Browser Header Decor */}
          <div className="h-10 bg-[#1e293b] border-b border-white/5 flex items-center px-4 gap-2">
            <div className="w-3 h-3 rounded-full bg-[#ef4444]/50"></div>
            <div className="w-3 h-3 rounded-full bg-[#f59e0b]/50"></div>
            <div className="w-3 h-3 rounded-full bg-[#10b981]/50"></div>
            <div className="ml-4 h-5 w-48 bg-[#0f172a] rounded-md border border-white/5 flex items-center px-2">
              <div className="text-[10px] text-[#475569] font-mono">contaflex.ar/dashboard</div>
            </div>
          </div>

          {/* Screenshot Container with masking */}
          <div className="relative aspect-video overflow-y-auto scrollbar-hide max-h-[500px]">
            {/* The Screenshots Joined */}
            <div className="flex flex-col">
              <img src="/dash_top.png" alt="Dashboard Top" className="w-full h-auto block" />
              <img src="/dash_bottom.png" alt="Dashboard Bottom" className="w-full h-auto block" />
            </div>

            {/* PRIVACY MASKS: Blocking the email areas */}
            {/* Top Right Email */}
            <div className="absolute top-[2.5%] right-[2%] w-[150px] h-[30px] bg-[#0a0e1a] backdrop-blur-xl border border-white/5 rounded pointer-events-none flex items-center justify-center">
              <div className="text-[8px] font-mono text-[#475569]">USUARIO PROTEGIDO</div>
            </div>
            {/* Bottom Left Email (Fixed Sidebar) */}
            <div className="absolute top-[88%] left-[2%] w-[140px] h-[40px] bg-[#0a0e1a] backdrop-blur-xl border border-white/5 rounded pointer-events-none flex items-center justify-center">
              <div className="text-[8px] font-mono text-[#475569]">USUARIO PROTEGIDO</div>
            </div>
          </div>

          {/* Overlay on hover hint */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0a0e1a] via-transparent to-transparent opacity-40 pointer-events-none"></div>
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-[#3b82f6]/20 border border-[#3b82f6]/40 backdrop-blur-md px-6 py-2 rounded-full text-xs font-semibold text-[#60a5fa] animate-bounce">
            Hacé scroll para ver más ↓
          </div>
        </div>

        {/* Supported Banks Grid */}
        <div className="mt-20">
          <p className="text-center text-[#475569] font-mono text-[10px] uppercase tracking-[2px] mb-12">// entidades soportadas</p>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-8 max-w-5xl mx-auto px-4">
            {[
              { n: "Santander", id: "santander" },
              { n: "Galicia", id: "galicia" },
              { n: "BBVA", id: "bbva" },
              { n: "Macro", id: "macro" },
              { n: "Nación", id: "nacion" },
              { n: "Provincia", id: "provincia" },
              { n: "Credicoop", id: "credicoop" },
              { n: "HSBC", id: "hsbc" },
              { n: "ICBC", id: "icbc" },
              { n: "Supervielle", id: "supervielle" },
              { n: "Ciudad", id: "ciudad" },
              { n: "Comafi", id: "comafi" },
              { n: "ARCA", id: "arca" },
              { n: "VISA", id: "visa" }
            ].map((banco) => (
              <div key={banco.n} className="group flex flex-col items-center justify-center gap-3 transition-all duration-500">
                <div className="h-10 w-24 flex items-center justify-center opacity-60 group-hover:opacity-100 transition-all">
                  <img 
                    src={`/logos/${banco.id}.png`} 
                    alt={banco.n} 
                    className="max-h-full max-w-full object-contain"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                </div>
                <span className="text-[10px] font-medium text-[#94a3b8] group-hover:text-[#60a5fa] transition-colors">{banco.n}</span>
              </div>
            ))}
          </div>
          <p className="text-center text-[#475569] text-xs mt-12 italic">
            ¿No ves tu banco? Lo desarrollamos a medida sin costo adicional.<br/>
            <a href="mailto:soporte@contaflex.ar" className="text-[#60a5fa] hover:underline mt-1 inline-block">soporte@contaflex.ar</a>
          </p>
        </div>
      </section>

      {/* File Flexibility & Compatibility */}
      <section className="max-w-6xl mx-auto px-6 py-24 border-t border-white/5" id="compatibilidad">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-6 lp-animate-fadeUp">
            <div className="font-mono text-[10px] text-[#60a5fa] uppercase tracking-[3px]">// compatibilidad sin fricción</div>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight leading-[1.15]">
              Subí tus archivos tal <br />
              <span className="bg-gradient-to-r from-[#60a5fa] to-[#10b981] bg-clip-text text-transparent">como salen de tu sistema</span>
            </h2>
            <p className="text-[#94a3b8] font-light leading-relaxed">
              Olvidate de las plantillas rígidas y de perder tiempo formateando columnas. Nuestro lector inteligente se adapta a tu forma de trabajar.
            </p>
            <div className="space-y-4">
              <div className="flex items-start gap-4">
                <div className="text-xl bg-[#60a5fa]/10 p-2.5 rounded-lg text-[#60a5fa] shrink-0">🤖</div>
                <div>
                  <h4 className="font-bold text-white text-base">Mapeo Inteligente de Columnas</h4>
                  <p className="text-sm text-[#94a3b8] mt-1">
                    El sistema detecta automáticamente columnas como <em>Fecha, Debe, Haber, Detalle</em> o <em>Documento</em>. Compatible con exportaciones directas de <strong>Tango, Bejerman, SAP, Xero, Colppy</strong> y más.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <div className="text-xl bg-[#10b981]/10 p-2.5 rounded-lg text-[#10b981] shrink-0">⚡</div>
                <div>
                  <h4 className="font-bold text-white text-base">Mayor Contable 100% Opcional</h4>
                  <p className="text-sm text-[#94a3b8] mt-1">
                    ¿Solo querés listar tus movimientos bancarios o procesar las tarjetas? Podés iniciar la conciliación sin subir un archivo de Mayor. El sistema asume valores en cero automáticamente.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <div className="text-xl bg-[#a78bfa]/10 p-2.5 rounded-lg text-[#a78bfa] shrink-0">💳</div>
                <div>
                  <h4 className="font-bold text-white text-base">Soporte Multimoneda (USD/ARS)</h4>
                  <p className="text-sm text-[#94a3b8] mt-1">
                    Ideal para tarjetas de crédito. Ahora podés procesar sin restricciones consumos tanto en pesos como en dólares (USD). Los consumos internacionales se destacan de forma automática en el reporte.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-[#141c2e] border border-white/5 rounded-3xl p-8 md:p-12 space-y-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#3b82f6]/5 blur-3xl rounded-full"></div>
            <div className="flex justify-between items-center border-b border-white/5 pb-4">
              <span className="text-xs font-mono text-[#94a3b8]">EJEMPLO DE DETECCIÓN INTELIGENTE</span>
              <span className="bg-emerald-500/10 text-emerald-400 text-[9px] font-bold px-2 py-0.5 rounded border border-emerald-500/20">ACTIVO</span>
            </div>
            
            <div className="space-y-4">
              <div className="bg-[#0a0e1a]/80 border border-white/5 rounded-2xl p-4 space-y-3">
                <p className="text-xs font-mono text-[#60a5fa]">// El motor reconoce tus columnas sin importar el orden:</p>
                <div className="grid grid-cols-4 gap-2 text-[10px] font-mono text-[#94a3b8] border-b border-white/5 pb-2">
                  <div className="text-emerald-400 font-bold">FECHA REGISTRO</div>
                  <div className="text-emerald-400 font-bold">OPERACIÓN Nº</div>
                  <div className="text-emerald-400 font-bold">FONDOS INGRESADOS</div>
                  <div className="text-emerald-400 font-bold">EGRESOS</div>
                </div>
                <div className="grid grid-cols-4 gap-2 text-[9px] font-mono text-[#475569]">
                  <div>15/05/2025</div>
                  <div>OP-9982</div>
                  <div>$ 150.000,00</div>
                  <div>$ 0,00</div>
                </div>
              </div>
              <p className="text-xs text-[#94a3b8] leading-relaxed">
                💡 <strong>¿Cómo funciona?</strong> No importa si tu columna se llama <em>"Debe"</em>, <em>"Ingreso"</em> o <em>"Fondos Ingresados"</em>, ni en qué orden estén posicionadas. El algoritmo de ContaFlex analiza la estructura y las palabras clave de tu planilla y hace el trabajo por vos.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="max-w-6xl mx-auto px-6 py-24 border-t border-white/5" id="precios">
        <div className="text-center mb-16">
          <div className="font-mono text-[10px] text-[#60a5fa] uppercase tracking-[3px] mb-4">// planes</div>
          <h2 className="text-4xl font-bold tracking-tight">Elegí el plan ideal</h2>
          <p className="text-[#94a3b8] mt-4">Sin permanencias. Cancelá cuando quieras. Precios en pesos.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <PriceCard name="GRATIS" price="Free" desc="Para conocer la herramienta" features={["5 conciliaciones/mes", "+17 bancos soportados", "PDF y Excel", "Exportación con fórmulas"]} onSelect={() => { setRegForm(f => ({...f, plan: 'Free'})); openModal('register'); }} />
          <PriceCard name="INDIVIDUAL" price="$14.900" desc="Para el profesional independiente" featured features={["20 conciliaciones/mes", "+17 bancos soportados", "Múltiples extractos en simultáneo", "Soporte por email"]} onSelect={() => { setRegForm(f => ({...f, plan: 'Individual'})); openModal('register'); }} />
          <PriceCard name="ESTUDIO" price="$32.500" desc="Para estudios contables" features={["100 conciliaciones/mes", "+17 bancos soportados", "Múltiples extractos en simultáneo", "Soporte prioritario"]} onSelect={() => { setRegForm(f => ({...f, plan: 'Estudio'})); openModal('register'); }} />
        </div>

        {/* Comparison Table */}
        <div className="mt-24 overflow-x-auto lp-animate-fadeUp">
          <h3 className="text-2xl font-bold text-center mb-10">Comparativa de Planes</h3>
          <table className="w-full text-sm text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10">
                <th className="py-4 px-4 text-[#94a3b8] font-mono text-[10px] uppercase">Característica</th>
                <th className="py-4 px-4 text-center text-[#94a3b8]">Gratis</th>
                <th className="py-4 px-4 text-center text-[#60a5fa]">Individual</th>
                <th className="py-4 px-4 text-center text-[#a78bfa]">Estudio</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              <ComparisonRow label="Conciliaciones/mes" v1="5" v2="20" v3="100" />
              <ComparisonRow label="Bancos e instituciones" v1="+17" v2="+17" v3="+17" />
              <ComparisonRow label="Formatos de entrada" v1="PDF + Excel" v2="PDF + Excel" v3="PDF + Excel" />
              <ComparisonRow label="Múltiples extractos" v1="✓" v2="✓" v3="✓" />
              <ComparisonRow label="Exportación con fórmulas" v1="✓" v2="✓" v3="✓" />
              <ComparisonRow label="Cruce con libro mayor" v1="✓" v2="✓" v3="✓" />
              <ComparisonRow label="Soporte" v1="Básico" v2="Email" v3="Prioritario" />
              <ComparisonRow label="Precio/mes" v1="Gratis" v2="$14.900" v3="$32.500" />
            </tbody>
          </table>
        </div>
      </section>

      {/* CTA Footer */}
      <footer className="border-t border-white/5 py-12 px-6 flex flex-col md:flex-row justify-between items-center gap-6 max-w-6xl mx-auto">
        <div className="font-mono text-lg font-medium">Conta<span>Flex</span></div>
        <p className="text-xs text-[#94a3b8]">© 2025 ContaFlex. Hecho en Argentina 🇦🇷</p>
        <div className="flex gap-6">
          <button onClick={() => setView('terminos')} className="text-xs text-[#94a3b8] hover:text-[#60a5fa] bg-transparent border-none cursor-pointer">Términos</button>
          <button onClick={() => setView('privacidad')} className="text-xs text-[#94a3b8] hover:text-[#60a5fa] bg-transparent border-none cursor-pointer">Privacidad</button>
        </div>
      </footer>

      {/* Auth Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in" onClick={(e) => e.target === e.currentTarget && setModalOpen(false)}>
          <div className="bg-[#141c2e] border border-white/10 rounded-2xl w-full max-w-[420px] overflow-hidden relative">
            <button onClick={() => setModalOpen(false)} className="absolute top-4 right-5 text-[#94a3b8] text-2xl hover:text-white">×</button>
            
            {!successMode ? (
              <>
                {/* Tabs — ocultas en modo forgot */}
                {authTab !== 'forgot' && (
                  <div className="flex border-b border-white/5">
                    <button onClick={() => setAuthTab('login')} className={`flex-1 py-4 text-sm font-semibold border-b-2 transition-all ${authTab === 'login' ? 'text-[#60a5fa] border-[#3b82f6]' : 'text-[#94a3b8] border-transparent'}`}>
                      Iniciar sesión
                    </button>
                    <button onClick={() => setAuthTab('register')} className={`flex-1 py-4 text-sm font-semibold border-b-2 transition-all ${authTab === 'register' ? 'text-[#60a5fa] border-[#3b82f6]' : 'text-[#94a3b8] border-transparent'}`}>
                      Registrarse
                    </button>
                  </div>
                )}

                <div className="p-8">
                  {/* LOGIN */}
                  {authTab === 'login' && (
                    <form onSubmit={handleLoginSubmit} className="space-y-5">
                      <h3 className="text-xl font-bold">Bienvenido de vuelta</h3>
                      
                      {/* Botón de Google Login */}
                      <div className="w-full flex justify-center">
                        <GoogleLogin
                          onSuccess={credentialResponse => {
                            onGoogleLogin(credentialResponse.credential, 'Free');
                          }}
                          onError={() => {
                            alert('Error en el inicio de sesión con Google');
                          }}
                          useOneTap
                          theme="filled_blue"
                          shape="pill"
                          width="356" // Ancho aproximado para el modal
                          locale="es"
                        />
                      </div>

                      <div className="relative flex py-2 items-center">
                        <div className="flex-grow border-t border-white/5"></div>
                        <span className="flex-shrink mx-4 text-[10px] text-slate-500 font-mono uppercase tracking-widest">o con tu email</span>
                        <div className="flex-grow border-t border-white/5"></div>
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Usuario o Email</label>
                        <input type="text" placeholder="usuario o tu@email.com"
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={loginForm.user} onChange={e => setLoginForm({...loginForm, user: e.target.value})} />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Contraseña</label>
                        <input type="password" placeholder="••••••••"
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={loginForm.pass} onChange={e => setLoginForm({...loginForm, pass: e.target.value})} />
                      </div>
                      <button type="submit" className="w-full bg-[#3b82f6] hover:bg-[#60a5fa] text-white py-3 rounded-xl font-semibold transition-all">
                        Ingresar al sistema →
                      </button>
                      <button type="button" onClick={() => setAuthTab('forgot')}
                        className="w-full text-[10px] text-[#94a3b8] hover:text-[#60a5fa] transition-colors">
                        ¿Olvidaste tu contraseña?
                      </button>
                      {authError && <p className="text-red-400 text-xs text-center font-medium">{authError}</p>}
                    </form>
                  )}

                  {/* REGISTRO */}
                  {authTab === 'register' && (
                    <form onSubmit={handleRegisterSubmit} className="space-y-4">
                      <h3 className="text-xl font-bold">Crear cuenta</h3>
                      
                      {/* Botón de Google Login */}
                      <div className="w-full flex justify-center">
                        <GoogleLogin
                          onSuccess={credentialResponse => {
                            onGoogleLogin(credentialResponse.credential, regForm.plan);
                          }}
                          onError={() => {
                            alert('Error en el registro con Google');
                          }}
                          useOneTap
                          theme="filled_blue"
                          shape="pill"
                          width="356"
                          locale="es"
                        />
                      </div>

                      <div className="relative flex py-2 items-center">
                        <div className="flex-grow border-t border-white/5"></div>
                        <span className="flex-shrink mx-4 text-[10px] text-slate-500 font-mono uppercase tracking-widest">o con tu email</span>
                        <div className="flex-grow border-t border-white/5"></div>
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Nombre de usuario</label>
                        <input type="text" placeholder="Ej: pablo.ponti"
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={regForm.username} onChange={e => setRegForm({...regForm, username: e.target.value})} />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Email</label>
                        <input type="email" placeholder="tu@email.com"
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={regForm.email} onChange={e => setRegForm({...regForm, email: e.target.value})} />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Contraseña</label>
                        <input type="password" placeholder="Mínimo 8 caracteres"
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={regForm.pass} onChange={e => setRegForm({...regForm, pass: e.target.value})} />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Plan</label>
                        <select className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={regForm.plan} onChange={e => setRegForm({...regForm, plan: e.target.value})}>
                          <option value="Free">Free — 5 usos/mes (gratis)</option>
                          <option value="Individual">Individual — 20 usos/mes</option>
                          <option value="Estudio">Estudio — 100 usos/mes</option>
                        </select>
                      </div>
                      <button type="submit" className="w-full bg-[#3b82f6] hover:bg-[#60a5fa] text-white py-3 rounded-xl font-semibold transition-all">
                        Crear cuenta →
                      </button>
                      {authError && <p className="text-red-400 text-xs text-center font-medium">{authError}</p>}
                    </form>
                  )}

                  {/* OLVIDÉ MI CONTRASEÑA */}
                  {authTab === 'forgot' && (
                    <form onSubmit={handleForgotSubmit} className="space-y-5">
                      <button type="button" onClick={() => setAuthTab('login')}
                        className="text-[#94a3b8] text-xs hover:text-white flex items-center gap-1">
                        ← Volver al login
                      </button>
                      <h3 className="text-xl font-bold">Recuperar contraseña</h3>
                      <p className="text-[#94a3b8] text-sm">Ingresá tu email o usuario y te enviamos un link para crear una nueva contraseña.</p>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Email o Usuario</label>
                        <input type="text" placeholder="tu@email.com"
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={forgotEmail} onChange={e => setForgotEmail(e.target.value)} />
                      </div>
                      <button type="submit" disabled={forgotLoading}
                        className="w-full bg-[#3b82f6] hover:bg-[#60a5fa] text-white py-3 rounded-xl font-semibold transition-all disabled:opacity-50">
                        {forgotLoading ? 'Enviando...' : 'Enviar instrucciones →'}
                      </button>
                    </form>
                  )}
                </div>
              </>
            ) : (
              /* SUCCESS SCREENS */
              <div className="p-12 text-center">
                {successMode === 'login' && (
                  <>
                    <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto mb-6">
                      <Check className="text-[#10b981]" size={32} />
                    </div>
                    <h3 className="text-xl font-bold mb-2">¡Todo listo!</h3>
                    <p className="text-[#94a3b8] text-sm mb-8">Tu sesión está activa.</p>
                    <button onClick={() => window.location.reload()}
                      className="w-full bg-[#10b981] hover:opacity-90 text-white py-3 rounded-xl font-semibold transition-all">
                      Ir al panel →
                    </button>
                  </>
                )}
                {successMode === 'registered' && (
                  <>
                    <div className="w-16 h-16 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center mx-auto mb-6">
                      <Check className="text-[#60a5fa]" size={32} />
                    </div>
                    <h3 className="text-xl font-bold mb-2">¡Registro exitoso!</h3>
                    <p className="text-[#94a3b8] text-sm mb-2">Te enviamos un email de verificación.</p>
                    <p className="text-[#94a3b8] text-sm mb-8">Revisá tu casilla y hacé clic en el link para activar tu cuenta.</p>
                    <button onClick={() => setModalOpen(false)}
                      className="w-full bg-[#3b82f6] hover:opacity-90 text-white py-3 rounded-xl font-semibold transition-all">
                      Entendido
                    </button>
                  </>
                )}
                {successMode === 'forgot' && (
                  <>
                    <div className="w-16 h-16 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center mx-auto mb-6">
                      <Check className="text-[#60a5fa]" size={32} />
                    </div>
                    <h3 className="text-xl font-bold mb-2">Email enviado</h3>
                    <p className="text-[#94a3b8] text-sm mb-8">Si el email existe en el sistema, recibirás las instrucciones para recuperar tu contraseña.</p>
                    <button onClick={() => { setModalOpen(false); setSuccessMode(false); setAuthTab('login'); }}
                      className="w-full bg-[#3b82f6] hover:opacity-90 text-white py-3 rounded-xl font-semibold transition-all">
                      Volver al inicio
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ComparisonRow({ label, v1, v2, v3 }) {
  const render = (v) => {
    if (v === '✓') return <span className="text-[#10b981] text-base font-bold">✓</span>;
    if (v === '—') return <span className="text-[#334155]">—</span>;
    return v;
  };
  return (
    <tr>
      <td className="py-5 px-4 font-medium text-[#f1f5f9]">{label}</td>
      <td className="py-5 px-4 text-center text-[#94a3b8]">{render(v1)}</td>
      <td className="py-5 px-4 text-center text-[#60a5fa] font-semibold">{render(v2)}</td>
      <td className="py-5 px-4 text-center text-[#a78bfa] font-semibold">{render(v3)}</td>
    </tr>
  );
}

function FeatureCard({ icon, title, desc }) {
  return (
    <div className="bg-[#141c2e] border border-white/5 rounded-2xl p-8 transition-all hover:border-[#3b82f6]/30 hover:-translate-y-1">
      <div className="w-11 h-11 rounded-lg bg-[#3b82f6]/10 border border-[#3b82f6]/30 flex items-center justify-center text-xl mb-5">
        {icon}
      </div>
      <h4 className="font-semibold mb-3">{title}</h4>
      <p className="text-sm text-[#94a3b8] leading-relaxed">{desc}</p>
    </div>
  );
}

function PriceCard({ name, price, desc, features, featured, onSelect, disabled }) {
  return (
    <div className={`bg-[#141c2e] border rounded-2xl p-8 transition-all flex flex-col ${featured ? 'border-[#3b82f6] relative scale-105 z-10' : 'border-white/5'}`}>
      {featured && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#3b82f6] text-white text-[10px] font-bold px-4 py-1 rounded-full uppercase tracking-wider">
          Más popular
        </div>
      )}
      <div className="font-mono text-xs text-[#94a3b8] mb-4">{name}</div>
      <div className="text-4xl font-bold font-mono tracking-tight mb-2">{price}</div>
      <div className="text-sm text-[#94a3b8] mb-8">{desc}</div>
      <ul className="space-y-3 mb-8 flex-1">
        {features.map((f, i) => (
          <li key={i} className="text-sm text-[#94a3b8] flex items-center gap-3">
            <span className="text-[#10b981]">✓</span> {f}
          </li>
        ))}
      </ul>
      <button 
        onClick={onSelect}
        disabled={disabled}
        className={`w-full py-3 rounded-xl font-semibold transition-all ${disabled ? 'bg-white/5 text-[#94a3b8] cursor-not-allowed' : featured ? 'bg-[#3b82f6] text-white hover:bg-[#60a5fa]' : 'bg-transparent border border-white/10 text-white hover:border-[#3b82f6]'}`}
      >
        {disabled ? 'Consultar' : 'Empezar gratis'}
      </button>
    </div>
  );
}
