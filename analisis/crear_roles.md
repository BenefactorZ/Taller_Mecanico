# Fase 1 · Crear roles

Cubre dos procesos: **crear una cuenta** (registro) y **crear un rol** (administrador). Estado: ✅ hecha y probada.

## 1. Proceso A · Creación de cuenta → registro → Invitado

**Objetivo.** Que cualquier persona pueda crear una cuenta sin elegir rol: toda cuenta autoregistrada es **Invitado**.

| Elemento | Detalle |
| --- | --- |
| Actor | Cualquier persona (sin sesión) |
| Pantalla | `/registro`, con el enlace «Crear cuenta» en el ingreso |
| Datos | Nombre completo (nombre y apellido), correo y contraseña (mínimo 12 caracteres) con confirmación |
| Resultado | Cuenta con rol `INVITADO`, sin sucursal, activa |
| Endpoint | `POST /api/auth/register` (público) → `201` |

**Flujo.**
1. La persona abre «Crear cuenta» e ingresa sus datos.
2. El frontend valida el formato; el servidor lo vuelve a validar.
3. El servidor verifica que el correo **no esté repetido** (sin distinguir mayúsculas).
4. Guarda la cuenta con la contraseña cifrada (Argon2) y el rol `INVITADO`.
5. La pantalla confirma la creación y ofrece ir a ingresar.

**Reglas.**
- El rol **no** viaja en la petición: si se envía uno, se ignora. Nadie se puede registrar como administrador.
- Correo duplicado → `409 Ya existe una cuenta con ese correo` (también protegido por la restricción única de la base ante dos registros simultáneos).
- Contraseña corta o correo inválido → `422`.
- Un Invitado puede ingresar y ve su panel con un aviso, pero **no** tiene acceso a roles, talleres, clientes ni empleados (la API responde `403` y las rutas del SPA lo devuelven al panel).

## 2. Proceso B · Crear un rol

**Objetivo.** Que sólo el administrador defina roles nuevos, verificando que no se dupliquen.

| Elemento | Detalle |
| --- | --- |
| Actor | Administrador |
| Pantalla | `/roles/nuevo` |
| Datos | Nombre del rol, clave única en mayúsculas (se sugiere desde el nombre) y descripción opcional |
| Endpoint | `POST /api/roles` → `201` |

**Verificación de duplicados.**

| Caso | Respuesta |
| --- | --- |
| Clave ya usada por un rol activo | `409 Ya existe un rol con esa clave` |
| Clave usada por un rol **eliminado** | `409` que indica restaurarlo desde la administración de roles |
| Nombre ya usado por un rol activo (sin distinguir mayúsculas) | `409 Ya existe un rol con ese nombre` |
| Clave reservada del sistema (`ADMINISTRADOR`, `RECEPCIONISTA`, `ASESOR_SERVICIO`, `TECNICO`, `CLIENTE`, `SISTEMA`, `INVITADO`) | `422` |
| Quien lo pide no es administrador | `403` |

## 2 bis. Proceso C · Asignar un rol al dar de alta un empleado

**Objetivo.** Que al crear un empleado se pueda elegir cualquier rol disponible **en la base de datos**: los de fábrica de empleado y los que creó el administrador.

| Elemento | Detalle |
| --- | --- |
| Actor | Administrador |
| Pantalla | `/empleados/nuevo`, lista desplegable «Rol» |
| Origen de la lista | `GET /api/roles/asignables`: Recepcionista, Asesor de servicio, Técnico y los roles personalizados con `bin_status = 1` (marcados «Personalizado») |
| Endpoint | `POST /api/users/employees` con `role` = código del rol |

**Cómo se guarda.** Un rol de fábrica se guarda en `users.role` como siempre. Un rol personalizado se guarda como `users.role = PERSONALIZADO` más `users.role_definition_id` apuntando a la tabla `role_definitions`; la API devuelve su nombre en `role_name`.

| Caso | Respuesta |
| --- | --- |
| Rol de empleado de fábrica o personalizado activo | `201` |
| `ADMINISTRADOR`, `CLIENTE`, `SISTEMA`, `INVITADO` o `PERSONALIZADO` (no son de empleado) | `422` |
| Rol personalizado eliminado o inexistente | `422` |
| Código en minúsculas o con formato inválido | `422` |

**Permisos.** Un rol personalizado nace **sin permisos**: la persona ingresa y ve su panel con un aviso, pero la API le responde `403` en todos los módulos hasta que el administrador le asigne permisos (ver [`permisos_roles.md`](permisos_roles.md)). La vista previa del alta de empleado muestra los permisos del rol elegido y avisa si no tiene ninguno.

## 3. Validaciones (frontend y backend)

| Campo | Regla |
| --- | --- |
| Nombre completo (registro) | 3 a 140 caracteres y no vacío en el servidor; en la pantalla además se piden al menos dos palabras (nombre y apellido) |
| Correo | Formato de correo válido |
| Contraseña | 12 a 128 caracteres; las dos contraseñas coinciden (en la pantalla) |
| Clave de rol | Empieza con letra; sólo mayúsculas, números y guion bajo; 3 a 40 caracteres |
| Nombre de rol | 3 a 80 caracteres |
| Descripción | Hasta 250 caracteres |

## 4. Criterios de aceptación

- [x] Una cuenta registrada queda como Invitado y puede ingresar.
- [x] No se puede registrar el mismo correo dos veces, ni con otra grafía.
- [x] Quien se registra no puede elegir ni forzar su rol.
- [x] Un Invitado no accede a ningún módulo, ni por menú ni por URL.
- [x] Sólo el administrador crea roles; no se aceptan claves ni nombres duplicados.
- [x] Los avisos de error y la confirmación aparecen junto al botón.
- [x] Al dar de alta un empleado, la lista de roles sale de la base de datos e incluye los roles personalizados.
- [x] Un empleado con rol personalizado ingresa, ve su nombre de rol y no accede a módulos por menú, URL ni API.

Pruebas: `backend/tests/e2e_roles_talleres.py` (secciones «registro de cuentas» y «administración de roles»).

## 5. Decisiones y pendientes

- El rol `INVITADO` es un valor más del enum `Role`; no requiere cambiar el esquema de la base.
- La asignación de un rol a un Invitado ya existe (ver [`administrar_empleados.md`](administrar_empleados.md)). **Pendiente:** un límite de registros por IP para evitar abuso.
- Los permisos de los roles personalizados ya se definen (ver [`permisos_roles.md`](permisos_roles.md)).
