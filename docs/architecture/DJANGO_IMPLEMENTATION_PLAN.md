# DJANGO_IMPLEMENTATION_PLAN.md

## A. Identificación

ID GEO-DB-01 · Persistencia documental geopolítica · 2026-11-15 · P0 · Diseño propuesto para implementación incremental · commit `2c7534a` y cambios sin confirmar revisados.

## B. Objetivo

Guardar noticias descompuestas, fuentes, afirmaciones, actores, acciones y efectos con evidencia y perspectiva. Preservar la API actual y permitir que la primera noticia se incorpore de manera reproducible. La búsqueda automática, extractores, clasificación sentimental automatizada y publicación externa no son parte de esta etapa.

## C. Diagnóstico

Verificado: Python 3.12.13, Django 6.1.3, SQLite local. `stories/models.py` está vacío y `stories` aún no figura en `INSTALLED_APPS`. `/api/stories/geopolitica/` sirve `news_data.GEOPOLITICS` estático; existe también Roma. No hay modelos geopolíticos ni publicación o ingestión automática verificadas. No suponer datos ni infraestructura adicional. Archivos previos y cambios de otros colaboradores deben conservarse.

## D. Solución propuesta y contrato entre equipos

Crear modelos relacionales en app `stories`; registrar app y migración SQLite. Alternativa: JSON único ofrece menor esfuerzo inicial pero no permite relacionar con integridad afirmaciones y fuentes. El modelo relacional separa evidencia y permite revisión progresiva. No usar `DateTimeField` como sustituto de fecha histórica incierta; para noticias modernas los campos opcionales `DateField` con precisión documentada son suficientes.

### Esquema v1 propuesto

Nombres concretos Python/ORM (definir `__str__` útil; `blank=True` y `null=True` solo según corresponde):

- `Event`: `slug` único, `title` 255, `summary` texto, `category` 80, `status` (`draft`, `reviewed`, `published`; inicial `draft`), `start_date` y `end_date` opcionales, `date_precision` (`exact`, `range`, `approximate`, `unknown`), `as_of` fecha de consulta opcional, `created_at`, `updated_at`. El resumen no sustituye afirmaciones verificables. Restricción `end_date >= start_date` cuando ambos existen; fechas desconocidas permanecen nulas. `exact` requiere fecha inicial y final igual o nula; `range` requiere ambas; `unknown` exige ambas nulas. `approximate` requiere al menos una fecha y expresa incertidumbre, sin inventar día. La precisión inferior a día puede representarse como intervalo explícito; el texto de presentación debe explicar aproximación.
- `Source`: `title` 500, `creator` 255, `url` URL única, `published_at` fecha nullable, `accessed_at` fecha nullable, `rights_note` texto opcional. `accessed_at` fecha de consulta, sin inventar fecha de publicación. Fuentes originales con su enlace; no almacenar obras completas ni representar un PDF de agenda como noticia independiente.
- `Claim`: `event` FK CASCADE, `text` texto, `kind` (`fact`, `statement`, `action`, `analysis`, `objective`), `status` (`draft`, `supported`, `disputed`, `uncertain`, `rejected`), `attributed_to` FK Actor nullable para declaración/objetivo, `created_at`. `objective` es objetivo declarado y atribuible, no intención inferida. `analysis` se muestra como interpretación. Los estados no establecen verdad absoluta.
- `Evidence`: `claim` FK CASCADE, `source` FK PROTECT, `locator` 500, `excerpt` opcional (solo fragmento autorizado). Unicidad `(claim, source, locator)`; referencias con localizador no vacío. Una afirmación sin evidencia puede existir como borrador, nunca como contenido respaldado/publicado mediante un servicio sin validación.
- `Actor`: `name` 255, `kind` (`country`, `organization`, `person`, `other`), `country_code` opcional de dos letras; unicidad por `(name, kind)` a falta de identificador externo. No resolver entidades automáticamente por nombre; normalización/duplicados quedan pendientes.
- `Participation`: `event` FK CASCADE, `actor` FK PROTECT, `role` (`participant`, `host`, `declared_initiator`, `affected`, `other`), `claim` FK PROTECT obligatoria, `note` texto opcional. El rol es una afirmación atribuida, no asigna responsabilidad jurídica o causal. `claim.event_id` debe coincidir con `event_id` y la afirmación debe tener evidencia antes de mostrarla como respaldada.
- `Effect`: `event` FK CASCADE, `description` texto, `affected_actor` FK PROTECT nullable, `perspective` FK Actor PROTECT nullable, `valence` (`unknown`, `positive`, `negative`, `mixed`, por defecto `unknown`), `claim` FK PROTECT obligatoria. `claim.event_id` debe coincidir con el evento. Para valoración distinta de unknown, exigir `perspective` e interpretación atribuida/documentada mediante esa afirmación y evidencia. Ausencia de perspectiva significa desconocido, no neutralidad. Efectos sin respaldo no se presentan como probados; no crear ninguno para COP31 sin fuente.
- `Location`: `event` FK CASCADE, `label` 255, `longitude`, `latitude` nullable FloatField, `precision` (`approximate`, `unknown`), `note` texto, `source` FK Source PROTECT nullable, `source_locator` 500 opcional. Coordenadas ambas nulas o ambas presentes; si presentes exigir rangos longitud ±180, latitud ±90, precisión `approximate`, fuente y localizador. Valores ausentes requieren precisión `unknown`. La coordenada señala la ciudad, no supone el recinto o límites.

