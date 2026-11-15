"""Incremental loader for editorial timeline files (docs/api/CONTRATO_CRONOLOGIAS.md §1).

Rules:
- The story is created if missing; existing records are never modified or
  deleted, except ``TimelineStory.as_of`` when the file's date is newer.
- Only events whose slug does not exist yet are added; existing events of the
  same story are reported as skipped. A slug that exists outside the story is
  an error.
- ``Source`` is reused by ``url`` and ``Actor`` by ``(name, kind)``; they are
  only created when a new event references them.
- The whole file is validated first (structure, references, categories,
  coordinates, evidence) and every record goes through ``full_clean()`` inside
  one transaction: any error rolls back the entire file. ``dry_run`` validates
  and then rolls back.
"""
import json
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import transaction
from django.db.models import Max

from .categories import EVENT_CATEGORIES
from .models import Actor, Claim, Event, Evidence, Location, Participation, Source, TimelineEntry, TimelineStory

SCHEMA_VERSION = 1

CLAIM_KINDS = set(Claim.Kind.values)
ACTOR_KINDS = set(Actor.Kind.values)
ROLES = set(Participation.Role.values)
PRECISIONS = {'exact', 'range', 'approximate'}
STORY_KINDS = set(TimelineStory.Kind.values)

KNOWN_KEYS = {
    '': {'schema_version', 'story', 'as_of', 'sources', 'actors', 'events'},
    'story': {'slug', 'title', 'summary', 'kind'},
    'source': {'url', 'title', 'creator', 'published_at', 'accessed_at', 'rights_note'},
    'actor': {'name', 'kind', 'country_code'},
    'event': {'slug', 'title', 'category', 'start_date', 'end_date', 'date_precision', 'summary', 'claims', 'location', 'participations'},
    'claim': {'key', 'kind', 'text', 'attributed_to', 'evidence'},
    'evidence': {'source', 'locator', 'excerpt'},
    'location': {'label', 'coordinates', 'note', 'source', 'source_locator'},
    'participation': {'actor', 'role', 'claim', 'note'},
}


