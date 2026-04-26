FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requerimientos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Exponer el puerto que usa FastAPI
EXPOSE 8000

# Comando para arrancar la app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
