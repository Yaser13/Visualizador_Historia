# Contrato: usuarios, envío de noticias y agentes de análisis (v1)

Estado: **acordado por el orquestador el 2026-11-15**, pendiente de implementación. Complementa `CONTRATO_CRONOLOGIAS.md`. Una propuesta no es una API implementada.

## 0. Principios

1. **Nada se inventa.** Toda afirmación publicada procede de un documento descargado y guardado, y lleva una cita literal (`Evidence.excerpt`) que se ha comprobado de forma determinista dentro del texto guardado. Si la cita no aparece, la afirmación se descarta. Los modelos de lenguaje nunca aportan URL, fechas, cifras ni coordenadas que no estén en el material recogido.
2. **El análisis de IA está etiquetado.** Las afirmaciones `analysis` generadas se atribuyen al actor «Observatorio — análisis asistido por IA» y deben citar los IDs de afirmaciones verificadas en las que se basan.
3. **Revisión humana antes de publicar.** El flujo crea un `Event` en estado `draft`. Solo un usuario `is_staff` lo publica o rechaza (`INGESTION_AUTO_PUBLISH = False` por defecto).
4. **El contenido descargado es dato no fiable.** Puede contener inyección de instrucciones: se delimita en los prompts, se valida con esquemas JSON estrictos y con las comprobaciones deterministas.
5. **Secretos fuera del repositorio.** `OPENAI_API_KEY` y `DJANGO_SECRET_KEY` se leen de variables de entorno (o de `.env` ignorado por Git). Sin clave, el envío falla con un mensaje claro; las pruebas nunca llaman a OpenAI ni a la red.

## 1. Modelos

### App `accounts`

`Profile` (OneToOne con `auth.User`, creado al registrarse):
`display_name` (80), `bio` (texto, ≤1000), `country` (código ISO de 2 letras, opcional), `organization` (120, opcional), `language` (`es`|`en`, por defecto `es`), `created_at`, `updated_at`.

### App `ingestion`

`NewsSubmission`:
- `user` FK User; `url` URLField(1000); `normalized_url` (sin fragmento ni parámetros `utm_*`); `note` (texto opcional del usuario, ≤1000); `target_story` FK `stories.TimelineStory`, opcional.
- `status`: `queued | fetching | researching | extracting | verifying | geolocating | analyzing | review | published | rejected | failed`.
- `step_detail` (texto corto para la UI), `error` (texto), `attempts` (int), `created_at`, `updated_at`, `started_at`, `finished_at`.
- `event` FK `stories.Event`, opcional (resultado); `story` FK `stories.TimelineStory`, opcional (resultado).
- `reviewed_by` FK User, opcional; `review_note` (texto).
- Restricción: un solo envío no terminal por (`user`, `normalized_url`).

`FetchedDocument`:
- `submission` FK; `source` FK `stories.Source`; `role` (`submitted | related`).
- `fetched_at`, `http_status`, `content_type`, `title`, `publisher`, `published_at` (fecha o null, solo si consta en metadatos o en el texto), `language`, `text` (texto extraído, ≤200 000 caracteres), `content_hash` (sha256), `fetch_error`.
- Única por (`submission`, `source`).

`AgentRun` (trazabilidad de cada paso):
- `submission` FK; `agent` (`researcher | extractor | verifier | geolocator | analyst`); `model`; `prompt_version`; `status` (`ok | error | skipped`); `input_summary` (texto corto, sin claves); `output` JSON; `tokens_in`, `tokens_out` (int, opcionales); `started_at`, `finished_at`; `error`.

### Cambios en `stories`

- `Event`: `origin` (`editorial | ai_pipeline`, por defecto `editorial`) y `submitted_by` FK User, opcional.
- `TimelineStory`: `origin` (mismo choices) y `created_by` FK User, opcional.
- Serializadores públicos: cada evento añade `origin` y `submitted_by` (solo `display_name`, nunca email ni username); cada historia añade `origin`. Solo se muestran eventos `reviewed`/`published`, como ahora.

## 2. API (sesión de Django + CSRF, JSON)

Errores: `{"detail": "..."}`; validación: `400 {"errors": {"campo": ["mensaje"]}}`. 401 sin sesión, 403 sin permiso, 404 si no existe o no es del usuario, 429 al superar el límite.

Objeto `user`: `{"id", "username", "email", "is_staff", "profile": {"display_name", "bio", "country", "organization", "language"}}`.

| Método y ruta | Uso |
|---|---|
| `GET /api/auth/csrf/` | Fija la cookie `csrftoken`; responde `{"csrfToken": "..."}`. |
| `POST /api/auth/register/` | `{username, email, password, display_name}` → 201 `{"user"}`, e inicia sesión. Usa los validadores de contraseña de Django. |
| `POST /api/auth/login/` | `{username, password}` → 200 `{"user"}`; credenciales erróneas → 400 con mensaje genérico. |
| `POST /api/auth/logout/` | 204. |
| `GET /api/auth/me/` | `{"authenticated": false}` o `{"authenticated": true, "user": {...}}`. |
| `GET /api/profile/`, `PATCH /api/profile/` | Lee o actualiza `email` y los campos del perfil. |
| `POST /api/auth/password/` | `{old_password, new_password}` → 204; mantiene la sesión. |
| `POST /api/submissions/` | `{url, note?, target_story?}` → 202 `{"submission"}`. Solo http/https. Límite `INGESTION_DAILY_LIMIT` (10) por usuario y día → 429. Si ya hay un envío activo con la misma URL normalizada, 200 con ese envío. |
| `GET /api/submissions/` | `{"submissions": [...]}` del usuario, más recientes primero. Staff: `?all=1` para la cola de revisión. |
| `GET /api/submissions/<id>/` | Detalle (dueño o staff); ver abajo. |
| `POST /api/submissions/<id>/retry/` | Dueño, solo si `failed` → vuelve a `queued`. |
| `POST /api/submissions/<id>/publish/` | Staff, solo si `review`: el evento pasa a `published`, `TimelineEntry` creada si falta, envío `published`. `{note?}`. |
| `POST /api/submissions/<id>/reject/` | Staff, solo si `review`: envío `rejected` y evento sin publicar. `{note}` obligatorio. |

