# Flujo de agentes de análisis (ING-01)

Estado: **implementado el 2026-11-15** en `backend/ingestion/pipeline/` y en el comando `process_submissions`. Validado con pruebas que no hacen llamadas a la red ni a OpenAI (`backend/ingestion/tests_pipeline.py`). **Aún no se ha ejecutado contra la API real de OpenAI.** Contrato: `docs/api/CONTRATO_USUARIOS_INGESTA.md` §0, §1 y §3.

## 1. Diagrama del flujo

```
POST /api/submissions/  ──►  NewsSubmission(status=queued)
                                   │
   process_submissions (trabajador) │  UPDATE … WHERE status='queued'  → fetching   (toma exclusiva)
                                   ▼
 ┌─ 0. build_client() ─ sin OPENAI_API_KEY → failed «Falta OPENAI_API_KEY: configúrala en .env…»
 │
 ├─ 1. fetching ──── SafeFetcher (SSRF) ─► Page ─► Source + FetchedDocument(role=submitted)   [D1]
 │
 ├─ 2. researching ─ researcher (Responses + web_search) ─► solo anotaciones url_citation
 │                    ├─ filtra: misma URL, mismo editor (dominio registrable), duplicados, máx. INGESTION_MAX_RELATED
 │                    ├─ SafeFetcher por cada una ─► FetchedDocument(role=related)               [D2…]
 │                    └─ error o 0 descargas ─► se continúa, nota «Fuente única»
 │
 ├─ 3. extracting ── extractor (JSON Schema estricto) por documento ─► propuestas
 │                    └─ comprobación determinista inmediata (verification.py):
 │                        cita literal en el texto guardado · fecha con cita que expresa día y mes ·
 │                        autor, actores y lugares presentes en el documento · sin URL
 │
 ├─ 4. verifying ─── verifier (JSON Schema) ─► paráfrasis fiel sí/no + grupos del mismo hecho
 │                    └─ reglas deterministas: solo ids existentes y fieles; grupos solo de «fact»
 │                       de documentos distintos; corroboración = nº de dominios registrables distintos
 │                       Sin ningún «fact» verificado ─► failed
 │
 ├─ 5. geolocating ─ geolocator (JSON Schema) normaliza menciones ─► NominatimGeocoder (1 req/s, caché)
 │                    └─ la mención debe estar en las afirmaciones verificadas; la consulta debe contenerla
 │                       (si no, se geocodifica la mención literal). Coordenadas solo de OSM.
 │
 ├─ 6. analyzing ─── analyst (JSON Schema) ─► título, resumen, categoría, historia, fecha, 1–4 análisis,
 │                    participaciones. Análisis con ids inexistentes/ninguno, URL o cifras sin respaldo ─► descartado.
 │                    Título/resumen con URL o cifras sin respaldo ─► sustituidos por el texto de los hechos.
 │
 └─ 7. persistencia ─ transaction.atomic + full_clean():
                      Event(draft, origin=ai_pipeline, submitted_by, as_of=hoy) · Claim(supported) ·
                      Evidence(excerpt = subcadena exacta del texto guardado) · Actor · Participation ·
                      Location(approximate, Source OSM, «OSM <tipo> <id>») · TimelineStory/TimelineEntry
                      ─► NewsSubmission(status=review)   (published si INGESTION_AUTO_PUBLISH=True)

 Cualquier PipelineError ─► status=failed, error legible, nada escrito en stories (rollback).
 Cada llamada a un agente ─► AgentRun(agent, model, prompt_version, status, input_summary, output, tokens).
```

Módulos: `fetcher.py`, `llm.py`, `agents.py` (prompts y esquemas, `PROMPT_VERSION = 'ing01-2026-11-15.v1'`), `verification.py`, `geocoding.py`, `runner.py`, `errors.py`.

## 2. Garantías contra contenido inventado

