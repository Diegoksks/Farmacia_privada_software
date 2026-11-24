# 💊 Private Clinic

Sistema web para la gestión de una farmacia/área clínica, desarrollado con **Django y Python**, con módulos para inventario, pacientes, tratamientos y análisis de ventas.

El proyecto también incorpora **Machine Learning y Google Gemini** para apoyar la predicción de demanda y generar información útil a partir de los datos del sistema.

---

## 🛠️ Tecnologías

<p align="center">

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white"/>
<img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white"/>
<img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white"/>
<img src="https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white"/>
<img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black"/>
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
<img src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonaws&logoColor=white"/>

</p>

---

## 📌 ¿Qué tiene?

### Inventario

* Registro de medicamentos.
* Control de stock.
* Gestión de lotes.
* Fechas de vencimiento.
* Historial de movimientos.
* Sistema FEFO para priorizar productos próximos a vencer.

### Pacientes y tratamientos

* Registro de pacientes.
* Gestión de tratamientos.
* Seguimiento de tratamientos crónicos.
* Alertas y notificaciones por correo.

### IA y Machine Learning

* Análisis de ventas históricas.
* Predicción de demanda.
* Apoyo para calcular necesidades de reposición.
* Generación de reportes utilizando Gemini.

### Seguridad

* Autenticación de usuarios.
* Roles y permisos.
* Protección CSRF.
* Protección contra XSS.
* ORM de Django para las consultas a la base de datos.
* Variables sensibles mediante `.env`.
* 2FA para usuarios administrativos.

---

## 📊 Dashboard

El dashboard muestra información del inventario y ventas de forma resumida para poder revisar rápidamente el estado del sistema.

---

## 🤖 Predicción de demanda

La parte de IA utiliza los datos históricos registrados en el sistema.

```text
Ventas históricas
       ↓
Procesamiento de datos
       ↓
Machine Learning
       ↓
Predicción
       ↓
Recomendación de stock
```

Además, se utiliza Gemini para trabajar con los resultados y generar información más fácil de interpretar.

---

## ☁️ Despliegue

El proyecto puede ejecutarse localmente o desplegarse en AWS.

```text
                AWS
                 │
        ┌────────┴────────┐
        │                 │
       EC2               RDS
        │                 │
     Django           PostgreSQL
        │
     Docker
        │
    Gunicorn
```

También se utilizan servicios como:

* EC2
* RDS PostgreSQL
* CloudWatch
* Docker
* Gunicorn
* WhiteNoise

---

## Revisión local

Desde la carpeta que contiene `manage.py`, usa Python 3.14 y PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py createsuperuser
.\venv\Scripts\python.exe manage.py runserver
```

Al iniciar sesión en local, el código de verificación aparece en la terminal donde corre el servidor si usas la configuración de correo de ejemplo.

Copia la configuración solo en la primera instalación. En `.env`, reemplaza el valor de ejemplo de `SECRET_KEY` por una clave propia. Puedes generarla con `.\venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. La revisión local usa SQLite por defecto. Para crear el administrador, indica el rol `ADMINISTRADOR` y completa los campos solicitados. Abre [la aplicación local](http://127.0.0.1:8000/).

Para ejecutar las pruebas usa `.\venv\Scripts\python.exe manage.py test --noinput`. En Linux o macOS, usa `cp` para copiar el archivo y `venv/bin/python` como intérprete del entorno virtual.

## 📁 Estructura

```text
private_clinic/
│
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── config/
│
├── apps/
│   ├── productos/
│   ├── inventario/
│   ├── clientes/
│   ├── convenios/
│   ├── recetas/
│   ├── ventas/
│   └── reportes/
│
├── templates/
├── static/
└── README.md
```

---

## 📚 Lo que aprendí con este proyecto

Este proyecto me sirvió principalmente para trabajar con:

* Desarrollo web con Django.
* PostgreSQL.
* APIs de Inteligencia Artificial.
* Machine Learning.
* Docker.
* AWS.
* Seguridad web.
* Optimización de consultas.
* Despliegue de aplicaciones.

También fue una buena oportunidad para juntar varias de las tecnologías que he ido aprendiendo en Ingeniería Informática en un solo proyecto.

---

## 👨‍💻 Autor

### Diego Muñoz

Estudiante de **Ingeniería Informática** y Analista Programador.
