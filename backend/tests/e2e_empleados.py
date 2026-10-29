"""Prueba de punta a punta de la administración de empleados: listado con búsqueda, filtros y paginación; edición de nombre, sucursal y rol
(incluida la conversión de una cuenta Invitado en empleado); borrado lógico con bloqueo inmediato de la sesión; y protecciones.
Usa SQLite temporal: no toca SQL Server ni backend/uploads.

Requisito de desarrollo: pip install -r requirements-dev.txt
Ejecución, desde backend/:   python tests/e2e_empleados.py
"""
import os, sys, tempfile

_BASE = tempfile.mkdtemp(prefix="taller_emp_")
os.environ.update(DATABASE_URL=os.environ.get("E2E_DATABASE_URL") or "sqlite:///" + os.path.join(_BASE, "prueba.db").replace("\\", "/"), UPLOADS_DIR=os.path.join(_BASE, "subidas"),
                  JWT_SECRET="x" * 40, BOOTSTRAP_ADMIN_EMAIL="admin@example.com", BOOTSTRAP_ADMIN_PASSWORD="AdminPrueba12345!")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.main import app
from app.database import engine
from app.customers.modelos import TallerModel
from app.models import Role, User

fallos = []
def esperar(nombre, real, esperado):
    ok = real == esperado
    print(("OK   " if ok else "FALLA"), nombre, "" if ok else f"-> {real!r} (esperado {esperado!r})")
    if not ok: fallos.append(nombre)

