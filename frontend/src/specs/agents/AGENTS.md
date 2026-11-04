# Guía del repositorio

## Estructura del proyecto y organización de módulos

`backend/app/` contiene la aplicación FastAPI, los modelos de SQLAlchemy, la configuración y los módulos funcionales (`customers/`, `talleres/`, `vehiculos/`). Los scripts de extremo a extremo del backend están en `backend/tests/` y las utilidades de importación de datos en `backend/scripts/`. `frontend/src/` contiene la aplicación Vue 3 y TypeScript, con componentes compartidos en `components/` y pantallas en `views/`. `docs/` incluye la documentación y los diagramas de patrones de diseño; `analisis/` contiene notas y diagramas de flujos. Mantenga el código de cada funcionalidad en su módulo y actualice la documentación relacionada cuando cambie el comportamiento.

## Comandos de compilación, pruebas y desarrollo

Ejecute los comandos del backend desde `backend/` y los del frontend desde `frontend/`.

- `python -m pip install -r requirements.txt` instala las dependencias de la API.
- `uvicorn app.main:app --reload --port 8000` inicia la API local.
- `python -m pip install -r requirements-dev.txt` instala las dependencias de pruebas de la API.
- `python tests/e2e_clientes.py` ejecuta el flujo de la API de clientes; los demás scripts `e2e_*.py` cubren roles, permisos, empleados, talleres, vehículos y migraciones.
- `npm install` instala los paquetes del frontend; `npm run dev` inicia Vite.
- `npm run build` ejecuta las comprobaciones de Vue/TypeScript y crea la compilación de producción en `frontend/dist/`.

## Estilo de código y convenciones de nombres

Siga las convenciones existentes: los módulos y las funciones de Python usan `snake_case`, los componentes de Vue usan nombres de archivo en PascalCase (por ejemplo, `FotoTaller.vue`) y las utilidades de TypeScript usan nombres descriptivos acordes con los archivos cercanos. Mantenga la validación y autorización de la API en el backend, aunque el frontend también valide o proteja rutas. No hay formateador ni linter configurados en los scripts del paquete; limite los cambios al alcance necesario y respete el formato circundante.

## Guía de pruebas

Las pruebas de integración del backend son scripts independientes `backend/tests/e2e_*.py` y usan bases de datos SQLite temporales de forma predeterminada. Ejecute los scripts pertinentes después de cambiar el comportamiento de la API; use `E2E_DATABASE_URL` solo con una base de datos exclusiva para pruebas. La verificación del frontend se realiza con `npm run build`, que incluye `vue-tsc -b`; no hay un script de pruebas independiente configurado para el frontend.

## Guía de commits y solicitudes de extracción

El historial disponible usa asuntos generales, sin una convención consistente. Para nuevos commits, prefiera un asunto breve en imperativo y con alcance, como `backend: validar códigos postales de talleres`. Las solicitudes de extracción deben explicar el cambio visible para la persona usuaria, enumerar los comandos y resultados de validación, enlazar trabajo relacionado cuando exista e incluir capturas para cambios de interfaz. Indique explícitamente los cambios de base de datos o configuración.

## Seguridad y configuración

Guarde los secretos en el archivo ignorado `backend/.env`; nunca incluya credenciales ni datos de producción en el repositorio. Use una base de datos independiente para pruebas al definir `E2E_DATABASE_URL` y no dirija pruebas o experimentos de migración al entorno de producción.
