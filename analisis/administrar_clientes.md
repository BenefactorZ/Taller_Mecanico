# Fase 5 · Administrar clientes

**Objetivo.** Que el recepcionista y el administrador puedan mantener la información de los clientes **con trazabilidad**, y que sólo el administrador pueda **suspenderlos**. Estado: ✅ hecha y probada.

## 1. Quién puede qué

| Acción | Recepcionista | Administrador | Permiso |
| --- | --- | --- | --- |
| Ver la administración de clientes y su historial | ✅ sólo los de **su taller** | ✅ los de **todos los talleres** | `clientes.administrar` |
| Actualizar los datos de un cliente | ✅ | ✅ | `clientes.administrar` |
| **Suspender** y reactivar | ❌ | ✅ | `clientes.suspender` |
| Cambiar el **taller asignado** | ❌ | ❌ (nadie) | — |

Ambos permisos están **reservados a roles de fábrica**: no se pueden delegar a un rol personalizado. El asesor de servicio, el técnico y los roles personalizados reciben `403`. Un cliente fuera del alcance de la persona responde `404` (no se revela que existe).

> El administrador no tiene sucursal, así que sigue sin dar de alta ni consultar clientes de un taller (`clientes.alta` y `clientes.consultar`); pero ahora los **administra** en todos los talleres.

## 2. Pantalla `/clientes/administracion`

| Elemento | Detalle |
| --- | --- |
| Menú | Clientes → **Administrar clientes** |
| Búsqueda y filtros | Por nombre, teléfono o correo (parcial, sin distinguir mayúsculas ni acentos), por estado (activos / suspendidos) y, para el administrador, por taller |
| Listado | Paginado de 8 en 8: ID, nombre, teléfono, correo, taller, cuántos vehículos tiene, estado y acciones |
| Acciones | **Historial**, **Registrar vehículo** (atajo con el cliente ya elegido), **Actualizar datos**, y — sólo administrador — **Suspender** / **Reactivar** |

### Ventana modal «Actualizar datos del cliente»

Al dar clic en actualizar se abre una ventana modal con **toda la información del cliente**: número, estado, fecha de alta, cuántos vehículos tiene, **taller asignado**, ID, nombre, **teléfono** y **correo**. La **única restricción** es el taller: aparece bloqueado (con candado) y la API lo rechaza aunque se intente cambiar desde fuera (`409`).

- «Guardar cambios» sólo se habilita si hay algo distinto.
- El nombre, el teléfono y el correo siguen las **mismas reglas de formato del alta** (nombre y apellido; teléfono de 10 a 15 dígitos; correo válido) y **los tres son obligatorios**. Se validan en TypeScript y otra vez en FastAPI.
- Si otro cliente del taller tiene el **mismo teléfono** o el **mismo correo** → `409` (ambos son únicos por taller).
- Si otro cliente del taller tiene el **mismo nombre** → advertencia con el cliente coincidente y el botón **«Guardar de todos modos»**, por si se trata de otra persona (homónimos). Nunca se guarda en silencio.
- Los mensajes aparecen **dentro de la ventana, junto al botón** de guardar.

## 3. Trazabilidad

Cada operación deja una fila en `auditoria` con **quién**, **cuándo**, **sobre qué cliente y taller**, y **qué cambió**:

| Acción registrada | Cuándo | Detalle guardado |
| --- | --- | --- |
| `ALTA_CUSTOMER` | Alta del cliente (ya existía) | «Alta confirmada sin coincidencias» |
| `ACTUALIZAR_CUSTOMER` | Se modifican datos | `nombre: de «A» a «B»; teléfono: de «x» a «y»; correo: de «m» a «n»` (sólo lo que cambió) |
| `SUSPENDER_CUSTOMER` | Se suspende | `Motivo: …` (obligatorio, 3 a 200 caracteres) |
| `REACTIVAR_CUSTOMER` | Se reactiva | «Cliente reactivado» |
| `ALTA_VEHICULO` | Se registra un vehículo | Marca, modelo, año, placa y VIN |

