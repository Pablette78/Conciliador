FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar (buscando en ambas posibles rutas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir -r backend/requirements.txt

# Copiar TODO el proyecto
COPY . .

# Configurar PYTHONPATH para que encuentre los parsers en la raíz y la lógica en backend
ENV PYTHONPATH=/app

# Exponer puerto
EXPOSE 8000

# Comando para arrancar el backend como módulo
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
