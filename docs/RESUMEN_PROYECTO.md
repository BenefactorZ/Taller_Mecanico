# Resumen del proyecto · Taller Mecánico

Documento para **retomar el proyecto en otra conversación**. Detalle completo en [`README.md`](README.md), [`plan_estructura_de_trabajo.md`](plan_estructura_de_trabajo.md) y la carpeta [`analisis/`](analisis).

## 1. Qué es
Sistema de gestión para un taller mecánico. Stack: **Vue 3 + TypeScript + Vite + Vuetify 3** (SPA, paleta blanca con #F07820 #F08020 #F06030 #F05040 #F04050 #F03060) · **Python + FastAPI + SQLAlchemy 2 + Pydantic 2** · **SQL Server** (ODBC 18, base `TallerMecanico`; SQLite sólo para pruebas) · Argon2 + JWT.
Las validaciones existen en el frontend (TypeScript) y en el backend (FastAPI); el servidor es la autoridad.

## 2. Cómo iniciarlo
```powershell
# Terminal 1 · backend (puerto 8000)
cd C:\Taller_Mecanico\backend ; .\.venv\Scripts\Activate.ps1 ; uvicorn app.main:app --reload --port 8000
# Terminal 2 · frontend (puerto 5173)
cd C:\Taller_Mecanico\frontend ; npm run dev
```
El administrador inicial sale de `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` en `backend\.env`. Docs de la API: <http://localhost:8000/docs>.
Pruebas (desde `backend/`, usan SQLite temporal, no tocan la base real): `.\.venv\Scripts\python.exe tests\e2e_<nombre>.py`.

## 3. Qué está hecho (fases del plan)
| Fase | Qué es | Documento |
| --- | --- | --- |
| 0 | Capa de seguridad: login, recuperación por código por correo, JWT, Argon2, sin saltarse permisos por URL | plan |
| 1 | Registro público de cuentas (rol **Invitado**) y creación de roles (sólo administrador, sin duplicados) | `crear_roles.md` |
| 2 | Administrar roles: de fábrica (sólo lectura) + personalizados; borrado lógico con `bin_status` → tabla `status` (1 activo, 2 eliminado) | `administrar_roles.md` |
| 2.1 | **17 permisos** aplicados en cada petición (`requiere("codigo")`); de fábrica fijos en código; en roles personalizados se asignan en `roles_permisos` | `permisos_roles.md` |
| 2.2 | Administrar empleados: búsqueda, filtro, edición, asignar rol a invitados, borrado lógico (bloquea la sesión al instante) | `administrar_empleados.md` |
| 3 | Alta de taller (**sólo administrador**): RFC con regex + fecha real, foto JPG/PNG/WebP ≤ 15 MB validada por bytes, nombre/RFC únicos, autollenado de domicilio por código postal (catálogo SEPOMEX de 2017, importado) | `alta_taller.md` |
| 4 | Módulo de Clientes con patrones GoF: Factory Method, Facade, Chain of Responsibility (+ Strategy); alta con alerta de duplicados, consulta, ficha | `docs/customer-patterns/` |
| 5 | **Administración de clientes** (recepcionista: su taller; administrador: todos): modal «Actualizar datos» con el taller bloqueado, historial con trazabilidad en `auditoria`, **suspender/reactivar sólo administrador** (estado `INACTIVO` = «Suspendido») | `administrar_clientes.md` |
| 6 | **Administración de talleres** (administrador): buscar, editar datos/foto, renombrar (arrastra la sucursal de los empleados), eliminar lógico, restaurar | `administrar_talleres.md` |
| 7 | **Registro de vehículos** (recepcionista y administrador): flujo datos → normalizar → duplicados → guardar → relacionar; VIN (17, sin I/O/Q) y placa con regex, marca, modelo, año ≥ 1981, color, imagen ≤ 15 MB, kilometraje opcional; resultado: vehículo activo asociado a un cliente activo | `registrar_vehiculos.md` |

**Cliente** = **ID, nombre, teléfono y correo** (ambos medios obligatorios y únicos por taller). Los clientes anteriores (sólo traían «contacto») quedaron repartidos por la migración y se marcan «Datos incompletos» hasta capturar el faltante.

Mapas de proceso (Archify): `analisis/diagramas/*.png` (plan, permisos, alta de taller, registro de vehículo); fuentes en `.archify/mapas-procesos-20261009-150000/`; los de clientes en `docs/customer-patterns/diagrams/`.

## 4. Reglas de permisos (importante)
- **Administrador:** todo menos `clientes.consultar` (no tiene sucursal; da de alta clientes eligiendo el taller); sí administra y suspende clientes de todos los talleres.
- **Recepcionista:** clientes (consultar, alta, administrar), vehículos (registrar, consultar), consultar talleres, recepciones, órdenes.
- **Asesor de servicio:** clientes (consultar, alta), órdenes. **Técnico:** órdenes, diagnósticos. **Cliente:** notificaciones. **Invitado:** nada.
- **No delegables a roles personalizados (9):** `empleados.alta`, `empleados.administrar`, `roles.administrar`, `talleres.alta`, `talleres.administrar`, `clientes.administrar`, `clientes.suspender`, `vehiculos.registrar`, `vehiculos.consultar`. Para delegar uno, quitar `delegable=False` en `backend/app/permisos.py`.
- Los empleados se asocian a su taller por el **nombre de la sucursal** (coincidencia sin distinguir mayúsculas).

## 5. Decisiones y particularidades técnicas
- **Borrado lógico** en roles, talleres, usuarios (`bin_status`); nada se borra físicamente. Clientes: se «suspenden».
- **Migraciones aditivas e idempotentes** en `backend/app/migraciones.py` (+ `create_all`): sólo agregan columnas, índices y tablas; nunca borran. La base real ya está migrada (17 permisos, tabla `vehiculos`, `customers.telefono/correo`).
- `customers.contacto` se conserva (= correo, o teléfono en clientes antiguos) sólo como clave de unicidad `(taller, contacto)`; la mantiene el repositorio.
- Columnas `VARCHAR` en SQL Server: caracteres fuera de cp1252 (p. ej. `→`) se pierden en `auditoria.detalle`; por eso el detalle usa «de … a …».
- Las fotos van a `backend/uploads/{talleres,vehiculos}/` y se sirven con token (`apiBlob` en el frontend). `uploads/` y `data/` no se versionan.
- SQL Server: no usar `IS 0/1` (usar `== False`); pyodbc `fast_executemany` para importaciones.
- Todo cambio se desarrolla en una copia, se prueba (SQLite + base temporal de SQL Server + navegador en puertos 8001/5174) y recién entonces se pasa al proyecto. **No se escribe en la base real** salvo las migraciones aditivas del arranque.

## 6. Estado de las pruebas
7 suites en `backend/tests/` (todas pasan; también en SQL Server las de clientes/permisos/roles): `e2e_clientes` (39), `e2e_roles_talleres` (106), `e2e_permisos` (68), `e2e_empleados` (60), `e2e_talleres_admin` (62), `e2e_clientes_vehiculos` (95), `e2e_migracion` (16). `vue-tsc --noEmit` sin errores.

## 7. Pendiente
- Editar, eliminar (lógico) y restaurar **vehículos**; verlos en la ficha del cliente; usarlos en recepción y órdenes.
- Módulos aún sin funcionalidad: recepción, órdenes de trabajo, diagnósticos, notificaciones (sus permisos ya existen).
- Pantalla para consultar la **auditoría**; auditar los cambios de permisos de roles.
- Empleados: restablecer contraseña desde administración, suspender sin eliminar, cambiar correo; cambio de contraseña desde el perfil.
- Completar teléfono/correo de los 2 clientes existentes en la base real (aparecen «Datos incompletos»).
- Reimportar un catálogo de códigos postales más reciente (el de Correos de México es de oct-2017).
- Límite de intentos de login/recuperación, Alembic, `lifespan` en vez de `on_event`, CORS por variable de entorno, división del bundle del frontend, pruebas unitarias por patrón y del frontend.
- Completar el RFC, domicilio y foto del taller legado «1» (editándolo en `/talleres`).