class TimelineLoadError(Exception):
    """Validation failure; ``errors`` holds messages prefixed with the JSON path."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__('\n'.join(self.errors))


@dataclass
class LoadResult:
    story_slug: str
    story_created: bool = False
    dry_run: bool = False
    events_created: list = field(default_factory=list)
    events_skipped: list = field(default_factory=list)
    sources_created: int = 0
    sources_reused: int = 0
    actors_created: int = 0
    actors_reused: int = 0
    as_of_updated: bool = False
    warnings: list = field(default_factory=list)


class _Validator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, path, message):
        self.errors.append(f'{path}: {message}')

    def unknown_keys(self, obj, kind, path):
        extra = sorted(set(obj) - KNOWN_KEYS[kind])
        if extra:
            self.warnings.append(f'{path or "(raíz)"}: claves no reconocidas e ignoradas: {", ".join(extra)}')

    def obj(self, value, path):
        if not isinstance(value, dict):
            self.error(path, 'debe ser un objeto JSON.')
            return False
        return True

    def text(self, obj, key, path, required=True):
        value = obj.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                self.error(f'{path}.{key}', 'es obligatorio y no puede estar vacío.')
            return ''
        if not isinstance(value, str):
            self.error(f'{path}.{key}', 'debe ser una cadena de texto.')
            return ''
        return value.strip()

    def date(self, obj, key, path, required=False):
        value = obj.get(key)
        if value is None:
            if required:
                self.error(f'{path}.{key}', 'es obligatorio (formato AAAA-MM-DD).')
            return None
        if not isinstance(value, str):
            self.error(f'{path}.{key}', 'debe ser una fecha AAAA-MM-DD.')
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            self.error(f'{path}.{key}', f'fecha no válida «{value}»; usa AAAA-MM-DD.')
            return None

    def choice(self, obj, key, path, allowed, default=None):
        value = obj.get(key, default)
        if value not in allowed:
            self.error(f'{path}.{key}', f'valor no admitido «{value}». Valores admitidos: {", ".join(sorted(allowed))}.')
            return None
        return value

    def items(self, obj, key, path, required=True):
        value = obj.get(key)
        if value is None:
            if required:
                self.error(f'{path}.{key}', 'es obligatorio.')
            return []
        if not isinstance(value, list):
            self.error(f'{path}.{key}', 'debe ser una lista.')
            return []
        return value

    def slug(self, value, path):
        if not isinstance(value, str) or not value:
            self.error(path, 'es obligatorio.')
            return False
        try:
            validate_slug(value)
        except ValidationError:
            self.error(path, f'slug no válido «{value}» (solo letras, números, guiones y guiones bajos).')
            return False
        return True


def parse_timeline(data):
    """Validate the file structure without touching the database.

    Returns a normalized dict or raises ``TimelineLoadError`` with every
    problem found.
    """
    v = _Validator()
    if not v.obj(data, '(raíz)'):
        raise TimelineLoadError(v.errors)
    v.unknown_keys(data, '', '')
    if data.get('schema_version') != SCHEMA_VERSION:
        v.error('schema_version', f'debe ser {SCHEMA_VERSION}; se recibió {data.get("schema_version")!r}.')
    as_of = v.date(data, 'as_of', '', required=True)

    story = {}
    raw_story = data.get('story')
    if v.obj(raw_story, 'story'):
        v.unknown_keys(raw_story, 'story', 'story')
        v.slug(raw_story.get('slug'), 'story.slug')
        story = {
            'slug': raw_story.get('slug'),
            'title': v.text(raw_story, 'title', 'story'),
            'summary': v.text(raw_story, 'summary', 'story'),
            'kind': v.choice(raw_story, 'kind', 'story', STORY_KINDS, default=TimelineStory.Kind.OTHER),
        }

    sources = {}
    raw_sources = data.get('sources', {})
    if v.obj(raw_sources, 'sources'):
        seen_urls = {}
        for key, raw in raw_sources.items():
            path = f'sources.{key}'
            if not v.obj(raw, path):
                continue
            v.unknown_keys(raw, 'source', path)
            url = v.text(raw, 'url', path)
            if url and not url.startswith(('https://', 'http://')):
                v.error(f'{path}.url', 'debe ser una URL http(s).')
            if url in seen_urls:
                v.error(f'{path}.url', f'URL duplicada; ya declarada en sources.{seen_urls[url]}.')
            seen_urls[url] = key
            sources[key] = {
                'url': url,
                'title': v.text(raw, 'title', path),
                'creator': v.text(raw, 'creator', path),
                'published_at': v.date(raw, 'published_at', path),
                'accessed_at': v.date(raw, 'accessed_at', path),
                'rights_note': v.text(raw, 'rights_note', path, required=False),
            }

    actors = {}
    raw_actors = data.get('actors', {})
    if v.obj(raw_actors, 'actors'):
        for key, raw in raw_actors.items():
            path = f'actors.{key}'
            if not v.obj(raw, path):
                continue
            v.unknown_keys(raw, 'actor', path)
            actors[key] = {
                'name': v.text(raw, 'name', path),
                'kind': v.choice(raw, 'kind', path, ACTOR_KINDS),
                'country_code': (v.text(raw, 'country_code', path, required=False) or '').upper(),
            }

    def source_ref(obj, key, path):
        ref = obj.get(key)
        if ref is None or ref == '':
            v.error(f'{path}.{key}', 'es obligatorio y debe ser una clave de «sources».')
        elif ref not in sources:
            v.error(f'{path}.{key}', f'referencia inexistente «{ref}»; no está declarada en «sources».')
        return ref

    events = []
    seen_slugs = {}
    for index, raw in enumerate(v.items(data, 'events', '')):
        path = f'events[{index}]'
        if not v.obj(raw, path):
            continue
        v.unknown_keys(raw, 'event', path)
        slug = raw.get('slug')
        if v.slug(slug, f'{path}.slug'):
            if slug in seen_slugs:
                v.error(f'{path}.slug', f'slug duplicado en el archivo; ya usado en events[{seen_slugs[slug]}].')
            seen_slugs[slug] = index
        category = raw.get('category')
        if category not in EVENT_CATEGORIES:
            v.error(f'{path}.category', f'categoría desconocida «{category}». Valores admitidos: {", ".join(EVENT_CATEGORIES)}.')
        precision = v.choice(raw, 'date_precision', path, PRECISIONS)
        start = v.date(raw, 'start_date', path)
        end = v.date(raw, 'end_date', path)
        if precision == 'exact' and (start is None or end is not None):
            v.error(f'{path}.date_precision', '«exact» requiere start_date y end_date nulo.')
        elif precision == 'range' and (start is None or end is None):
            v.error(f'{path}.date_precision', '«range» requiere start_date y end_date.')
        elif precision == 'approximate' and start is None and end is None:
            v.error(f'{path}.date_precision', '«approximate» requiere al menos una fecha.')
        if start and end and end < start:
            v.error(f'{path}.end_date', 'no puede ser anterior a start_date.')

        claims = []
        claim_keys = set()
        has_fact = False
        for c_index, raw_claim in enumerate(v.items(raw, 'claims', path)):
            c_path = f'{path}.claims[{c_index}]'
            if not v.obj(raw_claim, c_path):
                continue
            v.unknown_keys(raw_claim, 'claim', c_path)
            key = raw_claim.get('key')
            if not isinstance(key, str) or not key:
                v.error(f'{c_path}.key', 'es obligatorio.')
            elif key in claim_keys:
                v.error(f'{c_path}.key', f'clave duplicada «{key}» en el mismo evento.')
            claim_keys.add(key)
            kind = v.choice(raw_claim, 'kind', c_path, CLAIM_KINDS)
            attributed = raw_claim.get('attributed_to')
            if attributed is not None and attributed not in actors:
                v.error(f'{c_path}.attributed_to', f'referencia inexistente «{attributed}»; no está declarada en «actors».')
            evidence = []
            for e_index, raw_evidence in enumerate(v.items(raw_claim, 'evidence', c_path, required=False)):
                e_path = f'{c_path}.evidence[{e_index}]'
                if not v.obj(raw_evidence, e_path):
                    continue
                v.unknown_keys(raw_evidence, 'evidence', e_path)
                evidence.append({'source': source_ref(raw_evidence, 'source', e_path),
                                 'locator': v.text(raw_evidence, 'locator', e_path),
                                 'excerpt': v.text(raw_evidence, 'excerpt', e_path, required=False),
                                 'path': e_path})
            if kind == Claim.Kind.FACT and evidence:
                has_fact = True
            claims.append({'key': key, 'kind': kind, 'text': v.text(raw_claim, 'text', c_path),
                           'attributed_to': attributed, 'evidence': evidence, 'path': c_path})
        if not has_fact:
            v.error(f'{path}.claims', 'el evento necesita al menos una afirmación «fact» con evidencia.')

        location = None
        raw_location = raw.get('location')
        if raw_location is not None and v.obj(raw_location, f'{path}.location'):
            l_path = f'{path}.location'
            v.unknown_keys(raw_location, 'location', l_path)
            coordinates = raw_location.get('coordinates')
            longitude = latitude = None
            if coordinates is not None:
                valid = (isinstance(coordinates, list) and len(coordinates) == 2
                         and all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) for n in coordinates))
                if not valid:
                    v.error(f'{l_path}.coordinates', 'debe ser [longitud, latitud] con dos números.')
                else:
                    longitude, latitude = coordinates
                    if not -180 <= longitude <= 180:
                        v.error(f'{l_path}.coordinates[0]', f'longitud fuera de rango ({longitude}); debe estar entre -180 y 180.')
                    if not -90 <= latitude <= 90:
                        v.error(f'{l_path}.coordinates[1]', f'latitud fuera de rango ({latitude}); debe estar entre -90 y 90. Recuerda el orden [longitud, latitud].')
            has_coordinates = coordinates is not None
            location = {
                'label': v.text(raw_location, 'label', l_path),
                'longitude': longitude, 'latitude': latitude,
                'note': v.text(raw_location, 'note', l_path, required=False),
                'source': source_ref(raw_location, 'source', l_path) if has_coordinates or raw_location.get('source') else None,
                'source_locator': v.text(raw_location, 'source_locator', l_path, required=has_coordinates),
                'path': l_path,
            }

        participations = []
        for p_index, raw_part in enumerate(v.items(raw, 'participations', path, required=False)):
            p_path = f'{path}.participations[{p_index}]'
            if not v.obj(raw_part, p_path):
                continue
            v.unknown_keys(raw_part, 'participation', p_path)
            actor = raw_part.get('actor')
            if actor not in actors:
                v.error(f'{p_path}.actor', f'referencia inexistente «{actor}»; no está declarada en «actors».')
            claim_key = raw_part.get('claim')
            if claim_key not in claim_keys:
                v.error(f'{p_path}.claim', f'referencia inexistente «{claim_key}»; debe ser una «key» de las afirmaciones de este evento.')
            participations.append({'actor': actor, 'role': v.choice(raw_part, 'role', p_path, ROLES), 'claim': claim_key,
                                   'note': v.text(raw_part, 'note', p_path, required=False), 'path': p_path})

        events.append({'slug': slug, 'title': v.text(raw, 'title', path), 'summary': v.text(raw, 'summary', path),
                       'category': category, 'start_date': start, 'end_date': end, 'date_precision': precision,
                       'claims': claims, 'location': location, 'participations': participations, 'path': path})

    if v.errors:
        raise TimelineLoadError(v.errors)
    return {'as_of': as_of, 'story': story, 'sources': sources, 'actors': actors, 'events': events, 'warnings': v.warnings}


def _validated_save(instance, path):
    try:
        instance.full_clean()
    except ValidationError as exc:
        if hasattr(exc, 'error_dict'):
            messages = [f'{path}.{name}: {" ".join(m for e in errors for m in e.messages)}' if name != '__all__'
                        else f'{path}: {" ".join(m for e in errors for m in e.messages)}'
                        for name, errors in exc.error_dict.items()]
        else:
            messages = [f'{path}: {message}' for message in exc.messages]
        raise TimelineLoadError(messages) from exc
    instance.save()
    return instance


def load_timeline_data(data, dry_run=False):
    """Load an already-decoded timeline file. See module docstring."""
    parsed = parse_timeline(data)
    story_spec = parsed['story']
    as_of = parsed['as_of']
    result = LoadResult(story_slug=story_spec['slug'], dry_run=dry_run, warnings=list(parsed['warnings']))

    with transaction.atomic():
        story = TimelineStory.objects.select_for_update().filter(slug=story_spec['slug']).first()
        existing_events = {e.slug: e for e in Event.objects.filter(slug__in=[item['slug'] for item in parsed['events']])}
        own_event_ids = set(story.entries.values_list('event_id', flat=True)) if story else set()
        conflicts = [f'{item["path"]}.slug: el evento «{item["slug"]}» ya existe y no pertenece a la historia «{story_spec["slug"]}».'
                     for item in parsed['events']
                     if item['slug'] in existing_events and existing_events[item['slug']].pk not in own_event_ids]
        if conflicts:
            raise TimelineLoadError(conflicts)

        if story is None:
            story = _validated_save(TimelineStory(slug=story_spec['slug'], title=story_spec['title'], summary=story_spec['summary'],
                                                  kind=story_spec['kind'], as_of=as_of), 'story')
            result.story_created = True
        else:
            if story.kind != story_spec['kind']:
                result.warnings.append(f'story.kind: el archivo indica «{story_spec["kind"]}» pero la historia existente es «{story.kind}»; no se modificó.')
            if story.as_of is None or as_of > story.as_of:
                story.as_of = as_of
                story.save(update_fields=['as_of', 'updated_at'])
                result.as_of_updated = True

        sources, actors = {}, {}

        def get_source(key, path):
            if key not in sources:
                spec = parsed['sources'][key]
                source = Source.objects.filter(url=spec['url']).first()
                if source is None:
                    source = _validated_save(Source(url=spec['url'], title=spec['title'], creator=spec['creator'],
                                                    published_at=spec['published_at'], accessed_at=spec['accessed_at'] or as_of,
                                                    rights_note=spec['rights_note']), f'sources.{key}')
                    result.sources_created += 1
                else:
                    result.sources_reused += 1
                sources[key] = source
            return sources[key]

        def get_actor(key):
            if key not in actors:
                spec = parsed['actors'][key]
                actor = Actor.objects.filter(name=spec['name'], kind=spec['kind']).first()
                if actor is None:
                    actor = _validated_save(Actor(**spec), f'actors.{key}')
                    result.actors_created += 1
                else:
                    result.actors_reused += 1
                actors[key] = actor
            return actors[key]

        next_order = (story.entries.aggregate(top=Max('order'))['top'] or 0) + 1
        for item in parsed['events']:
            if item['slug'] in existing_events:
                result.events_skipped.append(item['slug'])
                continue
            path = item['path']
            event = _validated_save(Event(slug=item['slug'], title=item['title'], summary=item['summary'], category=item['category'],
                                          status=Event.Status.REVIEWED, start_date=item['start_date'], end_date=item['end_date'],
                                          date_precision=item['date_precision'], as_of=as_of), path)
            claims = {}
            for claim_spec in item['claims']:
                claim = _validated_save(Claim(event=event, text=claim_spec['text'], kind=claim_spec['kind'], status=Claim.Status.SUPPORTED,
                                              attributed_to=get_actor(claim_spec['attributed_to']) if claim_spec['attributed_to'] else None),
                                        claim_spec['path'])
                claims[claim_spec['key']] = claim
                for evidence_spec in claim_spec['evidence']:
                    _validated_save(Evidence(claim=claim, source=get_source(evidence_spec['source'], evidence_spec['path']),
                                             locator=evidence_spec['locator'], excerpt=evidence_spec['excerpt']), evidence_spec['path'])
            location = item['location']
            if location is not None:
                has_coordinates = location['longitude'] is not None
                _validated_save(Location(event=event, label=location['label'], longitude=location['longitude'], latitude=location['latitude'],
                                         precision=Location.Precision.APPROXIMATE if has_coordinates else Location.Precision.UNKNOWN,
                                         note=location['note'],
                                         source=get_source(location['source'], location['path']) if location['source'] else None,
                                         source_locator=location['source_locator']), location['path'])
            for part in item['participations']:
                _validated_save(Participation(event=event, actor=get_actor(part['actor']), role=part['role'],
                                              claim=claims[part['claim']], note=part['note']), part['path'])
            _validated_save(TimelineEntry(story=story, event=event, order=next_order), f'{path} (entrada de cronología)')
            next_order += 1
            result.events_created.append(item['slug'])

        if dry_run:
            transaction.set_rollback(True)
    return result


def _reject_constant(name):
    raise ValueError(f'valor no permitido {name}')


def load_timeline_file(path, dry_run=False):
    """Read a UTF-8 JSON timeline file (BOM tolerated) and load it."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        raise TimelineLoadError([f'{file_path}: el archivo no existe.'])
    except (OSError, UnicodeDecodeError) as exc:
        raise TimelineLoadError([f'{file_path}: no se pudo leer como UTF-8 ({exc}).'])
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise TimelineLoadError([f'{file_path}: JSON no válido ({exc}).'])
    return load_timeline_data(data, dry_run=dry_run)
