# Backend Django

API de lectura para desarrollo local. Desde la raíz en PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\manage.py migrate
python backend\manage.py seed_cop31
python backend\manage.py runserver
```

La noticia inicial está disponible en `http://127.0.0.1:8000/api/stories/geopolitica/`. Sus datos proceden de la base de datos y constituyen una instantánea documental, sin actualización automática. La carga inicial está en `stories/management/commands/seed_cop31.py`. El punto es una referencia aproximada de la ciudad, no del recinto. La antigua API de Roma permanece en `/api/stories/expansion-de-roma/`.

## Cronologías actualizables

Contrato: `docs/api/CONTRATO_CRONOLOGIAS.md`. Cada cronología es un archivo JSON (UTF-8) en `backend/stories/timelines/<slug>.json` que se carga con `load_timeline`. La lógica está en `stories/timeline_loader.py`; la lista única de categorías admitidas en `stories/categories.py` (debe coincidir con `frontend/src/icons.tsx`).

API de lectura:

- `GET /api/stories/`: lista de cronologías con al menos un hito visible y la noticia `geopolitica`, ordenadas por `last_event_date` descendente (`kind`, `events_count`, `first_event_date`, `last_event_date`, `as_of`).
- `GET /api/stories/<slug>/`: detalle de cualquier `TimelineStory`, con `kind`, `as_of`, `first_event_date`, `last_event_date` y `date.start`/`date.end` ISO por hito, ordenados por `start_date`. Sin base de datos responde 503; si no existe o no tiene hitos revisados con evidencia, 404 con `detail`.

### Cómo añadir un hito

1. Edita el JSON de la cronología y añade el evento al final de `events` con un `slug` nuevo (o crea otro JSON con el mismo `story.slug`). Declara en `sources` y `actors` las claves que use; cada evento necesita al menos un `fact` con evidencia (`source` + `locator`). Coordenadas en orden `[longitud, latitud]`, con `source` y `source_locator`; si no hay fuente geográfica, usa `"location": null` o `coordinates: null`.
2. Actualiza `as_of` a la fecha en que verificaste las fuentes.
3. Valida sin escribir:

   ```powershell
   python backend\manage.py load_timeline backend\stories\timelines\<slug>.json --dry-run
   ```

   Si hay errores, el comando indica la ruta exacta del campo (p. ej. `events[2].claims[0].evidence[0].source`) y no escribe nada.
4. Carga:

   ```powershell
   python backend\manage.py load_timeline backend\stories\timelines\<slug>.json
   ```

   El resumen muestra hitos creados y omitidos. Recargar el mismo archivo es idempotente.

Reglas del cargador: crea la historia si no existe; añade solo eventos cuyo `slug` no exista (orden = siguiente libre) con estado `reviewed`, afirmaciones `supported` y el `as_of` del archivo; nunca modifica ni borra registros existentes (para corregir un hito ya cargado usa el admin de Django: el JSON no lo sobrescribe). `TimelineStory.as_of` solo se actualiza si el del archivo es más reciente. Reutiliza `Source` por `url` y `Actor` por (`name`, `kind`). Un `slug` de evento que ya existe fuera de esa historia es un error. Todo se valida con `full_clean()` en una transacción por archivo: cualquier error revierte el archivo entero. Las claves no reconocidas se ignoran con un aviso.

Para comprobar el backend:

```powershell
python backend\manage.py check
python backend\manage.py test
```

## Usuarios, envío de noticias y revisión

Contrato: `docs/api/CONTRATO_USUARIOS_INGESTA.md`. Apps: `accounts` (perfil `Profile` y API de sesión) e `ingestion` (modelos `NewsSubmission`, `FetchedDocument`, `AgentRun`, API de envíos y transiciones en `ingestion/services.py`). El flujo de agentes (`ingestion/pipeline/`, comando `process_submissions`) es un componente aparte.

### Variables de entorno y `.env`

`config/settings.py` lee el entorno y, si existe, el archivo `.env` de la raíz del repositorio (parser mínimo propio, sin dependencias; las variables ya definidas en el entorno tienen prioridad). Copia la plantilla y rellénala; `.env` y `.env.*` están en `.gitignore` (salvo `.env.example`):

