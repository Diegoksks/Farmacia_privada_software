# Usa una imagen oficial de Python ligera
FROM python:3.12-slim

# Evita que Python escriba archivos .pyc en disco y fuerza a la salida estándar
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Establece el directorio de trabajo
WORKDIR /app

# Instala dependencias del sistema requeridas (por ejemplo, para psycopg2 si se usara PostgreSQL)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia los archivos de requerimientos y los instala
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia todo el código del proyecto
COPY . /app/

# Recopila los archivos estáticos de Django usando Whitenoise
RUN SECRET_KEY=solo-compilacion python manage.py collectstatic --noinput

# Expone el puerto 8000
EXPOSE 8000

# Comando por defecto para iniciar Gunicorn (servidor de producción)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
