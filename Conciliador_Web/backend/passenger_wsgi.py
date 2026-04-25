import sys
import os

# Añadir el directorio actual al path de Python para que encuentre main.py
sys.path.insert(0, os.path.dirname(__file__))

# Importar la aplicación FastAPI
from main import app

# Hostinger/Passenger utiliza WSGI. 
# Usamos a2wsgi para convertir nuestra app ASGI (FastAPI) a WSGI.
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
except ImportError:
    # Si falla, definimos una app mínima de error para diagnosticar en el navegador
    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [b"Error: a2wsgi no esta instalado. Por favor instala las dependencias en el panel de Hostinger."]