```powershell
Copy-Item .env.example .env
```

| Variable | Por defecto | Uso |
|---|---|---|
| `DJANGO_SECRET_KEY` | clave insegura solo si `DEBUG` | Obligatoria con `DJANGO_DEBUG=false` (si falta, Django no arranca). |
| `DJANGO_DEBUG` | `true` | Modo de desarrollo. |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | vacías | Listas separadas por comas. |
| `DJANGO_SECURE_COOKIES` | `not DEBUG` | Cookies de sesión y CSRF solo por HTTPS. |
| `OPENAI_API_KEY` | vacía | Sin clave, los envíos fallan con un mensaje claro. |
| `OPENAI_MODEL`, `OPENAI_SEARCH_MODEL` | `gpt-5-mini` | Modelos configurables (razonamiento y búsqueda web); comprueba su disponibilidad en tu cuenta. |
| `INGESTION_MAX_RELATED` | `5` | Máximo de fuentes relacionadas por envío. |
| `INGESTION_DAILY_LIMIT` | `10` | Envíos por usuario y día natural (zona `TIME_ZONE`); al superarlo, 429. |
| `INGESTION_AUTO_PUBLISH` | `false` | Publicación sin revisión humana (desaconsejado). |
| `INGESTION_USER_AGENT` | `GeoObservatorio/0.1 (+local-dev)` | User-Agent genérico de las descargas. |
| `NOMINATIM_URL` | `https://nominatim.openstreetmap.org/search` | Geocodificador. |

### Crear un administrador o un revisor (staff)

```powershell
python backend\manage.py migrate
python backend\manage.py createsuperuser
```

El superusuario entra en `http://127.0.0.1:8000/admin/` y en la API. Para que otra cuenta revise envíos sin ser superusuario, en el admin abre *Usuarios*, marca «Es staff» y guarda (o desde la shell: `User.objects.filter(username="...").update(is_staff=True)`). Los usuarios creados antes de esta app reciben un `Profile` automáticamente la primera vez que se leen sus datos; su nombre público por defecto es «Usuario <id>» (nunca el nombre de usuario ni el correo) y se cambia en *Perfiles* o con `PATCH /api/profile/`.

En el admin, *Envíos de noticias* se filtra por estado; las acciones «Publicar» y «Rechazar» usan las mismas funciones de servicio que la API (solo actúan sobre envíos en `review`). Para rechazar desde la lista, escribe antes el motivo en el campo «Review note» del envío.

### API de sesión (resumen)

Sesión de Django + CSRF: el cliente pide `GET /api/auth/csrf/`, guarda el token (cookie `csrftoken`, legible por JavaScript) y lo envía en la cabecera `X-CSRFToken` en cada POST/PATCH. Tras iniciar sesión Django rota el token: vuelve a leer la cookie. La cookie de sesión es `HttpOnly` y ambas usan `SameSite=Lax`.

- `/api/auth/register/`, `login/`, `logout/`, `me/`, `password/` y `/api/profile/` (GET/PATCH).
- `/api/submissions/` (GET lista propia, `?all=1` para staff, `?status=` opcional; POST crear), `/api/submissions/<id>/` (detalle con `documents`, `agent_runs`, `preview`), `retry/`, `publish/` y `reject/`.
- Errores: `{"detail": "..."}`; validación: `400 {"errors": {"campo": ["mensaje"]}}`; 401 sin sesión, 403 sin permiso, 404 si el envío no existe o es de otra persona, 429 por límite diario.

Pruebas:

```powershell
python backend\manage.py test accounts ingestion stories
```

## Frontend local

En una segunda terminal, desde la raíz:

```powershell
cd frontend
npm install
npm run dev
```

Abre la dirección que indique Vite. El proxy de desarrollo envía `/api` a Django en `127.0.0.1:8000`. El globo usa costas modernas de Natural Earth; la interfaz ofrece fuentes y alternativa textual. La noticia y su evidencia se guardan en modelos Django; la búsqueda automática y OpenAPI formal siguen pendientes. La configuración generada es solo para desarrollo local; SQLite se utiliza para las aplicaciones integradas de Django.

