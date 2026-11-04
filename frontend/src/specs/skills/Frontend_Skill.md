# Frontend_Skill.md

## Objetivo
Desarrollar vistas y componentes Vue 3 mantenibles, tipados, accesibles y coherentes con Vuetify 3.

## Principios Obligatorios
- Composition API con script setup
- TypeScript estricto sin any
- DRY
- KISS
- Separación de responsabilidades
- Componentes de una sola responsabilidad
- Props hacia abajo y eventos hacia arriba
- Validación espejo del backend
- Toda llamada HTTP por api.ts
- Permisos con tienePermiso
- Vuetify antes que HTML propio

## Estructura de Proyecto
```text
Taller_Mecanico/
├── .archify/
├── .chicory/
├── .claude/
├── analisis/
├── backend/
├── docs/
├── frontend/
│   └── src/
│       ├── specs/         # agentes, orquestador y skills
│       ├── views/
│       ├── components/
│       ├── api.ts         # único acceso HTTP
│       ├── auth.ts
│       ├── router.ts
│       ├── types.ts       # tipos de la API y tienePermiso
│       ├── modules.ts     # módulos del panel
│       ├── clientes.ts, vehiculos.ts, talleres.ts   # validaciones
│       └── styles.css
├── tools/
├── .gitignore
└── README.md
```


## Reglas Vue
### Vistas y componentes
- Una vista por ruta.
- Un componente con una sola responsabilidad.
- Sin reglas de negocio en la plantilla.
- Las reglas y validaciones van en el módulo del dominio.
- Sin fetch directo, siempre api().
- Props hacia abajo, eventos hacia arriba.
- Lo reutilizable va a components/

### Inyección de dependencias
- Datos y comportamiento por props y emits.
- provide/inject solo para contexto compartido en un árbol profundo.
- Lógica reutilizable en composables useXxx.
- Sin instanciar clases ni servicios dentro de los componentes.
- Acceso HTTP y sesión solo desde api.ts y auth.ts.

### Validación
- Reglas en el módulo del dominio.
- Mismas reglas que el backend.
- Validar con :rules antes de enviar.
- Normalizar antes de enviar.
- Tipar la respuesta de la API.

## Datos y Rendimiento
- Paginar todos los listados.
- Buscar con retardo (debounce).
- Pedir solo lo necesario.
- Sin llamadas repetidas en bucle.
- Cargar una vez y reutilizar.

### Acceso a la API
- Un solo cliente HTTP, api.ts.
- Un módulo por dominio.
- Manejar errores en un solo lugar.
- Sesión y token solo en auth.ts.

### Optimización
- Medir antes de optimizar.
- Minimizar peticiones al servidor.
- Cargar de forma diferida lo pesado.
- Evitar renders innecesarios.

## Seguridad
- JWT solo en auth.ts.
- Sin secretos en el código del cliente.
- URL del servidor por variable de entorno.
- Permisos con tienePermiso y meta.permiso.
- Sin v-html con datos de usuario.

## Errores y Logging
- Capturar los errores de cada llamada a la API.
- Mostrar al usuario un mensaje claro.
- Sin console.log en el código final.
- Sin datos sensibles en los mensajes.

## Testing
### Obligatorio hoy
- vue-tsc sin errores.
- Probar en el navegador el flujo feliz, el error y el vacío.
### Meta
- Unit Tests de las reglas de validación.
- Unit Tests de componentes reutilizables.

## Convenciones IA
Cuando una IA genere código frontend:
1. Analizar el requerimiento.
2. Leer una vista parecida y seguir su patrón.
3. Definir los tipos en types.ts.
4. Escribir las reglas en el módulo del dominio.
5. Crear la vista o el componente.
6. Registrar la ruta con meta.permiso y el menú.
7. Probar con vue-tsc y en el navegador.
8. Revisar seguridad y responsivo.
9. Entregar el resultado final.

## Checklist
- [ ] Composition API y TypeScript sin any
- [ ] Componentes de una sola responsabilidad
- [ ] Validación igual al backend
- [ ] Errores capturados y mensajes claros
- [ ] vue-tsc sin errores
- [ ] Probado en el navegador
- [ ] Permisos en ruta y menú
- [ ] Responsivo
- [ ] Documentación
