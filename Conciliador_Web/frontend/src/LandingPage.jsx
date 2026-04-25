import React, { useState } from 'react';
import { Lock, Check, Activity } from 'lucide-react';

export default function LandingPage({ onLogin, onRegister, authError, setView }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [authTab, setAuthTab] = useState('login'); // 'login' or 'register'
  const [successMode, setSuccessMode] = useState(false);
  
  // Form states
  const [loginForm, setLoginForm] = useState({ email: '', pass: '' });
  const [regForm, setRegForm] = useState({ name: '', email: '', pass: '' });

  const openModal = (tab) => {
    setAuthTab(tab);
    setModalOpen(true);
    setSuccessMode(false);
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    if (!loginForm.email || !loginForm.pass) return alert('Completá todos los campos');
    const success = await onLogin({ username: loginForm.email, password: loginForm.pass });
    if (success) setSuccessMode(true);
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    if (!regForm.name || !regForm.email || !regForm.pass) return alert('Completá todos los campos');
    if (regForm.pass.length < 8) return alert('La contraseña debe tener al menos 8 caracteres');
    
    const success = await onRegister({ 
      username: regForm.email, 
      password: regForm.pass,
      rol: 'usuario' // Por defecto
    });
    if (success) setSuccessMode(true);
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
            Contabilidad que<br />
            <em className="not-italic bg-gradient-to-r from-[#60a5fa] to-[#10b981] bg-clip-text text-transparent">trabaja por vos</em>
          </h1>
          
          <p className="text-[#94a3b8] text-lg max-w-xl mx-auto font-light leading-relaxed mb-10">
            Gestioná IVA, Ganancias, IIBB y más desde una sola plataforma. Diseñado para contadores, estudios y PyMEs argentinas.
          </p>
          
          <div className="flex flex-wrap justify-center gap-4">
            <button onClick={() => openModal('register')} className="lp-btn-primary px-8 py-3.5 rounded-xl text-base font-semibold">
              Empezar gratis — 14 días
            </button>
            <button onClick={() => openModal('login')} className="bg-transparent border border-white/10 hover:border-[#3b82f6] hover:text-[#60a5fa] text-white px-8 py-3.5 rounded-xl transition-all">
              Ya tengo cuenta →
            </button>
          </div>

          <div className="flex flex-wrap justify-center gap-12 mt-16">
            <div className="text-center">
              <div className="font-mono text-2xl font-medium"><span className="text-[#60a5fa]">+2.400</span></div>
              <div className="text-[11px] text-[#94a3b8] uppercase tracking-wider mt-1">empresas activas</div>
            </div>
            <div className="text-center">
              <div className="font-mono text-2xl font-medium"><span className="text-[#60a5fa]">98</span>%</div>
              <div className="text-[11px] text-[#94a3b8] uppercase tracking-wider mt-1">satisfacción</div>
            </div>
            <div className="text-center">
              <div className="font-mono text-2xl font-medium"><span className="text-[#60a5fa]">24/7</span></div>
              <div className="text-[11px] text-[#94a3b8] uppercase tracking-wider mt-1">actualización</div>
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
          <div className="font-mono text-[10px] text-[#60a5fa] uppercase tracking-[3px] mb-4">// el sistema en acción</div>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight">Así funciona tu nuevo Dashboard</h2>
          <p className="text-[#94a3b8] mt-4">Interfaz moderna, intuitiva y diseñada para la velocidad.</p>
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
          <p className="text-center text-[#475569] text-xs mt-12 italic">¿No ves tu banco? Lo desarrollamos a medida sin costo adicional.</p>
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
          <PriceCard name="INDEPENDIENTE" price="$14.900" desc="Para un solo profesional" features={["1 Usuario", "2 Bancos a elección", "Conciliaciones ilimitadas", "Soporte por email"]} onSelect={() => openModal('register')} />
          <PriceCard name="ESTUDIO" price="$32.500" desc="Para equipos pequeños" featured features={["3 Usuarios", "Todos los bancos", "Cruce de mayores avanzado", "Soporte por email prioritario"]} onSelect={() => openModal('register')} />
          <PriceCard name="CORPORATIVO" price="Consultar" desc="Grandes estudios / Integraciones" features={["Usuarios ilimitados", "Parsers a medida", "API de integración", "Soporte dedicado"]} onSelect={() => alert('Próximamente disponible. Contactanos por email.')} disabled />
        </div>

        {/* Comparison Table */}
        <div className="mt-24 overflow-x-auto lp-animate-fadeUp">
          <h3 className="text-2xl font-bold text-center mb-10">Comparativa de Planes</h3>
          <table className="w-full text-sm text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10">
                <th className="py-4 px-4 text-[#94a3b8] font-mono text-[10px] uppercase">Característica</th>
                <th className="py-4 px-4 text-center">Independiente</th>
                <th className="py-4 px-4 text-center text-[#60a5fa]">Estudio</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              <ComparisonRow label="Usuarios" v1="1" v2="3" />
              <ComparisonRow label="Bancos" v1="2" v2="Todos" />
              <ComparisonRow label="Cruce de Mayores" v1="Básico" v2="Avanzado" />
              <ComparisonRow label="Formatos" v1="PDF / Excel" v2="PDF / Excel" />
              <ComparisonRow label="Soporte" v1="Email" v2="Email Prioritario" />
              <ComparisonRow label="Actualizaciones" v1="Parsers" v2="Parsers (Bonificadas)" />
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
                <div className="flex border-b border-white/5">
                  <button onClick={() => setAuthTab('login')} className={`flex-1 py-4 text-sm font-semibold border-b-2 transition-all ${authTab === 'login' ? 'text-[#60a5fa] border-[#3b82f6]' : 'text-[#94a3b8] border-transparent'}`}>
                    Iniciar sesión
                  </button>
                  <button onClick={() => setAuthTab('register')} className={`flex-1 py-4 text-sm font-semibold border-b-2 transition-all ${authTab === 'register' ? 'text-[#60a5fa] border-[#3b82f6]' : 'text-[#94a3b8] border-transparent'}`}>
                    Registrarse
                  </button>
                </div>

                <div className="p-8">
                  {authTab === 'login' ? (
                    <form onSubmit={handleLoginSubmit} className="space-y-5">
                      <h3 className="text-xl font-bold">Bienvenido de vuelta</h3>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Email</label>
                        <input 
                          type="email" placeholder="tu@email.com" 
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={loginForm.email} onChange={e => setLoginForm({...loginForm, email: e.target.value})}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Contraseña</label>
                        <input 
                          type="password" placeholder="••••••••" 
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={loginForm.pass} onChange={e => setLoginForm({...loginForm, pass: e.target.value})}
                        />
                      </div>
                      <button type="submit" className="w-full bg-[#3b82f6] hover:bg-[#60a5fa] text-white py-3 rounded-xl font-semibold transition-all">
                        Ingresar al sistema →
                      </button>
                      {authError && <p className="text-red-400 text-xs text-center font-medium">{authError}</p>}
                    </form>
                  ) : (
                    <form onSubmit={handleRegisterSubmit} className="space-y-5">
                      <h3 className="text-xl font-bold">Crear cuenta gratis</h3>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Nombre completo</label>
                        <input 
                          type="text" placeholder="Tu Nombre" 
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={regForm.name} onChange={e => setRegForm({...regForm, name: e.target.value})}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Email profesional</label>
                        <input 
                          type="email" placeholder="tu@email.com" 
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={regForm.email} onChange={e => setRegForm({...regForm, email: e.target.value})}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-mono text-[#94a3b8] uppercase">Contraseña</label>
                        <input 
                          type="password" placeholder="Mínimo 8 caracteres" 
                          className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#3b82f6]"
                          value={regForm.pass} onChange={e => setRegForm({...regForm, pass: e.target.value})}
                        />
                      </div>
                      <button type="submit" className="w-full bg-[#3b82f6] hover:bg-[#60a5fa] text-white py-3 rounded-xl font-semibold transition-all">
                        Crear mi cuenta gratis →
                      </button>
                      {authError && <p className="text-red-400 text-xs text-center font-medium">{authError}</p>}
                    </form>
                  )}
                </div>
              </>
            ) : (
              <div className="p-12 text-center">
                <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto mb-6">
                  <Check className="text-[#10b981]" size={32} />
                </div>
                <h3 className="text-xl font-bold mb-2">¡Todo listo!</h3>
                <p className="text-[#94a3b8] text-sm mb-8">Tu sesión está activa. Ya podés acceder a tu panel de control.</p>
                <button 
                  onClick={() => window.location.reload()} 
                  className="w-full bg-[#10b981] hover:opacity-90 text-white py-3 rounded-xl font-semibold transition-all"
                >
                  Ir al panel →
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ComparisonRow({ label, v1, v2 }) {
  return (
    <tr>
      <td className="py-5 px-4 font-medium text-[#f1f5f9]">{label}</td>
      <td className="py-5 px-4 text-center text-[#94a3b8]">{v1}</td>
      <td className="py-5 px-4 text-center text-[#60a5fa] font-semibold">{v2}</td>
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
