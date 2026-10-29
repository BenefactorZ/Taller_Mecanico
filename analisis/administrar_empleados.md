# Fase 2.2 · Administrar empleados

**Objetivo.** Una pantalla para ver y mantener las cuentas del sistema: cambiar el nombre, la sucursal o el rol de un empleado, **asignar rol a quien se registró como invitado**, y eliminar cuentas con borrado lógico. Estado: ✅ hecha y probada.

**Quién.** Sólo quien tiene el permiso `empleados.administrar` (reservado al administrador; no se puede delegar a un rol personalizado, igual que `empleados.alta` y `roles.administrar`).

## 1. Pantalla `/empleados`

| Elemento | Detalle |
| --- | --- |
| Menú | Administración → **Empleados** (junto a «Nuevo empleado») |
| Búsqueda | Por nombre o correo, sin distinguir mayúsculas; espera a que se deje de escribir |
| Filtros | Por rol (de fábrica o personalizado), atajo **«Cuentas sin rol (invitados)»** e interruptor «Mostrar eliminadas» |
| Listado | Paginado de 8 en 8: nombre, correo, sucursal, rol, estado y acciones |
| Avisos en cada cuenta | «Usted» (su propia cuenta), «Protegida», «Sin rol asignado» (invitado), «Sucursal sin taller registrado» y rol eliminado (no concede permisos) |
| Acciones | **Asignar rol** (invitados), **Editar**, **Eliminar** y **Restaurar** |

## 2. Qué se puede hacer

| Acción | Endpoint | Regla |
| --- | --- | --- |
| Listar | `GET /api/users?buscar=&rol=&incluir_eliminados=&pagina=&tamano=` | Tamaño de 1 a 50; por omisión no incluye las eliminadas; nunca devuelve contraseñas |
| Editar / asignar rol | `PATCH /api/users/{id}` | Cambia **nombre, sucursal y rol**. El rol sale de la misma lista que el alta de empleado (de empleado de fábrica o personalizado activo). La sucursal es obligatoria. El **correo no se cambia**. |
| Eliminar | `DELETE /api/users/{id}` | Borrado lógico (ver abajo) |
| Restaurar | `POST /api/users/{id}/restaurar` | Reactiva la cuenta |

**Asignar rol a un invitado.** Al elegir un rol y una sucursal, la cuenta pasa a ser empleado. Como los permisos se leen en cada petición, **la persona ya opera con los del nuevo rol sin volver a iniciar sesión**. Lo mismo ocurre al cambiar el rol de un empleado: sus permisos anteriores se pierden de inmediato.

## 3. Borrado lógico de cuentas

Eliminar una cuenta **no la borra**:

- `users.bin_status` pasa al estatus «eliminado» de la tabla `status` (2), igual que en roles y talleres.
- La cuenta también se desactiva (`is_active = 0`). Esa es la comprobación que ya hacen el inicio de sesión, la recuperación de contraseña y **cada petición**, así que la persona **no puede ingresar ni recuperar su contraseña, y su sesión abierta deja de valer en la siguiente petición** (`401`).
- Restaurar devuelve `bin_status = 1` e `is_active = 1`; la persona vuelve a ingresar con su misma contraseña.
- Las cuentas eliminadas no se cuentan en el total de empleados de cada rol.

## 4. Protecciones

| Caso | Respuesta |
| --- | --- |
| Editar o eliminar **su propia cuenta** | `409` (la pantalla no muestra los botones) |
| Cuentas **protegidas**: Administrador, Cliente y Sistema | `409`; se muestran con el aviso «Protegida» |
| Editar una cuenta eliminada | `409` (hay que restaurarla primero) |
| Rol de administrador, de cliente o de sistema; rol inexistente o eliminado | `422` |
| Sucursal vacía o nombre muy corto | `422` |
| Cuenta inexistente | `404` |
| Quien no tiene `empleados.administrar` | `403` |

## 5. Sucursal y taller

La sucursal debe coincidir con el nombre de un taller registrado para que la persona opere en él (módulo de Clientes). El diálogo sugiere los talleres registrados y el listado marca con **«Sucursal sin taller registrado»** las que no coinciden.

## 6. Datos

Se agregó `users.bin_status` (clave foránea a `status`, por omisión 1). La migración al arrancar es idempotente y conserva las cuentas existentes (`backend/tests/e2e_migracion.py`).

## 7. Criterios de aceptación

- [x] El listado busca, filtra por rol y pagina, e incluye las eliminadas sólo si se pide.
- [x] Un invitado se convierte en empleado al asignarle rol y sucursal, y opera de inmediato.
- [x] Cambiar el rol de un empleado cambia sus permisos al instante.
- [x] Eliminar bloquea el inicio de sesión y la sesión abierta; restaurar lo devuelve.
- [x] La cuenta eliminada sigue en la base de datos.
- [x] No se puede editar ni eliminar la propia cuenta ni las protegidas.
- [x] Los errores de validación aparecen junto al botón de guardar.

Pruebas: `backend/tests/e2e_empleados.py` (60 comprobaciones; también ejecutada en SQL Server) y revisión de la pantalla en el navegador.

## 8. Pendiente

- Restablecer la contraseña de un empleado desde esta pantalla (hoy cada persona la recupera por correo).
- Suspender temporalmente una cuenta sin eliminarla.
- Cambiar el correo de una cuenta.
- Registrar en la auditoría los cambios de rol, las eliminaciones y las restauraciones (la tabla de auditoría exige un taller y el administrador no tiene uno).
