# Usar imagen oficial de Python
FROM python:3.11-slim

# Evitar que Python genere archivos .pyc y forzar logs inmediatos
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instalar dependencias del sistema necesarias para algunas librerías de Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requerimientos e instalar
COPY ["Conciliador Web/backend/requirements.txt", "./"]
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el motor original (necesario para las importaciones del backend)
COPY "conciliador v10" "./conciliador v10"

# Copiar el código del backend
COPY "Conciliador Web/backend" "./backend"

# Exponer el puerto
EXPOSE 8000

# Comando para iniciar la aplicación desde la carpeta del backend
# Ajustamos el PYTHONPATH para que encuentre el núcleo de v10
ENV PYTHONPATH="/app/conciliador v10:/app/backend"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
