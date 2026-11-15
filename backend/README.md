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
python backend\manage.py test stories
```

## Frontend local

En una segunda terminal, desde la raíz:

```powershell
cd frontend
npm install
npm run dev
```

Abre la dirección que indique Vite. El proxy de desarrollo envía `/api` a Django en `127.0.0.1:8000`. El globo usa costas modernas de Natural Earth; la interfaz ofrece fuentes y alternativa textual. La noticia y su evidencia se guardan en modelos Django; la búsqueda automática y OpenAPI formal siguen pendientes. La configuración generada es solo para desarrollo local; SQLite se utiliza para las aplicaciones integradas de Django.

