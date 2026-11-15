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
