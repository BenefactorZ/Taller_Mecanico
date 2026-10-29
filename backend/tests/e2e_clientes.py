"""Prueba de punta a punta del módulo de Clientes sobre una base SQLite temporal (no toca SQL Server).

Requisito de desarrollo: pip install -r requirements-dev.txt
Ejecución, desde backend/:   python tests/e2e_clientes.py
"""
import os, sys, tempfile

_BASE = tempfile.mkdtemp(prefix="taller_e2e_")
os.environ.update(DATABASE_URL=os.environ.get("E2E_DATABASE_URL") or "sqlite:///" + os.path.join(_BASE, "prueba.db").replace("\\", "/"),
                  JWT_SECRET="x" * 40, BOOTSTRAP_ADMIN_EMAIL="admin@example.com", BOOTSTRAP_ADMIN_PASSWORD="AdminPrueba12345!")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.main import app
from app.database import engine
from app.customers.modelos import CustomerModel, AuditoriaModel, TallerModel

fallos = []
def esperar(nombre, real, esperado):
    ok = real == esperado
    print(("OK   " if ok else "FALLA"), nombre, "" if ok else f"-> {real!r} (esperado {esperado!r})")
    if not ok: fallos.append(nombre)

with TestClient(app) as c:
    def login(correo, clave):
        r = c.post("/api/auth/login", json={"email": correo, "password": clave}); return {"Authorization": "Bearer " + r.json()["access_token"]}
    admin = login("admin@example.com", "AdminPrueba12345!")
    for nombre, correo, rol, suc in [("Rita Recepcion", "rita@example.com", "RECEPCIONISTA", "Centro"), ("Tomas Tecnico", "tomas@example.com", "TECNICO", "Centro"),
                                      ("Nora Norte", "nora@example.com", "RECEPCIONISTA", "norte"), ("Ana Asesora", "ana@example.com", "ASESOR_SERVICIO", "CENTRO")]:
        esperar(f"alta empleado {rol}", c.post("/api/users/employees", headers=admin, json={"full_name": nombre, "email": correo, "password": "ClaveSegura12345!", "role": rol, "branch": suc}).status_code, 201)
    with Session(engine) as db:  # los talleres se registran antes (alta de taller); aquí se insertan directo para no depender del catálogo
        db.add_all([TallerModel(nombre="Centro", activo=True), TallerModel(nombre="norte", activo=True)]); db.commit()
    empleado_fantasma = c.post("/api/users/employees", headers=admin, json={"full_name": "Fabio Fantasma", "email": "fabio@example.com", "password": "ClaveSegura12345!", "role": "RECEPCIONISTA", "branch": "Sucursal sin registrar"}).status_code
    rita, tomas, nora, ana = (login(x, "ClaveSegura12345!") for x in ("rita@example.com", "tomas@example.com", "nora@example.com", "ana@example.com"))

    fabio = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "fabio@example.com", "password": "ClaveSegura12345!"}).json()["access_token"]}
    r = c.get("/api/customers/alta/acceso", headers=fabio); esperar("sucursal sin taller registrado -> 403 que explica qué hacer", (r.status_code, "no está registrada" in r.json()["detail"]), (403, True))
    r = c.get("/api/customers/alta/acceso", headers=rita); esperar("abrir alta (recepcionista)", (r.status_code, r.json().get("taller")), (200, "Centro"))
    esperar("abrir alta (asesor, mismo taller sin importar mayúsculas)", c.get("/api/customers/alta/acceso", headers=ana).status_code, 200)
    esperar("abrir alta (técnico) -> 403", c.get("/api/customers/alta/acceso", headers=tomas).status_code, 403)
    esperar("abrir alta (administrador sin taller) -> 403", c.get("/api/customers/alta/acceso", headers=admin).status_code, 403)
    esperar("sin sesión -> 401/403", c.get("/api/customers/alta/acceso").status_code in (401, 403), True)

    datos = {"nombre_completo": "  María   López ", "telefono": "55 1234-5678", "correo": "Maria.Lopez@Correo.com"}
    r = c.post("/api/customers", headers=rita, json=datos); esperar("alta sin confirmar", (r.status_code, r.json()["resultado"]), (200, "PENDIENTE_CONFIRMACION"))
    with Session(engine) as db: esperar("nada persistido antes de confirmar", db.scalar(select(func.count()).select_from(CustomerModel)), 0)
    r = c.post("/api/customers", headers=rita, json={**datos, "confirmar": True}); creado = r.json()
    esperar("alta confirmada: ID, nombre, teléfono y correo normalizados", (r.status_code, creado["resultado"], creado["customer"]["estado"], creado["customer"]["nombre_completo"], creado["customer"]["telefono"], creado["customer"]["correo"], isinstance(creado["customer"]["id"], int)), (201, "CREADO", "ACTIVO", "María López", "5512345678", "maria.lopez@correo.com", True))
    cid = creado["customer"]["id"]
    for etiqueta, cuerpo in [("mismo nombre, otros medios", {"nombre_completo": "Maria Lopez", "telefono": "5599990000", "correo": "otro@correo.com"}),
                             ("mismo correo, otro nombre", {"nombre_completo": "Pedro Pérez", "telefono": "5599990001", "correo": "MARIA.LOPEZ@correo.com"}),
                             ("mismo teléfono, otro nombre", {"nombre_completo": "Pedro Pérez", "telefono": "(55) 1234 5678", "correo": "pedro@correo.com"})]:
        r = c.post("/api/customers", headers=rita, json={**cuerpo, "confirmar": True}); j = r.json()
        esperar(f"duplicado ({etiqueta}) alerta y no crea", (r.status_code, j["resultado"], len(j["coincidencias"]), j["customer"]), (200, "COINCIDENCIAS", 1, None))
    with Session(engine) as db:
        esperar("sólo un Customer en base", db.scalar(select(func.count()).select_from(CustomerModel)), 1)
        esperar("una Auditoría ALTA_CUSTOMER", [a.accion for a in db.scalars(select(AuditoriaModel))], ["ALTA_CUSTOMER"])
    for etiqueta, cuerpo in [("nombre de una palabra", {"nombre_completo": "Madonna", "telefono": "5511112222", "correo": "m@x.com"}), ("correo inválido", {"nombre_completo": "Juan Pérez", "telefono": "5511112222", "correo": "juan@@x"}),
                             ("teléfono corto", {"nombre_completo": "Juan Pérez", "telefono": "12345", "correo": "juan@x.com"}), ("teléfono con letras", {"nombre_completo": "Juan Pérez", "telefono": "55abc12345", "correo": "juan@x.com"}),
                             ("teléfono vacío", {"nombre_completo": "Juan Pérez", "telefono": "  ", "correo": "juan@x.com"}), ("correo vacío", {"nombre_completo": "Juan Pérez", "telefono": "5511112222", "correo": "  "}),
                             ("falta el correo", {"nombre_completo": "Juan Pérez", "telefono": "5511112222"})]:
        r = c.post("/api/customers", headers=rita, json=cuerpo); esperar(f"formato inválido ({etiqueta}) -> 422", r.status_code, 422)
    esperar("técnico no puede dar de alta -> 403", c.post("/api/customers", headers=tomas, json=datos).status_code, 403)
    r = c.post("/api/customers", headers=nora, json={**datos, "confirmar": True}); esperar("otro taller sí puede tener el mismo cliente", (r.status_code, r.json()["resultado"]), (201, "CREADO"))

    r = c.get("/api/customers", headers=ana, params={"criterio": "maria lopez"}); j = r.json(); esperar("consulta por nombre sin acentos (otro rol del mismo taller)", (r.status_code, j["total"], j["items"][0]["id"]), (200, 1, cid))
    r = c.get("/api/customers", headers=rita, params={"criterio": "Maria.Lopez@correo.com"}); esperar("consulta por correo", (r.status_code, r.json()["total"]), (200, 1))
    r = c.get("/api/customers", headers=rita, params={"criterio": "55 1234 5678"}); esperar("consulta por teléfono (con otro formato)", (r.status_code, r.json()["total"], r.json()["items"][0]["telefono"]), (200, 1, "5512345678"))
    r = c.get("/api/customers", headers=rita, params={"criterio": "zzz"}); esperar("consulta sin resultados", (r.json()["total"], r.json()["items"], r.json()["hay_mas"]), (0, [], False))
    r = c.get("/api/customers", headers=rita, params={"criterio": "100%"}); esperar("el criterio con % no actúa como comodín", r.json()["total"], 0)
    esperar("criterio vacío -> 422", c.get("/api/customers", headers=rita, params={"criterio": ""}).status_code, 422)
    esperar("tamaño de página inválido -> 422", c.get("/api/customers", headers=rita, params={"criterio": "m", "tamano": 500}).status_code, 422)
    for i in range(12):
        c.post("/api/customers", headers=rita, json={"nombre_completo": f"Cliente Paginado {i:02d}", "telefono": f"55000000{i:02d}", "correo": f"cliente{i}@correo.com", "confirmar": True})
    r = c.get("/api/customers", headers=rita, params={"criterio": "paginado", "pagina": 2, "tamano": 5}); j = r.json()
    esperar("paginación (página 2 de 12)", (j["total"], len(j["items"]), j["hay_mas"], j["numero"]), (12, 5, True, 2))
    r = c.get("/api/customers", headers=rita, params={"criterio": "paginado", "pagina": 3, "tamano": 5}); esperar("última página", (len(r.json()["items"]), r.json()["hay_mas"]), (2, False))

    r = c.get(f"/api/customers/{cid}", headers=rita); esperar("ficha", (r.status_code, r.json()["estado"]), (200, "ACTIVO"))
    esperar("ficha de otro taller -> 404", c.get(f"/api/customers/{cid}", headers=nora).status_code, 404)
    esperar("consulta de otro taller no ve clientes ajenos", c.get("/api/customers", headers=nora, params={"criterio": "paginado"}).json()["total"], 0)

print("\nRESULTADO:", "TODO OK" if not fallos else f"{len(fallos)} fallos: {fallos}")

sys.exit(1 if fallos else 0)
