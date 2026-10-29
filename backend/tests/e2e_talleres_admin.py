"""Prueba de punta a punta de la administración de talleres: listado con búsqueda y paginación, edición de datos y foto (con las reglas del
alta), renombrado que arrastra la sucursal de los empleados, borrado lógico que bloquea la operación del taller, restauración y permisos.
Usa SQLite temporal: no toca SQL Server ni backend/uploads.

Requisito de desarrollo: pip install -r requirements-dev.txt
Ejecución, desde backend/:   python tests/e2e_talleres_admin.py
"""
import os, sys, tempfile

_BASE = tempfile.mkdtemp(prefix="taller_adm_")
os.environ.update(DATABASE_URL=os.environ.get("E2E_DATABASE_URL") or "sqlite:///" + os.path.join(_BASE, "prueba.db").replace("\\", "/"), UPLOADS_DIR=os.path.join(_BASE, "subidas"),
                  JWT_SECRET="x" * 40, BOOTSTRAP_ADMIN_EMAIL="admin@example.com", BOOTSTRAP_ADMIN_PASSWORD="AdminPrueba12345!")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.main import app
from app.database import engine
from app.catalogos import CodigoPostalModel
from app.customers.modelos import AuditoriaModel, TallerModel
from app.models import User

fallos = []
def esperar(nombre, real, esperado):
    ok = real == esperado
    print(("OK   " if ok else "FALLA"), nombre, "" if ok else f"-> {real!r} (esperado {esperado!r})")
    if not ok: fallos.append(nombre)

JPG = b"\xff\xd8\xff\xe0" + b"0" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"1" * 200
GIF = b"GIF89a" + b"0" * 100
CLAVE = "ClaveSegura12345!"
subidas = Path(os.environ["UPLOADS_DIR"]) / "talleres"
def archivos(): return sorted(p.name for p in subidas.glob("*")) if subidas.exists() else []

