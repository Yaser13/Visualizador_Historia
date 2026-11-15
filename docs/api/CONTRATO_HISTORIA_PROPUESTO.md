# Contrato de lectura propuesto: primera historia

Estado: borrador coordinado para diseño, no existe una API implementada. Versión 0.1; 2026-11-15.

## Operación propuesta

`GET /api/stories/{slug}/` devuelve una historia pública y sus hitos ordenados. `200` JSON; `404` si no existe; fallo de red o `5xx` produce estado de error y opción de reintento. No se prevé paginación para esta historia acotada. No hay mecanismo de autenticación implementado. Definir CORS y despliegue según entorno sin desactivar controles de seguridad.

## Esquema conceptual

- Historia: `slug`, `title`, `summary`, `events`.
- Hito: `id`, `order`, `title`, `description`, `date`, `place` (objeto o null), `evidence_status`, `sources`.
- Fecha: `start_year`, `end_year` (enteros o null), `precision` (`year`, `approximate`, `range`, `unknown`), `label` legible. Convención de años históricos con signo: a. e. c. negativo, e. c. positivo, sin año 0; ordenar explícitamente y probar el cambio de era.
- Lugar: `label`, `coordinates` (null o `[longitud, latitud]` en grados WGS84), `precision` (`approximate` o `unknown`), `note`. Los puntos no expresan límites ni superficies. Validar longitud entre -180 y 180 y latitud entre -90 y 90.
- Fuente: `title`, `creator`, `publication`, `url`, `locator`, `rights_note`. Cada afirmación publicada debe incluir al menos una fuente y estado revisado; preservar incertidumbre. `evidence_status`: `under_review`, `supported`, `disputed`, `uncertain`. `supported` indica respaldo, no verdad absoluta.

El backend valida y sirve los datos; el frontend selecciona un hito sin alterar la respuesta. La propuesta debe transformarse en OpenAPI formal y probarse antes de conectar consumidores; no se ha validado con una implementación. No se aceptarán geometrías, fechas ni coordenadas inventadas para llenar campos.

## Implementación inicial — 2026-11-15

Existe `GET /api/stories/expansion-de-roma/` en Django para lectura local. Los cinco hitos se entregan desde datos estáticos, con estado `under_review` y coordenadas nulas; una historia desconocida devuelve JSON 404 y métodos distintos de GET reciben 405. No hay todavía modelos de historias, edición, conexión React ni OpenAPI formal. Se ejecutaron `manage.py check` y `manage.py test stories`: sin errores y tres pruebas satisfactorias. Pendiente contraste histórico, validación geográfica, formalización de OpenAPI e integración.

## Referencias de ubicación — 2026-11-15

Los objetos `place` pueden incluir `coordinate_source` (null o `{url, locator}`) para identificar la procedencia de la ubicación, independiente de las fuentes históricas. Roma, Veyes y Cartago tienen coordenadas modernas aproximadas en orden longitud-latitud; Sicilia permanece sin coordenadas. La validación de rangos y procedencia se comprueba en pruebas de los datos estáticos; aún no existe validación de entrada editable ni OpenAPI formal.