CLAVE = "ClaveSegura12345!"
with TestClient(app) as c:
    def login(correo, clave=CLAVE):
        r = c.post("/api/auth/login", json={"email": correo, "password": clave})
        return {"Authorization": "Bearer " + r.json()["access_token"]} if r.status_code == 200 else None
    admin = login("admin@example.com", "AdminPrueba12345!")
    with Session(engine) as db:
        db.add(TallerModel(nombre="Centro", activo=True)); db.commit()
    def alta(nombre, correo, rol, sucursal="Centro"):
        return c.post("/api/users/employees", headers=admin, json={"full_name": nombre, "email": correo, "password": CLAVE, "role": rol, "branch": sucursal})
    c.post("/api/roles", headers=admin, json={"code": "GESTOR", "name": "Gestor de clientes"})
    c.post("/api/roles", headers=admin, json={"code": "VIEJO", "name": "Rol que se eliminará"})
    for nombre, correo, rol, suc in [("Rita Recepcion", "rita@example.com", "RECEPCIONISTA", "Centro"), ("Tomas Tecnico", "tomas@example.com", "TECNICO", "Centro"),
                                     ("Sara Asesora", "sara@example.com", "ASESOR_SERVICIO", "Sucursal Fantasma"), ("Gina Gestora", "gina@example.com", "GESTOR", "Centro")]:
        esperar(f"alta {correo}", alta(nombre, correo, rol, suc).status_code, 201)
    for nombre, correo in [("Ivan Invitado", "ivan@example.com"), ("Ines Invitada", "ines@example.com")]:
        c.post("/api/auth/register", json={"full_name": nombre, "email": correo, "password": CLAVE})
    with Session(engine) as db:  # cuentas internas que no se administran desde la pantalla
        db.add(User(full_name="Cuenta Cliente", email="cliente@example.com", password_hash="x", role=Role.CLIENTE, branch=None)); db.commit()
    rita, tomas, sara, gina, ivan = (login(f"{n}@example.com") for n in ("rita", "tomas", "sara", "gina", "ivan"))

    # ---------- acceso ----------
    for etiqueta, cab in (("recepcionista", rita), ("empleado con rol personalizado", gina), ("invitado", ivan)):
        esperar(f"{etiqueta} no administra empleados -> 403", c.get("/api/users", headers=cab).status_code, 403)
    esperar("sin sesión no se accede", c.get("/api/users").status_code in (401, 403), True)

    # ---------- listado ----------
    r = c.get("/api/users", headers=admin); pagina = r.json(); por_correo = {u["email"]: u for u in pagina["items"]}
    esperar("listado completo (admin, 4 empleados, 2 invitados y 1 cuenta interna)", (r.status_code, pagina["total"]), (200, 8))
    esperar("el administrador está protegido y es «usted»", (por_correo["admin@example.com"]["protegido"], por_correo["admin@example.com"]["es_usted"], por_correo["admin@example.com"]["taller_registrado"]), (True, True, None))
    esperar("una cuenta interna está protegida", por_correo["cliente@example.com"]["protegido"], True)
    esperar("un empleado muestra rol, sucursal y si su taller está registrado", (por_correo["rita@example.com"]["role_name"], por_correo["rita@example.com"]["branch"], por_correo["rita@example.com"]["taller_registrado"], por_correo["rita@example.com"]["protegido"]), ("Recepcionista", "Centro", True, False))
    esperar("una sucursal sin taller registrado se marca", por_correo["sara@example.com"]["taller_registrado"], False)
    esperar("un empleado con rol personalizado muestra el nombre y la clave de su rol", (por_correo["gina@example.com"]["role"], por_correo["gina@example.com"]["role_name"], por_correo["gina@example.com"]["role_code"]), ("PERSONALIZADO", "Gestor de clientes", "GESTOR"))
    esperar("una cuenta Invitado se identifica", (por_correo["ivan@example.com"]["role_code"], por_correo["ivan@example.com"]["role_name"], por_correo["ivan@example.com"]["branch"]), ("INVITADO", "Invitado", None))
    esperar("el listado no expone contraseñas", any("password" in k for k in pagina["items"][0]), False)

    # ---------- búsqueda, filtros y paginación ----------
    esperar("buscar por nombre", [u["email"] for u in c.get("/api/users", headers=admin, params={"buscar": "rita"}).json()["items"]], ["rita@example.com"])
    esperar("buscar sin distinguir mayúsculas", c.get("/api/users", headers=admin, params={"buscar": "TOMAS"}).json()["total"], 1)
    esperar("buscar por parte del correo", c.get("/api/users", headers=admin, params={"buscar": "ines@"}).json()["total"], 1)
    esperar("el símbolo % no actúa como comodín", c.get("/api/users", headers=admin, params={"buscar": "%"}).json()["total"], 0)
    esperar("filtrar por rol de fábrica", [u["email"] for u in c.get("/api/users", headers=admin, params={"rol": "INVITADO"}).json()["items"]], ["ines@example.com", "ivan@example.com"])
    esperar("filtrar por rol personalizado", [u["email"] for u in c.get("/api/users", headers=admin, params={"rol": "GESTOR"}).json()["items"]], ["gina@example.com"])
    esperar("un rol desconocido no devuelve nada", c.get("/api/users", headers=admin, params={"rol": "NO_EXISTE"}).json()["total"], 0)
    p1 = c.get("/api/users", headers=admin, params={"tamano": 3, "pagina": 1}).json(); p3 = c.get("/api/users", headers=admin, params={"tamano": 3, "pagina": 3}).json()
    esperar("paginación (8 cuentas de 3 en 3)", (p1["total"], len(p1["items"]), len(p3["items"])), (8, 3, 2))
    esperar("las páginas no repiten cuentas", len({u["id"] for u in p1["items"]} & {u["id"] for u in c.get("/api/users", headers=admin, params={"tamano": 3, "pagina": 2}).json()["items"]}), 0)
    esperar("tamaño de página inválido -> 422", c.get("/api/users", headers=admin, params={"tamano": 100}).status_code, 422)
    ids = {correo: u["id"] for correo, u in por_correo.items()}

    # ---------- edición ----------
    def editar(correo, **datos):
        cuerpo = {"full_name": "Nombre Nuevo", "branch": "Centro", "role": "TECNICO", **datos}
        return c.patch(f"/api/users/{ids[correo]}", headers=admin, json=cuerpo)
    esperar("el recepcionista no edita cuentas -> 403", c.patch(f"/api/users/{ids['tomas@example.com']}", headers=rita, json={"full_name": "Xx Yy", "branch": "A", "role": "TECNICO"}).status_code, 403)
    r = editar("ivan@example.com", full_name="  Ivan   Ahora Tecnico ", role="TECNICO"); u = r.json()
    esperar("asignar un rol a una cuenta Invitado la convierte en empleado", (r.status_code, u["role"], u["role_name"], u["branch"], u["full_name"]), (200, "TECNICO", "Técnico", "Centro", "Ivan Ahora Tecnico"))
    esperar("la sesión del invitado ya trae los permisos del nuevo rol (sin volver a ingresar)", [p["codigo"] for p in c.get("/api/auth/me", headers=ivan).json()["permisos"]], ["ordenes.consultar", "diagnosticos.registrar"])
    esperar("y ya opera con ellos", c.get("/api/work-orders", headers=ivan).status_code, 200)
    r = editar("ines@example.com", role="GESTOR", branch="Centro"); u = r.json()
    esperar("asignar un rol personalizado", (r.status_code, u["role"], u["role_code"], u["role_name"]), (200, "PERSONALIZADO", "GESTOR", "Gestor de clientes"))
    r = editar("ines@example.com", role="RECEPCIONISTA"); esperar("pasar de rol personalizado a uno de fábrica", (r.json()["role"], r.json()["role_code"]), ("RECEPCIONISTA", "RECEPCIONISTA"))
    c.put(f"/api/roles/{next(x['id'] for x in c.get('/api/roles', headers=admin).json() if x['code'] == 'GESTOR')}/permisos", headers=admin, json={"permisos": ["clientes.consultar"]})
    esperar("cambiar a un empleado de rol surte efecto de inmediato: antes consultaba clientes", c.get("/api/customers?criterio=ana", headers=rita).status_code, 200)
    editar("rita@example.com", role="TECNICO", full_name="Rita Recepcion")
    esperar("... y después de cambiarla a Técnico ya no -> 403", c.get("/api/customers?criterio=ana", headers=rita).status_code, 403)
    esperar("... pero sí ve las órdenes", c.get("/api/work-orders", headers=rita).status_code, 200)
    for etiqueta, datos in (("sucursal vacía", {"branch": "   "}), ("nombre muy corto", {"full_name": "ab"}), ("rol ADMINISTRADOR", {"role": "ADMINISTRADOR"}), ("rol CLIENTE", {"role": "CLIENTE"}),
                            ("rol inexistente", {"role": "NO_EXISTE"}), ("rol en minúsculas", {"role": "tecnico"})):
        esperar(f"edición inválida ({etiqueta}) -> 422", editar("tomas@example.com", **datos).status_code, 422)
    c.delete(f"/api/roles/{next(x['id'] for x in c.get('/api/roles', headers=admin).json() if x['code'] == 'VIEJO')}", headers=admin)
    esperar("un rol personalizado eliminado no se asigna -> 422", editar("tomas@example.com", role="VIEJO").status_code, 422)
    esperar("no se puede editar la propia cuenta -> 409", editar("admin@example.com").status_code, 409)
    esperar("no se edita una cuenta protegida -> 409", editar("cliente@example.com").status_code, 409)
    esperar("cuenta inexistente -> 404", c.patch("/api/users/99999", headers=admin, json={"full_name": "Xx Yy", "branch": "A", "role": "TECNICO"}).status_code, 404)

    # ---------- borrado lógico ----------
    esperar("la cuenta puede ingresar antes de eliminarla", c.get("/api/work-orders", headers=tomas).status_code, 200)
    r = c.delete(f"/api/users/{ids['tomas@example.com']}", headers=admin); u = r.json()
    esperar("eliminar = borrado lógico y desactivación", (r.status_code, u["bin_status"], u["is_active"]), (200, 2, False))
    esperar("la sesión abierta deja de valer en la siguiente petición -> 401", c.get("/api/work-orders", headers=tomas).status_code, 401)
    esperar("la cuenta eliminada no puede iniciar sesión", login("tomas@example.com"), None)
    with Session(engine) as db: esperar("la cuenta sigue en la base", db.scalar(select(User.bin_status).where(User.email == "tomas@example.com")), 2)
    esperar("el listado normal oculta las eliminadas", "tomas@example.com" in [x["email"] for x in c.get("/api/users", headers=admin, params={"tamano": 50}).json()["items"]], False)
    ver = {x["email"]: x for x in c.get("/api/users", headers=admin, params={"tamano": 50, "incluir_eliminados": True}).json()["items"]}
    solo = c.get("/api/users", headers=admin, params={"tamano": 50, "solo_eliminados": True}).json()
    esperar("el listado puede mostrar sólo las suspendidas", (solo["total"], [x["email"] for x in solo["items"]]), (1, ["tomas@example.com"]))
    esperar("el listado puede incluir las eliminadas", (ver["tomas@example.com"]["bin_status"], ver["tomas@example.com"]["is_active"]), (2, False))
    esperar("las cuentas eliminadas no cuentan en el total de su rol", next(x["empleados"] for x in c.get("/api/roles", headers=admin).json() if x["code"] == "TECNICO"), 2)
    esperar("no se edita una cuenta eliminada -> 409", editar("tomas@example.com").status_code, 409)
    esperar("no se elimina la propia cuenta -> 409", c.delete(f"/api/users/{ids['admin@example.com']}", headers=admin).status_code, 409)
    esperar("no se elimina una cuenta protegida -> 409", c.delete(f"/api/users/{ids['cliente@example.com']}", headers=admin).status_code, 409)
    esperar("sólo el administrador elimina -> 403", c.delete(f"/api/users/{ids['sara@example.com']}", headers=rita).status_code, 403)
    r = c.post(f"/api/users/{ids['tomas@example.com']}/restaurar", headers=admin); esperar("restaurar la cuenta", (r.status_code, r.json()["bin_status"], r.json()["is_active"]), (200, 1, True))
    esperar("la cuenta restaurada vuelve a ingresar con su contraseña", login("tomas@example.com") is not None, True)
    esperar("restaurar una cuenta protegida -> 409", c.post(f"/api/users/{ids['cliente@example.com']}/restaurar", headers=admin).status_code, 409)

print("\nRESULTADO:", "TODO OK" if not fallos else f"{len(fallos)} fallos: {fallos}")
sys.exit(1 if fallos else 0)
