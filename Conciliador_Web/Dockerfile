FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar (desde la raíz del build)
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copiar todo el código de Conciliador_Web
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando para arrancar como módulo (esto arregla el error de "No module named backend")
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
