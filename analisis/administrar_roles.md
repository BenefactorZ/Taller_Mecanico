# Fase 2 · Administrar roles

**Objetivo.** Pantalla de administración de roles para **actualizar** y **eliminar** con **borrado lógico**. Estado: ✅ hecha y probada.

## 1. Borrado lógico

Eliminar un rol **no borra la fila**: sólo agrega/cambia un campo de estatus.

| Elemento | Detalle |
| --- | --- |
| Campo | `bin_status` (en `role_definitions`; también en `talleres`) |
| Tabla de estatus | `status`, con su propio **id**, **valor** y **descripción** |
| Relación | `bin_status` es una clave foránea a `status.id` |
| Valor por omisión | `1` (activo) |

Tabla `status` (se siembra al arrancar la API):

| id | valor | descripción |
| --- | --- | --- |
| 1 | activo | Registro activo |
| 2 | eliminado | Registro eliminado lógicamente (borrado lógico) |

> La descripción del id 1 se redactó como «Registro activo» (y no «usuario activo») porque la misma tabla sirve a roles y talleres.

## 1 bis. Roles de fábrica en la misma tabla

Los 7 roles que ya existían en el código (`Role`) se **siembran en `role_definitions`** al arrancar, con `es_sistema = 1`, para que aparezcan en la administración junto a los personalizados.

| Código | Nombre | ¿Asignable a empleados? |
| --- | --- | --- |
| `ADMINISTRADOR` | Administrador | No |
| `RECEPCIONISTA` | Recepcionista | Sí |
| `ASESOR_SERVICIO` | Asesor de servicio | Sí |
| `TECNICO` | Técnico | Sí |
| `CLIENTE` | Cliente | No |
| `SISTEMA` | Sistema | No |
| `INVITADO` | Invitado | No (es el rol de las cuentas autoregistradas) |

- Son de **sólo lectura**: no se editan, no se eliminan ni se restauran (`409`), porque sus permisos están definidos en el código y cambiarlos aquí no los cambiaría allá.
- Ningún rol personalizado puede llamarse igual que uno de fábrica.
- Cada rol muestra **cuántos usuarios lo tienen** (`empleados`).
- La siembra es idempotente y no toca los roles personalizados existentes (p. ej. `MECANICO` y `REPARTIDOR`).

## 2. Proceso

| Elemento | Detalle |
| --- | --- |
| Actor | Administrador |
| Pantalla | `/roles` («Administrar roles») |
| Listado | Dos secciones: **roles del sistema** (sólo lectura) y **roles personalizados** activos; el interruptor «Mostrar eliminados» incluye los personalizados eliminados |

| Acción | Endpoint | Regla |
| --- | --- | --- |
| Listar | `GET /api/roles?incluir_eliminados=` | Primero los de fábrica y luego los personalizados; por omisión sólo `bin_status = 1` |
| Asignables | `GET /api/roles/asignables` | Roles que se ofrecen al dar de alta un empleado (ver `crear_roles.md`) |
| Actualizar | `PATCH /api/roles/{id}` | Cambia **nombre y descripción**; la **clave no se modifica**. El nombre no puede repetirse entre roles activos. Un rol eliminado no se edita (`409`). |
| Eliminar | `DELETE /api/roles/{id}` | Borrado lógico: `bin_status = 2`. La pantalla pide confirmación y aclara que se puede restaurar. |
| Restaurar | `POST /api/roles/{id}/restaurar` | `bin_status = 1`; falla (`409`) si ya existe otro rol activo con el mismo nombre. |

Todas exigen administrador (`403` para cualquier otro rol, incluido el Invitado).

## 3. Efecto en el resto del sistema

- La clave de un rol eliminado **sigue ocupada**: crear un rol con esa clave responde `409` e indica restaurarlo.
- El panel del administrador sólo muestra los roles activos.
- Al agregar `bin_status` a una base que ya tenía roles, los existentes quedan **activos** (`bin_status = 1`) y sin perder datos.
- **Eliminar un rol en uso** está permitido: los empleados que lo tienen lo conservan (se les sigue mostrando su rol), pero el rol deja de ofrecerse al dar de alta nuevos empleados y, mientras esté eliminado, **no les concede permisos** (pierden el acceso a los módulos hasta que se restaure). La pantalla avisa cuántos empleados lo tienen antes de confirmar.

## 4. Migración de la base

`create_all` no agrega columnas a tablas existentes, por eso `app/migraciones.py` las agrega al arrancar:

- Es **idempotente**: si la columna existe, no hace nada.
- Sólo **agrega** columnas, claves foráneas e índices; no borra ni cambia datos.
- Se verificó partiendo del esquema anterior con datos, en SQLite y en una base temporal de SQL Server (`backend/tests/e2e_migracion.py`).

## 5. Criterios de aceptación

- [x] Se puede editar el nombre y la descripción; la clave queda bloqueada.
- [x] Eliminar conserva la fila en la base con `bin_status = 2`.
- [x] El listado normal oculta los eliminados; el interruptor los muestra.
- [x] Restaurar devuelve el rol a `bin_status = 1`.
- [x] No se puede editar un rol eliminado ni restaurar uno cuyo nombre ya usa otro activo.
- [x] Los roles que ya existían antes del cambio siguen activos.
- [x] Los 7 roles de fábrica aparecen en la administración, de sólo lectura y con su conteo de usuarios.

Pruebas: `backend/tests/e2e_roles_talleres.py` y `backend/tests/e2e_migracion.py`.

## 5 bis. Permisos

Cada rol muestra cuántos permisos tiene y desde la misma pantalla se definen (ver [`permisos_roles.md`](permisos_roles.md)). Un rol **eliminado no concede permisos** hasta que se restaure.

## 6. Pendiente

- Aplicar el mismo borrado lógico a los **clientes** (roles, talleres y usuarios ya lo tienen).
- El cambio de rol de un empleado existente ya está en [`administrar_empleados.md`](administrar_empleados.md).
