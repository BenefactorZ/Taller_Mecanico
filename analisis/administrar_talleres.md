# Fase 6 · Administrar talleres

**Objetivo.** Una pantalla para ver y mantener los talleres registrados: buscarlos, corregir sus datos, domicilio o foto, y eliminarlos con borrado lógico (sin perder información) o restaurarlos. Estado: ✅ hecha y probada.

**Quién.** Sólo quien tiene el permiso `talleres.administrar`, **reservado al administrador**: no se puede delegar a un rol personalizado, igual que `talleres.alta`, `empleados.alta`, `empleados.administrar` y `roles.administrar`. El recepcionista conserva únicamente `talleres.consultar` y no ve esta pantalla.

## 1. Pantalla `/talleres`

| Elemento | Detalle |
| --- | --- |
| Menú | Talleres → **Talleres** (junto a «Nuevo taller») |
| Búsqueda | Por nombre, RFC o municipio, sin distinguir mayúsculas; espera a que se deje de escribir |
| Filtro | Interruptor «Mostrar eliminados» (por omisión no se muestran) |
| Listado | Paginado de 8 en 8: **miniatura de la foto**, nombre, RFC, domicilio, correo, cuántos **empleados** y **clientes** tiene, estado y acciones |
| Avisos | «Datos incompletos» en los talleres antiguos sin RFC, domicilio o foto |
| Acciones | **Editar**, **Eliminar** y **Restaurar**; «Nuevo taller» lleva al alta |

## 2. Qué se puede hacer

| Acción | Endpoint | Regla |
| --- | --- | --- |
| Listar | `GET /api/talleres/administracion?buscar=&incluir_eliminados=&pagina=&tamano=` | Tamaño de 1 a 50; por omisión no incluye los eliminados; el comodín `%` o `_` se busca como texto |
| Ver uno | `GET /api/talleres/{id}` | Datos completos para llenar el formulario de edición |
| Editar | `PUT /api/talleres/{id}` (`multipart/form-data`) | Las **mismas reglas del alta**: RFC con expresión regular y fecha real, correo, domicilio verificado contra el catálogo de códigos postales y **nombre y RFC únicos** (el taller puede conservar los suyos). La **foto es opcional**: sin archivo se conserva la actual |
| Eliminar | `DELETE /api/talleres/{id}` | Borrado lógico (ver abajo) |
| Restaurar | `POST /api/talleres/{id}/restaurar` | Vuelve a dejarlo activo |

La edición reutiliza la pantalla del alta (`/talleres/:id/editar`): el formulario se llena con los datos del taller, el código postal recupera estado, municipio y colonia, y se muestra la foto actual. Un taller eliminado no se edita (`409`): primero se restaura.

## 3. Reglas que conviene conocer

| Regla | Detalle |
| --- | --- |
| **Cambiar el nombre** | Los empleados se asocian al taller por el nombre de su sucursal. Al renombrar, las sucursales que usaban el nombre anterior **se actualizan en la misma transacción**; así nadie pierde acceso a su taller. |
| **Cambiar la foto** | La nueva se valida por sus bytes (JPG, PNG o WebP, máximo 15 MB) y la anterior se borra del disco sólo después de guardar. Si algo falla no queda ninguna foto huérfana. |
| **Eliminar** | No borra nada: cambia `bin_status` al estatus «eliminado» y deja `activo = 0`. Los clientes, la foto y la auditoría se conservan. Los empleados de ese taller **dejan de poder operar clientes** (la guarda `TallerActivo` los rechaza) y el diálogo avisa cuántos son. |
| **Restaurar** | Reactiva el taller y, con él, a sus empleados. |
| **Duplicados** | Nombre y RFC siguen siendo únicos aun frente a talleres eliminados (el alta pide restaurar en lugar de crear de nuevo). |
| **Auditoría** | Cada edición, eliminación y restauración queda en `auditoria` (`EDITAR_TALLER`, `ELIMINAR_TALLER`, `RESTAURAR_TALLER`) con el RFC y, si se renombró, el nombre anterior. |

## 4. Fotos con sesión

La foto está protegida con el token de sesión, y un `<img>` no puede enviarlo. El frontend la descarga con la API (`apiBlob`) y la muestra desde un objeto local (`components/FotoTaller.vue`), que se libera al salir de la pantalla.

## 5. Criterios de aceptación

- [x] Sólo el administrador lista, edita, elimina y restaura talleres (el recepcionista, el técnico, el asesor, el invitado y los roles personalizados reciben `403`; la ruta redirige al panel).
- [x] El permiso `talleres.administrar` no se puede asignar a un rol personalizado, ni siquiera escribiéndolo en la base.
- [x] La búsqueda por nombre, RFC y municipio y la paginación funcionan.
- [x] Editar aplica las reglas del alta y no choca consigo mismo; nombre o RFC de otro taller → `409`.
- [x] Cambiar la foto reemplaza la anterior; un formato falso, una foto de más de 15 MB o un fallo de validación no dejan archivos huérfanos.
- [x] Renombrar un taller actualiza la sucursal de sus empleados y siguen operando.
- [x] Eliminar conserva todo, oculta el taller de las listas y bloquea a sus empleados; restaurar los habilita.
- [x] El error o la confirmación aparecen junto al botón de envío.

Pruebas: `backend/tests/e2e_talleres_admin.py` (62 comprobaciones). El resto de las suites se actualizó por el permiso nuevo y sigue pasando.

## 6. Decisiones y pendientes

- **Sin tablas nuevas:** sólo se agrega un permiso al catálogo (13 en total) y la API lo siembra al arrancar.
- Eliminar un taller **no se bloquea** aunque tenga empleados: es reversible y el diálogo advierte el efecto. Una alternativa más estricta sería exigir reasignar antes a los empleados.
- Los clientes de un taller eliminado no se pueden consultar mientras esté eliminado (las consultas se limitan al taller del usuario, que ya no es válido).
- **Pendiente:** consultar la auditoría desde la interfaz; la administración de clientes (fase 5); reimportar un catálogo de códigos postales más reciente.