| Riesgo | Garantía (determinista salvo que se indique) | Dónde |
|---|---|---|
| Cita inventada o alterada | `quote` normalizada (NFKC, comillas, guiones, guion blando, espacios de ancho cero, dígitos de cualquier sistema, mayúsculas, espacios) debe ser **subcadena** del texto guardado; no se toleran palabras añadidas, omitidas ni puntos suspensivos internos. Mínimo 20 caracteres y 4 palabras; máximo 600. | `NormalizedDocument.check_quote` |
| Cita no literal en la parte pública | `Evidence.excerpt` es la **subcadena exacta** del `FetchedDocument.text` (NFC) localizada mediante un mapa de índices, no el texto devuelto por el modelo. | `QuoteCheck.excerpt` |
| Fecha inventada o inferida | `event_date` ISO válida, entre 1900 y hoy + 366 días; `event_date_quote` presente en el texto **y** que exprese ese día y mes (ISO, `d/m[/a]` o día + nombre de mes en es/en/fr/pt/de/it; un año presente debe coincidir). «Ayer», «el martes» → rechazada. La fecha del acontecimiento solo procede de un «fact» con fecha verificada. | `check_event_date`, `date_quote_states`, `Pipeline.step_analyze` |
| URL inventadas por el investigador | Solo se aceptan las URL de anotaciones `url_citation` de la herramienta `web_search`; las URL escritas en el texto se registran como ignoradas. Cada URL pasa por el `SafeFetcher`. | `OpenAIClient.web_search`, `Pipeline.step_research` |
| Autor o actor inventado | `attributed_to`, actores y lugares deben aparecer como palabra completa en el documento de origen. Una declaración sin autor verificable se descarta. | `Pipeline._check_claims` |
| Paráfrasis infiel | Agente `verifier` (LLM): solo las marcadas `faithful=true` sobreviven; ante ausencia o duda, se descarta. | `Pipeline.step_verify` |
| Corroboración inflada | Se cuenta por dominio registrable distinto; los grupos del `verifier` solo se aceptan entre «fact» fieles de documentos distintos. Los resultados del mismo editor que la fuente enviada se descartan. | `registrable_domain`, `step_verify` |
| Análisis sin base | Cada análisis debe citar IDs existentes (si cita uno inexistente o ninguno, se descarta); no puede contener URL ni cifras que no estén en las afirmaciones verificadas o sus citas. Se atribuye a «Observatorio — análisis asistido por IA». | `valid_references`, `_supported_text` |
| Coordenadas inventadas | El LLM nunca da coordenadas; solo Nominatim. La consulta debe contener la mención verificada (el modelo puede desambiguar, no reubicar). Precisión `approximate` y nota «no es la posición de fuerzas». | `step_geolocate`, `geocoding.py` |
| Inyección de instrucciones | Documento entre delimitadores con un *nonce* aleatorio que la página no puede prever; reglas explícitas en cada prompt; esquemas estrictos; todas las comprobaciones anteriores; publicación solo por staff (`draft` por defecto). | `agents.py`, `runner.py` |

Límites conocidos: (1) si el propio documento contiene una frase falsa o una instrucción con forma de afirmación, la cita es literal y pasa la comprobación determinista; la protegen el `verifier`, la atribución y la **revisión humana obligatoria**. (2) El título, el resumen y la historia los redacta el `analyst`: solo se comprueban URL y cifras, no la semántica; quedan etiquetados como IA y pasan por revisión. (3) El `country_code` del geolocalizador restringe la búsqueda y podría elegir un homónimo; la ubicación es aproximada y revisable. (4) La corroboración usa una heurística de dominio (sin lista pública de sufijos) y no detecta sindicación de un mismo teletipo en varios medios.

## 3. Seguridad de descarga (SSRF)

`SafeFetcher` aplica en la URL inicial y en **cada** redirección: solo `http`/`https`, puertos 80/443, sin credenciales, sin `localhost`/`.local`/`.internal`; resuelve DNS y exige que **todas** las direcciones sean públicas (rechaza privadas, loopback, link-local —incluido `169.254.169.254`—, reservadas, multicast, no especificadas, CGNAT y IPv4 incrustada en IPv6: mapeada, 6to4, Teredo, NAT64). La conexión se fija a la IP comprobada (cabecera `Host` y SNI con el nombre original: el certificado se sigue verificando), lo que cierra la ventana de *DNS rebinding*. Máximo 5 redirecciones, 15 s en total, 3 MB de cuerpo **descomprimido** leído en streaming (también frena bombas de compresión), solo `text/html`, `application/xhtml+xml` o `text/plain`, y sin proxies del entorno (`trust_env=False`). User-Agent: `INGESTION_USER_AGENT`.

Extracción: `trafilatura` (texto principal, sin comentarios ni tablas) con alternativa por elementos `<p>`; metadatos con `lxml` (`og:title`/`<title>`, `og:site_name`, `article:published_time`, `<html lang>`). `published_at` solo se toma de metadatos; nunca se deduce. Texto en NFC, un párrafo por línea, ≤ 200 000 caracteres.

## 4. OpenAI: decisiones de API

