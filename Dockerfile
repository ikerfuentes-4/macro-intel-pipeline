# Imagen unica para la API y para los comandos del pipeline (main.py run|evaluate|sync-conflicts).
# `docker-compose.yml` decide que comando ejecuta cada servicio sobre esta misma imagen -- no
# hay una imagen separada por servicio, para no duplicar dependencias ni mantenimiento.
FROM python:3.12-slim

WORKDIR /app

# build-essential + libxml2-dev/libxslt1-dev: requeridos para compilar lxml (parseo del
# registro de conflictos, ver ingestion/conflict_registry.py).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Por defecto arranca la API. El servicio "scheduler" de docker-compose.yml sobreescribe este
# comando para ejecutar el pipeline periodicamente en vez de servir HTTP.
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
