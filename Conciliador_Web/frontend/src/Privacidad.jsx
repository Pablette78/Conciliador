export default function Privacidad({ onBack }) {
  return (
    <div className="min-h-screen bg-[#0a0e1a] text-[#f1f5f9] px-6 py-12">
      <div className="max-w-3xl mx-auto">
        <button
          onClick={onBack}
          className="mb-8 text-xs font-mono text-[#60a5fa] hover:text-white transition-colors flex items-center gap-2"
        >
          ← Volver
        </button>

        <h1 className="text-3xl font-bold mb-2">Política de Privacidad</h1>
        <p className="text-xs text-[#475569] mb-10">Última actualización: mayo de 2025</p>

        <div className="space-y-8 text-sm text-[#94a3b8] leading-relaxed">

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">1. Responsable del tratamiento</h2>
            <p>ContaFlex, con contacto en <a href="mailto:soporte@contaflex.ar" className="text-[#60a5fa] hover:underline">soporte@contaflex.ar</a>, es el responsable del tratamiento de los datos personales recolectados a través de esta plataforma, en cumplimiento de la Ley 25.326 de Protección de Datos Personales de la República Argentina.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">2. Datos que recopilamos</h2>
            <p className="mb-3">Al registrarse y utilizar el servicio, recopilamos:</p>
            <ul className="space-y-2 pl-4 list-disc">
              <li><span className="text-[#f1f5f9] font-medium">Datos de cuenta:</span> nombre de usuario y dirección de correo electrónico.</li>
              <li><span className="text-[#f1f5f9] font-medium">Contraseña:</span> almacenada de forma cifrada (bcrypt). Nunca se guarda en texto plano.</li>
              <li><span className="text-[#f1f5f9] font-medium">Datos de uso:</span> cantidad de conciliaciones realizadas, plan activo y fecha de registro.</li>
              <li><span className="text-[#f1f5f9] font-medium">Datos de pago:</span> gestionados exclusivamente por Mercado Pago. ContaFlex no almacena datos de tarjetas ni información bancaria del usuario.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">3. Archivos subidos</h2>
            <p>Los archivos de extractos bancarios y libros mayores que el usuario carga son procesados en memoria y eliminados automáticamente de nuestros servidores al finalizar cada operación. ContaFlex no lee, analiza ni almacena el contenido financiero de esos documentos más allá del tiempo estrictamente necesario para generar el reporte.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">4. Uso de los datos</h2>
            <p className="mb-3">Los datos recopilados se utilizan exclusivamente para:</p>
            <ul className="space-y-1 pl-4 list-disc">
              <li>Gestionar la cuenta y autenticar al usuario.</li>
              <li>Controlar el límite mensual de conciliaciones según el plan.</li>
              <li>Enviar correos transaccionales (verificación de email, confirmación de suscripción).</li>
              <li>Mejorar el servicio de forma agregada y anónima.</li>
            </ul>
            <p className="mt-3">No vendemos, cedemos ni compartimos datos personales con terceros con fines comerciales.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">5. Terceros involucrados</h2>
            <p className="mb-3">El funcionamiento del servicio involucra los siguientes proveedores:</p>
            <ul className="space-y-2 pl-4 list-disc">
              <li><span className="text-[#f1f5f9] font-medium">Mercado Pago:</span> procesamiento de pagos y suscripciones.</li>
              <li><span className="text-[#f1f5f9] font-medium">Brevo:</span> envío de correos transaccionales desde soporte@contaflex.ar.</li>
              <li><span className="text-[#f1f5f9] font-medium">Railway:</span> infraestructura de servidores donde se aloja el backend y la base de datos.</li>
            </ul>
            <p className="mt-3">Estos proveedores cuentan con sus propias políticas de privacidad y estándares de seguridad.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">6. Retención de datos</h2>
            <p>Los datos de cuenta se conservan mientras la cuenta esté activa. Al solicitar la baja, los datos personales son eliminados dentro de los 30 días hábiles siguientes, excepto aquellos que deban retenerse por obligaciones legales o contables.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">7. Seguridad</h2>
            <p>Implementamos medidas técnicas para proteger la información: cifrado de contraseñas, comunicaciones HTTPS, acceso restringido a la base de datos y tokens de sesión con expiración automática.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">8. Derechos del usuario</h2>
            <p>En virtud de la Ley 25.326, el usuario tiene derecho a acceder, rectificar, actualizar o suprimir sus datos personales. Para ejercer estos derechos, escribir a <a href="mailto:soporte@contaflex.ar" className="text-[#60a5fa] hover:underline">soporte@contaflex.ar</a> con el asunto <span className="italic">"Datos Personales"</span>.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">9. Cookies</h2>
            <p>ContaFlex no utiliza cookies de rastreo ni publicidad. La sesión del usuario se gestiona mediante tokens almacenados localmente en el navegador (sessionStorage).</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-[#f1f5f9] mb-3">10. Cambios en esta política</h2>
            <p>Ante modificaciones relevantes, notificaremos al usuario por correo electrónico con al menos 15 días de anticipación.</p>
          </section>

          <section className="pt-4 border-t border-white/5">
            <p>Contacto: <a href="mailto:soporte@contaflex.ar" className="text-[#60a5fa] hover:underline">soporte@contaflex.ar</a></p>
          </section>

        </div>
      </div>
    </div>
  );
}
