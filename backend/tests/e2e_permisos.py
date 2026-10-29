"""Prueba de punta a punta de los permisos de los roles: catálogo, permisos de fábrica, asignación a roles personalizados y aplicación en cada
petición (sin volver a iniciar sesión). Usa SQLite temporal: no toca SQL Server ni backend/uploads.

Requisito de desarrollo: pip install -r requirements-dev.txt
Ejecución, desde backend/:   python tests/e2e_permisos.py
"""
import os, sys, tempfile

_BASE = tempfile.mkdtemp(prefix="taller_perm_")
os.environ.update(DATABASE_URL=os.environ.get("E2E_DATABASE_URL") or "sqlite:///" + os.path.join(_BASE, "prueba.db").replace("\\", "/"), UPLOADS_DIR=os.path.join(_BASE, "subidas"),
                  JWT_SECRET="x" * 40, BOOTSTRAP_ADMIN_EMAIL="admin@example.com", BOOTSTRAP_ADMIN_PASSWORD="AdminPrueba12345!")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.main import app
from app.database import engine
from app.catalogos import PermisoModel, RolPermisoModel
from app.customers.modelos import TallerModel

fallos = []
def esperar(nombre, real, esperado):
    ok = real == esperado
    print(("OK   " if ok else "FALLA"), nombre, "" if ok else f"-> {real!r} (esperado {esperado!r})")
    if not ok: fallos.append(nombre)

