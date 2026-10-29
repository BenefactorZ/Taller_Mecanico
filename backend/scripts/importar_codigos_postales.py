"""Importa el Catálogo Nacional de Códigos Postales (Correos de México) a la tabla `codigos_postales`.

Uso, desde backend/:
    python scripts/importar_codigos_postales.py               # importa si la tabla está vacía
    python scripts/importar_codigos_postales.py --reemplazar  # borra el catálogo y lo vuelve a cargar
    python scripts/importar_codigos_postales.py --archivo otra/ruta/CPdescarga.txt

El archivo (CPdescarga.txt, codificación ISO-8859-1, columnas separadas por «|») se descarga de
https://www.correosdemexico.gob.mx/datosabiertos/cp/cpdescarga.txt y se guarda en backend/data/.
Los datos son de Correos de México (uso gratuito y personal): por eso el archivo no se versiona.
"""
import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, delete, func, insert, select  # noqa: E402

from app.catalogos import CodigoPostalModel  # noqa: E402
from app.config import settings  # noqa: E402

LOTE = 5000


def leer(ruta: Path) -> list[dict]:
    filas: dict[tuple, dict] = {}
    with ruta.open(encoding="latin-1") as archivo:
        for linea in archivo:
            campos = linea.rstrip("\r\n").split("|")
            if len(campos) < 5 or not campos[0].isdigit():  # salta el aviso inicial y el encabezado
                continue
            fila = {"codigo_postal": campos[0].zfill(5), "colonia": campos[1].strip(), "tipo_asentamiento": campos[2].strip(),
                    "municipio": campos[3].strip(), "estado": campos[4].strip()}
            filas[tuple(fila.values())] = fila  # descarta renglones idénticos
    return list(filas.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archivo", type=Path, default=BACKEND / "data" / "CPdescarga.txt")
    parser.add_argument("--reemplazar", action="store_true", help="borra el catálogo actual antes de importar")
    args = parser.parse_args()
    if not args.archivo.is_file():
        print(f"No existe {args.archivo}. Descárguelo de https://www.correosdemexico.gob.mx/datosabiertos/cp/cpdescarga.txt")
        return 1

    motor = create_engine(settings.database_url, fast_executemany=True) if settings.database_url.startswith("mssql") else create_engine(settings.database_url)
    CodigoPostalModel.__table__.create(motor, checkfirst=True)
    with motor.begin() as conexion:
        existentes = conexion.scalar(select(func.count()).select_from(CodigoPostalModel)) or 0
        if existentes and not args.reemplazar:
            print(f"El catálogo ya tiene {existentes:,} registros. Use --reemplazar para volver a importarlo.")
            return 0
        filas = leer(args.archivo)
        if not filas:
            print("El archivo no contiene registros válidos; no se modificó nada.")
            return 1
        if existentes:
            conexion.execute(delete(CodigoPostalModel))
        for inicio in range(0, len(filas), LOTE):
            conexion.execute(insert(CodigoPostalModel), filas[inicio:inicio + LOTE])
        total = conexion.scalar(select(func.count()).select_from(CodigoPostalModel))
    print(f"Importados {total:,} asentamientos de {len({f['codigo_postal'] for f in filas}):,} códigos postales.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
