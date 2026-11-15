# Contrato: cronologías actualizables (v1)

Estado: **acordado por el orquestador el 2026-11-15**, pendiente de implementación. Una propuesta no es una API implementada.

## 1. Archivo de cronología (entrada editorial)

Ubicación: `backend/stories/timelines/<slug>.json`, UTF-8. Lo carga `python backend/manage.py load_timeline <ruta> [--dry-run]`.

```json
{
  "schema_version": 1,
  "story": {
    "slug": "guerra-sudan",
    "title": "Guerra en Sudán",
    "summary": "Selección parcial de hitos ...; no es exhaustiva.",
    "kind": "conflict"
  },
  "as_of": "2026-11-15",
  "sources": {
    "clave": {"url": "https://...", "title": "...", "creator": "...", "published_at": "2023-04-15", "rights_note": "..."}
  },
  "actors": {
    "clave": {"name": "...", "kind": "country|organization|person|other", "country_code": "SD"}
  },
  "events": [
    {
      "slug": "sudan-inicio-2023",
      "title": "Estallan los combates en Jartum",
      "category": "conflicto",
      "start_date": "2023-04-15",
      "end_date": null,
      "date_precision": "exact",
      "summary": "Texto breve neutral.",
      "claims": [
        {"key": "c1", "kind": "fact", "text": "...", "attributed_to": null,
         "evidence": [{"source": "clave", "locator": "párrafo / sección / página"}]}
      ],
      "location": {"label": "Jartum, Sudán", "coordinates": [32.53, 15.59],
                   "note": "Referencia aproximada de la ciudad; no es posición de fuerzas.",
                   "source": "clave", "source_locator": "City Details — coordenadas"},
      "participations": [{"actor": "clave", "role": "participant", "claim": "c1", "note": ""}]
    }
  ]
}
```

Reglas:

- `kind` de claim: `fact | statement | analysis | objective | action`. Cada evento necesita al menos un `fact` con evidencia. `statement` y `analysis` deben llevar `attributed_to` cuando exista atribución.
- `date_precision`: `exact` (solo `start_date`), `range` (ambas), `approximate` (al menos una).
- `location` puede ser `null`. Si tiene coordenadas: orden **[longitud, latitud]**, `source` y `source_locator` obligatorios; la precisión se guarda como `approximate`.
- `role`: `participant | host | declared_initiator | affected | other`; `claim` referencia una `key` del mismo evento.
- `category` (ver §3). Valores desconocidos se rechazan.
- **Actualización incremental**: el cargador crea la historia si no existe; añade solo eventos cuyo `slug` no exista; nunca modifica ni borra registros existentes (informa «omitido»). Reutiliza `Source` por `url` y `Actor` por (`name`, `kind`). Todo se valida con `full_clean()` dentro de una transacción por archivo; cualquier error revierte el archivo entero. `--dry-run` valida sin escribir. Un evento con `slug` existente que pertenezca a otra historia es un error.
- Para añadir información nueva: agregar el evento al JSON (o un JSON nuevo con el mismo `story.slug`) y volver a ejecutar el comando. `as_of` se aplica como fecha de verificación a los eventos nuevos y actualiza `TimelineStory.as_of` si es más reciente.

## 2. API

### `GET /api/stories/`

```json
{"stories": [{"slug": "guerra-sudan", "title": "...", "summary": "...", "kind": "conflict",
              "events_count": 8, "first_event_date": "2023-04-15", "last_event_date": "2026-...",
              "as_of": "2026-11-15"}]}
```

Incluye cada `TimelineStory` con al menos un evento visible, y la noticia `geopolitica` (kind `diplomacy`) si existe. Orden: `last_event_date` descendente. Sin base de datos → 503 con `detail`.

### `GET /api/stories/<slug>/`

Para cualquier `TimelineStory`: el formato actual de `timeline_from_database` más:

- nivel historia: `kind`, `as_of`, `first_event_date`, `last_event_date`;
- cada evento: `date.start` y `date.end` (ISO `YYYY-MM-DD` o `null`) además de los campos actuales (`label`, `precision`, `start_year`, `end_year`).

Eventos ordenados por `start_date` ascendente. Se mantienen `expansion-de-roma`, `geopolitica` y `conflicto-armado` sin romper su formato.

## 3. Categorías e iconos

Fuente única en el frontend: `frontend/src/categories.ts` (`CATEGORIES`, `categoryMeta`) y el componente `CategoryIcon` en `frontend/src/icons.tsx`. El backend valida contra la misma lista:

`conflicto, ataque, humanitario, desplazamiento, negociacion, acuerdo, politica, vencimiento, clima`

Los iconos son convenciones de tipo de acontecimiento. **No** representan fuerzas, armas, frentes, rutas ni control territorial. No se dibujan líneas entre hitos.

## 4. Interfaz del globo

```ts
export type GlobeMarker = {
  id: string
  coordinates: [number, number]   // [lon, lat]
  category: string
  label: string                   // lugar
  title: string                   // título del hito
  dateLabel: string
  state: 'active' | 'past' | 'future'
}
<Globe markers={GlobeMarker[]} activeId={string | null} onSelect={(id) => void} />
```

- El globo dibuja todos los marcadores recibidos; React decide cuáles pasa (p. ej. ocultar `future`).
- `active`: icono grande, anillo pulsante y etiqueta. `past`: icono atenuado. `future`: muy tenue.
- Marcadores con coordenadas idénticas se agrupan en un solo icono con contador; al pulsar se selecciona el activo del grupo o el más reciente.
- Pulsar un icono llama a `onSelect(id)`. La cámara se desplaza con animación al activo; sin activo con coordenadas, vista general.
- Se respeta `prefers-reduced-motion` (sin pulso ni animación de cámara).

## 5. Notas de implementación del backend (GEO-11, 2026-11-15)

Implementado en `backend/stories/` (§1–§3). Precisiones e interpretaciones donde el contrato no era explícito; ninguna elimina campos ni cambia formatos acordados:

- `first_event_date` / `last_event_date`: mínima y máxima `start_date` de los hitos **visibles** (revisados, con un `fact` respaldado y con evidencia); no se usa `end_date`. `events_count` cuenta solo hitos visibles.
- El 404 del detalle para slugs distintos de `geopolitica` usa `detail` «Historia no encontrada o sin hitos revisados con evidencia.». El slug `geopolitica` queda reservado a la noticia (no se lista una `TimelineStory` con ese slug).
- Un `slug` de evento existente que no pertenezca a la historia del archivo es error también cuando no pertenece a ninguna historia (p. ej. `geopolitica`).
- Historia existente: `title`, `summary` y `kind` no se modifican; si `story.kind` difiere se emite un aviso.
- `date_precision: "exact"` exige `end_date: null`.
- Campos opcionales aceptados además de los del ejemplo: `sources.<clave>.accessed_at` (por defecto, el `as_of` del archivo) y `evidence[].excerpt`. Claves no reconocidas: aviso, no error.
- `Source` y `Actor` solo se crean si los referencia un evento nuevo (una recarga no escribe nada).
- `location` sin coordenadas puede llevar `source`; se guarda con precisión `unknown`.
- La migración 0004 marca `conflicto-armado` como `conflict` y rellena `as_of` de historias existentes solo con la máxima `as_of` ya registrada en sus eventos.
