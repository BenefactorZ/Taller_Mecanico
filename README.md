# Taller Mecánico - Capa de Seguridad

Proyecto con SPA Vue 3 + Vite + Vuetify 3 y API FastAPI para la gestión de acceso del taller.

## Arranque

1. Cree una base de datos SQL Server llamada `TallerMecanico` y copie `backend/.env.example` a `backend/.env`.
2. En una terminal: `cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000`
3. En otra: `cd frontend; npm install; npm run dev`

La API crea las tablas al iniciar. Para crear el primer administrador, configure `BOOTSTRAP_ADMIN_EMAIL` y `BOOTSTRAP_ADMIN_PASSWORD` en `backend/.env`; se registra una sola vez. Nunca exponga esas variables al frontend.

## Seguridad aplicada

- Contraseñas con hash Argon2, no cifrado reversible ni visible en pantalla.
- JWT de sesión, validado por la API para todas las rutas protegidas.
- RBAC en backend y guardas de rutas en el SPA; modificar una URL no concede permisos.
- Correo único en base de datos y validado en cliente/servidor.
- Recuperación mediante código de un solo uso, con caducidad y envío SMTP configurable.

