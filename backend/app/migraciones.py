"""Migraciones mínimas e idempotentes. `create_all` crea tablas nuevas, pero no agrega columnas a tablas que ya existen.

Sólo se agregan columnas (nunca se borra ni se modifica nada) y las filas existentes quedan intactas.
"""
from sqlalchemy import Engine, inspect, text

# tabla -> (columna, definición SQL con el tipo y si admite nulos). `bin_status` nace en 1 (activo).
COLUMNAS_NUEVAS: dict[str, list[tuple[str, str]]] = {
    "role_definitions": [("bin_status", "INT NOT NULL DEFAULT 1"), ("es_sistema", "{BOOL} NOT NULL DEFAULT 0")],
    "users": [("role_definition_id", "INT NULL"), ("bin_status", "INT NOT NULL DEFAULT 1")],
    # El cliente ahora tiene teléfono y correo por separado; `contacto` se conserva (es la clave de unicidad histórica)
    "customers": [("telefono", "VARCHAR(15) NULL"), ("correo", "VARCHAR(254) NULL")],
    "talleres": [
        ("rfc", "VARCHAR(13) NULL"), ("email_contacto", "VARCHAR(254) NULL"), ("calle", "VARCHAR(150) NULL"),
        ("colonia", "VARCHAR(120) NULL"), ("codigo_postal", "VARCHAR(5) NULL"), ("estado", "VARCHAR(60) NULL"),
        ("municipio", "VARCHAR(100) NULL"), ("foto", "VARCHAR(80) NULL"), ("bin_status", "INT NOT NULL DEFAULT 1"),
        ("created_by", "INT NULL"),
    ],
}
# claves foráneas que se agregan aparte (SQLite no admite ALTER ... ADD CONSTRAINT)
FOREIGNES = [("role_definitions", "bin_status", "status"), ("talleres", "bin_status", "status"), ("talleres", "created_by", "users"),
             ("users", "role_definition_id", "role_definitions"), ("users", "bin_status", "status")]
INDICES_NUEVOS = ("talleres", "customers")  # tablas donde un índice nuevo (RFC o teléfono únicos) se debe crear aunque la tabla ya existiera


def _definicion(motor: Engine, definicion: str) -> str:
    definicion = definicion.replace("{BOOL}", "BIT" if motor.dialect.name == "mssql" else "BOOLEAN")
    if motor.dialect.name == "mssql":
        return definicion.replace(" DEFAULT ", " CONSTRAINT {df} DEFAULT ")
    return definicion


def migrar(motor: Engine) -> list[str]:
    """Aplica las migraciones pendientes y devuelve lo que hizo (vacío si no había nada que hacer)."""
    hechos: list[str] = []
    with motor.begin() as conexion:
        inspector = inspect(conexion)
        tablas = set(inspector.get_table_names())
        for tabla, columnas in COLUMNAS_NUEVAS.items():
            if tabla not in tablas:
                continue  # la tabla es nueva: create_all ya la crea completa
            existentes = {c["name"] for c in inspector.get_columns(tabla)}
            for columna, definicion in columnas:
                if columna in existentes:
                    continue
                sql = _definicion(motor, definicion).replace("{df}", f"DF_{tabla}_{columna}")
                conexion.execute(text(f"ALTER TABLE {tabla} ADD {columna} {sql}"))
                hechos.append(f"{tabla}.{columna}")
        if "customers.telefono" in hechos or "customers.correo" in hechos:
            # Los clientes existentes sólo tenían «contacto»: se reparte en el campo que corresponde (sin borrar nada)
            conexion.execute(text("UPDATE customers SET correo = contacto WHERE correo IS NULL AND contacto LIKE '%@%'"))
            conexion.execute(text("UPDATE customers SET telefono = contacto WHERE telefono IS NULL AND contacto NOT LIKE '%@%'"))
            hechos.append("customers: contacto repartido en teléfono y correo")
        if motor.dialect.name == "mssql":
            inspector = inspect(conexion)
            for tabla, columna, destino in FOREIGNES:
                if tabla not in tablas:
                    continue
                ya = any(columna in (f["constrained_columns"] or []) for f in inspector.get_foreign_keys(tabla))
                if not ya:
                    conexion.execute(text(f"ALTER TABLE {tabla} ADD CONSTRAINT FK_{tabla}_{columna} FOREIGN KEY ({columna}) REFERENCES {destino}(id)"))
                    hechos.append(f"FK {tabla}.{columna}")
        # create_all no agrega índices a tablas que ya existían (p. ej. el RFC único del taller)
        from .database import Base
        inspector = inspect(conexion)
        for tabla in INDICES_NUEVOS:
            if tabla in tablas and tabla in Base.metadata.tables:
                presentes = {i["name"] for i in inspector.get_indexes(tabla)}
                for indice in Base.metadata.tables[tabla].indexes:
                    if indice.name not in presentes:
                        indice.create(conexion)
                        hechos.append(f"índice {indice.name}")
    return hechos
