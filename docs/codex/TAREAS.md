# Tareas y primera mision

Una tarea contiene ID, prioridad (P0 imprescindible, P1 siguiente, P2 mejora), estado (pendiente, en curso, bloqueada, terminada), responsable, dependencias, alcance, aceptacion y validacion. Una dependencia se considera resuelta solo con evidencia revisada. El orquestador registra bloqueos y asigna archivos sin solapamientos. Los contratos de entrada y entrega estan en `docs/codex/CONTRATOS.md`.

## Mision: globo y cronologia de Roma - preparacion

Objetivo: preparar una demostracion de un globo 3D con linea temporal de expansion romana. Sus formas y fechas sinteticas son ilustrativas, no reconstrucciones historicas ni afirmaciones verificadas. No hay aplicacion implementada en la rama analizada.

| ID | Prioridad | Responsable | Depende de | Estado | Aceptacion y validacion |
|---|---|---|---|---|---|
| T1 | P0 | orchestrator | ninguna | pendiente | Inspeccionar codigo real, dependencias y decidir alcance; registrar arquitectura y comandos comprobados. |
| T2 | P0 | historical_research | T1 | pendiente | Identificar evidencia y licencias disponibles, o declarar falta de fuentes; separar explicitamente datos ficticios. Revisar referencias. |
| T3 | P0 | data_engineer | T1 | pendiente | Acordar esquema de muestras, intervalos, anos y GeoJSON; indicar datos sinteticos y validar geometrias. |
| T4 | P0 | django_backend, django_developer | T3 | pendiente | Definir e implementar contrato y entrega de muestras en el backend acordado; verificar contrato y errores. |
| T5 | P0 | globe_3d | T3 | pendiente | Disenar e implementar globo y representacion sintetica con interfaz acordada; verificar geometrias y recursos. |
| T6 | P0 | react_architect, react_frontend | T3, contrato T4, interfaz T5 | pendiente | Implementar linea temporal accesible y conectarla al globo; distinguir demostracion y comprobar estados y teclado. |
| T7 | P0 | qa_testing | T2-T6 | pendiente | Verificar flujo integrado, cronologia, datos y senalizacion; registrar resultados y limitaciones. |

T2 y T3 pueden ejecutarse simultaneamente tras T1. T4 y T5 pueden avanzar en paralelo despues de T3 si no comparten archivos. T6 necesita contratos estables; T7 valida la integracion. No se necesita ejecutar tareas ficticias ni crear datos sin la implementacion que los consuma.

## Inicio de la historia de Roma — 2026-11-15

El usuario eligió la expansión de Roma. H1 queda resuelta para el tema; el periodo inicial propuesto es República–Principado. H2 está en curso: se registraron fuentes y cinco hitos candidatos en `docs/historia/ROMA_FUENTES.md`, pendientes de contraste y coordenadas. H3 está en curso: propuesta de contrato en `docs/api/CONTRATO_HISTORIA_PROPUESTO.md`, sin API implementada. Node v24.14.0 y npm 11.9.0 responden; `python --version` no encuentra una instalación funcional, aunque `uv` está disponible. No se ha ejecutado aplicación ni pruebas. Siguiente paso: completar contrato y datos, preparar Python/Django y crear el primer recorrido integrado.

## Backend inicial — 2026-11-15

Se creó `backend/` con Django 6.1.3 y el endpoint de lectura de Roma, con cinco hitos estáticos y en revisión; las coordenadas son nulas. `manage.py check` pasó y `manage.py test stories` pasó 3 pruebas. No existen modelos históricos ni integración frontend; H2, H3 y H4 siguen en curso. Los comandos de arranque están en `backend/README.md`.

## Interfaz inicial — 2026-11-15

La plantilla React se sustituyó por una cronología y un panel de detalle que consumen la API mediante el proxy de desarrollo Vite. Se muestran enlaces a fuentes y aviso de revisión; las ubicaciones no verificadas no se representan en un mapa. Se comprobó `npm run build`, `manage.py test stories` (3 pruebas) y una solicitud a la API a través del servidor Vite (5 hitos). No se realizó comprobación visual en navegador ni pruebas de accesibilidad completas. El globo 3D, la verificación de coordenadas, OpenAPI y pruebas integradas de interacción siguen pendientes.

## Globo inicial — 2026-11-15

Se añadió una esfera 3D interactiva en React, cargada de forma diferida con Three.js. El mapa base representa costas modernas simplificadas, no territorios históricos; no contiene marcadores ni conecta la selección temporal a ubicaciones todavía. Fuente: `world-atlas` 2.0.2, `land-110m.json`, derivado de Natural Earth 4.1.0, escala 1:110 millones; paquete distribuido bajo licencia ISC. Los derechos de los datos originales deben revisarse antes de una publicación externa. Hay controles por botones y un mensaje alternativo ante fallos de WebGL. La cronología sigue siendo la alternativa textual. Compilación Vite correcta; el módulo diferido supera el aviso de 500 kB (aprox. 609 kB, 160 kB gzip). `npm run lint` informó una advertencia sobre el estado de error de WebGL en el efecto; no hubo errores. Se verificó que el archivo TopoJSON contiene una colección con geometría MultiPolygon. No se ha comprobado visualmente ni en navegador real el renderizado, la interacción o el fallo de WebGL. Pendientes: comprobar esas interacciones y accesibilidad; verificar coordenadas históricas y enlazar selección y globo.