CLAVE = "ClaveSegura12345!"
with TestClient(app) as c:
    def login(correo, clave=CLAVE):
        r = c.post("/api/auth/login", json={"email": correo, "password": clave}).json()
        return {"Authorization": "Bearer " + r["access_token"]}, r["user"]
    admin, _ = login("admin@example.com", "AdminPrueba12345!")
    def empleado(nombre, correo, rol, sucursal="Centro"):
        return c.post("/api/users/employees", headers=admin, json={"full_name": nombre, "email": correo, "password": CLAVE, "role": rol, "branch": sucursal}).status_code
    with Session(engine) as db:
        db.add(TallerModel(nombre="Centro", activo=True)); db.commit()
    empleado("Rita Recepcion", "rita@example.com", "RECEPCIONISTA"); empleado("Tomas Tecnico", "tomas@example.com", "TECNICO")
    rita, _ = login("rita@example.com"); tomas, _ = login("tomas@example.com")
    CODIGOS = ["empleados.alta", "empleados.administrar", "roles.administrar", "talleres.consultar", "talleres.alta", "talleres.administrar", "clientes.consultar", "clientes.alta", "clientes.administrar", "clientes.suspender", "vehiculos.registrar", "vehiculos.consultar", "recepciones.registrar",
               "ordenes.consultar", "ordenes.corregir", "diagnosticos.registrar", "notificaciones.consultar"]

    # ---------- catálogo y permisos de fábrica ----------
    r = c.get("/api/permisos", headers=admin); catalogo = r.json()
    esperar("catálogo con los 17 permisos", (r.status_code, [p["codigo"] for p in catalogo]), (200, CODIGOS))
    esperar("sólo los reservados al administrador no se pueden delegar", sorted(p["codigo"] for p in catalogo if not p["delegable"]), ["clientes.administrar", "clientes.suspender", "empleados.administrar", "empleados.alta", "roles.administrar", "talleres.administrar", "talleres.alta", "vehiculos.consultar", "vehiculos.registrar"])
    esperar("los módulos sin funcionalidad se marcan en desarrollo", sorted(p["codigo"] for p in catalogo if p["en_desarrollo"]), sorted(["recepciones.registrar", "ordenes.consultar", "ordenes.corregir", "diagnosticos.registrar", "notificaciones.consultar"]))
    esperar("el catálogo es sólo para quien administra roles -> 403", c.get("/api/permisos", headers=rita).status_code, 403)
    roles = {x["code"]: x for x in c.get("/api/roles", headers=admin).json()}
    esperar("permisos del recepcionista (de fábrica): ya no da de alta talleres", roles["RECEPCIONISTA"]["permisos"], ["talleres.consultar", "clientes.consultar", "clientes.alta", "clientes.administrar", "vehiculos.registrar", "vehiculos.consultar", "recepciones.registrar", "ordenes.consultar"])
    esperar("sólo el administrador tiene «dar de alta talleres»", [x["code"] for x in roles.values() if "talleres.alta" in x["permisos"]], ["ADMINISTRADOR"])
    esperar("permisos del técnico (de fábrica)", roles["TECNICO"]["permisos"], ["ordenes.consultar", "diagnosticos.registrar"])
    esperar("el administrador tiene todo menos consultar clientes", [p for p in CODIGOS if p not in roles["ADMINISTRADOR"]["permisos"]], ["clientes.consultar"])
    esperar("invitado y sistema no tienen permisos", (roles["INVITADO"]["permisos"], roles["SISTEMA"]["permisos"]), ([], []))
    r = c.get(f"/api/roles/{roles['TECNICO']['id']}/permisos", headers=admin); esperar("un rol de fábrica se ve de sólo lectura", (r.status_code, r.json()["editable"], r.json()["permisos"]), (200, False, ["ordenes.consultar", "diagnosticos.registrar"]))
    esperar("los permisos de un rol de fábrica no se cambian -> 409", c.put(f"/api/roles/{roles['TECNICO']['id']}/permisos", headers=admin, json={"permisos": ["clientes.alta"]}).status_code, 409)

    # ---------- permisos de un rol personalizado ----------
    gestor = c.post("/api/roles", headers=admin, json={"code": "GESTOR", "name": "Gestor de clientes", "description": "Atiende clientes"}).json()
    ruta = f"/api/roles/{gestor['id']}/permisos"
    r = c.get(ruta, headers=admin); esperar("un rol nuevo no tiene permisos y es editable", (r.json()["permisos"], r.json()["editable"]), ([], True))
    r = c.put(ruta, headers=admin, json={"permisos": ["roles.administrar"]}); esperar("no se delega «administrar roles» -> 422", (r.status_code, "reservado" in r.json()["detail"]), (422, True))
    esperar("no se delega «dar de alta talleres» -> 422", c.put(ruta, headers=admin, json={"permisos": ["clientes.alta", "talleres.alta"]}).status_code, 422)
    esperar("no se delega «dar de alta empleados» -> 422", c.put(ruta, headers=admin, json={"permisos": ["clientes.alta", "empleados.alta"]}).status_code, 422)
    esperar("un permiso inexistente -> 422", c.put(ruta, headers=admin, json={"permisos": ["clientes.borrar"]}).status_code, 422)
    esperar("un rechazo no cambia nada", c.get(ruta, headers=admin).json()["permisos"], [])
    esperar("sólo quien administra roles define permisos -> 403", c.put(ruta, headers=rita, json={"permisos": ["clientes.alta"]}).status_code, 403)
    esperar("rol inexistente -> 404", c.put("/api/roles/9999/permisos", headers=admin, json={"permisos": []}).status_code, 404)
    r = c.put(ruta, headers=admin, json={"permisos": ["clientes.consultar", "talleres.consultar", "clientes.consultar"]})
    esperar("asignar permisos (sin duplicar, en orden del catálogo)", (r.status_code, r.json()["permisos"]), (200, ["talleres.consultar", "clientes.consultar"]))
    esperar("el listado de roles informa los permisos del rol", {x["code"]: x["permisos"] for x in c.get("/api/roles", headers=admin).json()}["GESTOR"], ["talleres.consultar", "clientes.consultar"])

    # ---------- se aplican en cada petición ----------
    esperar("empleado con el rol personalizado", empleado("Gina Gestor", "gina@example.com", "GESTOR"), 201)
    gina, usuario = login("gina@example.com")
    esperar("el inicio de sesión trae sus permisos", ([p["codigo"] for p in usuario["permisos"]], usuario["role"], usuario["role_name"]), (["talleres.consultar", "clientes.consultar"], "PERSONALIZADO", "Gestor de clientes"))
    esperar("los permisos traen su nombre para mostrarlos", usuario["permisos"][1]["nombre"], "Consultar clientes")
    esperar("/api/auth/me también trae los permisos", [p["codigo"] for p in c.get("/api/auth/me", headers=gina).json()["permisos"]], ["talleres.consultar", "clientes.consultar"])
    esperar("clientes.consultar permite buscar clientes", c.get("/api/customers?criterio=ana", headers=gina).status_code, 200)
    esperar("sin clientes.alta no se abre el alta -> 403", c.get("/api/customers/alta/acceso", headers=gina).status_code, 403)
    esperar("sin clientes.alta no se crean clientes -> 403", c.post("/api/customers", headers=gina, json={"nombre_completo": "Ana Prueba", "telefono": "5511223344", "correo": "ana@example.com", "confirmar": True}).status_code, 403)
    esperar("talleres.consultar permite ver los talleres", c.get("/api/talleres", headers=gina).status_code, 200)
    esperar("sin talleres.alta no se usa el catálogo de códigos postales -> 403", c.get("/api/catalogos/estados", headers=gina).status_code, 403)
    esperar("sin talleres.alta no se crean talleres -> 403", c.post("/api/talleres", headers=gina, data={"nombre": "X"}).status_code, 403)
    for etiqueta, metodo, ruta_ in (("órdenes", "get", "/api/work-orders"), ("recepciones", "post", "/api/receptions"), ("diagnósticos", "post", "/api/work-orders/1/diagnostics"), ("notificaciones", "get", "/api/notifications")):
        esperar(f"sin el permiso no se accede a {etiqueta} -> 403", getattr(c, metodo)(ruta_, headers=gina).status_code, 403)
    for etiqueta, metodo, ruta_ in (("roles", "get", "/api/roles"), ("empleados (listado)", "get", "/api/users"), ("permisos", "get", "/api/permisos"), ("empleados", "post", "/api/users/employees"), ("roles asignables", "get", "/api/roles/asignables")):
        esperar(f"la administración sigue reservada al administrador: {etiqueta} -> 403", getattr(c, metodo)(ruta_, headers=gina).status_code, 403)

    c.put(ruta, headers=admin, json={"permisos": ["clientes.consultar", "clientes.alta", "ordenes.consultar", "recepciones.registrar"]})
    esperar("un permiso nuevo surte efecto sin volver a iniciar sesión: abrir alta", c.get("/api/customers/alta/acceso", headers=gina).status_code, 200)
    r = c.post("/api/customers", headers=gina, json={"nombre_completo": "Ana Prueba", "telefono": "5511223344", "correo": "ana@example.com", "confirmar": False}); esperar("alta de cliente: pide confirmación", (r.status_code, r.json()["resultado"]), (200, "PENDIENTE_CONFIRMACION"))
    r = c.post("/api/customers", headers=gina, json={"nombre_completo": "Ana Prueba", "telefono": "5511223344", "correo": "ana@example.com", "confirmar": True}); esperar("alta de cliente: se crea", (r.status_code, r.json()["resultado"]), (201, "CREADO"))
    esperar("ordenes.consultar abre las órdenes", c.get("/api/work-orders", headers=gina).status_code, 200)
    esperar("recepciones.registrar abre las recepciones", c.post("/api/receptions", headers=gina).status_code, 200)
    esperar("sin ordenes.corregir sigue cerrado -> 403", c.patch("/api/work-orders/1/corrections", headers=gina).status_code, 403)
    esperar("el conjunto anterior (talleres.consultar) se reemplazó -> 403", c.get("/api/talleres", headers=gina).status_code, 403)

    c.put(ruta, headers=admin, json={"permisos": ["clientes.consultar"]})
    esperar("quitar un permiso surte efecto de inmediato: alta -> 403", c.post("/api/customers", headers=gina, json={"nombre_completo": "Beto Prueba", "telefono": "5522334455", "correo": "beto@example.com", "confirmar": True}).status_code, 403)
    esperar("quitar un permiso: órdenes -> 403", c.get("/api/work-orders", headers=gina).status_code, 403)
    esperar("lo que se conserva sigue funcionando", c.get("/api/customers?criterio=ana", headers=gina).json()["total"], 1)
    c.put(ruta, headers=admin, json={"permisos": []})
    esperar("sin permisos se pierde todo -> 403", c.get("/api/customers?criterio=ana", headers=gina).status_code, 403)
    esperar("sin permisos la sesión lo informa", c.get("/api/auth/me", headers=gina).json()["permisos"], [])

    # ---------- rol eliminado, rol restaurado y permisos no delegables ----------
    c.put(ruta, headers=admin, json={"permisos": ["clientes.consultar"]})
    c.delete(f"/api/roles/{gestor['id']}", headers=admin)
    esperar("un rol eliminado no concede permisos -> 403", c.get("/api/customers?criterio=ana", headers=gina).status_code, 403)
    esperar("un rol eliminado deja la sesión sin permisos", c.get("/api/auth/me", headers=gina).json()["permisos"], [])
    esperar("no se editan los permisos de un rol eliminado -> 409", c.put(ruta, headers=admin, json={"permisos": ["clientes.alta"]}).status_code, 409)
    esperar("sus permisos se conservan mientras está eliminado", c.get(ruta, headers=admin).json()["permisos"], ["clientes.consultar"])
    c.post(f"/api/roles/{gestor['id']}/restaurar", headers=admin)
    esperar("al restaurar el rol vuelven sus permisos", c.get("/api/customers?criterio=ana", headers=gina).status_code, 200)
    with Session(engine) as db:  # aunque alguien alterara la base, un permiso no delegable jamás se concede
        for codigo in ("roles.administrar", "empleados.alta", "talleres.alta", "talleres.administrar"):
            db.add(RolPermisoModel(role_definition_id=gestor["id"], permiso_id=db.scalar(select(PermisoModel.id).where(PermisoModel.codigo == codigo))))
        db.commit()
    esperar("un permiso de administración puesto a mano en la base no se concede", (c.get("/api/roles", headers=gina).status_code, c.post("/api/users/employees", headers=gina).status_code, c.get("/api/catalogos/estados", headers=gina).status_code), (403, 403, 403))
    esperar("y no aparece en sus permisos", [p["codigo"] for p in c.get("/api/auth/me", headers=gina).json()["permisos"]], ["clientes.consultar"])

    from app.permisos import sembrar_permisos
    with Session(engine) as db:
        antes = len(db.scalars(select(RolPermisoModel.id).join(PermisoModel, PermisoModel.id == RolPermisoModel.permiso_id).where(PermisoModel.delegable == False)).all())  # noqa: E712
        sembrar_permisos(db)  # lo que hace el arranque: retira las concesiones de permisos que dejaron de ser delegables
        despues = len(db.scalars(select(RolPermisoModel.id).join(PermisoModel, PermisoModel.id == RolPermisoModel.permiso_id).where(PermisoModel.delegable == False)).all())  # noqa: E712
    esperar("el arranque retira las concesiones de permisos no delegables que hubiera en la base", (antes, despues), (4, 0))

    # ---------- los demás no cambian ----------
    esperar("el técnico conserva sus órdenes", c.get("/api/work-orders", headers=tomas).status_code, 200)
    esperar("el técnico sigue sin clientes -> 403", c.get("/api/customers?criterio=ana", headers=tomas).status_code, 403)
    esperar("el recepcionista conserva clientes y la consulta de talleres", (c.get("/api/customers?criterio=ana", headers=rita).status_code, c.get("/api/talleres", headers=rita).status_code), (200, 200))
    esperar("pero el recepcionista ya no da de alta talleres ni usa el catálogo de códigos postales -> 403", (c.post("/api/talleres", headers=rita, data={"nombre": "X"}).status_code, c.get("/api/catalogos/estados", headers=rita).status_code), (403, 403))
    esperar("el administrador sí da de alta talleres (llega a validar los datos -> 422)", c.post("/api/talleres", headers=admin, data={"nombre": "X"}).status_code, 422)
    esperar("el administrador conserva la administración", (c.get("/api/roles", headers=admin).status_code, c.get("/api/work-orders", headers=admin).status_code), (200, 200))
    esperar("el administrador sigue sin gestionar clientes -> 403", c.get("/api/customers?criterio=ana", headers=admin).status_code, 403)
    c.post("/api/auth/register", json={"full_name": "Ivan Invitado", "email": "ivan@example.com", "password": CLAVE})
    invitado, uinv = login("ivan@example.com")
    esperar("el invitado no tiene permisos", (uinv["permisos"], c.get("/api/work-orders", headers=invitado).status_code), ([], 403))

print("\nRESULTADO:", "TODO OK" if not fallos else f"{len(fallos)} fallos: {fallos}")
sys.exit(1 if fallos else 0)