En cada FK de `Actor` relacionadas usar `related_name` explícito distinto. Implementar restricciones compatibles con SQLite para rangos/pares de coordenadas y fechas; aplicar reglas entre tablas en `clean()` y también en funciones de escritura / administración mediante `full_clean()`, porque Django no invoca `full_clean()` automáticamente en `save()`. DB constraints para lo que sea local; no fingir garantías de FK cruzadas mediante `CheckConstraint`. Proteger integridad referencial mediante `PROTECT` de fuentes y actores; nunca cascada accidental de evidencia de una fuente al eliminarla. Integridad de acciones y efectos depende de servicio de publicación transaccional posterior; documentar que insertar directo por ORM evade `clean`.

Separar `Event` del artículo fuente: una noticia puede tener múltiples fuentes y cada fuente respaldar múltiples afirmaciones. `as_of`, publicación y fecha del evento son conceptos distintos. Relacionar categorías/tipos sin inferir una taxonomía definitiva ni usar etiquetas positivas/negativas globales. No exponer API de escritura pública.

### API y siembra

No modificar consumidor ni reemplazar ruta estática hasta que migración y conversión estén verificadas. Mantener `/api/stories/geopolitica/` y `/api/stories/expansion-de-roma/` compatibles. Integración posterior: comando de gestión idempotente bajo `transaction.atomic` y `update_or_create`, solo contenido comprobado de `news_data.py`/`docs/geopolitica/COP31_FUENTES.md`, enlazar fuente a cada afirmación; no fabricar afectaciones, efectos ni objetivos. Si falta evidencia para descomponer, conservar texto en borrador, no inventar. La API seguirá estática hasta que el contrato de lectura de base de datos se apruebe y pruebe; el plan no afirma que esté implementado.

## E. Plan de ejecución

### TASK GEO-DB-1

Objetivo/Prioridad: implementar almacenamiento revisable P0. Dependencias: este contrato. Archivos: `backend/config/settings.py`, `backend/stories/models.py`, `backend/stories/migrations/0001_initial.py`, `backend/stories/admin.py`, pruebas nuevas. Registrar app; crear tablas, restricciones e interfaz administrativa apropiada, sin API de escritura. Permisos administrativos existentes; no habilitar acceso público. `full_clean` en formularios/servicios, restricciones locales de BD. Comprobar migración nueva y reversible, validaciones y rechazo de vinculaciones cruzadas. Aceptación: pruebas de modelos y migración sin errores en SQLite, datos con fuentes/locators y perspectiva conservados. Riesgos: bypass por bulk/ORM y coherencia cruzada; no publicar hasta servicio de escritura transaccional. Rollback: backup antes de cualquier migración con datos; revertir migración solo tras preservar registros. Documentar comandos y resultado.

### TASK GEO-DB-2

Objetivo/Prioridad: materializar noticia documentada P0. Dependencia GEO-DB-1. Archivos propuestos: `backend/stories/management/commands/seed_cop31.py` y pruebas aisladas. Idempotencia transaccional usando identificadores estables; crear solo datos atribuidos y comprobados, sin asignar responsabilidades, efectos o valores inventados. No tocar datos existentes por sustitución destructiva. Probar ejecución doble, conteos/relaciones, referencias y rollback por error. Sin dependencia de red ni publicación automática. Entrega separada; coordinar con equipo de investigación.

### TASK GEO-DB-3

Objetivo/Prioridad: servir datos persistentes P1. Dependencias: GEO-DB-1, GEO-DB-2 y contrato frontend acordado. Diseñar OpenAPI y transición compatible antes de editar `views.py` o consumidor. La API actual sigue siendo válida; evitar N+1 con `select_related`/`prefetch_related` donde se pruebe necesario. Probar contrato, vacío, errores y contenido sin evidencia no publicado. No asegurar velocidad sin medición. Si falla, restaurar vista estática sin borrar DB y conservar copias antes de rollback.

## F. Estrategia de pruebas

Obligatorias: migración limpia en SQLite; modelos con fechas incompletas e intervalos inválidos, pares/rangos de coordenadas, links de fuente y locators, borradores sin evidencia, efectos con valoración sin perspectiva, referencias cruzadas y exclusión de causas no verificadas. Probar eliminación protegida y unicidad. Cuando se implemente siembra: doble ejecución y atomicidad. API: probar compatibilidad y errores solo al cambiarla. Concurrencia en SQLite no demuestra garantías PostgreSQL; no declarar probada concurrencia de otro motor. Medición de carga opcional después de registrar necesidad y baseline.

## G. Despliegue

Primero migrar en entorno local aislado, luego respaldar datos y probar recuperación antes de aplicar en otro entorno. Verificar configuración y migraciones; no se autoriza despliegue productivo. Reversión de migración con datos es destructiva; respaldar antes y restaurar si hace falta. Configuración actual es para desarrollo.

## H. Métricas de éxito

Para noticia semilla: cada afirmación respaldada visible tiene fuente/localizador verificables; cada acción/efecto mostrado cuenta con afirmación y evidencia; 0 coordenadas fuera de rango; seed repetido no duplica registros. Medir mediante pruebas/reportes, no hay baseline de rendimiento.

## I. Mejoras futuras

Revisión humana/versionado fino, importación y búsqueda de fuentes, actualización con sello temporal, OpenAPI, resolución de entidades, anotaciones de desacuerdo, trazabilidad de cambios, análisis geográfico más fino, límites de carga y observabilidad. No implementar fetching remoto sin seguridad SSRF, límites, cumplimiento de licencias y diseño específico; el usuario proveerá noticia pero esta etapa aún no automatiza investigación.

## J. Checklist de entrega

[ ] Modelo/migración implementados y verificados. [ ] Integridad de fuentes/locators y perspectiva probada. [ ] Seed idempotente revisado. [ ] API existente sin regresión. [ ] Reportar comandos y resultados, migraciones, riesgos y desviaciones al arquitecto. [ ] No marcar publicada información no sustentada.

