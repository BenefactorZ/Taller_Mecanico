"""Prueba de punta a punta de registro de cuentas (INVITADO), administración de roles (borrado lógico), catálogo de códigos
postales y alta de taller. Usa SQLite y una carpeta de fotos temporales: no toca SQL Server ni backend/uploads.

Requisito de desarrollo: pip install -r requirements-dev.txt
Ejecución, desde backend/:   python tests/e2e_roles_talleres.py
"""
import os, sys, tempfile

_BASE = tempfile.mkdtemp(prefix="taller_e2e_")
os.environ.update(DATABASE_URL=os.environ.get("E2E_DATABASE_URL") or "sqlite:///" + os.path.join(_BASE, "prueba.db").replace("\\", "/"), UPLOADS_DIR=os.path.join(_BASE, "subidas"),
                  JWT_SECRET="x" * 40, BOOTSTRAP_ADMIN_EMAIL="admin@example.com", BOOTSTRAP_ADMIN_PASSWORD="AdminPrueba12345!")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.main import app
from app.database import engine
from app.catalogos import CodigoPostalModel, StatusModel
from app.customers.modelos import AuditoriaModel, TallerModel
from app.models import RoleDefinition

fallos = []
def esperar(nombre, real, esperado):
    ok = real == esperado
    print(("OK   " if ok else "FALLA"), nombre, "" if ok else f"-> {real!r} (esperado {esperado!r})")
    if not ok: fallos.append(nombre)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200
JPG = b"\xff\xd8\xff\xe0" + b"0" * 200
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"0" * 100
GIF = b"GIF89a" + b"0" * 100
CLAVE = "ClaveSegura12345!"
subidas = Path(os.environ["UPLOADS_DIR"]) / "talleres"
def archivos(): return sorted(p.name for p in subidas.glob("*")) if subidas.exists() else []

