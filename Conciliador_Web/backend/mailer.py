import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.hostinger.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
USE_SSL   = os.getenv("USE_SSL", "true").lower() == "true"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "pablo.ponti@gmail.com")
BASE_URL  = os.getenv("FRONTEND_URL", "https://contaflex.ar")
API_URL   = os.getenv("API_URL", "https://conciliador-production-5319.up.railway.app")

_BTN_BLUE  = "display:inline-block;padding:14px 28px;background:#3b82f6;color:white;text-decoration:none;border-radius:8px;font-weight:bold;margin:20px 0;"
_BTN_GREEN = "display:inline-block;padding:14px 28px;background:#10b981;color:white;text-decoration:none;border-radius:8px;font-weight:bold;margin:20px 0;"
_WRAP      = "font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0e1a;color:#f1f5f9;padding:40px;border-radius:12px;"
_FOOTER    = "<hr style='border-color:#1e293b;margin:30px 0;'><p style='color:#475569;font-size:11px;'>ContaFlex &mdash; Consultas: <a href='mailto:soporte@contaflex.ar' style='color:#60a5fa;'>soporte@contaflex.ar</a></p>"


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Envio generico. Soporta SSL directo (465) y STARTTLS (587)."""
    if not SMTP_USER or not SMTP_PASS:
        print(f"[MAILER] Sin credenciales — email para {to_email} NO enviado.")
        print(f"  ASUNTO: {subject}")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = f"ContaFlex <{SMTP_USER}>"
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html"))

        if USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()

        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print(f"[MAILER] OK — email enviado a {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"[MAILER] ERROR enviando a {to_email}: {e}")
        return False


def enviar_verificacion(email: str, token: str) -> bool:
    """Email al suscriptor para verificar su casilla."""
    url = f"{API_URL}/auth/verificar?token={token}"
    html = f"""
    <div style="{_WRAP}">
      <h1 style="color:#60a5fa;">Bienvenido a ContaFlex!</h1>
      <p>Gracias por registrarte. Hace clic en el boton para verificar tu cuenta:</p>
      <a href="{url}" style="{_BTN_BLUE}">Verificar mi cuenta</a>
      <p style="color:#94a3b8;font-size:12px;">Si no podes hacer clic, copia este link:<br>{url}</p>
      {_FOOTER}
    </div>"""
    return send_email(email, "Verifica tu cuenta en ContaFlex", html)


def enviar_notificacion_upgrade(username: str, email_usuario: str,
                                 plan_solicitado: str, token_aprobacion: str) -> bool:
    """Email a Pablo cuando un usuario quiere un plan pago."""
    url = f"{API_URL}/auth/aprobar-suscripcion?token={token_aprobacion}"
    html = f"""
    <div style="{_WRAP}">
      <h2 style="color:#10b981;">Nueva solicitud de suscripcion</h2>
      <table style="width:100%;background:#141c2e;border-radius:8px;padding:20px;margin:20px 0;">
        <tr><td style="color:#94a3b8;padding:8px 0;">Usuario:</td><td style="font-weight:bold;">{username}</td></tr>
        <tr><td style="color:#94a3b8;padding:8px 0;">Email:</td><td>{email_usuario}</td></tr>
        <tr><td style="color:#94a3b8;padding:8px 0;">Plan solicitado:</td><td style="color:#60a5fa;font-weight:bold;">{plan_solicitado}</td></tr>
      </table>
      <p>Una vez recibido el pago, aproba la suscripcion:</p>
      <a href="{url}" style="{_BTN_GREEN}">APROBAR SUSCRIPCION</a>
      <p style="color:#94a3b8;font-size:12px;">Link directo: {url}</p>
      {_FOOTER}
    </div>"""
    return send_email(ADMIN_EMAIL,
                      f"[ContaFlex] Nueva suscripcion: {username} - Plan {plan_solicitado}",
                      html)


def enviar_aprobacion_usuario(email: str, username: str, plan: str) -> bool:
    """Email al usuario confirmando que su plan fue aprobado y puede ingresar."""
    html = f"""
    <div style="{_WRAP}">
      <h2 style="color:#10b981;">Suscripcion aprobada!</h2>
      <p>Hola <b>{username}</b>, tu plan <b style="color:#60a5fa;">{plan}</b> fue activado con exito.</p>
      <p>Ya podes ingresar al sistema:</p>
      <a href="{BASE_URL}" style="{_BTN_BLUE}">Ingresar a ContaFlex</a>
      {_FOOTER}
    </div>"""
    return send_email(email, f"[ContaFlex] Tu plan {plan} fue activado!", html)


def enviar_reset_password(email: str, token: str) -> bool:
    """Email para recuperar contrasena."""
    url = f"{BASE_URL}/?reset_token={token}"
    html = f"""
    <div style="{_WRAP}">
      <h2 style="color:#60a5fa;">Recuperacion de Contrasena</h2>
      <p>Recibimos una solicitud para restablecer tu contrasena. Si no fuiste vos, ignora este mensaje.</p>
      <a href="{url}" style="{_BTN_BLUE}">Crear nueva contrasena</a>
      <p style="color:#94a3b8;font-size:12px;">Este link expira en 24 horas.<br>Link directo: {url}</p>
      {_FOOTER}
    </div>"""
    return send_email(email, "Recupera tu contrasena - ContaFlex", html)
