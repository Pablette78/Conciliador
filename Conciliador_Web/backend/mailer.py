import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Configuración ---
# Estas variables deben configurarse en el entorno (Render/Vercel)
# Para Hotmail usa: smtp-mail.outlook.com
# Configuración SMTP desde variables de entorno
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.hostinger.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
USE_SSL = os.getenv("USE_SSL", "True").lower() == "true"
 # Tu Contraseña de Aplicación
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "pablo.ponti@gmail.com")
BASE_URL = os.getenv("FRONTEND_URL", "https://contaflex.ar")
API_URL = os.getenv("API_URL", "http://localhost:8000")

def send_email(to_email, subject, html_content):
    """Función genérica para enviar correos HTML."""
    if not SMTP_USER or not SMTP_PASS:
        print(f"[MAILER] Simulación: Correo para {to_email} NO ENVIADO (Faltan credenciales)")
        print(f"ASUNTO: {subject}")
        print(f"CONTENIDO: {html_content[:100]}...")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f"ContaFlex <{SMTP_USER}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"[MAILER] Error enviando email: {e}")
        return False

def enviar_verificacion(email, token):
    url = f"{BASE_URL}/verificar?token={token}"
    subject = "Verificá tu cuenta en ContaFlex"
    html = f"""
    <h2>¡Bienvenido a ContaFlex!</h2>
    <p>Gracias por registrarte. Para empezar a conciliar tus extractos, por favor verificá tu cuenta:</p>
    <p><a href='{url}' style='padding: 10px 20px; background-color: #3b82f6; color: white; text-decoration: none; border-radius: 5px;'>Verificar Cuenta</a></p>
    <p>Si no podés hacer clic, copiá este link: {url}</p>
    """
    return send_email(email, subject, html)

def enviar_notificacion_upgrade(usuario_email, plan_solicitado, token_aprobacion):
    url_aprobacion = f"{API_URL}/auth/aprobar-suscripcion?token={token_aprobacion}"
    subject = f"Solicitud de Upgrade: {usuario_email} -> {plan_solicitado}"
    html = f"""
    <h2>Nueva solicitud de suscripción</h2>
    <p>El usuario <b>{usuario_email}</b> quiere pasar al plan <b>{plan_solicitado}</b>.</p>
    <p>Para aprobar este cambio y actualizar su límite mensual automáticamente, hacé clic en el botón:</p>
    <p><a href='{url_aprobacion}' style='padding: 10px 20px; background-color: #10b981; color: white; text-decoration: none; border-radius: 5px;'>APROBAR UPGRADE</a></p>
    <p>Una vez aprobado, el usuario recibirá el nuevo cupo de forma instantánea.</p>
    """
    return send_email(ADMIN_EMAIL, subject, html)

def enviar_reset_password(email, token):
    url = f"{BASE_URL}/reset-password?token={token}"
    subject = "Recuperá tu contraseña - ContaFlex"
    html = f"""
    <h2>Recuperación de Contraseña</h2>
    <p>Recibimos una solicitud para restablecer tu contraseña. Si no fuiste vos, ignorá este mensaje.</p>
    <p><a href='{url}' style='padding: 10px 20px; background-color: #3b82f6; color: white; text-decoration: none; border-radius: 5px;'>Restablecer Contraseña</a></p>
    """
    return send_email(email, subject, html)
