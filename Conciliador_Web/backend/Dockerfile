FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo (ahora que movimos los archivos aquí)
COPY . .

# Exponer puerto (Railway sobreescribe con $PORT)
EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
