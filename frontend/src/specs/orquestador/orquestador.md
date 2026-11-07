---
name: orquestador
description: Coordina tareas del sistema Taller Mecanico mediante las guías de backend, frontend, pruebas y documentación.
metadata:
  short-description: Coordina cambios del proyecto
---

# Orquestador de desarrollo

## Propósito

Convertir cada solicitud en trabajo controlado, limitado a su alcance y alineado con las reglas vigentes del repositorio. Este documento coordina las guías; no sustituye sus reglas especializadas.

## Fuentes de verdad

Leer las fuentes que correspondan al cambio antes de editar código:

| Área | Documento | Cuándo aplicarlo |
| --- | --- | --- |
| Reglas del repositorio | [AGENTS.md](../agents/AGENTS.md) | Siempre: estructura, comandos, pruebas y seguridad. |
| Backend | [Python/FastAPI](../skills/Python_FastAPI_Best_Practices_Skill.md) | FastAPI, SQLAlchemy, SQL Server, seguridad, API o pruebas. |
| Frontend general | [Skill_Vue.md](../frontend/Skill_Vue.md) | Patrones de Vue 3, TypeScript y composición de componentes. |
| Documentación backend | [Guía backend](../documentacion/backend/documentacion-backend.md) | Cambios documentales de API, servicios o datos. |
| Documentación frontend | [Guía frontend](../documentacion/frontend/documentacion-frontend.md) | Cambios documentales de componentes, rutas o UI. |
| Plan y análisis funcional | [Plan de trabajo](../../../../docs/plan_estructura_de_trabajo.md) y [análisis](../../../../analisis/) | Cambios que afecten fases, reglas de negocio o decisiones del proyecto. |

En caso de conflicto, prevalecen las instrucciones explícitas de la persona usuaria, seguidas de `AGENTS.md`, las reglas de dominio y las guías técnicas específicas.

## Uso

Invocar explícitamente con `$orquestador` antes o junto con una solicitud del proyecto. Aplicar sólo las fuentes de verdad que correspondan al alcance de esa solicitud.

## Reglas de operación

1. Ejecutar exclusivamente lo solicitado y conservar los cambios ajenos presentes en el árbol de trabajo.
2. Confirmar el alcance, las restricciones, las entidades afectadas y la fuente de datos antes de implementar.
3. No inventar endpoints, modelos, permisos ni propiedades; reutilizar los patrones y contratos existentes.
4. Aplicar validaciones equivalentes en frontend y backend cuando haya entrada de usuario.
5. Tratar al backend como autoridad de autenticación, autorización y reglas de negocio; la protección de rutas SPA nunca reemplaza la validación del servidor.
6. No exponer secretos, datos personales ni credenciales en código, documentación o salidas de prueba.
7. No usar la base de datos real para pruebas. Las migraciones deben ser aditivas, idempotentes y ejecutarse sólo cuando se soliciten.
8. Actualizar la documentación relacionada únicamente cuando el comportamiento entregado cambie.

## Flujo de trabajo

### 1. Comprensión

- Extraer objetivo, actores, reglas, restricciones y criterios de aceptación.
- Identificar el tipo de cambio: backend, frontend, datos, seguridad, documentación o pruebas.
- Revisar los módulos y documentos relacionados antes de proponer cambios.

### 2. Diseño

- Delimitar archivos, contratos, validaciones y riesgos.
- Definir autorización por petición y protección de rutas cuando aplique.
- Elegir pruebas proporcionales al impacto: unitarias, integración, extremo a extremo, build y revisión en navegador.

### 3. Ejecución

- Implementar sólo los elementos aprobados por el alcance.
- Mantener la separación entre API, dominio, persistencia y presentación.
- Mostrar errores y confirmaciones del formulario cerca de la acción que los origina.

### 4. Validación

- Ejecutar las pruebas pertinentes en entornos aislados.
- Compilar el frontend con `npm run build` cuando cambie TypeScript o Vue.
- Verificar que una URL directa no eluda autenticación ni autorización.
- Revisar que la documentación, rutas y enlaces modificados sigan siendo coherentes.

## Entrega

La respuesta final debe indicar, de forma breve:

- qué se hizo y las decisiones relevantes;
- cómo probarlo;
- qué se verificó y con qué comandos o evidencias;
- riesgos o pendientes reales.

## Seguimiento

| Fase | Resultado esperado | Estado |
| --- | --- | --- |
| Análisis | Alcance y reglas identificados | Pendiente |
| Diseño | Archivos, contratos y riesgos definidos | Pendiente |
| Ejecución | Cambio limitado al alcance | Pendiente |
| Validación | Pruebas y controles aplicables ejecutados | Pendiente |
| Entrega | Documentación y resumen actualizados cuando corresponda | Pendiente |



