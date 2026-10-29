"""Prueba de migración: parte de una base con el esquema ANTERIOR (role_definitions y talleres sin las columnas nuevas, con datos) y
comprueba que el arranque la actualiza sin perder filas, que es idempotente y que el sistema funciona después. Usa SQLite temporal.

Ejecución, desde backend/:   python tests/e2e_migracion.py
"""
import os, sys, tempfile

_BASE = tempfile.mkdtemp(prefix="taller_mig_")
RUTA = os.path.join(_BASE, "antigua.db").replace("\\", "/")
os.environ.update(DATABASE_URL="sqlite:///" + RUTA, UPLOADS_DIR=os.path.join(_BASE, "subidas"), JWT_SECRET="x" * 40,
                  BOOTSTRAP_ADMIN_EMAIL="admin@example.com", BOOTSTRAP_ADMIN_PASSWORD="AdminPrueba12345!")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sqlite3
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

fallos = []
def esperar(nombre, real, esperado):
    ok = real == esperado
    print(("OK   " if ok else "FALLA"), nombre, "" if ok else f"-> {real!r} (esperado {esperado!r})")
    if not ok: fallos.append(nombre)

# Esquema anterior de las dos tablas que cambian, con datos reales de ejemplo
antigua = sqlite3.connect(RUTA)
antigua.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, full_name VARCHAR(140) NOT NULL, email VARCHAR(254) NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(15) NOT NULL, branch VARCHAR(100), is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, CONSTRAINT uq_users_email UNIQUE (email));
CREATE INDEX ix_users_email ON users (email);
INSERT INTO users (full_name, email, password_hash, role, branch, is_active, created_at) VALUES ('Rita Antigua', 'rita@example.com', 'hash-antiguo', 'RECEPCIONISTA', 'Taller antiguo', 1, '2026-10-01 10:00:00');
CREATE TABLE role_definitions (id INTEGER PRIMARY KEY, code VARCHAR(40) NOT NULL, name VARCHAR(80) NOT NULL, description VARCHAR(250), created_at DATETIME NOT NULL, CONSTRAINT uq_role_definitions_code UNIQUE (code));
CREATE TABLE talleres (id INTEGER PRIMARY KEY, nombre VARCHAR(100) NOT NULL, activo BOOLEAN NOT NULL, created_at DATETIME NOT NULL, CONSTRAINT uq_talleres_nombre UNIQUE (nombre));
INSERT INTO role_definitions (code, name, description, created_at) VALUES ('VIEJO', 'Rol anterior', 'creado antes del cambio', '2026-10-01 10:00:00');
INSERT INTO talleres (nombre, activo, created_at) VALUES ('Taller antiguo', 1, '2026-10-01 10:00:00');
INSERT INTO talleres (nombre, activo, created_at) VALUES ('Taller antiguo dos', 1, '2026-10-01 10:00:00');
CREATE TABLE customers (id INTEGER PRIMARY KEY, taller_id INTEGER NOT NULL REFERENCES talleres(id), nombre_completo VARCHAR(140) NOT NULL, nombre_clave VARCHAR(140) NOT NULL, contacto VARCHAR(254) NOT NULL, estado VARCHAR(8) NOT NULL, created_at DATETIME NOT NULL, CONSTRAINT uq_customers_taller_contacto UNIQUE (taller_id, contacto));
INSERT INTO customers (taller_id, nombre_completo, nombre_clave, contacto, estado, created_at) VALUES (1, 'Ana Antigua', 'ana antigua', 'ana@correo.com', 'ACTIVO', '2026-10-01 10:00:00');
INSERT INTO customers (taller_id, nombre_completo, nombre_clave, contacto, estado, created_at) VALUES (1, 'Beto Antiguo', 'beto antiguo', '5512345678', 'ACTIVO', '2026-10-01 10:00:00');
""")
antigua.commit(); antigua.close()

from app.main import app
from app.database import engine
from app.migraciones import migrar

with TestClient(app) as c:
    columnas = lambda t: {x["name"] for x in inspect(engine).get_columns(t)}
    esperar("role_definitions recibe bin_status y es_sistema", {"bin_status", "es_sistema"} <= columnas("role_definitions"), True)
    esperar("users recibe role_definition_id y bin_status", {"role_definition_id", "bin_status"} <= columnas("users"), True)
    esperar("talleres recibe domicilio, RFC, foto y bin_status", {"rfc", "email_contacto", "calle", "colonia", "codigo_postal", "estado", "municipio", "foto", "bin_status", "created_by"} <= columnas("talleres"), True)
    esperar("tablas nuevas creadas (status y codigos_postales)", {"status", "codigos_postales"} <= set(inspect(engine).get_table_names()), True)
    esperar("índice único de RFC creado en la tabla antigua", "uq_talleres_rfc" in {i["name"] for i in inspect(engine).get_indexes("talleres")}, True)
    with engine.connect() as conexion:
        esperar("los roles antiguos se conservan, activos y como personalizados", conexion.execute(text("SELECT code, name, bin_status, es_sistema FROM role_definitions WHERE code = 'VIEJO'")).all(), [("VIEJO", "Rol anterior", 1, 0)])
        esperar("se sembraron los 7 roles de fábrica", conexion.execute(text("SELECT count(*) FROM role_definitions WHERE es_sistema = 1")).scalar(), 7)
        esperar("el usuario antiguo se conserva sin rol personalizado", conexion.execute(text("SELECT email, role, role_definition_id, bin_status FROM users WHERE email = 'rita@example.com'")).all(), [("rita@example.com", "RECEPCIONISTA", None, 1)])
        esperar("los talleres antiguos se conservan y quedan activos con RFC vacío", conexion.execute(text("SELECT nombre, activo, bin_status, rfc FROM talleres ORDER BY id")).all(), [("Taller antiguo", 1, 1, None), ("Taller antiguo dos", 1, 1, None)])
        esperar("los clientes antiguos conservan su contacto y lo reparten en correo o teléfono", conexion.execute(text("SELECT nombre_completo, contacto, telefono, correo FROM customers ORDER BY id")).all(),
                [("Ana Antigua", "ana@correo.com", None, "ana@correo.com"), ("Beto Antiguo", "5512345678", "5512345678", None)])
    esperar("índice único de teléfono creado en la tabla antigua", "uq_customers_taller_telefono" in {i["name"] for i in inspect(engine).get_indexes("customers")}, True)
    esperar("segundo arranque no vuelve a migrar (idempotente)", migrar(engine), [])

    admin = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "admin@example.com", "password": "AdminPrueba12345!"}).json()["access_token"]}
    esperar("el rol antiguo aparece en la administración junto a los de fábrica", [r["code"] for r in c.get("/api/roles", headers=admin).json() if not r["es_sistema"]], ["VIEJO"])
    esperar("el rol antiguo ya se puede asignar a un empleado", "VIEJO" in [r["code"] for r in c.get("/api/roles/asignables", headers=admin).json()], True)
    viejo = next(r for r in c.get("/api/roles", headers=admin).json() if r["code"] == "VIEJO")
    r = c.delete(f"/api/roles/{viejo['id']}", headers=admin); esperar("se puede eliminar lógicamente un rol antiguo", (r.status_code, r.json()["bin_status"]), (200, 2))
    esperar("dos talleres antiguos sin RFC no chocan por el índice único", c.get("/api/talleres", headers=admin).json().__len__(), 2)

print("\nRESULTADO:", "TODO OK" if not fallos else f"{len(fallos)} fallos: {fallos}")
sys.exit(1 if fallos else 0)
