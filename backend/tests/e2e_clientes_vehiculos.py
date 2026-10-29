"""Prueba de punta a punta de la administración de clientes (modificación con trazabilidad, suspensión sólo del administrador, el taller
no cambia) y del registro de vehículos (flujo datos → normalizar → duplicados → guardar → relacionar, resultado: vehículo activo).
Usa SQLite temporal: no toca SQL Server ni backend/uploads.

Requisito de desarrollo: pip install -r requirements-dev.txt
Ejecución, desde backend/:   python tests/e2e_clientes_vehiculos.py
"""
import os, sys, tempfile

_BASE = tempfile.mkdtemp(prefix="taller_cv_")
os.environ.update(DATABASE_URL=os.environ.get("E2E_DATABASE_URL") or "sqlite:///" + os.path.join(_BASE, "prueba.db").replace("\\", "/"), UPLOADS_DIR=os.path.join(_BASE, "subidas"),
                  JWT_SECRET="x" * 40, BOOTSTRAP_ADMIN_EMAIL="admin@example.com", BOOTSTRAP_ADMIN_PASSWORD="AdminPrueba12345!")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.main import app
from app.database import engine
from app.customers.modelos import AuditoriaModel, CustomerModel, TallerModel
from app.vehiculos.modelos import VehiculoModel

fallos = []
def esperar(nombre, real, esperado):
    ok = real == esperado
    print(("OK   " if ok else "FALLA"), nombre, "" if ok else f"-> {real!r} (esperado {esperado!r})")
    if not ok: fallos.append(nombre)

JPG = b"\xff\xd8\xff\xe0" + b"0" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"1" * 200
GIF = b"GIF89a" + b"0" * 100
CLAVE = "ClaveSegura12345!"
subidas = Path(os.environ["UPLOADS_DIR"]) / "vehiculos"
def archivos(): return sorted(p.name for p in subidas.glob("*")) if subidas.exists() else []