- Endpoint: **Responses API** (`client.responses.create`) del SDK oficial `openai` 3.51.0, con `store=False` y `max_output_tokens` (16 000 por defecto).
- Salidas estructuradas: `text={"format": {"type": "json_schema", "name": …, "schema": …, "strict": True}}`. Todos los objetos llevan `additionalProperties: false` y todos sus campos en `required`; los opcionales son `["tipo", "null"]` (lo comprueba una prueba). Se tratan `status="incomplete"` y los bloques `refusal`.
- Búsqueda web: herramienta `{"type": "web_search", "search_context_size": "medium"}` con `tool_choice="auto"`; se leen las anotaciones `url_citation` (`url`, `title`) del `output_text`. No se combina con salida estructurada (la documentación no garantiza las anotaciones en ese modo).
- Reintentos: los del SDK (`max_retries=2`; reintenta conexiones, tiempos agotados, 408/409/429/5xx). Tiempo máximo por llamada: 120 s. Los errores se resumen como clase + código HTTP; nunca se registra la clave ni el cuerpo de la petición. Un 401 se convierte en un mensaje de configuración.
- Tokens: `usage.input_tokens`/`output_tokens` se guardan en `AgentRun.tokens_in/out`.
- Fuentes consultadas (2026-11-15): [Web search](https://developers.openai.com/api/docs/guides/tools-web-search), [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Models](https://developers.openai.com/api/docs/models), [GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini).
- Modelos: `settings.py` usa por defecto `gpt-5-mini` para `OPENAI_MODEL` y `OPENAI_SEARCH_MODEL`. Según la página del modelo, `gpt-5-mini` admite Responses, salidas estructuradas y `web_search`, pero figura como **obsoleto** (sin fecha de retirada publicada). La página de modelos consultada recomienda familias más recientes; configura `OPENAI_MODEL`/`OPENAI_SEARCH_MODEL` en `.env` con un modelo vigente de esa página antes de usarlo en producción.

## 5. Configuración

| Variable | Uso | Por defecto |
|---|---|---|
| `OPENAI_API_KEY` | Obligatoria. Sin ella el envío queda en `failed` con «Falta OPENAI_API_KEY: configúrala en .env…». | — |
| `OPENAI_MODEL` | extractor, verifier, geolocator, analyst | `gpt-5-mini` (settings) |
| `OPENAI_SEARCH_MODEL` | researcher (web_search) | `gpt-5-mini` (settings) |
| `INGESTION_MAX_RELATED` | Máximo de documentos relacionados (0 desactiva la búsqueda) | 5 |
| `INGESTION_AUTO_PUBLISH` | Publicar sin revisión (no recomendado) | `False` |
| `INGESTION_USER_AGENT` | User-Agent de descargas y Nominatim, sin datos personales | `GeoObservatorio/0.1 (+local-dev)` |
| `NOMINATIM_URL` | Endpoint de búsqueda completo | `https://nominatim.openstreetmap.org/search` |
| Opcionales (solo `getattr`, no definidos en settings) | `OPENAI_TIMEOUT` (120), `OPENAI_MAX_RETRIES` (2), `OPENAI_REASONING_EFFORT` (sin enviar), `OPENAI_MAX_OUTPUT_TOKENS` (16 000) | |

Para la instancia pública de Nominatim, el `User-Agent` debe identificar la aplicación con un contacto del proyecto (política de uso de OSMF); para volúmenes altos, usar una instancia propia.

## 6. Ejecución del trabajador

```
.venv/Scripts/python.exe backend/manage.py process_submissions            # sondeo cada 5 s (--interval N)
.venv/Scripts/python.exe backend/manage.py process_submissions --once     # vacía la cola y termina
.venv/Scripts/python.exe backend/manage.py process_submissions --id 12    # un envío concreto en cola
.venv/Scripts/python.exe backend/manage.py process_submissions --max 3    # como mucho 3 envíos
```

La toma es una actualización condicional (`queued` → `fetching`, `attempts + 1`), segura con varios trabajadores. Un reintento (`failed` → `queued` desde la API) borra los `FetchedDocument` del intento anterior y conserva los `AgentRun` como historial.

## 7. Costes y límites

Por envío: 1 llamada `researcher` con búsqueda web (coste de la herramienta además de tokens), 1 `extractor` por documento descargado (hasta 1 + `INGESTION_MAX_RELATED` = 6; cada documento se trunca a 60 000 caracteres para el modelo), 1 `verifier`, como mucho 1 `geolocator` y 1 `analyst`: hasta **10 llamadas**. Con documentos de prensa típicos (5–15 k tokens) cabe esperar del orden de 50–120 k tokens de entrada por envío; el coste exacto depende del modelo elegido y se puede auditar sumando `AgentRun.tokens_in/out`. Límite de envíos: `INGESTION_DAILY_LIMIT` por usuario y día (API). Nominatim: 1 petición/s y hasta 3 lugares por envío.

## 8. Riesgos y pendientes

- **Licencias del contenido descargado**: el texto completo se guarda solo en `FetchedDocument.text` (interno, para verificar y auditar); la parte pública solo muestra citas breves (≤ 600 caracteres) con enlace a la fuente, y cada `Source` creada lleva una nota de derechos. Conviene definir una política de retención y borrar textos antiguos.
- **Envíos huérfanos**: si el proceso muere a mitad de un paso, el envío queda en un estado intermedio (`fetching`…`analyzing`); hoy hay que devolverlo a `queued` o `failed` desde el admin. Pendiente: recuperación por tiempo de espera.
- **Ejecución real no probada**: falta probar con una clave real (formato real de anotaciones, latencia, coste) y ajustar prompts con ejemplos reales.
- **Páginas con JavaScript o de pago**: si el texto extraído no llega a 200 caracteres el envío falla con un mensaje claro.
- **Búsqueda dirigida**: el `researcher` ve un extracto de la página enviada, que podría intentar dirigir la búsqueda; las URL siguen pasando por SSRF, verificación literal y revisión.
- Las fuentes `Source` se reutilizan por URL y no se modifican; una `Source` creada para una descarga relacionada fallida no aparece públicamente salvo que una evidencia la cite.
