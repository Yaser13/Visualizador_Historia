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

## Selección de ubicaciones — 2026-11-15

La API expone referencias modernas aproximadas y fuentes de ubicación para Roma, Veyes y Cartago; Sicilia queda sin punto. React muestra la fuente geográfica y centra el globo en el marcador seleccionado, sin dibujar límites históricos. Los datos históricos conservan el estado `under_review`. `manage.py test stories`: 3 pruebas satisfactorias, incluyendo rangos, procedencia y ausencia de punto para Sicilia. `npm run build`: satisfactorio, con aviso por tamaño del módulo del globo. Sin prueba visual real de colocación o interacción; pendiente comprobar en navegador, contraste histórico adicional y OpenAPI.

## Diseño centrado en el globo — 2026-11-15

A petición del usuario se priorizó el globo, con acercamiento a ubicaciones documentadas, una ficha breve, fuentes desplegables y cronología. Se añadieron controles para girar y acercar/alejar; Sicilia utiliza una vista general sin marcador. Los iconos de ejércitos y rutas siguen pendientes de datos verificables, sin posiciones inventadas. Agentes React, globo y QA trabajaron sobre áreas separadas. Validación integrada: `npm run build` y tres pruebas Django satisfactorias; Vite advierte de un módulo 3D superior a 500 kB. QA examinó capturas Edge headless en 1440×900 y 390×844 con renderizado software, seleccionó Sicilia, abrió fuentes y comprobó ausencia de desbordamiento horizontal; no se probaron lector de pantalla ni gestos táctiles físicos.

## Dirección visual tipo atlas — 2026-11-15

Se adaptó la presentación a la referencia aportada por el usuario: mapa dominante, paleta oscura, panel histórico, cronología y etiquetas geográficas. El globo conserva costas modernas, retícula y marcadores aproximados con procedencia. No se han añadido modelos de terreno, ciudades, ejércitos ni movimientos históricos por falta de datos y activos verificados. React y globo trabajaron en archivos separados; QA verificó build, tres pruebas Django, capturas Edge headless de escritorio y móvil, selección de Sicilia y acceso a fuentes. La etiqueta de Roma coincide con el marcador en la captura. Las pruebas visuales usan renderizado por software; la experiencia con lector de pantalla y gestos táctiles físicos sigue pendiente. El módulo 3D supera el aviso de tamaño de Vite.

## Cambio de enfoque: informante geopolitico — 2026-11-15

El usuario solicita sustituir el foco historico por noticias geopoliticas contextualizadas de forma neutral y visualizadas en el globo. Los registros anteriores se conservan como historial del proyecto; las tareas de Roma no definen la mision actual. La primera iteracion debe seleccionar una noticia trazable, distinguir fecha del evento y publicacion, hechos atribuidos, analisis e incertidumbre, y representar solo ubicaciones documentadas. Los perfiles actuales estan en `.codex/agents/` y los documentos originales de `agents/` permanecen como legado.

| ID | Prioridad | Responsable | Dependencias | Estado | Criterio de aceptacion |
|---|---|---|---|---|---|
| GEO-01 | P0 | geopolitical_research | ninguna | en curso | Seleccionar una noticia actual, comprobar fuentes independientes disponibles, fechas, atribucion, incertidumbres y ubicacion. |
| GEO-02 | P0 | django_backend / django_developer | GEO-01 para contenido | en curso | Adaptar el contrato y entrega de datos con fuentes, fechas, analisis diferenciado y precision geografica; probar API y errores. |
| GEO-03 | P0 | react_architect / react_frontend / globe_3d | contrato GEO-02 | en curso | Visualizar noticia, ubicacion e icono de categoria, fuente y analisis claramente separados; conservar accesibilidad y estados. |
| GEO-04 | P0 | qa_testing | GEO-01–GEO-03 | pendiente | Verificar fuentes, fechas, ausencia de afirmaciones y geometrias inventadas, integracion, responsividad y comportamiento accesible. |

Los estados se actualizaran solo con evidencia revisada. Las fuentes independientes son deseables cuando esten disponibles; cualquier limitacion se declara. Los reportes previos son evidencia de versiones historicas, no de la nueva implementacion.

## Primera entrega geopolítica — 2026-11-15

Se creó una instantánea sobre la apertura de COP31 en Antalya, respaldada por AP y la agenda de UNFCCC, con coordenada de ciudad de UNGEGN, corte y limitaciones en `docs/geopolitica/COP31_FUENTES.md`. La API `GET /api/stories/geopolitica/` y React muestran hechos, análisis atribuido y ubicación aproximada; la API de Roma se conserva. Los datos son estáticos y no existe ingesta ni actualización automática. Se actualizaron `AGENTS.md` y perfiles `.codex/agents/`, manteniendo `agents/` como legado. Validación: 4 pruebas Django y compilación frontend satisfactorias; QA en Edge headless con renderizado por software revisó escritorio/móvil, fuentes, fechas, icono, error/reintento, proxy y ausencia de desbordamiento. No se probaron lector de pantalla, gestos táctiles físicos ni GPU real; queda pendiente OpenAPI y una solución de actualización de noticias. GEO-01–GEO-03 entregadas para esta instantánea; GEO-04 en revisión hasta completar los controles pendientes.

