# Taller Mecánico · Sistema de gestión

Aplicación web para la gestión de un taller mecánico. Está hecha la **capa de seguridad y administración de accesos** (inicio de sesión, recuperación de contraseña, registro de cuentas con rol Invitado, empleados, roles personalizados y **17 permisos** aplicados en cada petición), la **administración de talleres** (alta con RFC, foto y autollenado del domicilio por código postal; edición y borrado lógico), el **módulo de Clientes** (alta con alerta de duplicados, consulta, ficha y **administración con trazabilidad y suspensión**; cada cliente tiene ID, nombre, teléfono y correo) y el **registro de vehículos** asociados a un cliente. Los demás módulos operativos (recepción de vehículos, órdenes de trabajo, diagnósticos y notificaciones) están definidos a nivel de permisos, pero todavía no tienen funcionalidad. Para retomar el proyecto en otra conversación, empiece por [`RESUMEN_PROYECTO.md`](RESUMEN_PROYECTO.md).

| Capa | Tecnología |
| --- | --- |
| Frontend | Vue 3 + TypeScript, Vite, Vuetify 3, Vue Router, Material Design Icons |
| Backend | Python, FastAPI, SQLAlchemy 2, Pydantic 2 |
| Base de datos | SQL Server (ODBC Driver 18). Para pruebas locales también funciona con SQLite |
| Seguridad | Hash Argon2 (`pwdlib`), JWT HS256 (`python-jose`), RBAC en servidor |
| Diagramas | [Archify](https://github.com/tt-a1i/archify), instalado en `tools/archify` |

---

## Estado del proyecto

### ✅ Funcionando

| Funcionalidad | Detalle |
| --- | --- |
| Inicio de sesión | Correo y contraseña, con JWT válido por `ACCESS_TOKEN_MINUTES` (60 min por defecto). Las cuentas inactivas no pueden ingresar. |
| Recuperación de contraseña | Asistente de 3 pasos: correo → código de 6 dígitos → nueva contraseña. El código se guarda con hash, caduca (`RESET_CODE_MINUTES`) y sólo se usa una vez. Permite reenviar el código. |
| Envío del código | Por SMTP si está configurado; en desarrollo (sin `SMTP_HOST`) el código se imprime en la consola del backend. |
| Control de acceso por rol (RBAC) | La API valida el rol en cada endpoint protegido; el SPA además protege las rutas. Cambiar la URL no concede permisos. |
| Administrador inicial | Se crea automáticamente al arrancar la API a partir de `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` (sólo si no existe). |
| Alta de empleado | Sólo administrador. El **rol se elige de la base de datos** (`GET /api/roles/asignables`): los 3 roles de empleado de fábrica (Recepcionista, Asesor de servicio y Técnico) **más los roles personalizados activos** que haya creado el administrador, que se marcan como «Personalizado». Sucursal obligatoria, correo único (409 si se repite), contraseña de al menos 12 caracteres, con generador y medidor de seguridad. El formulario abre vacío y el navegador no lo autocompleta. |
| Registro de cuenta | Pantalla pública `/registro`: nombre completo, correo y contraseña (mínimo 12 caracteres). La cuenta siempre nace con el rol **Invitado**; quien se registra no puede elegir su rol. Correo único (409 si ya existe). El invitado puede ingresar y ver su panel, pero ningún módulo hasta que un administrador le asigne un rol. |
| Alta de rol | Sólo administrador. Nombre, clave única en mayúsculas (se sugiere desde el nombre) y descripción. Verifica duplicados de clave y de nombre (sin distinguir mayúsculas), rechaza claves reservadas del sistema (incluida `INVITADO`) y avisa si la clave pertenece a un rol eliminado. |
| **Administración de empleados** | Sólo administrador, en `/empleados` (permiso `empleados.administrar`, no delegable). Lista todas las cuentas con **búsqueda** por nombre o correo, **filtro por rol**, atajo de **cuentas sin rol (invitados)** y paginación. Permite **editar** nombre, sucursal y rol, **asignar rol a una cuenta Invitado** (la convierte en empleado y opera de inmediato) y **eliminar con borrado lógico**: la cuenta se conserva (`users.bin_status` → `status`), se desactiva y **su sesión abierta deja de valer en la siguiente petición**; se puede restaurar. Avisa de las sucursales sin taller registrado. No permite modificar la propia cuenta ni las protegidas (administrador, cliente, sistema). |
| **Permisos de los roles** | Cada permiso es una capacidad concreta que la API protege (17 en total: clientes, vehículos, talleres, órdenes, recepciones, diagnósticos, notificaciones y los de administración). Los **roles de fábrica** conservan sus permisos fijos (definidos en el código); a los **roles personalizados** el administrador les asigna permisos desde `/roles` (casillas agrupadas por módulo). **Se aplican en cada petición**: un cambio surte efecto de inmediato, sin volver a iniciar sesión. Los permisos **reservados** (`empleados.alta`, `empleados.administrar`, `roles.administrar`, `talleres.alta`, `talleres.administrar`, `clientes.administrar`, `clientes.suspender`, `vehiculos.registrar` y `vehiculos.consultar`) **no se pueden delegar** a un rol personalizado: los de administración, para evitar escaladas de privilegios, y los demás porque corresponden a roles de fábrica concretos. Un rol eliminado no concede permisos hasta que se restaure. El menú, el panel y las rutas muestran sólo lo que cada persona puede usar. |
| **Administración de roles** | Sólo administrador, en `/roles`. Muestra los **7 roles de fábrica** (de sólo lectura, con cuántos usuarios los tienen) y los **personalizados**, que se pueden **editar** (nombre y descripción; la clave no cambia) y **eliminar con borrado lógico**: eliminar no borra la fila, cambia su `bin_status` al id del estatus «eliminado» de la tabla `status` (1 = activo, 2 = eliminado). Se pueden mostrar los eliminados y **restaurarlos**. Un rol de fábrica no se edita, no se elimina y su nombre no se puede repetir en un rol personalizado. |
| **Alta de taller** | **Sólo el administrador** (permiso `talleres.alta`, no delegable), en `/talleres/nuevo`. Datos: nombre, RFC, email de contacto, domicilio (calle y número, código postal, estado, municipio, colonia) y **foto** (JPG, PNG o WebP, máximo 15 MB; el tipo se verifica por los bytes del archivo, no por la extensión). Verifica **taller único** (nombre y RFC, sin distinguir mayúsculas) y valida el **RFC con expresión regular** (12 o 13 caracteres, fecha real, se guarda en mayúsculas). Deja registro en la auditoría. |
| **Administración de talleres** | Sólo administrador, en `/talleres` (permiso `talleres.administrar`, no delegable). Lista los talleres con **miniatura de la foto**, **búsqueda** por nombre, RFC o municipio, cuántos empleados y clientes tiene cada uno y paginación. Permite **editar** (mismas reglas del alta, foto opcional: sin archivo se conserva la actual) y **eliminar con borrado lógico**: el taller se conserva (`talleres.bin_status` → `status`), se desactiva y **sus empleados dejan de poder operar clientes** hasta que se restaure. **Renombrar un taller actualiza la sucursal de sus empleados.** Las ediciones, eliminaciones y restauraciones quedan en la auditoría. |
| **Administración de clientes** | Recepcionista y administrador, en `/clientes/administracion` (permiso `clientes.administrar`). La recepcionista ve y modifica **sólo los clientes de su taller**; el administrador, **los de todos los talleres** (con filtro por taller). Al dar clic en actualizar se abre una **ventana modal con toda la información del cliente**; la única restricción es que **el taller asignado no se puede cambiar** (la API también lo rechaza). Las modificaciones se hacen con **trazabilidad**: cada una queda en la auditoría con quién, cuándo y qué cambió, y se consulta en el **historial** del cliente. **Sólo el administrador suspende y reactiva** (`clientes.suspender`, con motivo obligatorio). Un cliente suspendido no se modifica ni recibe vehículos. |
| **Registro de vehículos** | Recepcionista y administrador, en `/vehiculos/nuevo` (permiso `vehiculos.registrar`). Flujo: **datos → normalizar → duplicados → guardar → relacionar**, con resultado «vehículo activo». Datos: **VIN** (17 caracteres, expresión regular ISO 3779), **placa** (expresión regular, 5 a 7 caracteres), marca, modelo, año, color, **imagen** (JPG, PNG o WebP, máximo 15 MB) y kilometraje opcional. VIN y placa son únicos. Cada vehículo se **asocia a un cliente** activo y hereda su taller. Lista en `/vehiculos`. |
| **Autollenado del domicilio** | Al escribir el código postal se llenan estado, municipio y colonia (catálogo oficial de Correos de México en la tabla `codigos_postales`). Si no se conoce el código postal, se elige estado → municipio → colonia y se carga el código postal. El servidor también comprueba que el código postal, el estado, el municipio y la colonia se correspondan. |
| **Alta de cliente** | Recepcionista y Asesor de servicio. Flujo: abrir alta (guardas) → captura de nombre completo, teléfono y correo (el ID lo asigna el sistema) → normalización → búsqueda de coincidencias → confirmación → persistencia → auditoría. Valida el formato (nombre y apellido; correo válido o teléfono de 10 a 15 dígitos). **Si hay coincidencias (mismo nombre o mismo contacto en el taller) alerta y no crea un segundo registro**; sin coincidencias pide confirmación y deja un `Customer` activo. |
| **Datos del cliente** | Todo cliente tiene **ID, nombre, teléfono y correo**; el teléfono (10 a 15 dígitos) y el correo son obligatorios y únicos por taller. Los clientes anteriores a esta separación sólo traían un «contacto»: la migración lo reparte en teléfono o correo sin borrar nada, y en la administración quedan marcados «Datos incompletos» hasta que se les captura el que falta. |
| **Consulta de cliente** | Criterio (nombre, o teléfono o correo completos) → normalización → búsqueda paginada → coincidencias → ficha. Los resultados se limitan al taller del usuario y la búsqueda se conserva en la URL. |
| Precondiciones de Clientes | Cada operación exige usuario autenticado, rol autorizado y taller activo (cadena de guardas de la Facade). El taller es el **taller registrado** cuyo nombre coincide con la sucursal del usuario (sin distinguir mayúsculas); si la sucursal no está registrada, o el taller fue eliminado, la API responde 403 y explica qué hacer. |
| Panel de trabajo | Saludo, datos de la sesión, módulos disponibles por rol con su estado, roles personalizados (administrador) o permisos del usuario (otros roles). |
| Sesión en el cliente | El token se guarda en `sessionStorage`; al vencer, o si la API responde 401, la sesión se cierra y se redirige al acceso. |
| Interfaz | Diseño responsivo con menú lateral, barra superior con menú de usuario, pantallas de acceso divididas y animaciones suaves (se desactivan con `prefers-reduced-motion`). |

### 🟡 Parcial

| Funcionalidad | Qué existe | Qué falta |
| --- | --- | --- |
| Roles personalizados | Se crean, listan, editan, eliminan (borrado lógico), restauran, **se asignan a empleados** y **tienen permisos** definidos por el administrador. | Los módulos de órdenes, recepciones, diagnósticos y notificaciones aún no tienen funcionalidad, así que esos permisos se pueden asignar pero hoy sólo abren el endpoint de ejemplo. Los cambios de permisos no se registran en la auditoría. |
| Cuentas Invitado | El registro público, el ingreso y la **asignación de rol** desde «Empleados» funcionan. | Un límite de registros por IP para evitar abuso. |
| Endpoints operativos | `/api/work-orders`, `/api/receptions`, `/api/work-orders/{id}/corrections`, `/api/work-orders/{id}/diagnostics`, `/api/notifications` ya aplican la regla de permisos. | Sólo devuelven un mensaje fijo: no hay modelos, tablas, lógica ni pantallas. |
| Módulo de Clientes | Alta, consulta y ficha (Recepcionista y Asesor de servicio), con diseño de patrones documentado; **administración** con trazabilidad y suspensión (Recepcionista y Administrador). | Fusionar duplicados y mover un cliente de taller (hoy prohibido); consultar la auditoría completa desde la interfaz; búsqueda parcial por contacto en la consulta del alta; pruebas unitarias de cada patrón y pruebas del frontend. |
| Vehículos | Registro con VIN, placa, datos, imagen y kilometraje opcional; asociado a un cliente; lista con búsqueda. | Editar, eliminar (borrado lógico) y restaurar vehículos; transferirlos de cliente; usarlos en recepción y órdenes de trabajo; mostrarlos en la ficha del cliente. |
| Talleres y Auditoría | Alta y **administración de talleres** (editar, eliminar con borrado lógico, restaurar y ver la foto); las tablas `talleres` y `auditoria` se llenan. | Consultar la auditoría desde la interfaz. Los talleres creados antes de esta versión (a partir de la sucursal de un empleado) no tienen RFC ni domicilio: se completan editándolos. |

### ⏳ Pendiente

**Funcionalidad**
- Recepción de vehículos, órdenes de trabajo, diagnósticos y notificaciones.
- Empleados: restablecer la contraseña desde la administración, suspender temporalmente una cuenta sin eliminarla y cambiar el correo.
- Administración de **vehículos** (editar, eliminar con borrado lógico y restaurar).
- Consulta de la **Auditoría**.
- Aplicar el borrado lógico (`bin_status`) a los **clientes**: hoy lo usan roles, talleres y usuarios.
- Registrar en la **auditoría** los cambios de permisos de los roles.
- Cambio de contraseña desde el perfil y cambio obligatorio en el primer ingreso.

**Calidad y seguridad**
- Pruebas automatizadas: hay siete pruebas de punta a punta del backend en `backend/tests/` (Clientes, roles y talleres, permisos, empleados, administración de talleres, administración de clientes y vehículos, y migración del esquema). Faltan pruebas del resto del backend (login y recuperación), unitarias por patrón y del frontend.
- **El catálogo de códigos postales descargado es de octubre de 2017**: faltarán los códigos creados después. Hay que reimportar uno actualizado (ver *Catálogo de códigos postales*).
- La subida de fotos lee el cuerpo completo antes de validar si no declara `Content-Length`; en producción conviene limitar el tamaño del cuerpo en el servidor web.
- Límite de intentos en inicio de sesión y en la verificación del código de recuperación.
- Migraciones con Alembic: hoy `create_all` crea tablas nuevas y `app/migraciones.py` sólo agrega las columnas que faltan en roles, talleres y clientes al arrancar (idempotente, sin borrar ni cambiar datos); cualquier otro cambio de esquema requiere una migración real.
- Reemplazar `@app.on_event("startup")` (obsoleto) por `lifespan` en FastAPI.
- Orígenes CORS configurables por variable de entorno (hoy están fijos en `main.py`).
- División del bundle del frontend (el JS principal pesa ~670 kB).

**Repositorio**
- `backend/.vs/` (archivos de Visual Studio) está versionado y debería ignorarse.
- `tools/archify` es un clon completo de otro repositorio (~111 MB, con su propio `.git`); conviene decidir si se agrega como submódulo o se excluye.
- Los archivos `*.db` (SQLite local), `backend/data/` (catálogo de Correos de México, de uso gratuito y personal) y `backend/uploads/` (fotos) están en `.gitignore`: no se versionan.

---

## Documentación de trabajo

| Documento | Contenido |
| --- | --- |
| [`plan_estructura_de_trabajo.md`](plan_estructura_de_trabajo.md) | Fases del proyecto, lo realizado en la capa de seguridad y los campos del alta de taller |
| [`analisis/crear_roles.md`](analisis/crear_roles.md) | Registro de cuentas (Invitado) y creación de roles con verificación de duplicados |
| [`analisis/administrar_roles.md`](analisis/administrar_roles.md) | Actualizar y eliminar roles con borrado lógico (`bin_status` → `status`) |
| [`analisis/administrar_empleados.md`](analisis/administrar_empleados.md) | Pantalla de empleados: búsqueda, edición, asignación de rol a invitados y borrado lógico de cuentas |
| [`analisis/permisos_roles.md`](analisis/permisos_roles.md) | Catálogo de permisos, permisos de cada rol, asignación a roles personalizados y por qué los de administración no se delegan |
| [`analisis/alta_taller.md`](analisis/alta_taller.md) | Alta de taller: RFC, foto, taller único y autollenado por código postal |
| [`analisis/administrar_talleres.md`](analisis/administrar_talleres.md) | Administración de talleres: búsqueda, edición, foto, renombrado y borrado lógico |
| [`analisis/administrar_clientes.md`](analisis/administrar_clientes.md) | Administración de clientes: ID, nombre, teléfono y correo; modal de actualización, trazabilidad y suspensión |
| [`analisis/registrar_vehiculos.md`](analisis/registrar_vehiculos.md) | Registro de vehículos: flujo, VIN, placa, imagen y asociación al cliente |
| [`analisis/diagramas/`](analisis/diagramas) | Mapas de proceso en PNG (plan, permisos, alta de taller y registro de vehículo) generados con Archify |
| [`RESUMEN_PROYECTO.md`](RESUMEN_PROYECTO.md) | Resumen del estado del proyecto para retomarlo en otra conversación |
| [`docs/customer-patterns`](docs/customer-patterns/README.md) | Módulo de Clientes y sus patrones de diseño |

---

## Estructura

```
Taller_Mecanico/
├── backend/
│   ├── app/
│   │   ├── main.py            # Endpoints y arranque (crea tablas y administrador inicial)
│   │   ├── models.py          # User, PasswordResetCode, RoleDefinition y enum Role (las tablas de Clientes y Talleres están en customers/modelos.py)
│   │   ├── catalogos.py       # Tablas status (borrado lógico) y codigos_postales
│   │   ├── migraciones.py     # Agrega al arrancar las columnas nuevas de tablas existentes
│   │   ├── cuentas_api.py    # Registro público de cuentas (rol Invitado)
│   │   ├── roles_api.py      # Administración de roles con borrado lógico
│   │   ├── empleados_api.py  # Administración de empleados: listado, edición, asignación de rol y borrado lógico
│   │   ├── talleres/          # Alta de taller (api.py), administración (administracion.py), validaciones de RFC y foto, catálogo de códigos postales
│   │   ├── schemas.py         # Validaciones Pydantic de entrada/salida
│   │   ├── security.py        # Argon2, JWT y sesión actual
│   │   ├── permisos.py        # Catálogo de permisos, permisos de cada rol, requiere() y API de permisos
│   │   ├── config.py          # Variables de entorno
│   │   ├── database.py        # Motor y sesión de SQLAlchemy
│   │   ├── email_service.py   # Envío del código de recuperación
│   │   ├── customers/         # Módulo de Clientes: dominio, patrones, modelos, repositorio SQL, endpoints y administración (administracion.py)
│   │   │   ├── api.py         # Endpoints /api/customers y traducción de reglas a códigos HTTP
│   │   │   ├── fachada.py     # CustomerFacade: AltaCliente() y ConsultarCliente()
│   │   │   ├── cadena.py      # Chain of Responsibility: guardas, formato y coincidencias
│   │   │   ├── estrategias.py # Strategy: búsqueda paginada y política de duplicados
│   │   │   ├── fabrica.py     # Factory Method: creación del Customer activo
│   │   │   ├── modelos.py     # Tablas talleres, customers y auditoria
│   │   │   ├── repositorio_sql.py  # Implementación SQLAlchemy de los repositorios
│   │   │   └── ejemplo.py     # Recorrido ejecutable con datos en memoria
│   │   └── vehiculos/         # Registro de vehículos: modelo, validaciones (VIN, placa) y endpoints
│   ├── scripts/importar_codigos_postales.py   # Carga el catálogo de Correos de México
│   ├── tests/             # Pruebas de punta a punta (Clientes, roles y talleres, permisos, empleados, talleres, clientes y vehículos, migración)
│   ├── data/              # CPdescarga.txt (no se versiona)
│   ├── uploads/           # Fotos de talleres (no se versiona)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── components/        # AppShell (menú y barra) y AuthLayout (pantallas de acceso)
│       ├── views/             # Login, Registro, Recuperación, Panel, Empleados (administración y alta), Roles (alta y administración), Talleres (administración y alta), Clientes (consulta, alta y ficha)
│       ├── clientes.ts        # Reglas de formato y utilidades del módulo de Clientes
│       ├── talleres.ts        # Reglas del alta de taller (RFC, foto) espejo de las del servidor
│       ├── vehiculos.ts       # Reglas del registro de vehículos (VIN, placa, año, kilometraje) espejo de las del servidor
│       ├── api.ts             # Cliente HTTP con token y manejo de errores
│       ├── auth.ts            # Sesión en sessionStorage y vencimiento del token
│       ├── modules.ts         # Catálogo de módulos y su estado
│       ├── router.ts          # Rutas y guardas por rol
│       ├── types.ts           # Tipos, nombres de roles y permisos
│       └── styles.css         # Sistema visual
├── analisis/                  # Un documento por fase, y diagramas/ con los mapas de proceso
├── RESUMEN_PROYECTO.md        # Estado del proyecto para retomarlo en otra conversación
├── .archify/                  # Fuentes JSON y diagramas HTML generados con Archify
├── docs/customer-patterns/    # README por patrón, tabla resumen y diagramas (PNG)
└── tools/archify/             # Herramienta Archify
```

---

## Puesta en marcha

### Requisitos

- Python 3.11 o superior
- Node.js 20 o superior
- SQL Server con una base de datos llamada `TallerMecanico`
- [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)

### 1. Configurar el backend

Copie `backend/.env.example` a `backend/.env` y complete los valores:

| Variable | Descripción |
| --- | --- |
| `DATABASE_URL` | Cadena de conexión de SQLAlchemy (ver abajo). |
| `JWT_SECRET` | Secreto largo y aleatorio para firmar los tokens (mínimo 32 caracteres). |
| `ACCESS_TOKEN_MINUTES` | Duración de la sesión. Por defecto, 60. |
| `RESET_CODE_MINUTES` | Vigencia del código de recuperación. Por defecto, 15. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Servidor de correo. Si `SMTP_HOST` queda vacío, el código se muestra en la consola del backend. |
| `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` | Administrador que se crea en el primer arranque. |

**Cadena de conexión a SQL Server**

```
# Instancia predeterminada (MSSQLSERVER)
DATABASE_URL=mssql+pyodbc://USUARIO:CONTRASENA@localhost/TallerMecanico?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

# Instancia con nombre (p. ej. SQLEXPRESS): habilite TCP/IP y use el puerto de la instancia
DATABASE_URL=mssql+pyodbc://USUARIO:CONTRASENA@localhost:1433/TallerMecanico?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

> No escriba la instancia como `localhost%5CSQLEXPRESS`: el controlador no decodifica `%5C` y la conexión falla. Si la contraseña contiene caracteres como `@`, `:` o `/`, sí debe codificarlos (`@` → `%40`).

Para pruebas rápidas sin SQL Server puede usar SQLite: `DATABASE_URL=sqlite:///./taller_local.db`.

### 2. Iniciar la API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Al arrancar se crean las tablas nuevas, se siembran los estatus (`status`: 1 activo, 2 eliminado), se agregan las columnas que falten en `role_definitions` y `talleres` (`app/migraciones.py`; no borra ni modifica datos) y, si no existe, se crea el administrador inicial. La documentación interactiva queda en http://localhost:8000/docs.

> Las fotos de los talleres se guardan en `backend/uploads/` (o en la carpeta de la variable opcional `UPLOADS_DIR`). Hay que incluirla en los respaldos.

#### Catálogo de códigos postales (una sola vez)

El autollenado del domicilio usa el Catálogo Nacional de Códigos Postales de Correos de México. Descargue el archivo a `backend/data/` y cárguelo:

```powershell
cd backend
New-Item -ItemType Directory -Force data | Out-Null
Invoke-WebRequest https://www.correosdemexico.gob.mx/datosabiertos/cp/cpdescarga.txt -OutFile data\CPdescarga.txt
.\.venv\Scripts\python.exe scripts\importar_codigos_postales.py              # importa si la tabla está vacía
.\.venv\Scripts\python.exe scripts\importar_codigos_postales.py --reemplazar # vuelve a cargarlo
```

Son ~14 MB y ~145 mil asentamientos (32 292 códigos postales, 32 estados, 2 458 municipios); la importación tarda alrededor de 20 segundos. **El archivo que publica esa dirección tiene fecha de octubre de 2017**, así que no incluye los códigos postales creados después. Correos de México lo ofrece de forma gratuita para uso personal; por eso no se incluye en el repositorio.

### 3. Iniciar el frontend

```powershell
cd frontend
npm install
npm run dev
```

Abra http://localhost:5173. Si la API usa otro puerto, cree `frontend/.env.local` con `VITE_API_URL=http://localhost:PUERTO/api`. Los orígenes permitidos por CORS son `localhost` y `127.0.0.1` en los puertos 5173 y 5174.

Para generar la versión de producción: `npm run build` (resultado en `frontend/dist`).

---

## Pantallas

| Ruta | Pantalla | Acceso |
| --- | --- | --- |
| `/ingresar` | Inicio de sesión | Público |
| `/recuperar` | Recuperación de contraseña en 3 pasos | Público |
| `/registro` | Crear cuenta (rol Invitado) | Público |
| `/panel` | Panel de trabajo | Usuario autenticado |
| `/empleados` | Administrar empleados: buscar, editar, asignar rol a invitados, eliminar y restaurar | `empleados.administrar` (administrador) |
| `/empleados/nuevo` | Alta de empleado | Administrador |
| `/roles` | Administrar roles: ver los de fábrica, editar/eliminar (lógico)/restaurar los personalizados | Administrador |
| `/roles/nuevo` | Alta de rol | Administrador |
| `/talleres` | Administrar talleres: buscar, editar, eliminar (lógico) y restaurar | Administrador (`talleres.administrar`) |
| `/talleres/nuevo` | Alta de taller mecánico | Administrador (`talleres.alta`) |
| `/talleres/:id/editar` | Editar un taller (datos, domicilio y foto) | Administrador (`talleres.administrar`) |
| `/clientes` | Consultar clientes: búsqueda paginada | Recepcionista, Asesor de servicio |
| `/clientes/nuevo` | Alta de cliente (captura → coincidencias → confirmación → listo) | Recepcionista, Asesor de servicio |
| `/clientes/:id` | Ficha de cliente | Recepcionista, Asesor de servicio |
| `/clientes/administracion` | Administrar clientes: buscar, actualizar datos (ventana modal), historial, suspender y reactivar | Recepcionista y Administrador (`clientes.administrar`); suspender: sólo Administrador |
| `/vehiculos` | Lista de vehículos | Recepcionista y Administrador (`vehiculos.consultar`) |
| `/vehiculos/nuevo` | Registrar un vehículo y asociarlo a un cliente | Recepcionista y Administrador (`vehiculos.registrar`) |

## API

| Método | Ruta | Roles | Estado |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | Público | ✅ |
| GET | `/api/auth/me` | Autenticado | ✅ |
| POST | `/api/auth/recovery` | Público | ✅ |
| POST | `/api/auth/recovery/verify` | Público | ✅ |
| POST | `/api/auth/recovery/reset` | Público | ✅ |
| GET | `/api/users?buscar=&rol=&incluir_eliminados=&pagina=&tamano=` | `empleados.administrar` | ✅ cuentas paginadas |
| PATCH | `/api/users/{id}` | `empleados.administrar` | ✅ nombre, sucursal y rol (también convierte a un invitado en empleado) |
| DELETE | `/api/users/{id}` | `empleados.administrar` | ✅ borrado lógico; bloquea el acceso de inmediato |
| POST | `/api/users/{id}/restaurar` | `empleados.administrar` | ✅ |
| POST | `/api/users/employees` | Administrador | ✅ `role` es el código de un rol asignable (de empleado de fábrica o personalizado activo) |
| POST | `/api/auth/register` | Público | ✅ crea una cuenta con rol `INVITADO` |
| GET | `/api/roles?incluir_eliminados=` | Administrador | ✅ roles de fábrica y personalizados, con `es_sistema` y `empleados` |
| GET | `/api/roles/asignables` | `empleados.alta` | ✅ roles que se pueden elegir al dar de alta un empleado |
| GET | `/api/permisos` | `roles.administrar` | ✅ catálogo de permisos |
| GET | `/api/roles/{id}/permisos` | `roles.administrar` | ✅ permisos de un rol (los de fábrica, de sólo lectura) |
| PUT | `/api/roles/{id}/permisos` | `roles.administrar` | ✅ define los permisos de un rol personalizado |
| POST | `/api/roles` | Administrador | ✅ |
| PATCH | `/api/roles/{id}` | Administrador | ✅ nombre y descripción |
| DELETE | `/api/roles/{id}` | Administrador | ✅ borrado lógico |
| POST | `/api/roles/{id}/restaurar` | Administrador | ✅ |
| GET | `/api/talleres` | `talleres.consultar` (administrador y recepcionista) | ✅ talleres activos |
| POST | `/api/talleres` | `talleres.alta` (sólo administrador) | ✅ `multipart/form-data` con los datos y la `foto` |
| GET | `/api/talleres/{id}/foto` | `talleres.consultar` | ✅ |
| GET | `/api/talleres/administracion` | `talleres.administrar` (sólo administrador) | ✅ búsqueda, paginación y `incluir_eliminados`; con empleados y clientes de cada taller |
| GET | `/api/talleres/{id}` | `talleres.administrar` | ✅ |
| PUT | `/api/talleres/{id}` | `talleres.administrar` | ✅ `multipart/form-data`; la `foto` es opcional |
| DELETE | `/api/talleres/{id}` | `talleres.administrar` | ✅ borrado lógico |
| POST | `/api/talleres/{id}/restaurar` | `talleres.administrar` | ✅ |
| GET | `/api/catalogos/codigo-postal/{cp}` | `talleres.alta` (sólo administrador) | ✅ estado, municipio y colonias |
| GET | `/api/catalogos/estados`, `/municipios?estado=`, `/colonias?estado=&municipio=` | `talleres.alta` (sólo administrador) | ✅ camino inverso (la colonia trae su código postal) |
| GET | `/api/customers/alta/acceso` | Recepcionista, Asesor | ✅ «abrir alta»: sólo aplica las guardas y devuelve el taller |
| POST | `/api/customers` | Recepcionista, Asesor | ✅ cuerpo `{nombre_completo, telefono, correo, confirmar}`. `200` con `COINCIDENCIAS` o `PENDIENTE_CONFIRMACION`; `201` con `CREADO` |
| GET | `/api/customers?criterio=&pagina=&tamano=` | Recepcionista, Asesor | ✅ búsqueda paginada (tamaño de 1 a 50) |
| GET | `/api/customers/{id}` | Recepcionista, Asesor | ✅ ficha (sólo de clientes del propio taller) |
| GET | `/api/administracion/clientes` | `clientes.administrar` | ✅ búsqueda, filtro por estado y taller, paginación; la recepcionista sólo ve su taller |
| GET/PUT | `/api/administracion/clientes/{id}` | `clientes.administrar` | ✅ el taller asignado no se puede cambiar |
| GET | `/api/administracion/clientes/{id}/historial` | `clientes.administrar` | ✅ trazabilidad |
| POST | `/api/administracion/clientes/{id}/suspender` y `/reactivar` | `clientes.suspender` (sólo administrador) | ✅ |
| POST | `/api/vehiculos` | `vehiculos.registrar` | ✅ `multipart/form-data` con los datos y la `foto` |
| GET | `/api/vehiculos` y `/api/vehiculos/{id}/foto` | `vehiculos.consultar` | ✅ |
| GET | `/api/work-orders` | Administrador, Recepcionista, Asesor, Técnico | 🟡 sólo permisos |
| POST | `/api/receptions` | Administrador, Recepcionista | 🟡 sólo permisos |
| PATCH | `/api/work-orders/{id}/corrections` | Administrador, Asesor | 🟡 sólo permisos |
| POST | `/api/work-orders/{id}/diagnostics` | Administrador, Técnico | 🟡 sólo permisos |
| GET | `/api/notifications` | Administrador, Cliente | 🟡 sólo permisos |

## Roles del sistema

| Rol | Permisos actuales |
| --- | --- |
| `ADMINISTRADOR` | Alta de empleados, administración de roles y alta y administración de talleres; acceso a los endpoints de órdenes, recepciones, diagnósticos y notificaciones. **No** da de alta ni consulta clientes de un taller (no tiene sucursal), pero sí los **administra** en todos los talleres y es el único que los **suspende**. |
| `RECEPCIONISTA` | Dar de alta, consultar y **administrar** clientes de su taller; registrar y consultar **vehículos**; consultar talleres; registrar recepciones y consultar órdenes de trabajo. |
| `ASESOR_SERVICIO` | Dar de alta y consultar clientes; consultar y corregir órdenes de trabajo. |
| `TECNICO` | Consultar órdenes y registrar diagnósticos. |
| `CLIENTE` | Consultar notificaciones. |
| `SISTEMA` | Reservado para procesos internos. |
| `INVITADO` | Cuenta autoregistrada: ingresa y ve su panel, sin acceso a ningún módulo hasta que un administrador le asigne un rol. |
| `PERSONALIZADO` | Marcador interno de un empleado con un rol creado por el administrador (su nombre va en `role_name`). Sus permisos son los que el administrador asignó a ese rol. No se puede usar como clave de un rol nuevo. |

Estas claves están reservadas: no se pueden usar al crear roles personalizados.

---

## Seguridad aplicada

- Las contraseñas y los códigos de recuperación se guardan con hash Argon2; nunca en texto plano ni cifrado reversible.
- JWT firmado con `JWT_SECRET` y validado en cada endpoint protegido; el usuario debe seguir activo.
- Control de acceso por **permisos** en el backend (`requiere("clientes.alta")`, etc.), calculados en cada petición a partir del rol de la persona, y guardas de ruta en el SPA.
- La recuperación responde igual exista o no el correo, para no revelar qué cuentas están registradas.
- Validación de datos en cliente y servidor (correo, longitud de contraseña, formato de clave de rol).
- Las credenciales del administrador inicial sólo viven en `backend/.env`, que está en `.gitignore`; nunca se exponen al frontend.

> **Importante:** no comparta el contenido de `backend/.env`. Si una contraseña o el `JWT_SECRET` se expusieron, cámbielos. Al cambiar `JWT_SECRET`, todas las sesiones activas quedan invalidadas.

## Diseño de patrones · módulo Clientes

Documentación completa en [`docs/customer-patterns`](docs/customer-patterns/README.md): evaluación de patrones, tabla resumen, diagramas de clases y de secuencia (generados con Archify, `.archify/customer-patterns-20261002-120000/`) y un README por patrón.

| Patrón | Categoría | Uso en el módulo Clientes |
| --- | --- | --- |
| [Factory Method](docs/customer-patterns/factory-method/README.md) | Creacional | Único punto de creación de `Customer`, invocado sólo si no hay coincidencias. |
| [Facade](docs/customer-patterns/facade/README.md) | Estructural | `AltaCliente()` y `ConsultarCliente()` ocultan guardas, normalización, búsqueda, paginación, persistencia y auditoría. |
| [Chain of Responsibility](docs/customer-patterns/chain-of-responsibility/README.md) | Comportamiento | Pasos del alta con salida temprana: autenticación, autorización, Taller activo, formato y coincidencias. |
| [Strategy](docs/customer-patterns/strategy/README.md) | Comportamiento | Búsqueda paginada y política de no auto-crear ante coincidencias. |

Los patrones están implementados en `backend/app/customers/` y conectados a la API, a SQL Server y al frontend. Además, `python -m app.customers.ejemplo` (desde `backend/`) recorre el flujo con datos en memoria, sin base de datos.

### Cómo probar el módulo de Clientes

1. Inicie la API y el frontend como se indica en *Puesta en marcha* e importe el catálogo de códigos postales.
2. Ingrese como administrador y dé de alta el taller en **Talleres → Nuevo taller** (por ejemplo, «Taller Centro»): escriba el código postal y compruebe que se llenan estado, municipio y colonia; adjunte una foto.
3. Como administrador, cree un empleado con rol **Recepcionista** y como **sucursal** el nombre exacto del taller (sin distinguir mayúsculas). Esa sucursal es la que lo asocia al taller.
4. Cierre la sesión e ingrese como ese recepcionista. En el menú aparece **Clientes → Nuevo cliente** y **Consultar clientes**. Si su sucursal no está registrada como taller, la API lo rechaza con un mensaje que lo explica.
5. Dé de alta un cliente y luego intente registrar otro con el mismo nombre, teléfono o correo: la pantalla alerta y no guarda nada.

Para probar el registro de cuentas, cierre la sesión y use **Crear cuenta** en la pantalla de ingreso: la cuenta nace como **Invitado**. La administración de roles está en **Administración → Administrar roles**.

**Pruebas automáticas** (usan SQLite temporal y una carpeta de fotos temporal; no tocan su SQL Server ni `backend/uploads`). Desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tests\e2e_clientes.py          # Clientes: guardas, alta, duplicados, paginación, ficha, aislamiento
.\.venv\Scripts\python.exe tests\e2e_roles_talleres.py    # registro de cuentas, roles (borrado lógico), catálogo y alta de taller
.\.venv\Scripts\python.exe tests\e2e_permisos.py         # permisos de los roles: catálogo, asignación, efecto inmediato y no delegables
.\.venv\Scripts\python.exe tests\e2e_empleados.py        # administración de empleados: listado, edición, asignación de rol y borrado lógico
.\.venv\Scripts\python.exe tests\e2e_talleres_admin.py   # administración de talleres: búsqueda, edición, foto, renombrado, borrado lógico
.\.venv\Scripts\python.exe tests\e2e_clientes_vehiculos.py  # administración de clientes (trazabilidad, suspensión) y registro de vehículos
.\.venv\Scripts\python.exe tests\e2e_migracion.py         # arranque sobre un esquema anterior con datos
```

Las dos primeras también se pueden ejecutar contra una base de SQL Server de pruebas definiendo `E2E_DATABASE_URL` (use una base distinta de la real).

> Las tablas nuevas usan `VARCHAR` como el resto del esquema: con la intercalación predeterminada de SQL Server se conservan los acentos del español, pero no caracteres fuera de ese conjunto (por ejemplo, emojis).