with TestClient(app) as c:
    def login(correo, clave=CLAVE):
        r = c.post("/api/auth/login", json={"email": correo, "password": clave})
        return {"Authorization": "Bearer " + r.json()["access_token"]} if r.status_code == 200 else None
    admin = login("admin@example.com", "AdminPrueba12345!")
    with Session(engine) as db:
        db.add_all([TallerModel(nombre="Centro", activo=True), TallerModel(nombre="Norte", activo=True)]); db.commit()
    for nombre, correo, rol, suc in [("Rita Recepcion", "rita@example.com", "RECEPCIONISTA", "Centro"), ("Nora Norte", "nora@example.com", "RECEPCIONISTA", "Norte"),
                                     ("Ana Asesora", "ana@example.com", "ASESOR_SERVICIO", "Centro"), ("Tomas Tecnico", "tomas@example.com", "TECNICO", "Centro")]:
        c.post("/api/users/employees", headers=admin, json={"full_name": nombre, "email": correo, "password": CLAVE, "role": rol, "branch": suc})
    rita, nora, ana, tomas = (login(f"{n}@example.com") for n in ("rita", "nora", "ana", "tomas"))
    def cliente(cab, nombre, telefono, correo):
        r = c.post("/api/customers", headers=cab, json={"nombre_completo": nombre, "telefono": telefono, "correo": correo, "confirmar": True}); return r.json()["customer"]["id"]
    maria = cliente(rita, "Maria Lopez", "5511111111", "maria@correo.com")
    jose = cliente(rita, "Jose Perez", "5512345678", "jose@correo.com")
    pedro = cliente(nora, "Pedro Ramos", "5522222222", "pedro@correo.com")
    ADM = "/api/administracion/clientes"

    # ---------- permisos ----------
    for etiqueta, cab in (("asesor", ana), ("técnico", tomas)):
        esperar(f"{etiqueta} no administra clientes -> 403", (c.get(ADM, headers=cab).status_code, c.put(f"{ADM}/{maria}", headers=cab, json={"nombre_completo": "Maria Lopez", "telefono": "5511111111", "correo": "maria@correo.com"}).status_code), (403, 403))
    esperar("sin sesión no se accede", c.get(ADM).status_code in (401, 403), True)
    mis = [p["codigo"] for p in c.get("/api/auth/me", headers=rita).json()["permisos"]]
    esperar("la recepcionista puede administrar clientes y vehículos, pero no suspender", ("clientes.administrar" in mis, "vehiculos.registrar" in mis, "clientes.suspender" in mis), (True, True, False))
    mis = [p["codigo"] for p in c.get("/api/auth/me", headers=admin).json()["permisos"]]
    esperar("el administrador administra, suspende y da de alta, pero no consulta clientes de un taller", ("clientes.administrar" in mis, "clientes.suspender" in mis, "clientes.alta" in mis, "clientes.consultar" in mis), (True, True, True, False))
    catalogo = {p["codigo"]: p["delegable"] for p in c.get("/api/permisos", headers=admin).json()}
    esperar("los permisos nuevos no son delegables", [catalogo[k] for k in ("clientes.administrar", "clientes.suspender", "vehiculos.registrar", "vehiculos.consultar")], [False] * 4)

    # ---------- listado y alcance ----------
    r = c.get(ADM, headers=rita).json()
    esperar("la recepcionista ve sólo los clientes de su taller", sorted(x["nombre_completo"] for x in r["items"]), ["Jose Perez", "Maria Lopez"])
    r = c.get(ADM, headers=admin).json()
    esperar("el administrador ve los de todos los talleres, con el nombre del taller", sorted((x["nombre_completo"], x["taller"]) for x in r["items"]), [("Jose Perez", "Centro"), ("Maria Lopez", "Centro"), ("Pedro Ramos", "Norte")])
    esperar("el administrador filtra por taller", [x["nombre_completo"] for x in c.get(f"{ADM}?taller_id={r['items'][0]['taller_id']}", headers=admin).json()["items"]] != [], True)
    esperar("búsqueda parcial por nombre sin acentos ni mayúsculas", [x["id"] for x in c.get(f"{ADM}?buscar=LOPE", headers=rita).json()["items"]], [maria])
    esperar("búsqueda parcial por teléfono", [x["id"] for x in c.get(f"{ADM}?buscar=5512", headers=rita).json()["items"]], [jose])
    esperar("búsqueda parcial por correo", [x["id"] for x in c.get(f"{ADM}?buscar=JOSE@", headers=rita).json()["items"]], [jose])
    esperar("el listado trae ID, nombre, teléfono y correo", {k: next(x for x in c.get(ADM, headers=rita).json()["items"] if x["id"] == jose)[k] for k in ("id", "nombre_completo", "telefono", "correo", "datos_incompletos")},
            {"id": jose, "nombre_completo": "Jose Perez", "telefono": "5512345678", "correo": "jose@correo.com", "datos_incompletos": False})
    esperar("un % no actúa como comodín", c.get(f"{ADM}?buscar=%25", headers=rita).json()["total"], 0)
    esperar("paginación", (c.get(f"{ADM}?tamano=1&pagina=2", headers=admin).json()["total"], len(c.get(f"{ADM}?tamano=1&pagina=2", headers=admin).json()["items"])), (3, 1))
    esperar("un cliente de otro taller no se ve ni se modifica (404)", (c.get(f"{ADM}/{pedro}", headers=rita).status_code, c.put(f"{ADM}/{pedro}", headers=rita, json={"nombre_completo": "Pedro Ramos", "telefono": "5522222222", "correo": "x@y.com"}).status_code), (404, 404))

    # ---------- modificar con trazabilidad ----------
    r = c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "  María   López Díaz ", "telefono": "55-1111 1111", "correo": "MARIA.Lopez@Correo.com"})
    esperar("modificar nombre y correo (normalizados)", (r.status_code, r.json().get("nombre_completo"), r.json().get("telefono"), r.json().get("correo"), r.json().get("taller")), (200, "María López Díaz", "5511111111", "maria.lopez@correo.com", "Centro"))
    h = c.get(f"{ADM}/{maria}/historial", headers=rita).json()
    esperar("el historial registra la modificación con quién y qué cambió", (h[0]["accion"], h[0]["usuario"], "nombre" in h[0]["detalle"] and "correo" in h[0]["detalle"] and "teléfono" not in h[0]["detalle"] and " a «" in h[0]["detalle"]), ("ACTUALIZAR_CUSTOMER", "Rita Recepcion", True))
    esperar("el historial conserva el alta original", h[-1]["accion"], "ALTA_CUSTOMER")
    antes = len(h)
    r = c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "María López Díaz", "telefono": "5511111111", "correo": "maria.lopez@correo.com"})
    esperar("guardar sin cambios no genera movimiento", (r.status_code, len(c.get(f"{ADM}/{maria}/historial", headers=rita).json())), (200, antes))
    r = c.put(f"{ADM}/{maria}", headers=admin, json={"nombre_completo": "María López Díaz", "telefono": "5599887766", "correo": "maria.lopez@correo.com"})
    esperar("el administrador también modifica (y queda su nombre en el historial)", (r.status_code, c.get(f"{ADM}/{maria}/historial", headers=admin).json()[0]["usuario"]), (200, "Administrador inicial"))
    esperar("el taller asignado no se puede cambiar", (c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "María López Díaz", "telefono": "5599887766", "correo": "maria.lopez@correo.com", "taller_id": 2}).status_code,
                                                          c.get(f"{ADM}/{maria}", headers=admin).json()["taller"]), (409, "Centro"))
    esperar("enviar su mismo taller es inofensivo", c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "María López Díaz", "telefono": "5599887766", "correo": "maria.lopez@correo.com", "taller_id": c.get(f"{ADM}/{maria}", headers=admin).json()["taller_id"]}).status_code, 200)
    esperar("teléfono de otro cliente del taller -> 409", c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "María López Díaz", "telefono": "5512345678", "correo": "maria.lopez@correo.com"}).status_code, 409)
    esperar("correo de otro cliente del taller -> 409", c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "María López Díaz", "telefono": "5599887766", "correo": "JOSE@correo.com"}).status_code, 409)
    r = c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "jose perez", "telefono": "5599887766", "correo": "maria.lopez@correo.com"})
    esperar("mismo nombre que otro cliente -> 409 con código COINCIDENCIA", (r.status_code, r.json().get("codigo")), (409, "COINCIDENCIA"))
    r = c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "jose perez", "telefono": "5599887766", "correo": "maria.lopez@correo.com", "confirmar": True})
    esperar("al confirmar se guarda", (r.status_code, r.json().get("nombre_completo")), (200, "jose perez"))
    c.put(f"{ADM}/{maria}", headers=rita, json={"nombre_completo": "María López Díaz", "telefono": "5599887766", "correo": "maria.lopez@correo.com"})
    for etiqueta, cuerpo in (("nombre sin apellido", {"nombre_completo": "Maria", "telefono": "5599887766", "correo": "maria@correo.com"}), ("teléfono inválido", {"nombre_completo": "Maria Lopez", "telefono": "abc", "correo": "maria@correo.com"}),
                             ("correo inválido", {"nombre_completo": "Maria Lopez", "telefono": "5599887766", "correo": "a@b"}), ("sin correo", {"nombre_completo": "Maria Lopez", "telefono": "5599887766", "correo": ""}),
                             ("sin teléfono", {"nombre_completo": "Maria Lopez", "telefono": "", "correo": "maria@correo.com"})):
        esperar(f"formato inválido ({etiqueta}) -> 422", c.put(f"{ADM}/{maria}", headers=rita, json=cuerpo).status_code, 422)
    esperar("cliente inexistente -> 404", c.put(f"{ADM}/9999", headers=rita, json={"nombre_completo": "Maria Lopez", "telefono": "5599887766", "correo": "maria@correo.com"}).status_code, 404)
    esperar("la consulta de Clientes existente refleja el cambio", c.get("/api/customers?criterio=lopez", headers=rita).json()["total"], 1)

    # ---------- suspender: sólo el administrador ----------
    esperar("la recepcionista no suspende -> 403", (c.post(f"{ADM}/{jose}/suspender", headers=rita, json={"motivo": "Prueba"}).status_code, c.post(f"{ADM}/{jose}/reactivar", headers=rita).status_code), (403, 403))
    esperar("el motivo es obligatorio -> 422", c.post(f"{ADM}/{jose}/suspender", headers=admin, json={"motivo": ""}).status_code, 422)
    r = c.post(f"{ADM}/{jose}/suspender", headers=admin, json={"motivo": "Cuenta con adeudo"})
    esperar("el administrador suspende", (r.status_code, r.json().get("estado")), (200, "INACTIVO"))
    esperar("suspender dos veces -> 409", c.post(f"{ADM}/{jose}/suspender", headers=admin, json={"motivo": "Otra vez"}).status_code, 409)
    h = c.get(f"{ADM}/{jose}/historial", headers=rita).json()
    esperar("la suspensión queda en el historial con su motivo", (h[0]["accion"], h[0]["detalle"], h[0]["usuario"]), ("SUSPENDER_CUSTOMER", "Motivo: Cuenta con adeudo", "Administrador inicial"))
    r = c.put(f"{ADM}/{jose}", headers=rita, json={"nombre_completo": "Jose Perez Ruiz", "telefono": "5512345678", "correo": "jose@correo.com"})
    esperar("un cliente suspendido no se modifica -> 409", (r.status_code, r.json().get("codigo")), (409, "CLIENTE_SUSPENDIDO"))
    esperar("filtra por estado suspendido", [x["id"] for x in c.get(f"{ADM}?estado=INACTIVO", headers=rita).json()["items"]], [jose])
    esperar("el alta sigue detectando al suspendido como coincidencia", c.post("/api/customers", headers=rita, json={"nombre_completo": "Jose Perez", "telefono": "5500000000", "correo": "otro@correo.com"}).json()["resultado"], "COINCIDENCIAS")
    r = c.post(f"{ADM}/{jose}/reactivar", headers=admin)
    esperar("el administrador reactiva", (r.status_code, r.json().get("estado")), (200, "ACTIVO"))
    esperar("reactivar uno activo -> 409", c.post(f"{ADM}/{jose}/reactivar", headers=admin).status_code, 409)
    esperar("tras reactivar se puede modificar", c.put(f"{ADM}/{jose}", headers=rita, json={"nombre_completo": "Jose Perez Ruiz", "telefono": "5512345678", "correo": "jose@correo.com"}).status_code, 200)

    # ---------- clientes anteriores a la separación (sólo traen un medio de contacto) ----------
    with Session(engine) as db:
        taller_centro = db.get(CustomerModel, maria).taller_id
        db.add(CustomerModel(taller_id=taller_centro, nombre_completo="Luis Antiguo", nombre_clave="luis antiguo", contacto="5533334444", telefono="5533334444", correo=None))
        db.commit()
        luis = db.scalar(select(CustomerModel.id).where(CustomerModel.nombre_clave == "luis antiguo"))
    r = c.get(f"{ADM}/{luis}", headers=rita).json()
    esperar("un cliente antiguo se marca con datos incompletos", (r["telefono"], r["correo"], r["datos_incompletos"]), ("5533334444", None, True))
    esperar("para guardarlo hay que completar el correo (422)", c.put(f"{ADM}/{luis}", headers=rita, json={"nombre_completo": "Luis Antiguo", "telefono": "5533334444", "correo": ""}).status_code, 422)
    r = c.put(f"{ADM}/{luis}", headers=rita, json={"nombre_completo": "Luis Antiguo", "telefono": "5533334444", "correo": "luis@correo.com"})
    esperar("al completarlo queda con ID, nombre, teléfono y correo", (r.status_code, r.json()["telefono"], r.json()["correo"], r.json()["datos_incompletos"]), (200, "5533334444", "luis@correo.com", False))
    h = c.get(f"{ADM}/{luis}/historial", headers=rita).json()
    esperar("el historial registra el correo agregado", (h[0]["accion"], "sin dato" in h[0]["detalle"] and "luis@correo.com" in h[0]["detalle"]), ("ACTUALIZAR_CUSTOMER", True))

    # ---------- vehículos ----------
    V = "/api/vehiculos"
    def alta(cab, cambios=None, foto=("auto.jpg", JPG, "image/jpeg"), cliente_id=None):
        datos = {"customer_id": cliente_id or maria, "vin": "1HGCM82633A004352", "placa": "ABC-123-D", "marca": "honda", "modelo": "Civic", "anio": "2019", "color": "rojo", "kilometraje": "45000", **(cambios or {})}
        return c.post(V, headers=cab, data={k: str(v) for k, v in datos.items()}, files={"foto": foto} if foto else None)
    for etiqueta, cab in (("asesor", ana), ("técnico", tomas)):
        esperar(f"{etiqueta} no registra vehículos -> 403", (alta(cab).status_code, c.get(V, headers=cab).status_code), (403, 403))
    r = alta(rita)
    v1 = r.json()
    esperar("registrar un vehículo (datos normalizados, activo y asociado al cliente)", (r.status_code, v1.get("vin"), v1.get("placa"), v1.get("marca"), v1.get("color"), v1.get("estado"), v1.get("customer_id"), v1.get("cliente"), v1.get("taller"), v1.get("kilometraje"), v1.get("tiene_foto")),
            (201, "1HGCM82633A004352", "ABC123D", "Honda", "Rojo", "ACTIVO", maria, "María López Díaz", "Centro", 45000, True))
    esperar("la imagen se guardó", len(archivos()), 1)
    foto = c.get(f"{V}/{v1['id']}/foto", headers=rita)
    esperar("la imagen se sirve con su tipo", (foto.status_code, foto.headers["content-type"]), (200, "image/jpeg"))
    with Session(engine) as db:
        fila = db.get(VehiculoModel, v1["id"])
        esperar("en la base: activo, con el taller del cliente", (fila.bin_status, fila.taller_id == db.get(CustomerModel, maria).taller_id, fila.created_by is not None), (1, True, True))
    h = c.get(f"{ADM}/{maria}/historial", headers=rita).json()
    esperar("el vínculo cliente-vehículo queda en el historial del cliente", (h[0]["accion"], "ABC123D" in h[0]["detalle"]), ("ALTA_VEHICULO", True))
    esperar("duplicado por VIN (otra grafía) -> 409", alta(rita, {"vin": "1hgcm82633a004352", "placa": "ZZZ-999"}).status_code, 409)
    esperar("duplicado por placa (otra grafía) -> 409", alta(rita, {"vin": "2HGCM82633A004352", "placa": "abc 123 d"}).status_code, 409)
    esperar("los duplicados no dejan imágenes huérfanas", len(archivos()), 1)
    r = alta(rita, {"vin": "JH4KA8260MC000000", "placa": "1AB-234", "kilometraje": "", "marca": "BMW", "modelo": "CX-5", "color": "azul marino"}, foto=("a.png", PNG, "image/png"))
    esperar("kilometraje opcional; marca con mayúsculas se respeta", (r.status_code, r.json().get("kilometraje"), r.json().get("marca"), r.json().get("modelo"), r.json().get("color")), (201, None, "BMW", "CX-5", "Azul Marino"))
    malos = [("VIN corto", {"vin": "1HGCM8263"}), ("VIN con letra prohibida (I)", {"vin": "1HGCM82633A00435I"}), ("VIN con símbolos", {"vin": "1HGCM8263@A004352"}),
             ("placa sólo números", {"placa": "123456"}), ("placa sólo letras", {"placa": "ABCDEF"}), ("placa demasiado larga", {"placa": "ABC12345"}), ("placa con símbolos", {"placa": "AB#123"}),
             ("año anterior a 1981", {"anio": "1970"}), ("año futuro", {"anio": "2099"}), ("año no numérico", {"anio": "abc"}), ("kilometraje negativo", {"kilometraje": "-5"}),
             ("kilometraje no numérico", {"kilometraje": "mucho"}), ("marca vacía", {"marca": ""}), ("modelo vacío", {"modelo": ""}), ("color vacío", {"color": ""})]
    for etiqueta, cambios in malos:
        esperar(f"{etiqueta} -> 422", alta(rita, {"vin": "3HGCM82633A004353", "placa": "QWE-456", **cambios}).status_code, 422)
    esperar("sin imagen -> 422", alta(rita, {"vin": "3HGCM82633A004353", "placa": "QWE-456"}, foto=None).status_code, 422)
    esperar("imagen en formato no permitido (GIF) -> 422", alta(rita, {"vin": "3HGCM82633A004353", "placa": "QWE-456"}, foto=("a.gif", GIF, "image/gif")).status_code, 422)
    esperar("imagen disfrazada (.jpg con contenido GIF) -> 422", alta(rita, {"vin": "3HGCM82633A004353", "placa": "QWE-456"}, foto=("a.jpg", GIF, "image/jpeg")).status_code, 422)
    esperar("imagen de más de 15 MB -> 413", alta(rita, {"vin": "3HGCM82633A004353", "placa": "QWE-456"}, foto=("g.jpg", JPG + b"0" * (15 * 1024 * 1024), "image/jpeg")).status_code, 413)
    esperar("sin cliente -> 422", alta(rita, {"customer_id": 0, "vin": "3HGCM82633A004353", "placa": "QWE-456"}).status_code, 422)
    esperar("cliente inexistente -> 404", alta(rita, {"customer_id": 9999, "vin": "3HGCM82633A004353", "placa": "QWE-456"}).status_code, 404)
    esperar("cliente de otro taller -> 404", alta(rita, {"vin": "3HGCM82633A004353", "placa": "QWE-456"}, cliente_id=pedro).status_code, 404)
    esperar("ningún rechazo dejó imágenes huérfanas", len(archivos()), 2)
    c.post(f"{ADM}/{jose}/suspender", headers=admin, json={"motivo": "Prueba de vehiculos"})
    r = alta(rita, {"vin": "3HGCM82633A004353", "placa": "QWE-456"}, cliente_id=jose)
    esperar("a un cliente suspendido no se le registran vehículos -> 409", (r.status_code, r.json().get("codigo")), (409, "CLIENTE_SUSPENDIDO"))
    c.post(f"{ADM}/{jose}/reactivar", headers=admin)
    r = alta(admin, {"vin": "4HGCM82633A004354", "placa": "RTY-789"}, cliente_id=pedro)
    esperar("el administrador registra para un cliente de cualquier taller", (r.status_code, r.json().get("taller")), (201, "Norte"))
    # listado
    esperar("la recepcionista ve los vehículos de su taller", sorted(x["placa"] for x in c.get(V, headers=rita).json()["items"]), ["1AB234", "ABC123D"])
    esperar("el administrador ve todos", c.get(V, headers=admin).json()["total"], 3)
    esperar("busca por placa con otro formato", [x["placa"] for x in c.get(f"{V}?buscar=abc-123", headers=rita).json()["items"]], ["ABC123D"])
    esperar("busca por marca", [x["placa"] for x in c.get(f"{V}?buscar=honda", headers=rita).json()["items"]], ["ABC123D"])
    esperar("busca por nombre del cliente", c.get(f"{V}?buscar=lopez", headers=rita).json()["total"], 2)
    esperar("filtra por cliente", c.get(f"{V}?customer_id={maria}", headers=rita).json()["total"], 2)
    esperar("el conteo de vehículos aparece en la administración de clientes", {x["id"]: x["vehiculos"] for x in c.get(ADM, headers=admin).json()["items"]}, {maria: 2, jose: 0, pedro: 1, luis: 0})
    esperar("una recepcionista de otro taller no ve la imagen (404)", (c.get(f"{V}/{v1['id']}/foto", headers=nora).status_code, c.get(f"{V}/{v1['id']}/foto", headers=admin).status_code), (404, 200))
    esperar("registrar un vehículo no cambia el taller del cliente", c.get(f"{ADM}/{maria}", headers=admin).json()["taller"], "Centro")
    with Session(engine) as db:
        esperar("auditoría: una fila por vehículo", len(db.scalars(select(AuditoriaModel).where(AuditoriaModel.accion == "ALTA_VEHICULO")).all()), 3)

    # ---------- modificar, eliminar y restaurar vehículos ----------
    def editar(cab, vid, cambios=None, foto=None):
        datos = {"vin": "1HGCM82633A004352", "placa": "ABC-123-D", "marca": "Honda", "modelo": "Civic", "anio": "2019", "color": "Rojo", "kilometraje": "45000", **(cambios or {})}
        return c.put(f"{V}/{vid}", headers=cab, data=datos, files={"foto": foto} if foto else None)
    v2 = c.get(f"{V}?buscar=1AB234", headers=rita).json()["items"][0]["id"]
    for etiqueta, cab in (("asesor", ana), ("técnico", tomas)):
        esperar(f"{etiqueta} no modifica ni elimina -> 403", (editar(cab, v1["id"]).status_code, c.delete(f"{V}/{v1['id']}", headers=cab).status_code), (403, 403))
    esperar("otro taller no ve, modifica ni elimina (404)", (c.get(f"{V}/{v1['id']}", headers=nora).status_code, editar(nora, v1["id"]).status_code, c.delete(f"{V}/{v1['id']}", headers=nora).status_code), (404, 404, 404))
    esperar("consultar uno", (c.get(f"{V}/{v1['id']}", headers=rita).json()["placa"], c.get(f"{V}/9999", headers=rita).status_code), ("ABC123D", 404))
    r = editar(rita, v1["id"], {"kilometraje": "50000", "color": "azul"})
    esperar("modificar kilometraje y color", (r.status_code, r.json().get("kilometraje"), r.json().get("color"), r.json().get("customer_id")), (200, 50000, "Azul", maria))
    h = c.get(f"{ADM}/{maria}/historial", headers=rita).json()
    esperar("la modificación queda en el historial con de/a", (h[0]["accion"], "kilometraje de «45000» a «50000»" in h[0]["detalle"], "color" in h[0]["detalle"], "marca" in h[0]["detalle"]), ("ACTUALIZAR_VEHICULO", True, True, False))
    n = len(h)
    editar(rita, v1["id"], {"kilometraje": "50000", "color": "Azul"})
    esperar("guardar sin cambios no genera movimiento", len(c.get(f"{ADM}/{maria}/historial", headers=rita).json()), n)
    esperar("conservar los mismos VIN y placa no es duplicado", editar(rita, v1["id"], {"kilometraje": "50000", "color": "Azul"}).status_code, 200)
    esperar("VIN de otro vehículo -> 409", editar(rita, v1["id"], {"vin": "JH4KA8260MC000000"}).status_code, 409)
    esperar("placa de otro vehículo -> 409", editar(rita, v1["id"], {"placa": "1ab 234"}).status_code, 409)
    esperar("datos inválidos -> 422", (editar(rita, v1["id"], {"vin": "123"}).status_code, editar(rita, v1["id"], {"anio": "1900"}).status_code), (422, 422))
    antes = archivos()
    r = editar(rita, v1["id"], {"kilometraje": "50000", "color": "Azul"}, foto=("n.png", PNG, "image/png"))
    esperar("cambiar la imagen reemplaza el archivo anterior", (r.status_code, len(archivos()), set(archivos()) != set(antes), c.get(f"{V}/{v1['id']}/foto", headers=rita).headers["content-type"]), (200, 3, True, "image/png"))
    esperar("imagen inválida al modificar -> 422 y no deja archivos", (editar(rita, v1["id"], foto=("a.gif", GIF, "image/gif")).status_code, len(archivos())), (422, 3))
    esperar("imagen de más de 15 MB al modificar -> 413", editar(rita, v1["id"], foto=("g.jpg", JPG + b"0" * (15 * 1024 * 1024), "image/jpeg")).status_code, 413)
    # baja lógica
    r = c.delete(f"{V}/{v2}", headers=rita)
    esperar("eliminar es lógico (estado ELIMINADO)", (r.status_code, r.json().get("estado")), (200, "ELIMINADO"))
    with Session(engine) as db:
        esperar("sigue en la base con bin_status 2 y su imagen", (db.get(VehiculoModel, v2).bin_status, len(archivos())), (2, 3))
    esperar("ya no aparece en el listado activo ni en el conteo del cliente", ([x["id"] for x in c.get(V, headers=rita).json()["items"]], {x["id"]: x["vehiculos"] for x in c.get(ADM, headers=rita).json()["items"]}[maria]), ([v1["id"]], 1))
    esperar("aparece al listar eliminados", [x["id"] for x in c.get(f"{V}?estado=ELIMINADO", headers=rita).json()["items"]], [v2])
    esperar("eliminar de nuevo o modificar uno eliminado -> 409", (c.delete(f"{V}/{v2}", headers=rita).status_code, editar(rita, v2, {"vin": "JH4KA8260MC000000", "placa": "1AB234"}).status_code), (409, 409))
    esperar("el VIN de un eliminado sigue ocupado -> 409", alta(rita, {"vin": "JH4KA8260MC000000", "placa": "NEW-123"}).status_code, 409)
    h = c.get(f"{ADM}/{maria}/historial", headers=rita).json()
    esperar("la baja queda en el historial", h[0]["accion"], "ELIMINAR_VEHICULO")
    # restauración
    esperar("otro taller no restaura (404)", c.post(f"{V}/{v2}/restaurar", headers=nora).status_code, 404)
    c.post(f"{ADM}/{maria}/suspender", headers=admin, json={"motivo": "Prueba de restauracion"})
    r = c.post(f"{V}/{v2}/restaurar", headers=rita)
    esperar("con el cliente suspendido no se restaura -> 409", (r.status_code, r.json().get("codigo")), (409, "CLIENTE_SUSPENDIDO"))
    c.post(f"{ADM}/{maria}/reactivar", headers=admin)
    r = c.post(f"{V}/{v2}/restaurar", headers=rita)
    esperar("restaurar deja el vehículo activo", (r.status_code, r.json().get("estado")), (200, "ACTIVO"))
    esperar("restaurar uno activo -> 409", c.post(f"{V}/{v2}/restaurar", headers=rita).status_code, 409)
    esperar("tras restaurar vuelve al listado y al conteo", (c.get(V, headers=rita).json()["total"], {x["id"]: x["vehiculos"] for x in c.get(ADM, headers=rita).json()["items"]}[maria]), (2, 2))
    with Session(engine) as db:
        esperar("auditoría de modificación, baja y restauración", [len(db.scalars(select(AuditoriaModel).where(AuditoriaModel.accion == a)).all()) for a in ("ACTUALIZAR_VEHICULO", "ELIMINAR_VEHICULO", "RESTAURAR_VEHICULO")], [2, 1, 1])

print("\nFALLARON:" if fallos else "\nRESULTADO: TODO OK", fallos if fallos else "")
sys.exit(1 if fallos else 0)