with TestClient(app) as c:
    def login(correo, clave=CLAVE):
        r = c.post("/api/auth/login", json={"email": correo, "password": clave})
        return {"Authorization": "Bearer " + r.json()["access_token"]} if r.status_code == 200 else None
    admin = login("admin@example.com", "AdminPrueba12345!")
    def empleado(nombre, correo, rol, sucursal):
        c.post("/api/users/employees", headers=admin, json={"full_name": nombre, "email": correo, "password": CLAVE, "role": rol, "branch": sucursal})
        return login(correo)
    with Session(engine) as db:
        db.add_all([CodigoPostalModel(codigo_postal=cp, colonia=col, tipo_asentamiento="Colonia", municipio=mun, estado=est) for cp, col, mun, est in [
            ("06000", "Centro (Área 1)", "Cuauhtémoc", "Ciudad de México"), ("06300", "Guerrero", "Cuauhtémoc", "Ciudad de México"),
            ("44100", "Centro", "Guadalajara", "Jalisco"), ("45000", "Centro", "Zapopan", "Jalisco")]])
        db.commit()
    BASE = {"nombre": "Taller Centro", "rfc": "ABC010203AB1", "email_contacto": "centro@taller.com", "calle": "Av. Reforma 125", "colonia": "Centro (Área 1)",
            "codigo_postal": "06000", "estado": "Ciudad de México", "municipio": "Cuauhtémoc"}
    def alta(datos, foto=("f.jpg", JPG, "image/jpeg")):
        return c.post("/api/talleres", headers=admin, data=datos, files={"foto": foto})
    def editar(taller_id, cambios=None, foto=None, headers=None):
        archivos_ = {"foto": foto} if foto else None
        return c.put(f"/api/talleres/{taller_id}", headers=headers or admin, data={**BASE, **(cambios or {})}, files=archivos_)

    t1 = alta(BASE).json()
    t2 = alta({**BASE, "nombre": "Taller Norte", "rfc": "XYZ990101AA9", "colonia": "Guerrero", "codigo_postal": "06300"}).json()
    t3 = alta({**BASE, "nombre": "Taller Tapatío", "rfc": "TAP880808BB2", "colonia": "Centro", "codigo_postal": "44100", "estado": "Jalisco", "municipio": "Guadalajara"}).json()
    rita = empleado("Rita Recepcion", "rita@example.com", "RECEPCIONISTA", "Taller Centro")
    tomas = empleado("Tomas Tecnico", "tomas@example.com", "TECNICO", "taller centro")
    sara = empleado("Sara Asesora", "sara@example.com", "ASESOR_SERVICIO", "Taller Norte")
    esperar("fotos guardadas del alta", len(archivos()), 3)
    cliente = c.post("/api/customers", headers=rita, json={"nombre_completo": "Ana López", "telefono": "5511223344", "correo": "ana@correo.com", "confirmar": True})
    esperar("rita registra un cliente en Taller Centro", cliente.status_code, 201)

    # ---------- permisos ----------
    for etiqueta, cab in (("recepcionista", rita), ("técnico", tomas), ("asesor", sara)):
        esperar(f"{etiqueta} no administra talleres -> 403", (c.get("/api/talleres/administracion", headers=cab).status_code, c.put(f"/api/talleres/{t1['id']}", headers=cab, data=BASE).status_code,
                                                            c.delete(f"/api/talleres/{t1['id']}", headers=cab).status_code), (403, 403, 403))
    esperar("sin sesión no se accede", c.get("/api/talleres/administracion").status_code in (401, 403), True)
    r = c.get("/api/auth/me", headers=admin)
    esperar("el administrador tiene el permiso", "talleres.administrar" in [p["codigo"] for p in r.json()["permisos"]], True)
    r = c.get("/api/permisos", headers=admin)
    esperar("el permiso no es delegable", [p["delegable"] for p in r.json() if p["codigo"] == "talleres.administrar"], [False])
    c.post("/api/roles", headers=admin, json={"code": "GESTOR", "name": "Gestor"})
    rol_id = next(x["id"] for x in c.get("/api/roles", headers=admin).json() if x["code"] == "GESTOR")
    esperar("no se delega «administrar talleres» -> 422", c.put(f"/api/roles/{rol_id}/permisos", headers=admin, json={"permisos": ["talleres.administrar"]}).status_code, 422)

    # ---------- listado ----------
    r = c.get("/api/talleres/administracion", headers=admin); pagina = r.json(); por_nombre = {t["nombre"]: t for t in pagina["items"]}
    esperar("listado de los 3 talleres, ordenado por nombre", (r.status_code, pagina["total"], [t["nombre"] for t in pagina["items"]]), (200, 3, ["Taller Centro", "Taller Norte", "Taller Tapatío"]))
    esperar("cuenta empleados (sin distinguir mayúsculas) y clientes", (por_nombre["Taller Centro"]["empleados"], por_nombre["Taller Centro"]["clientes"], por_nombre["Taller Norte"]["empleados"], por_nombre["Taller Tapatío"]["empleados"]), (2, 1, 1, 0))
    esperar("indica si tiene foto y su estatus", (por_nombre["Taller Centro"]["tiene_foto"], por_nombre["Taller Centro"]["bin_status"]), (True, 1))
    esperar("búsqueda por nombre", [t["nombre"] for t in c.get("/api/talleres/administracion?buscar=norte", headers=admin).json()["items"]], ["Taller Norte"])
    esperar("búsqueda por RFC (minúsculas)", [t["nombre"] for t in c.get("/api/talleres/administracion?buscar=tap880", headers=admin).json()["items"]], ["Taller Tapatío"])
    esperar("búsqueda por municipio", [t["nombre"] for t in c.get("/api/talleres/administracion?buscar=guadalajara", headers=admin).json()["items"]], ["Taller Tapatío"])
    esperar("búsqueda sin coincidencias", c.get("/api/talleres/administracion?buscar=zzz", headers=admin).json()["total"], 0)
    esperar("un % no actúa como comodín", c.get("/api/talleres/administracion?buscar=%25", headers=admin).json()["total"], 0)
    r = c.get("/api/talleres/administracion?tamano=2&pagina=2", headers=admin).json()
    esperar("paginación", (r["total"], [t["nombre"] for t in r["items"]]), (3, ["Taller Tapatío"]))
    esperar("tamaño de página fuera de rango -> 422", c.get("/api/talleres/administracion?tamano=500", headers=admin).status_code, 422)
    esperar("detalle de un taller", (c.get(f"/api/talleres/{t2['id']}", headers=admin).json()["rfc"], c.get("/api/talleres/9999", headers=admin).status_code), ("XYZ990101AA9", 404))

    # ---------- edición ----------
    antes = archivos()
    r = editar(t1["id"], {"email_contacto": "nuevo@taller.com", "calle": "Calle Nueva 9"})
    esperar("editar sin cambiar nombre ni RFC (no choca consigo mismo)", (r.status_code, r.json().get("email_contacto"), r.json().get("calle")), (200, "nuevo@taller.com", "Calle Nueva 9"))
    esperar("sin foto nueva se conserva la actual", (archivos(), r.json()["tiene_foto"]), (antes, True))
    r = editar(t1["id"], {"rfc": "abc010203ab1", "nombre": "  Taller   Centro  "})
    esperar("el RFC se guarda en mayúsculas y el nombre sin espacios sobrantes", (r.status_code, r.json()["rfc"], r.json()["nombre"]), (200, "ABC010203AB1", "Taller Centro"))
    r = editar(t1["id"], {"codigo_postal": "44100", "estado": "Jalisco", "municipio": "Guadalajara", "colonia": "Centro"})
    esperar("cambiar el domicilio con el catálogo", (r.status_code, r.json()["estado"], r.json()["municipio"]), (200, "Jalisco", "Guadalajara"))
    esperar("domicilio que no corresponde al código postal -> 422", editar(t1["id"], {"colonia": "Guerrero"}).status_code, 422)
    esperar("código postal fuera del catálogo -> 422", editar(t1["id"], {"codigo_postal": "99999"}).status_code, 422)
    esperar("RFC inválido -> 422", editar(t1["id"], {"rfc": "MALO"}).status_code, 422)
    esperar("RFC con fecha inexistente -> 422", editar(t1["id"], {"rfc": "ABC300230AB1"}).status_code, 422)
    esperar("correo inválido -> 422", editar(t1["id"], {"email_contacto": "no-es-correo"}).status_code, 422)
    esperar("nombre vacío -> 422", editar(t1["id"], {"nombre": ""}).status_code, 422)
    esperar("nombre de otro taller -> 409", editar(t1["id"], {"nombre": "taller norte"}).status_code, 409)
    esperar("RFC de otro taller -> 409", editar(t1["id"], {"rfc": "XYZ990101AA9"}).status_code, 409)
    esperar("taller inexistente -> 404", editar(9999).status_code, 404)

    # ---------- foto ----------
    antes = archivos()
    r = editar(t1["id"], foto=("nueva.png", PNG, "image/png"))
    despues = archivos()
    esperar("foto nueva: se guarda la nueva y se retira la anterior", (r.status_code, len(despues), set(despues) != set(antes)), (200, 3, True))
    foto = c.get(f"/api/talleres/{t1['id']}/foto", headers=admin)
    esperar("la foto servida es la nueva (PNG)", (foto.status_code, foto.headers["content-type"], foto.content[:4]), (200, "image/png", b"\x89PNG"))
    esperar("foto en formato no permitido (GIF) -> 422 y nada cambia", (editar(t1["id"], foto=("a.gif", GIF, "image/gif")).status_code, archivos()), (422, despues))
    esperar("foto disfrazada (.jpg con contenido GIF) -> 422", editar(t1["id"], foto=("a.jpg", GIF, "image/jpeg")).status_code, 422)
    esperar("foto de más de 15 MB -> 413 y nada cambia", (editar(t1["id"], foto=("g.jpg", JPG + b"0" * (15 * 1024 * 1024), "image/jpeg")).status_code, archivos()), (413, despues))
    esperar("si falla la validación del texto no queda foto huérfana", (editar(t1["id"], {"rfc": "MALO"}, foto=("x.jpg", JPG, "image/jpeg")).status_code, archivos()), (422, despues))

    # ---------- renombrar arrastra la sucursal de los empleados ----------
    r = editar(t1["id"], {"nombre": "Taller Matriz", "codigo_postal": "06000", "estado": "Ciudad de México", "municipio": "Cuauhtémoc", "colonia": "Centro (Área 1)"})
    esperar("renombrar el taller", (r.status_code, r.json()["nombre"], r.json()["empleados"], r.json()["clientes"]), (200, "Taller Matriz", 2, 1))
    with Session(engine) as db:
        esperar("las sucursales de los empleados se renombran con el taller", sorted(db.scalars(select(User.branch).where(User.email.in_(["rita@example.com", "tomas@example.com"])))), ["Taller Matriz", "Taller Matriz"])
        esperar("las de otros talleres no se tocan", db.scalar(select(User.branch).where(User.email == "sara@example.com")), "Taller Norte")
    esperar("rita sigue operando clientes tras el cambio de nombre", c.get("/api/customers?criterio=ana", headers=rita).status_code, 200)
    esperar("la auditoría registra los cambios", [a.accion for a in Session(engine).scalars(select(AuditoriaModel).where(AuditoriaModel.accion == "EDITAR_TALLER", AuditoriaModel.taller_id == t1["id"]))].count("EDITAR_TALLER") >= 3, True)

    # ---------- eliminar (borrado lógico) ----------
    esperar("sara opera clientes antes de eliminar su taller", c.get("/api/customers?criterio=ana", headers=sara).status_code, 200)
    r = c.delete(f"/api/talleres/{t2['id']}", headers=admin)
    esperar("eliminar taller", (r.status_code, r.json()["bin_status"]), (200, 2))
    esperar("eliminar dos veces -> 409", c.delete(f"/api/talleres/{t2['id']}", headers=admin).status_code, 409)
    with Session(engine) as db:
        fila = db.get(TallerModel, t2["id"])
        esperar("el taller se conserva en la base, desactivado", (fila is not None, fila.bin_status, fila.activo, fila.foto is not None), (True, 2, False, True))
    esperar("no aparece en el listado por omisión", [t["nombre"] for t in c.get("/api/talleres/administracion", headers=admin).json()["items"]], ["Taller Matriz", "Taller Tapatío"])
    r = c.get("/api/talleres/administracion?incluir_eliminados=true", headers=admin).json()
    esperar("aparece al mostrar eliminados", (r["total"], [t["nombre"] for t in r["items"] if t["bin_status"] == 2]), (3, ["Taller Norte"]))
    esperar("puede mostrar sólo los suspendidos", [t["nombre"] for t in c.get("/api/talleres/administracion?solo_eliminados=true", headers=admin).json()["items"]], ["Taller Norte"])
    esperar("tampoco en la lista de talleres para consulta", [t["nombre"] for t in c.get("/api/talleres", headers=admin).json()], ["Taller Matriz", "Taller Tapatío"])
    esperar("sus empleados dejan de operar clientes", c.get("/api/customers?criterio=ana", headers=sara).status_code in (403, 409, 422), True)
    esperar("un taller eliminado no se edita -> 409", editar(t2["id"], {"calle": "Otra calle 1"}).status_code, 409)
    esperar("no se puede dar de alta otro con su nombre ni su RFC (se pide restaurar)", (alta({**BASE, "nombre": "Taller Norte", "rfc": "ZZZ010101ZZ1"}).status_code, "restáurelo" in alta({**BASE, "nombre": "Taller Norte", "rfc": "ZZZ010101ZZ1"}).json()["detail"]), (409, True))
    esperar("eliminar un taller inexistente -> 404", c.delete("/api/talleres/9999", headers=admin).status_code, 404)

    # ---------- restaurar ----------
    esperar("restaurar un taller activo -> 409", c.post(f"/api/talleres/{t3['id']}/restaurar", headers=admin).status_code, 409)
    r = c.post(f"/api/talleres/{t2['id']}/restaurar", headers=admin)
    esperar("restaurar", (r.status_code, r.json()["bin_status"]), (200, 1))
    with Session(engine) as db:
        fila = db.get(TallerModel, t2["id"]); esperar("vuelve a estar activo", (fila.bin_status, fila.activo), (1, True))
    esperar("sara vuelve a operar", c.get("/api/customers?criterio=ana", headers=sara).status_code, 200)
    esperar("vuelve al listado", len(c.get("/api/talleres/administracion", headers=admin).json()["items"]), 3)
    esperar("la auditoría registra eliminar y restaurar", sorted(a.accion for a in Session(engine).scalars(select(AuditoriaModel).where(AuditoriaModel.taller_id == t2["id"]))), ["ALTA_TALLER", "ELIMINAR_TALLER", "RESTAURAR_TALLER"])
    esperar("al final las fotos siguen siendo 3 (ninguna huérfana)", len(archivos()), 3)

print("\nFALLARON:" if fallos else "\nTodo correcto", fallos if fallos else "")
sys.exit(1 if fallos else 0)
