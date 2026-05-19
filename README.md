# Sintetic App

Aplicación de reservas para canchas sintéticas con panel administrativo, POS de productos, reportes financieros y reservas recurrentes.

## Stack

- **Backend:** Django 4.2 + SQLite
- **Frontend:** Templates Django + Tailwind + JS vanilla
- **Imágenes:** Pillow

## Funcionalidades

### Cliente
- Reserva en 3 pasos (Cancha → Día y hora → Confirmar)
- Calendario con disponibilidad en tiempo real
- Reserva rápida (un toque para repetir última reserva)
- Botón de contacto WhatsApp
- Historial guardado localmente + búsqueda por teléfono

### Admin
- Dashboard con KPIs
- Gestión de reservas con filtros (hoy, ayer, semana, próximas, etc.)
- Reservas recurrentes (alquileres fijos semanales)
- POS rápido con catálogo de productos
- Reportes financieros (ingresos, ventas, métodos de pago, ventas por hora)
- Cierre de caja del día
- Calendario visual de reservas
- Export a CSV

## Setup local

```bash
# 1) Crear entorno
python3 -m venv env
source env/bin/activate      # Linux/Mac
env\Scripts\activate         # Windows

# 2) Instalar deps
pip install -r requirements.txt

# 3) Migraciones
cd canchas
python manage.py migrate

# 4) Crear superusuario
python manage.py createsuperuser

# 5) Correr
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/> (cliente) y <http://127.0.0.1:8000/admin-panel/> (admin).

## Deploy en producción (Ubuntu)

Ver `docs/DEPLOY.md` (gunicorn + nginx + Let's Encrypt).