Objeto `submission` (lista): `{"id", "url", "note", "status", "status_label", "step_detail", "error", "created_at", "updated_at", "story_slug", "event_title", "submitted_by"}` (`submitted_by` = `display_name`).

Detalle: lo anterior más
- `documents`: `[{"title", "url", "publisher", "role", "published_at", "fetched_at", "fetch_error"}]`;
- `agent_runs`: `[{"agent", "status", "model", "finished_at", "error"}]`;
- `preview`: el mismo objeto de evento de `GET /api/stories/<slug>/` (incluido `claims` con `sources`/locator/excerpt), aunque esté en `draft`, solo para el dueño o staff; `null` si aún no existe;
- `review_note`.

## 3. Flujo de agentes (`backend/ingestion/pipeline/`)

Lo ejecuta un trabajador con cola en base de datos: `python backend/manage.py process_submissions [--once] [--id N]`. Cada paso actualiza `status` y `step_detail` y registra un `AgentRun`; cualquier error deja el envío en `failed` con `error` legible.

1. **fetching**: descarga la URL enviada. Protección SSRF (solo http/https y puertos 80/443; resuelve DNS y rechaza IP privadas, loopback, link-local y reservadas, también tras redirecciones; máximo 5 redirecciones, 15 s y 3 MB; solo HTML o texto). Extrae el texto principal y los metadatos (`og:title`, `og:site_name`, `article:published_time`). User-Agent genérico del proyecto, sin datos personales.
2. **researching** (agente `researcher`, API Responses de OpenAI con la herramienta de búsqueda web): busca cobertura independiente del mismo acontecimiento (instituciones, agencias y medios diversos). Solo se aceptan URL que aparezcan como citas de la herramienta de búsqueda, como máximo `INGESTION_MAX_RELATED` (5), y cada una se descarga con las mismas protecciones. Si la búsqueda falla, se continúa con la fuente enviada y se anota «fuente única».
3. **extracting** (agente `extractor`, salida estructurada por documento): afirmaciones `{kind: fact|statement|analysis, text_es, quote, attributed_to, actors[{name, kind}], places[], event_date, event_date_quote}`. `quote` es literal en el idioma original.
4. **verifying** (determinista + agente `verifier`): la `quote` debe estar en `FetchedDocument.text` (normalizando espacios, comillas, guiones y mayúsculas); si no, se descarta. Una fecha solo se acepta si `event_date_quote` también está en el texto. Después, el agente `verifier` comprueba que `text_es` sea una paráfrasis fiel de `quote`; las que no lo sean se descartan. Se marca la corroboración: cuántos documentos de editores distintos respaldan cada hecho.
5. **geolocating** (agente `geolocator` + geocodificador): el agente solo normaliza nombres de lugar mencionados en afirmaciones verificadas. Las coordenadas salen de Nominatim/OpenStreetMap (una petición por segundo, caché y atribución ODbL) y se guardan como `Source` con localizador `OSM <tipo> <id>`. Precisión `approximate`, con una nota que diga que es una referencia del lugar, no la posición de fuerzas. Si no hay resultado, sin ubicación.
6. **analyzing** (agente `analyst`): redacta título, resumen y categoría (lista de `CONTRATO_CRONOLOGIAS.md` §3), además de 1 a 4 afirmaciones `analysis` (contexto, perspectivas de las partes en proporción a la evidencia, incertidumbres). Cada una cita IDs de afirmaciones verificadas; si cita IDs inexistentes o ninguno, se descarta. Su `Evidence` enlaza a las fuentes de las afirmaciones citadas, con localizador `Síntesis de afirmaciones #…`.
7. **persistencia** (transacción, `full_clean`): `Source`, `Claim` (`supported`; las de una sola fuente se marcan en el texto del localizador), `Evidence` (`excerpt` = cita), `Actor`, `Participation`, `Location`, `Event` (`draft`, `origin=ai_pipeline`, `submitted_by`, `as_of` = fecha de proceso, fechas solo si están verificadas; si no, `unknown`). Si hay `target_story`, se añade allí; si no, se crea una `TimelineStory` (`origin=ai_pipeline`). El envío pasa a `review`.

Configuración (`settings.py`, desde el entorno): `OPENAI_API_KEY`, `OPENAI_MODEL` (modelo de razonamiento para extracción y análisis), `OPENAI_SEARCH_MODEL` (modelo compatible con búsqueda web), `INGESTION_MAX_RELATED=5`, `INGESTION_DAILY_LIMIT=10`, `INGESTION_AUTO_PUBLISH=False`, `INGESTION_USER_AGENT`, `NOMINATIM_URL`.

## 4. Frontend

- Sesión: el cliente pide `/api/auth/csrf/` al iniciar y envía `X-CSRFToken` en cada POST, PATCH o DELETE (`credentials: 'same-origin'`).
- Vistas: inicio (globo), entrar, registrarse, perfil (editar datos y contraseña), enviar noticia, mis envíos, detalle de envío (estado por pasos con consultas periódicas cada 4 s hasta un estado terminal, documentos, borrador) y cola de revisión para staff.
- Toda observación con `origin = ai_pipeline` muestra una insignia visible: «Observación generada con IA a partir de las fuentes enlazadas · enviada por <display_name> · revisada por el equipo».
