FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código del backend
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando simple (ahora que los imports están limpios)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
