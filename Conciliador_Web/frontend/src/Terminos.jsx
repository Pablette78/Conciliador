export default function Terminos({ onBack }) {
  return (
    <div className="min-h-screen bg-[#0a0e1a] text-[#f1f5f9] px-6 py-12">
      <div className="max-w-3xl mx-auto">
        <button
          onClick={onBack}
          className="mb-8 text-xs font-mono text-[#60a5fa] hover:text-white transition-colors flex items-center gap-2"
        >
          ← Volver
        </button>

        <h1 className="text-3xl font-bold mb-2">Términos y Condiciones de Uso</h1>
        <p className="text-xs text-[#475569] mb-10">Última actualización: mayo de 2025</p>

        <div className="space-y-8 text-sm text-[#94a3b8] leading-relaxed">

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">1. Descripción del servicio</h2>
            <p>ContaFlex es una plataforma web de conciliación bancaria automatizada. Permite a profesionales y estudios contables procesar extractos bancarios (en formato PDF y Excel), cruzarlos con el libro mayor y generar reportes de auditoría en formato Excel.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">2. Registro y cuenta</h2>
            <p>Para utilizar el servicio es necesario crear una cuenta con nombre de usuario, dirección de correo electrónico y contraseña. El usuario es responsable de mantener la confidencialidad de sus credenciales. Cada cuenta es personal e intransferible.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">3. Planes y límites de uso</h2>
            <p className="mb-3">El servicio se ofrece en tres modalidades:</p>
            <ul className="space-y-1 pl-4 list-disc">
              <li><span className="text-[#f1f5f9] font-medium">Free:</span> 5 conciliaciones por mes, sin costo.</li>
              <li><span className="text-[#f1f5f9] font-medium">Individual:</span> 20 conciliaciones por mes, $14.900 ARS/mes.</li>
              <li><span className="text-[#f1f5f9] font-medium">Estudio:</span> 100 conciliaciones por mes, $32.500 ARS/mes.</li>
            </ul>
            <p className="mt-3">Los límites se reinician el primer día de cada mes calendario. El uso no consumido no se acumula ni se transfiere.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">4. Pagos y suscripciones</h2>
            <p>Los planes pagos se gestionan mediante suscripción mensual a través de Mercado Pago. El cobro se realiza automáticamente cada mes en la fecha de activación. El usuario puede cancelar su suscripción en cualquier momento desde su perfil; la cancelación tiene efecto al vencimiento del período ya abonado. ContaFlex no realiza reintegros proporcionales por períodos no utilizados.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">5. Procesamiento de archivos</h2>
            <p>Los archivos subidos (extractos bancarios, libros mayores) se procesan en tiempo real y se eliminan de los servidores de forma automática una vez generado el reporte. ContaFlex no almacena el contenido de los documentos financieros del usuario.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">6. Exactitud de los resultados</h2>
            <p>ContaFlex automatiza el proceso de conciliación, pero el usuario es el único responsable de verificar y validar los resultados antes de utilizarlos en declaraciones impositivas, presentaciones profesionales o cualquier otro fin. La plataforma no reemplaza el criterio profesional del contador.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">7. Propiedad intelectual</h2>
            <p>Todo el software, algoritmos, diseño e interfaces de ContaFlex son propiedad exclusiva de sus desarrolladores. Queda prohibida su reproducción, distribución o ingeniería inversa sin autorización expresa.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">8. Modificaciones del servicio</h2>
            <p>ContaFlex se reserva el derecho de modificar los planes, precios o funcionalidades con un preaviso mínimo de 30 días comunicado por correo electrónico. El uso continuado del servicio implica la aceptación de las nuevas condiciones.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">9. Suspensión y baja</h2>
            <p>ContaFlex puede suspender o dar de baja una cuenta en caso de uso indebido, violación de estos términos o falta de pago. El usuario puede solicitar la eliminación de su cuenta en cualquier momento escribiendo a <a href="mailto:soporte@contaflex.ar" className="text-[#60a5fa] hover:underline">soporte@contaflex.ar</a>.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">10. Limitación de responsabilidad</h2>
            <p>ContaFlex no será responsable por pérdidas económicas, decisiones profesionales ni perjuicios derivados del uso de los reportes generados. El servicio se provee "tal como está", sin garantías de disponibilidad continua.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">11. Ley aplicable</h2>
            <p>Estos términos se rigen por las leyes de la República Argentina. Cualquier controversia se someterá a la jurisdicción de los tribunales ordinarios de la Ciudad Autónoma de Buenos Aires.</p>
          </section>

          <section className="pt-4 border-t border-white/5">
            <p>Contacto: <a href="mailto:soporte@contaflex.ar" className="text-[#60a5fa] hover:underline">soporte@contaflex.ar</a></p>
          </section>

        </div>
      </div>
    </div>
  );
}