with TestClient(app) as c:
    def login(correo, clave=CLAVE):
        return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": correo, "password": clave}).json()["access_token"]}
    admin = login("admin@example.com", "AdminPrueba12345!")
    def empleado(nombre, correo, rol, sucursal):
        c.post("/api/users/employees", headers=admin, json={"full_name": nombre, "email": correo, "password": CLAVE, "role": rol, "branch": sucursal})
        return login(correo)

    # ---------- catálogo de apoyo ----------
    with Session(engine) as db:
        esperar("estatus base sembrados", [(s.id, s.valor) for s in db.scalars(select(StatusModel).order_by(StatusModel.id))], [(1, "activo"), (2, "eliminado")])
        db.add_all([CodigoPostalModel(codigo_postal=cp, colonia=col, tipo_asentamiento="Colonia", municipio=mun, estado=est) for cp, col, mun, est in [
            ("06000", "Centro (Área 1)", "Cuauhtémoc", "Ciudad de México"), ("06000", "Centro (Área 2)", "Cuauhtémoc", "Ciudad de México"),
            ("06300", "Guerrero", "Cuauhtémoc", "Ciudad de México"), ("01000", "San Ángel", "Álvaro Obregón", "Ciudad de México"),
            ("44100", "Centro", "Guadalajara", "Jalisco"), ("45000", "Centro", "Zapopan", "Jalisco")]])
        db.commit()

    # ---------- registro de cuentas (INVITADO) ----------
    datos = {"full_name": "Ivan Invitado", "email": "Ivan@Example.com", "password": CLAVE}
    r = c.post("/api/auth/register", json=datos); esperar("registro crea cuenta", (r.status_code, r.json().get("role"), r.json().get("branch"), r.json().get("email")), (201, "INVITADO", None, "ivan@example.com"))
    esperar("registro con correo repetido (otra grafía) -> 409", c.post("/api/auth/register", json={**datos, "email": "IVAN@example.com"}).status_code, 409)
    esperar("contraseña corta -> 422", c.post("/api/auth/register", json={**datos, "email": "otro@example.com", "password": "corta"}).status_code, 422)
    esperar("correo inválido -> 422", c.post("/api/auth/register", json={**datos, "email": "no-es-correo"}).status_code, 422)
    r = c.post("/api/auth/register", json={**datos, "email": "astuto@example.com", "role": "ADMINISTRADOR"}); esperar("quien se registra no puede elegir su rol", r.json().get("role"), "INVITADO")
    invitado = login("ivan@example.com")
    for ruta in ("/api/roles", "/api/talleres", "/api/catalogos/estados", "/api/customers?criterio=ana"):
        esperar(f"invitado sin acceso a {ruta.split('?')[0]} -> 403", c.get(ruta, headers=invitado).status_code, 403)
    esperar("invitado no puede dar de alta empleados -> 403", c.post("/api/users/employees", headers=invitado, json={"full_name": "X Y Z", "email": "x@example.com", "password": CLAVE, "role": "TECNICO", "branch": "A"}).status_code, 403)

    # ---------- administración de roles ----------
    recep = empleado("Rita Recepcion", "rita@example.com", "RECEPCIONISTA", "Servicio Automotriz del Centro")
    tecnico = empleado("Tomas Tecnico", "tomas@example.com", "TECNICO", "Servicio Automotriz del Centro")
    nuevo = {"code": "SUPERVISOR", "name": "Supervisor de Taller", "description": "Coordina al personal"}
    r = c.post("/api/roles", headers=admin, json=nuevo); rol = r.json(); esperar("crear rol", (r.status_code, rol["bin_status"]), (201, 1))
    esperar("clave repetida -> 409", c.post("/api/roles", headers=admin, json={**nuevo, "name": "Otro nombre"}).status_code, 409)
    esperar("nombre repetido (otra grafía) -> 409", c.post("/api/roles", headers=admin, json={**nuevo, "code": "OTRO", "name": "supervisor DE taller"}).status_code, 409)
    esperar("clave reservada INVITADO -> 422", c.post("/api/roles", headers=admin, json={"code": "INVITADO", "name": "Invitado falso"}).status_code, 422)
    esperar("recepcionista no puede crear roles -> 403", c.post("/api/roles", headers=recep, json={"code": "X1X", "name": "Intruso"}).status_code, 403)
    esperar("recepcionista no puede listar roles -> 403", c.get("/api/roles", headers=recep).status_code, 403)
    r = c.patch(f"/api/roles/{rol['id']}", headers=admin, json={"name": "Jefe de Taller", "description": "Dirige el taller"}); esperar("actualizar rol (la clave no cambia)", (r.status_code, r.json()["name"], r.json()["code"]), (200, "Jefe de Taller", "SUPERVISOR"))
    otro = c.post("/api/roles", headers=admin, json={"code": "AUXILIAR", "name": "Auxiliar"}).json()
    esperar("actualizar con un nombre ya usado -> 409", c.patch(f"/api/roles/{otro['id']}", headers=admin, json={"name": "jefe de taller"}).status_code, 409)
    esperar("actualizar un rol inexistente -> 404", c.patch("/api/roles/9999", headers=admin, json={"name": "Nadie"}).status_code, 404)
    r = c.delete(f"/api/roles/{rol['id']}", headers=admin); esperar("eliminar = borrado lógico (bin_status 2)", (r.status_code, r.json()["bin_status"]), (200, 2))
    with Session(engine) as db: esperar("la fila sigue en la base", (db.get(RoleDefinition, rol["id"]) is not None, db.get(RoleDefinition, rol["id"]).bin_status), (True, 2))
    esperar("el listado normal oculta eliminados", [x["code"] for x in c.get("/api/roles", headers=admin).json() if not x["es_sistema"]], ["AUXILIAR"])
    esperar("el listado puede incluir eliminados", sorted(x["code"] for x in c.get("/api/roles?incluir_eliminados=true", headers=admin).json() if not x["es_sistema"]), ["AUXILIAR", "SUPERVISOR"])
    esperar("no se edita un rol eliminado -> 409", c.patch(f"/api/roles/{rol['id']}", headers=admin, json={"name": "Nuevo nombre"}).status_code, 409)
    r = c.post("/api/roles", headers=admin, json=nuevo); esperar("crear con la clave de un rol eliminado -> 409 que sugiere restaurar", (r.status_code, "eliminado" in r.json()["detail"]), (409, True))
    c.post("/api/roles", headers=admin, json={"code": "JEFE_NUEVO", "name": "Jefe de Taller"})
    esperar("restaurar con nombre ya usado por otro activo -> 409", c.post(f"/api/roles/{rol['id']}/restaurar", headers=admin).status_code, 409)
    c.patch(f"/api/roles/{otro['id']}", headers=admin, json={"name": "Auxiliar general"})
    jefe_nuevo = next(x for x in c.get("/api/roles", headers=admin).json() if x["code"] == "JEFE_NUEVO")
    c.delete(f"/api/roles/{jefe_nuevo['id']}", headers=admin)
    r = c.post(f"/api/roles/{rol['id']}/restaurar", headers=admin); esperar("restaurar un rol", (r.status_code, r.json()["bin_status"]), (200, 1))
    with Session(engine) as db: esperar("ningún rol se borró físicamente (7 de fábrica + 3 personalizados)", db.scalar(select(func.count()).select_from(RoleDefinition)), 10)


    # ---------- roles de fábrica en la base y asignación a empleados ----------
    todos = c.get("/api/roles", headers=admin).json()
    esperar("los 7 roles de fábrica están en la administración y van primero", ([x["code"] for x in todos[:7]], all(x["es_sistema"] for x in todos[:7]), any(x["es_sistema"] for x in todos[7:])),
            (["ADMINISTRADOR", "ASESOR_SERVICIO", "CLIENTE", "INVITADO", "RECEPCIONISTA", "SISTEMA", "TECNICO"], True, False))
    conteo = {x["code"]: x["empleados"] for x in todos}
    esperar("cada rol informa cuántos usuarios lo tienen", (conteo["ADMINISTRADOR"], conteo["INVITADO"], conteo["RECEPCIONISTA"], conteo["TECNICO"], conteo["CLIENTE"]), (1, 2, 1, 1, 0))
    sistema = {x["code"]: x for x in todos if x["es_sistema"]}
    tec = sistema["TECNICO"]
    esperar("un rol de fábrica no se edita -> 409", c.patch(f"/api/roles/{tec['id']}", headers=admin, json={"name": "Otro nombre"}).status_code, 409)
    esperar("un rol de fábrica no se elimina -> 409", c.delete(f"/api/roles/{tec['id']}", headers=admin).status_code, 409)
    esperar("un rol de fábrica no se restaura -> 409", c.post(f"/api/roles/{tec['id']}/restaurar", headers=admin).status_code, 409)
    esperar("un rol personalizado no puede llamarse como uno de fábrica -> 409", c.post("/api/roles", headers=admin, json={"code": "TECNICO_B", "name": "Técnico"}).status_code, 409)
    asignables = c.get("/api/roles/asignables", headers=admin).json()
    esperar("asignables = 3 roles de empleado de fábrica + personalizados activos", [x["code"] for x in asignables], ["ASESOR_SERVICIO", "RECEPCIONISTA", "TECNICO", "AUXILIAR", "SUPERVISOR"])
    esperar("los roles asignables son sólo para el administrador -> 403", c.get("/api/roles/asignables", headers=recep).status_code, 403)

    def alta_empleado(rol, correo, sucursal="Servicio Automotriz del Centro"):
        return c.post("/api/users/employees", headers=admin, json={"full_name": "Pedro Prueba", "email": correo, "password": CLAVE, "role": rol, "branch": sucursal})
    r = alta_empleado("SUPERVISOR", "super@example.com"); esperar("alta de empleado con un rol personalizado", (r.status_code, r.json()["role"], r.json()["role_name"]), (201, "PERSONALIZADO", "Jefe de Taller"))
    r = alta_empleado("TECNICO", "tec2@example.com"); esperar("alta de empleado con un rol de fábrica", (r.status_code, r.json()["role"], r.json()["role_name"]), (201, "TECNICO", None))
    esperar("rol ADMINISTRADOR no se asigna a empleados -> 422", alta_empleado("ADMINISTRADOR", "a1@example.com").status_code, 422)
    esperar("rol CLIENTE no se asigna a empleados -> 422", alta_empleado("CLIENTE", "a2@example.com").status_code, 422)
    esperar("rol PERSONALIZADO (marcador interno) no se asigna -> 422", alta_empleado("PERSONALIZADO", "a3@example.com").status_code, 422)
    esperar("rol personalizado eliminado no se asigna -> 422", alta_empleado("JEFE_NUEVO", "a4@example.com").status_code, 422)
    esperar("rol inexistente -> 422", alta_empleado("NO_EXISTE", "a5@example.com").status_code, 422)
    esperar("código en minúsculas -> 422", alta_empleado("supervisor", "a6@example.com").status_code, 422)
    supervisor = login("super@example.com")
    r = c.get("/api/auth/me", headers=supervisor); esperar("la sesión del empleado trae el nombre de su rol", (r.json()["role"], r.json()["role_name"], r.json()["branch"]), ("PERSONALIZADO", "Jefe de Taller", "Servicio Automotriz del Centro"))
    for ruta in ("/api/roles", "/api/talleres", "/api/customers?criterio=ana", "/api/customers/alta/acceso", "/api/catalogos/estados"):
        esperar(f"rol personalizado sin permisos propios: {ruta.split('?')[0]} -> 403", c.get(ruta, headers=supervisor).status_code, 403)
    esperar("el conteo del rol personalizado sube a 1", next(x["empleados"] for x in c.get("/api/roles", headers=admin).json() if x["code"] == "SUPERVISOR"), 1)
    c.delete(f"/api/roles/{rol['id']}", headers=admin)
    esperar("eliminar un rol en uso: el empleado conserva su rol", c.get("/api/auth/me", headers=supervisor).json()["role_name"], "Jefe de Taller")
    esperar("un rol eliminado deja de ser asignable", "SUPERVISOR" in [x["code"] for x in c.get("/api/roles/asignables", headers=admin).json()], False)
    c.post(f"/api/roles/{rol['id']}/restaurar", headers=admin)

    # ---------- catálogo de códigos postales ----------
    r = c.get("/api/catalogos/codigo-postal/06000", headers=admin); esperar("CP prellena estado, municipio y colonias", (r.status_code, r.json()), (200, {"codigo_postal": "06000", "estado": "Ciudad de México", "municipio": "Cuauhtémoc", "colonias": ["Centro (Área 1)", "Centro (Área 2)"]}))
    esperar("CP inexistente -> 404", c.get("/api/catalogos/codigo-postal/99999", headers=admin).status_code, 404)
    esperar("CP mal formado -> 422", c.get("/api/catalogos/codigo-postal/abc", headers=admin).status_code, 422)
    esperar("estados", c.get("/api/catalogos/estados", headers=admin).json(), ["Ciudad de México", "Jalisco"])
    esperar("municipios de un estado", c.get("/api/catalogos/municipios", headers=admin, params={"estado": "Jalisco"}).json(), ["Guadalajara", "Zapopan"])
    esperar("colonias traen su CP (camino inverso)", c.get("/api/catalogos/colonias", headers=admin, params={"estado": "Ciudad de México", "municipio": "Cuauhtémoc"}).json(),
            [{"colonia": "Centro (Área 1)", "codigo_postal": "06000"}, {"colonia": "Centro (Área 2)", "codigo_postal": "06000"}, {"colonia": "Guerrero", "codigo_postal": "06300"}])
    esperar("catálogo cerrado al técnico -> 403", c.get("/api/catalogos/estados", headers=tecnico).status_code, 403)

    # ---------- alta de taller ----------
    base = {"nombre": "Servicio Automotriz del Centro", "rfc": "abc010203ab1", "email_contacto": "contacto@taller.com", "calle": "Av. Reforma 125, local 2",
            "colonia": "Centro (Área 1)", "codigo_postal": "06000", "estado": "Ciudad de México", "municipio": "Cuauhtémoc"}
    def alta(headers, campos=None, foto=("f.png", PNG, "image/png")):
        return c.post("/api/talleres", headers=headers, data={**base, **(campos or {})}, files={"foto": foto} if foto else None)
    r = alta(admin); taller = r.json()
    esperar("administrador da de alta un taller", (r.status_code, taller["rfc"], taller["tiene_foto"], len(archivos())), (201, "ABC010203AB1", True, 1))
    with Session(engine) as db: esperar("alta de taller queda en la auditoría", [a.accion for a in db.scalars(select(AuditoriaModel))], ["ALTA_TALLER"])
    norte = {"nombre": "Taller Norte", "rfc": "XYZ990101AA9", "colonia": "Guerrero", "codigo_postal": "06300"}
    esperar("el recepcionista ya no da de alta talleres -> 403", alta(recep, norte, ("f.jpg", JPG, "image/jpeg")).status_code, 403)
    esperar("... ni usa el catálogo de códigos postales -> 403", c.get("/api/catalogos/estados", headers=recep).status_code, 403)
    r = alta(admin, norte, ("f.jpg", JPG, "image/jpeg")); esperar("el administrador da de alta otro taller (JPG)", r.status_code, 201)
    esperar("el recepcionista sigue viendo la lista de talleres", c.get("/api/talleres", headers=recep).status_code, 200)
    esperar("el técnico no puede -> 403", alta(tecnico, {"nombre": "Otro", "rfc": "QWE010101AA1"}).status_code, 403)
    esperar("el invitado no puede -> 403", alta(invitado, {"nombre": "Otro", "rfc": "QWE010101AA1"}).status_code, 403)
    esperar("WebP aceptado", alta(admin, {"nombre": "Taller Webp", "rfc": "WEB010101AA1", "estado": "Jalisco", "municipio": "Guadalajara", "colonia": "Centro", "codigo_postal": "44100"}, ("f.webp", WEBP, "image/webp")).status_code, 201)
    esperar("RFC de persona física (13) aceptado", alta(admin, {"nombre": "Taller Fisico", "rfc": "ABCD010203AB1", "estado": "Jalisco", "municipio": "Zapopan", "colonia": "Centro", "codigo_postal": "45000"}).status_code, 201)
    esperar("cuatro altas = cuatro fotos", len(archivos()), 4)

    for rfc in ("ABC0102", "ABC013203AB1", "ABC010230AB1", "ABC010431AB1", "ABC010200AB1", "1BC010203AB1", "ABC010203AB!", "ABCDE010203AB1", "", "ABC 010203AB1"):
        esperar(f"RFC inválido «{rfc}» -> 422", alta(admin, {"nombre": f"Taller RFC {len(rfc)}", "rfc": rfc}).status_code, 422)
    esperar("nombre repetido (otra grafía) -> 409", alta(admin, {"nombre": "servicio automotriz DEL centro", "rfc": "NEW010101AA1"}).status_code, 409)
    esperar("RFC repetido -> 409", alta(admin, {"nombre": "Taller Distinto", "rfc": "ABC010203AB1"}).status_code, 409)
    for etiqueta, campos in [("colonia que no es del CP", {"nombre": "T1", "rfc": "TTT010101AA1", "colonia": "Guerrero"}), ("municipio que no es del CP", {"nombre": "T2", "rfc": "TTT010101AA2", "municipio": "Zapopan"}),
                             ("estado que no es del CP", {"nombre": "T3", "rfc": "TTT010101AA3", "estado": "Jalisco"}), ("CP inexistente", {"nombre": "T4", "rfc": "TTT010101AA4", "codigo_postal": "99999"}),
                             ("CP de 4 dígitos", {"nombre": "T5", "rfc": "TTT010101AA5", "codigo_postal": "0600"}), ("correo inválido", {"nombre": "T6", "rfc": "TTT010101AA6", "email_contacto": "sin-arroba"}),
                             ("nombre muy corto", {"nombre": "ab", "rfc": "TTT010101AA7"}), ("calle vacía", {"nombre": "T8", "rfc": "TTT010101AA8", "calle": "  "})]:
        esperar(f"{etiqueta} -> 422", alta(admin, campos).status_code, 422)
    nuevo_t = {"nombre": "Taller Foto", "rfc": "FOT010101AA1"}
    esperar("sin foto -> 422", alta(admin, nuevo_t, foto=None).status_code, 422)
    esperar("foto vacía -> 422", alta(admin, nuevo_t, ("f.png", b"", "image/png")).status_code, 422)
    esperar("texto con extensión .png -> 422", alta(admin, nuevo_t, ("f.png", b"esto no es una imagen", "image/png")).status_code, 422)
    esperar("GIF -> 422", alta(admin, nuevo_t, ("f.gif", GIF, "image/gif")).status_code, 422)
    r = alta(admin, nuevo_t, ("f.png", PNG + b"0" * (15 * 1024 * 1024), "image/png")); esperar("foto de más de 15 MB -> 413", r.status_code, 413)
    esperar("las altas rechazadas no dejan fotos huérfanas", len(archivos()), 4)

    r = c.get("/api/talleres", headers=recep); esperar("listado de talleres", (r.status_code, [t["nombre"] for t in r.json()]), (200, ["Servicio Automotriz del Centro", "Taller Fisico", "Taller Norte", "Taller Webp"]))
    r = c.get(f"/api/talleres/{taller['id']}/foto", headers=recep); esperar("la foto se sirve con su tipo y sin cambios", (r.status_code, r.headers["content-type"], r.content), (200, "image/png", PNG))
    esperar("la foto exige sesión con permiso", (c.get(f"/api/talleres/{taller['id']}/foto").status_code in (401, 403), c.get(f"/api/talleres/{taller['id']}/foto", headers=invitado).status_code), (True, 403))

    # ---------- integración con Clientes ----------
    r = c.get("/api/customers/alta/acceso", headers=recep); esperar("recepcionista de un taller registrado abre el alta de clientes", (r.status_code, r.json().get("taller")), (200, "Servicio Automotriz del Centro"))
    sin_taller = empleado("Sara Sinregistro", "sara@example.com", "RECEPCIONISTA", "Sucursal Fantasma")
    r = c.get("/api/customers/alta/acceso", headers=sin_taller); esperar("sucursal no registrada -> 403 que explica qué hacer", (r.status_code, "no está registrada" in r.json()["detail"]), (403, True))
    with Session(engine) as db:
        t = db.get(TallerModel, taller["id"]); t.bin_status = 2; db.commit()
    esperar("taller eliminado lógicamente deja sin acceso a Clientes -> 403", c.get("/api/customers/alta/acceso", headers=recep).status_code, 403)
    esperar("un taller eliminado no aparece en el listado", "Servicio Automotriz del Centro" in [t["nombre"] for t in c.get("/api/talleres", headers=recep).json()], False)
    r = alta(admin); esperar("no se vuelve a crear un taller eliminado: se sugiere restaurar", (r.status_code, "eliminado" in r.json()["detail"]), (409, True))

print("\nRESULTADO:", "TODO OK" if not fallos else f"{len(fallos)} fallos: {fallos}")
sys.exit(1 if fallos else 0)