## Persistencia documental — 2026-11-15

Se añadieron modelos relacionales y administración para acontecimientos, fuentes, afirmaciones, evidencia, actores, participaciones, efectos y ubicaciones. El comando `seed_cop31` carga una instantánea con procedencia sin sobrescribir registros existentes; la API geopolítica lee afirmaciones sustentadas desde la base. Se aplicaron migraciones localmente y se cargaron 1 acontecimiento, 8 afirmaciones, 4 fuentes, 5 actores, 3 participaciones, 1 ubicación y 0 efectos; la API local respondió 200. En pruebas SQLite temporales pasan las comprobaciones de modelos, API, evidencia y carga repetida; el frontend compila. La entrada de noticias por usuario, búsqueda externa, extracción, revisión editorial y actualización automática siguen pendientes; el ORM directo puede eludir `full_clean`, por lo que aún falta un servicio de publicación que garantice integridad entre tablas.

La interfaz ahora muestra actores y papeles, afirmaciones con su fuente y efectos cuando existan. Para la COP31 no se registraron efectos ni valoraciones por falta de evidencia individualizada; las declaraciones y análisis se presentan separados. Tras el ajuste de la siembra, si ya existe el acontecimiento el comando no modifica ni repara sus registros.

## Conflicto armado con iconos y cronología actualizable — 2026-11-15

A petición del usuario se añadió la noticia «Guerra en Sudán» (10 hitos, 2023-04-15 a 2026-10-21, 32 fuentes) como cronología actualizable, y el globo muestra todos los hitos como iconos de categoría. Contrato: `docs/api/CONTRATO_CRONOLOGIAS.md`; iconos: `frontend/src/categories.ts` e `icons.tsx`; fuentes: `docs/geopolitica/SUDAN_FUENTES.md`.

| ID | Responsable | Estado | Evidencia |
|---|---|---|---|
| GEO-10 | geopolitical_research | terminada | JSON y documento de fuentes; `load_timeline --dry-run` correcto; revisión del orquestador: hechos/declaraciones atribuidos, sin cifras sin localizador. Huecos registrados (Kordofán 2026, AP/Reuters no legibles directamente). |
| GEO-11 | django_backend / django_developer | terminada | `load_timeline` incremental, `GET /api/stories/`, migración 0004; `manage.py test stories`: 37 OK (verificado por el orquestador). Carga real: 10 hitos; recarga: 0 creados. |
| GEO-12 | globe_3d | terminada | Iconos sprite por categoría, agrupación, oclusión, estados activo/pasado/futuro, clic para seleccionar, `prefers-reduced-motion`; sin líneas ni áreas. |
| GEO-13 | react_architect / react_frontend | terminada | Selector dinámico, barra temporal proporcional, reproducción, teclado, leyenda; build y lint correctos. |
| GEO-14 | qa_testing | en curso | Verificación integrada en navegador headless. |

## Misión: usuarios y noticias enviadas con análisis por agentes — 2026-11-15

El usuario solicita inicio de sesión con información personal, envío de enlaces de noticias por los usuarios y un grupo de agentes con la API de OpenAI que recoja información relacionada, la analice y la almacene con referencias, sin inventar contenido. Contrato: `docs/api/CONTRATO_USUARIOS_INGESTA.md`. Decisiones del orquestador: cita literal verificada de forma determinista para toda afirmación; análisis de IA etiquetado y atribuido; borrador con revisión de staff antes de publicar; cola en base de datos con trabajador `process_submissions`; coordenadas solo de Nominatim/OSM con atribución; secretos por entorno. No hay `OPENAI_API_KEY` en el entorno: las pruebas usan cliente simulado.

| ID | Prioridad | Responsable | Depende de | Estado | Aceptación |
|---|---|---|---|---|---|
| USR-01 | P0 | django_backend / django_developer | contrato | en curso | Perfiles, autenticación por sesión con CSRF, modelos de ingesta, API de envíos y revisión, origen en `stories`; pruebas de permisos y aislamiento. |
| ING-01 | P0 | django_developer / data_engineer | contrato; modelos USR-01 | en curso | Descarga con SSRF, búsqueda relacionada, agentes extractor/verificador/geolocalizador/analista, verificación determinista de citas, persistencia en borrador; pruebas sin red. |
| USR-02 | P0 | react_architect / react_frontend | contrato | en curso | Sesión, perfil, enviar noticia, mis envíos con estado por pasos, revisión staff, insignia de IA; accesible y responsive. |
| USR-03 | P0 | qa_testing | USR-01, ING-01, USR-02 | pendiente | Flujo integrado de registro → envío → proceso simulado → revisión → publicación en el globo; seguridad (CSRF, aislamiento, SSRF) y regresión. |