El **historial** del cliente (botón con el reloj) muestra estos movimientos del más reciente al más antiguo. Guardar sin cambios no genera movimiento.

## 4. Suspensión

Suspender **no borra** nada: el cliente pasa a estado `INACTIVO` (se muestra como «Suspendido»). Mientras esté suspendido:

- no se puede **modificar** (`409`, `CLIENTE_SUSPENDIDO`);
- no se le pueden **registrar vehículos** (`409`);
- el alta de clientes **sigue detectándolo** como coincidencia, para no duplicarlo;
- sus datos, vehículos e historial se conservan, y un administrador puede **reactivarlo**.

## 5. API

| Método | Ruta | Requiere | Detalle |
| --- | --- | --- | --- |
| GET | `/api/administracion/clientes?buscar=&estado=&taller_id=&pagina=&tamano=` | `clientes.administrar` | Tamaño de 1 a 50; `taller_id` sólo tiene efecto para el administrador |
| GET | `/api/administracion/clientes/{id}` | `clientes.administrar` | Detalle |
| PUT | `/api/administracion/clientes/{id}` | `clientes.administrar` | `nombre_completo`, `telefono`, `correo`, `confirmar`; `taller_id` sólo se acepta si no cambia |
| POST | `/api/administracion/clientes/{id}/suspender` | `clientes.suspender` | `motivo` obligatorio |
| POST | `/api/administracion/clientes/{id}/reactivar` | `clientes.suspender` | — |
| GET | `/api/administracion/clientes/{id}/historial` | `clientes.administrar` | Movimientos de auditoría con el nombre de quien los hizo |

## 6. Criterios de aceptación

- [x] Recepcionista y administrador modifican datos; el asesor, el técnico y los roles personalizados no.
- [x] Sólo el administrador suspende y reactiva; la recepcionista recibe `403`.
- [x] La recepcionista sólo ve y modifica clientes de su taller; el administrador, los de todos.
- [x] Al actualizar se abre una ventana modal con la información del cliente y el taller asignado bloqueado.
- [x] El taller asignado no cambia por ninguna vía.
- [x] Cada modificación, suspensión y reactivación queda en el historial con usuario, fecha y detalle.
- [x] Un cliente suspendido no se modifica ni recibe vehículos.
- [x] Mismas validaciones de formato que el alta, en frontend y backend.

Pruebas: `backend/tests/e2e_clientes_vehiculos.py` (86 comprobaciones junto con el módulo de vehículos; también ejecutada en SQL Server).

## 7. Decisiones y pendientes

- **Suspendido = `INACTIVO`.** Se reutilizó el estado que ya existía en el dominio; no hay tabla ni columna nueva.
- **Sin borrado lógico de clientes** todavía: la baja definitiva de un cliente no se pidió. La suspensión cubre el caso de uso.
- **Pendiente:** mover un cliente de taller (hoy prohibido por decisión del negocio), fusionar duplicados y una pantalla para consultar la auditoría completa.

## 8. Datos del cliente: ID, nombre, teléfono y correo

| Campo | Regla |
| --- | --- |
| **ID** | Lo asigna el sistema al guardar; no se edita. Aparece en la ficha, la lista, el modal y el historial |
| **Nombre** | Nombre y apellido (hasta 140 caracteres) |
| **Teléfono** | De 10 a 15 dígitos; se guarda sin espacios, paréntesis ni guiones (`55 1234-5678` → `5512345678`). **Único por taller** |
| **Correo** | Correo válido; se guarda en minúsculas. **Único por taller** |

Las coincidencias del alta se buscan por **teléfono, por correo y por nombre**. En la base, `customers` tiene `telefono` y `correo`, con un índice único `(taller, teléfono)`; la columna histórica `contacto` se conserva como clave de unicidad `(taller, correo)` y la mantiene el repositorio.

**Clientes anteriores.** Los que sólo tenían un contacto quedan con uno de los dos campos vacío y se marcan **«Datos incompletos»**. Para guardarlos hay que capturar el que falta; el historial registra el cambio (`correo: de «sin dato» a «…»`).
