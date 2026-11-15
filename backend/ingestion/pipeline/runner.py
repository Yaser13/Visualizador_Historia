"""Orchestration of the agent pipeline (contract §3).

``process_submission`` runs every step for one ``NewsSubmission`` that has been
claimed by the worker (status ``fetching``), updates ``status``/``step_detail``,
records one ``AgentRun`` per agent call and persists the draft observation in a
single transaction with ``full_clean``. Any error leaves the submission in
``failed`` with a readable message; nothing partial is written to ``stories``.

Dependencies (LLM client, fetcher, geocoder, date) are injectable for tests.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone
from django.utils.text import slugify

from stories.categories import EVENT_CATEGORIES
from stories.models import Actor, Claim, Event, Evidence, Location, Participation, Source, TimelineEntry, TimelineStory

from ..models import AgentRun, FetchedDocument, NewsSubmission
from . import agents
from .errors import FetchError, LLMError, PipelineError, UnsafeURLError
from .fetcher import SafeFetcher, canonical_url
from .geocoding import ATTRIBUTION, NominatimGeocoder
from .llm import build_client
from .verification import (NormalizedDocument, check_event_date, normalize_text, registrable_domain,
                           valid_references)

logger = logging.getLogger(__name__)

Status = NewsSubmission.Status
AI_ACTOR_NAME = 'Observatorio — análisis asistido por IA'
MIN_SUBMITTED_TEXT_CHARS = 200
MAX_CLAIM_TEXT_CHARS = 2000
MAX_TITLE_CHARS = 120
RIGHTS_NOTE = ('Contenido © de su editor. El observatorio solo reproduce citas breves con enlace a la fuente; '
               'el texto completo descargado se conserva únicamente para verificación interna.')
LOCATION_NOTE = ('Referencia aproximada del lugar mencionado («{mention}») obtenida de OpenStreetMap/Nominatim. '
                 'No es la posición de fuerzas ni el punto exacto del acontecimiento.')
_URL_PATTERN = re.compile(r'https?://|www\.', re.IGNORECASE)
_NUMBER_PATTERN = re.compile(r'\d+(?:[.,\s]\d{3})*(?:[.,]\d+)?')


@dataclass
class Document:
    label: str
    role: str
    record: FetchedDocument
    norm: NormalizedDocument
    publisher: str
    page: object = None  # fetcher.Page

    @property
    def domain(self):
        return registrable_domain(self.record.source.url)


@dataclass
class Candidate:
    id: int
    document: Document
    kind: str
    text_es: str
    quote: object  # verification.QuoteCheck
    attributed_to: str | None
    actors: list
    places: list
    event_date: date | None


@dataclass
class VerifiedClaim:
    id: int
    kind: str
    text_es: str
    attributed_to: str | None
    attributed_kind: str
    actors: list
    places: list
    event_date: date | None
    members: list = field(default_factory=list)

    @property
    def publishers(self):
        return len({member.document.domain for member in self.members})


def _truncate(value, model, name):
    limit = model._meta.get_field(name).max_length
    value = (value or '').strip()
    return value[:limit] if limit else value


def _validated_save(instance, label):
    try:
        instance.full_clean()
    except ValidationError as error:
        details = '; '.join(f'{key}: {" ".join(messages)}' for key, messages in error.message_dict.items()) \
            if hasattr(error, 'error_dict') else ' '.join(error.messages)
        raise PipelineError(f'No se pudo guardar {label}: {details}') from error
    instance.save()
    return instance


def _unique_slug(model, text, suffix):
    limit = model._meta.get_field('slug').max_length
    base = slugify(text)[:limit - len(suffix) - 1].strip('-') or 'observacion'
    slug, counter = f'{base}-{suffix}', 2
    while model.objects.filter(slug=slug).exists():
        extra = f'-{suffix}-{counter}'
        slug = f'{base[:limit - len(extra)]}{extra}'
        counter += 1
    return slug


def _numbers(text):
    return {re.sub(r'[.,\s]', '', item) for item in _NUMBER_PATTERN.findall(normalize_text(text))}


def _supported_text(text, corpus_numbers):
    """No URLs and no number absent from the verified material (titles, summaries, AI analysis)."""
    return bool(text and text.strip()) and not _URL_PATTERN.search(text) and _numbers(text) <= corpus_numbers


def claim_submission(pk):
    """Atomically move a ``queued`` submission to ``fetching``. Returns ``True`` if this worker got it."""
    now = timezone.now()
    return NewsSubmission.objects.filter(pk=pk, status=Status.QUEUED).update(
        status=Status.FETCHING, step_detail='Descargando la noticia enviada', error='', started_at=now,
        finished_at=None, attempts=F('attempts') + 1, updated_at=now) == 1


def next_queued_id():
    return (NewsSubmission.objects.filter(status=Status.QUEUED).order_by('created_at', 'pk')
            .values_list('pk', flat=True).first())


def process_next(**dependencies):
    """Claim and process the oldest queued submission. Returns it, or ``None`` if the queue is empty."""
    while True:
        pk = next_queued_id()
        if pk is None:
            return None
        if claim_submission(pk):
            return process_submission(NewsSubmission.objects.get(pk=pk), **dependencies)


def process_submission(submission, *, llm=None, fetcher=None, geocoder=None, today=None):
    """Run the pipeline for a claimed submission (status ``fetching``); returns it refreshed."""
    Pipeline(submission, llm=llm, fetcher=fetcher, geocoder=geocoder, today=today).run()
    submission.refresh_from_db()
    return submission


class Pipeline:
    def __init__(self, submission, *, llm=None, fetcher=None, geocoder=None, today=None):
        self.submission = submission
        self.llm = llm
        self.fetcher = fetcher or SafeFetcher()
        self.geocoder = geocoder or NominatimGeocoder()
        self.today = today or timezone.localdate()
        self.documents = []
        self.single_source = True
        self.notes = []

    # --- status and tracing -------------------------------------------------------

    def set_status(self, status, detail):
        self.submission.status = status
        self.submission.step_detail = detail[:255]
        self.submission.save(update_fields=['status', 'step_detail', 'updated_at'])

    def record_run(self, agent, *, started, status, input_summary='', output=None, result=None, error='', model=''):
        return AgentRun.objects.create(
            submission=self.submission, agent=agent, prompt_version=agents.PROMPT_VERSION, status=status,
            model=((result.model if result else '') or model)[:100], input_summary=input_summary[:1000],
            output=output if output is not None else {}, tokens_in=result.tokens_in if result else None,
            tokens_out=result.tokens_out if result else None, started_at=started, finished_at=timezone.now(),
            error=error[:2000])

    def fail(self, message):
        self.submission.status = Status.FAILED
        self.submission.error = message
        self.submission.step_detail = 'El análisis se detuvo; consulta el error.'
        self.submission.finished_at = timezone.now()
        self.submission.save(update_fields=['status', 'error', 'step_detail', 'finished_at', 'updated_at'])

    def run(self):
        try:
            if self.llm is None:
                self.llm = build_client()
            self.submission.documents.all().delete()  # leftovers of a previous failed attempt
            submitted = self.step_fetch()
            self.step_research(submitted)
            candidates = self.step_extract()
            verified = self.step_verify(candidates)
            place = self.step_geolocate(verified)
            analysis = self.step_analyze(verified)
            self.persist(verified, place, analysis)
        except PipelineError as error:
            logger.info('Submission %s failed: %s', self.submission.pk, error)
            self.fail(str(error))
        except Exception:  # noqa: BLE001 - the worker must survive and report
            logger.exception('Unexpected error processing submission %s', self.submission.pk)
            self.fail('Error interno inesperado durante el análisis. El equipo puede revisarlo y reintentarlo.')

    # --- 1. fetching ------------------------------------------------------------------

    def _source_for(self, url, title, publisher, published_at):
        url = canonical_url(url)
        source = Source.objects.filter(url=url).first()
        if source is None:
            source = _validated_save(Source(
                url=url, title=_truncate(title or url, Source, 'title'),
                creator=_truncate(publisher or registrable_domain(url), Source, 'creator'),
                published_at=published_at, accessed_at=self.today, rights_note=RIGHTS_NOTE), 'la fuente')
        return source

    def _store_document(self, page, role, label):
        source = self._source_for(page.final_url, page.title, page.publisher, page.published_at)
        if any(item.record.source_id == source.pk for item in self.documents):
            return None
        record = _validated_save(FetchedDocument(
            submission=self.submission, source=source, role=role, fetched_at=timezone.now(),
            http_status=page.http_status, content_type=_truncate(page.content_type, FetchedDocument, 'content_type'),
            title=_truncate(page.title, FetchedDocument, 'title'),
            publisher=_truncate(page.publisher, FetchedDocument, 'publisher'), published_at=page.published_at,
            language=_truncate(page.language, FetchedDocument, 'language'), text=page.text,
            content_hash=page.content_hash), 'el documento descargado')
        document = Document(label=label, role=role, record=record, norm=NormalizedDocument(page.text),
                            publisher=page.publisher or registrable_domain(source.url), page=page)
        self.documents.append(document)
        return document

    def step_fetch(self):
        self.set_status(Status.FETCHING, 'Descargando la noticia enviada')
        url = self.submission.normalized_url or self.submission.url
        try:
            page = self.fetcher.fetch(url)
        except FetchError as error:
            raise PipelineError(f'No se pudo descargar la URL enviada: {error}') from error
        if len(page.text) < MIN_SUBMITTED_TEXT_CHARS:
            raise PipelineError('No se pudo extraer texto suficiente de la página enviada '
                                '(puede requerir JavaScript, suscripción o no ser un artículo).')
        return self._store_document(page, FetchedDocument.Role.SUBMITTED, 'D1')

    # --- 2. researching ---------------------------------------------------------------

    def step_research(self, submitted):
        self.set_status(Status.RESEARCHING, 'Buscando cobertura independiente')
        max_related = int(getattr(settings, 'INGESTION_MAX_RELATED', 5) or 0)
        started = timezone.now()
        if max_related <= 0:
            self.record_run('researcher', started=started, status=AgentRun.Status.SKIPPED,
                            output={'motivo': 'INGESTION_MAX_RELATED = 0'})
            self.set_status(Status.RESEARCHING, 'Fuente única: búsqueda de cobertura desactivada')
            return
        instructions, prompt = agents.researcher_request(submitted.page, max_related)
        summary = f'Búsqueda de cobertura para {submitted.record.source.url}'
        try:
            result = self.llm.web_search(instructions=instructions, input=prompt)
        except LLMError as error:
            self.record_run('researcher', started=started, status=AgentRun.Status.ERROR, input_summary=summary,
                            error=str(error))
            self.notes.append('Fuente única: la búsqueda de cobertura independiente falló.')
            self.set_status(Status.RESEARCHING, 'Fuente única: la búsqueda falló; se continúa con la fuente enviada')
            return
        cited = {canonical_url(item.url) for item in result.citations if item.url.startswith(('http://', 'https://'))}
        text_urls = re.findall(r'https?://[^\s)\]>"\']+', result.text or '')
        ignored = sorted({url for url in text_urls if canonical_url(url.rstrip('.,;')) not in cited})
        own = canonical_url(submitted.record.source.url)
        accepted, rejected = [], []
        for citation in result.citations:
            if len(accepted) >= max_related:
                break
            if not citation.url.startswith(('http://', 'https://')):
                continue
            url = canonical_url(citation.url)
            if url == own or url in [item['url'] for item in accepted]:
                continue
            if registrable_domain(url) == submitted.domain:
                rejected.append({'url': url, 'motivo': 'mismo editor que la fuente enviada'})
                continue
            accepted.append({'url': url, 'title': citation.title})
        fetched = 0
        for index, item in enumerate(accepted, start=2):
            self.set_status(Status.RESEARCHING, f'Descargando cobertura relacionada ({index - 1}/{len(accepted)})')
            try:
                page = self.fetcher.fetch(item['url'])
            except UnsafeURLError as error:
                item['error'] = str(error)
                continue
            except FetchError as error:
                item['error'] = str(error)
                self._store_failed(item, error)
                continue
            if len(page.text) < MIN_SUBMITTED_TEXT_CHARS:
                item['error'] = 'texto insuficiente'
                continue
            if self._store_document(page, FetchedDocument.Role.RELATED, f'D{len(self.documents) + 1}'):
                fetched += 1
        self.record_run('researcher', started=started, status=AgentRun.Status.OK, input_summary=summary, result=result,
                        output={'citadas_por_la_herramienta': accepted, 'descartadas': rejected,
                                'urls_en_texto_no_citadas_ignoradas': ignored, 'descargadas': fetched})
        self.single_source = fetched == 0
        if self.single_source:
            self.notes.append('Fuente única: no se encontró cobertura independiente descargable.')
            self.set_status(Status.RESEARCHING, 'Fuente única: sin cobertura independiente descargable')

    def _store_failed(self, item, error):
        source = self._source_for(item['url'], item.get('title') or item['url'], '', None)
        if any(doc.record.source_id == source.pk for doc in self.documents) or \
                FetchedDocument.objects.filter(submission=self.submission, source=source).exists():
            return
        _validated_save(FetchedDocument(
            submission=self.submission, source=source, role=FetchedDocument.Role.RELATED, fetched_at=timezone.now(),
            http_status=error.http_status, content_type=_truncate(error.content_type, FetchedDocument, 'content_type'),
            title=_truncate(item.get('title'), FetchedDocument, 'title'), fetch_error=str(error)), 'el documento fallido')

    # --- 3. extracting ----------------------------------------------------------------

    def step_extract(self):
        candidates = []
        for document in self.documents:
            self.set_status(Status.EXTRACTING, f'Extrayendo afirmaciones del documento {document.label} '
                                               f'({len(candidates)} hasta ahora)')
            started = timezone.now()
            instructions, prompt = agents.extractor_request(document.page, document.label)
            summary = f'{document.label} {document.record.source.url} ({len(document.page.text)} caracteres)'
            try:
                result = self.llm.structured(instructions=instructions, input=prompt, schema_name='afirmaciones',
                                             schema=agents.EXTRACTOR_SCHEMA)
            except LLMError as error:
                self.record_run('extractor', started=started, status=AgentRun.Status.ERROR, input_summary=summary,
                                error=str(error))
                if document.role == FetchedDocument.Role.SUBMITTED:
                    raise PipelineError(f'No se pudieron extraer afirmaciones de la noticia enviada: {error}') from error
                continue
            accepted, discarded = self._check_claims(document, result.data.get('claims'), candidates)
            self.record_run('extractor', started=started, status=AgentRun.Status.OK, input_summary=summary,
                            result=result, output={'propuestas': result.data, 'aceptadas': accepted,
                                                   'descartadas': discarded})
        return candidates

    def _check_claims(self, document, proposals, candidates):
        """Deterministic verification of quotes, dates, attribution, actors and places."""
        accepted, discarded = [], []
        for index, raw in enumerate(proposals if isinstance(proposals, list) else []):
            if not isinstance(raw, dict):
                continue
            kind = raw.get('kind')
            text_es = (raw.get('text_es') or '').strip()
            if kind not in ('fact', 'statement', 'analysis') or not text_es:
                discarded.append({'indice': index, 'motivo': 'tipo o texto no válido'})
                continue
            if _URL_PATTERN.search(text_es):
                discarded.append({'indice': index, 'motivo': 'el texto contiene una URL'})
                continue
            quote = document.norm.check_quote(raw.get('quote'))
            if not quote.ok:
                discarded.append({'indice': index, 'motivo': quote.reason})
                continue
            attributed = (raw.get('attributed_to') or '').strip() or None
            if attributed and not document.norm.contains(attributed):
                if kind == 'statement':
                    discarded.append({'indice': index, 'motivo': 'el autor atribuido no aparece en el documento'})
                    continue
                attributed = None
            if kind == 'statement' and not attributed:
                discarded.append({'indice': index, 'motivo': 'declaración sin autor verificable'})
                continue
            actors, seen = [], set()
            for actor in raw.get('actors') or []:
                name = (actor.get('name') or '').strip() if isinstance(actor, dict) else ''
                kind_actor = actor.get('kind') if isinstance(actor, dict) else None
                key = normalize_text(name)
                if kind_actor in Actor.Kind.values and key not in seen and document.norm.contains(name, min_chars=2):
                    seen.add(key)
                    actors.append({'name': name[:255], 'kind': kind_actor})
            places = []
            for place in raw.get('places') or []:
                if isinstance(place, str) and place.strip() and document.norm.contains(place, min_chars=2) \
                        and normalize_text(place) not in [normalize_text(item) for item in places]:
                    places.append(place.strip()[:200])
            event_date = None
            if raw.get('event_date'):
                check = check_event_date(raw.get('event_date'), raw.get('event_date_quote'), document.norm, today=self.today)
                if check.ok:
                    event_date = check.value
                else:
                    discarded.append({'indice': index, 'motivo': f'fecha descartada ({check.reason}); se conserva la afirmación'})
            candidate = Candidate(id=len(candidates) + 1, document=document, kind=kind, text_es=text_es[:MAX_CLAIM_TEXT_CHARS],
                                  quote=quote, attributed_to=attributed, actors=actors, places=places, event_date=event_date)
            candidates.append(candidate)
            accepted.append({'indice': index, 'id': candidate.id, 'localizador': quote.locator,
                             'fecha': event_date.isoformat() if event_date else None})
        return accepted, discarded

    # --- 4. verifying -------------------------------------------------------------------

    def step_verify(self, candidates):
        self.set_status(Status.VERIFYING, f'Comprobando la fidelidad de {len(candidates)} afirmaciones citadas')
        if not candidates:
            raise PipelineError('Ninguna afirmación pudo verificarse con una cita literal del material descargado; '
                                'no se crea la observación.')
        started = timezone.now()
        payload = [{'id': item.id, 'kind': item.kind, 'document': item.document.label, 'quote': item.quote.excerpt,
                    'text_es': item.text_es, 'attributed_to': item.attributed_to} for item in candidates]
        instructions, prompt = agents.verifier_request(payload)
        summary = f'{len(candidates)} afirmaciones con cita comprobada en {len(self.documents)} documentos'
        try:
            result = self.llm.structured(instructions=instructions, input=prompt, schema_name='verificacion',
                                         schema=agents.VERIFIER_SCHEMA)
        except LLMError as error:
            self.record_run('verifier', started=started, status=AgentRun.Status.ERROR, input_summary=summary, error=str(error))
            raise PipelineError(f'No se pudo comprobar la fidelidad de las afirmaciones: {error}') from error
        by_id = {item.id: item for item in candidates}
        faithful = set()
        for entry in result.data.get('results') or []:
            if isinstance(entry, dict) and entry.get('faithful') is True and entry.get('id') in by_id:
                faithful.add(entry['id'])
        survivors = {pk: item for pk, item in by_id.items() if pk in faithful}
        groups, used = [], set()
        for entry in result.data.get('groups') or []:
            ids = entry.get('ids') if isinstance(entry, dict) else None
            ids = sorted(set(i for i in ids if isinstance(i, int) and not isinstance(i, bool))) if isinstance(ids, list) else []
            members = [survivors.get(i) for i in ids]
            if (len(ids) < 2 or None in members or any(i in used for i in ids)
                    or any(item.kind != 'fact' for item in members)
                    or len({item.document.label for item in members}) != len(members)):
                continue
            used.update(ids)
            groups.append(members)
        groups.extend([item] for pk, item in sorted(survivors.items()) if pk not in used)
        verified = [self._merge(members) for members in groups]
        verified.sort(key=lambda claim: claim.id)
        if not any(claim.kind == 'fact' for claim in verified):
            self.record_run('verifier', started=started, status=AgentRun.Status.OK, input_summary=summary, result=result,
                            output={'propuesta': result.data, 'fieles': sorted(faithful), 'verificadas': []})
            raise PipelineError('No quedó ningún hecho verificado tras comprobar la fidelidad de las paráfrasis; '
                                'no se crea la observación.')
        self.record_run('verifier', started=started, status=AgentRun.Status.OK, input_summary=summary, result=result,
                        output={'propuesta': result.data, 'fieles': sorted(faithful),
                                'descartadas_por_infidelidad': sorted(set(by_id) - faithful),
                                'verificadas': [{'id': claim.id, 'tipo': claim.kind, 'editores': claim.publishers,
                                                 'documentos': [m.document.label for m in claim.members]} for claim in verified]})
        return verified

    def _merge(self, members):
        members = sorted(members, key=lambda item: (item.document.role != FetchedDocument.Role.SUBMITTED, item.id))
        lead = members[0]
        actors, seen = [], set()
        for member in members:
            for actor in member.actors:
                key = (normalize_text(actor['name']), actor['kind'])
                if key not in seen:
                    seen.add(key)
                    actors.append(actor)
        places = []
        for member in members:
            for place in member.places:
                if normalize_text(place) not in [normalize_text(item) for item in places]:
                    places.append(place)
        dates = {member.event_date for member in members if member.event_date}
        attributed_kind = next((actor['kind'] for actor in lead.actors
                                if lead.attributed_to and normalize_text(actor['name']) == normalize_text(lead.attributed_to)),
                               Actor.Kind.OTHER)
        return VerifiedClaim(id=min(item.id for item in members), kind=lead.kind, text_es=lead.text_es,
                             attributed_to=lead.attributed_to, attributed_kind=attributed_kind, actors=actors,
                             places=places, event_date=dates.pop() if len(dates) == 1 else None, members=members)

    # --- 5. geolocating -------------------------------------------------------------------

    def step_geolocate(self, verified):
        self.set_status(Status.GEOLOCATING, 'Normalizando lugares mencionados')
        started = timezone.now()
        mentions = {}
        for claim in verified:
            for place in claim.places:
                entry = mentions.setdefault(normalize_text(place), {'mention': place, 'claim_ids': [], 'claims': []})
                entry['claim_ids'].append(claim.id)
                entry['claims'].append(claim.text_es)
        if not mentions:
            self.record_run('geolocator', started=started, status=AgentRun.Status.SKIPPED,
                            output={'motivo': 'las afirmaciones verificadas no mencionan lugares'})
            return None
        instructions, prompt = agents.geolocator_request(list(mentions.values()))
        summary = f'{len(mentions)} menciones de lugar'
        try:
            result = self.llm.structured(instructions=instructions, input=prompt, schema_name='lugares',
                                         schema=agents.GEOLOCATOR_SCHEMA)
        except LLMError as error:
            self.record_run('geolocator', started=started, status=AgentRun.Status.ERROR, input_summary=summary, error=str(error))
            self.notes.append('Sin ubicación: no se pudieron normalizar los lugares.')
            return None
        self.set_status(Status.GEOLOCATING, 'Consultando OpenStreetMap (Nominatim)')
        attempts, place = [], None
        for entry in (result.data.get('places') or [])[:agents.MAX_PLACES]:
            mention = mentions.get(normalize_text(entry.get('mention') or '')) if isinstance(entry, dict) else None
            if mention is None:
                attempts.append({'propuesta': entry, 'motivo': 'mención no presente en las afirmaciones verificadas'})
                continue
            query = (entry.get('query') or '').strip()
            if not query or _URL_PATTERN.search(query) or not NormalizedDocument(query).contains(mention['mention']):
                query = mention['mention']  # the model may disambiguate, never relocate
            found = self.geocoder.search(query, entry.get('country_code'))
            attempts.append({'mencion': mention['mention'], 'consulta': query, 'pais': entry.get('country_code'),
                             'resultado': found.locator if found else None})
            if found:
                place = {'mention': mention['mention'], 'query': query, 'result': found}
                break
        self.record_run('geolocator', started=started, status=AgentRun.Status.OK, input_summary=summary, result=result,
                        output={'propuesta': result.data, 'geocodificacion': attempts})
        return place

    # --- 6. analyzing ----------------------------------------------------------------------

    def step_analyze(self, verified):
        self.set_status(Status.ANALYZING, 'Redactando título, resumen y análisis')
        started = timezone.now()
        claims_payload = [{'id': claim.id, 'kind': claim.kind, 'text_es': claim.text_es, 'attributed_to': claim.attributed_to,
                           'actors': [actor['name'] for actor in claim.actors],
                           'date': claim.event_date.isoformat() if claim.event_date else None,
                           'editores_que_lo_respaldan': claim.publishers} for claim in verified]
        publishers = len({doc.domain for claim in verified for doc in (m.document for m in claim.members)})
        instructions, prompt = agents.analyst_request(claims_payload, publishers, publishers <= 1)
        summary = f'{len(verified)} afirmaciones verificadas de {publishers} editores'
        try:
            result = self.llm.structured(instructions=instructions, input=prompt, schema_name='analisis',
                                         schema=agents.ANALYST_SCHEMA)
        except LLMError as error:
            self.record_run('analyst', started=started, status=AgentRun.Status.ERROR, input_summary=summary, error=str(error))
            raise PipelineError(f'No se pudo redactar el análisis: {error}') from error
        data = result.data
        by_id = {claim.id: claim for claim in verified}
        corpus = set()
        for claim in verified:
            corpus |= _numbers(claim.text_es)
            for member in claim.members:
                corpus |= _numbers(member.quote.excerpt)
            if claim.event_date:
                corpus |= _numbers(claim.event_date.isoformat()) | {str(claim.event_date.day), str(claim.event_date.year)}
        facts = [claim for claim in verified if claim.kind == 'fact']
        decisions = []

        title = (data.get('title') or '').strip()
        if not _supported_text(title, corpus) or len(title) > 255:
            decisions.append('título sustituido: contenía URL o cifras sin respaldo, o era inválido')
            title = facts[0].text_es
        if len(title) > MAX_TITLE_CHARS:
            title = title[:MAX_TITLE_CHARS].rsplit(' ', 1)[0].rstrip(',;:') + '…'
        summary_text = (data.get('summary') or '').strip()
        if not _supported_text(summary_text, corpus):
            decisions.append('resumen sustituido: contenía URL o cifras sin respaldo, o estaba vacío')
            summary_text = ' '.join(claim.text_es for claim in facts[:2])
        category = data.get('category')
        if category not in EVENT_CATEGORIES:
            raise PipelineError('El análisis propuso una categoría no admitida.')

        story = data.get('story') if isinstance(data.get('story'), dict) else {}
        story_title = (story.get('title') or '').strip()
        story_summary = (story.get('summary') or '').strip()
        if not _supported_text(story_title, corpus) or len(story_title) > 255:
            story_title = title
        if not _supported_text(story_summary, corpus):
            story_summary = summary_text
        story_kind = story.get('kind') if story.get('kind') in TimelineStory.Kind.values else TimelineStory.Kind.OTHER

        date_claim = by_id.get(data.get('event_date_claim_id'))
        if date_claim is None or date_claim.kind != 'fact' or date_claim.event_date is None:
            if data.get('event_date_claim_id') is not None:
                decisions.append('fecha propuesta descartada: la afirmación citada no tiene fecha verificada')
            dated = {claim.event_date for claim in facts if claim.event_date}
            event_date = dated.pop() if len(dated) == 1 else None
        else:
            event_date = date_claim.event_date

        analyses = []
        for entry in (data.get('analyses') or [])[:agents.MAX_ANALYSES]:
            text = (entry.get('text_es') or '').strip() if isinstance(entry, dict) else ''
            references = valid_references(entry.get('based_on'), set(by_id)) if isinstance(entry, dict) else None
            if references is None:
                decisions.append('análisis descartado: cita afirmaciones inexistentes o ninguna')
            elif not _supported_text(text, corpus) or len(text) > MAX_CLAIM_TEXT_CHARS:
                decisions.append('análisis descartado: contiene URL o cifras sin respaldo, o es inválido')
            else:
                analyses.append({'text': text, 'based_on': references})

        participations, seen = [], set()
        for entry in data.get('participations') or []:
            if not isinstance(entry, dict):
                continue
            claim = by_id.get(entry.get('claim_id'))
            role = entry.get('role')
            if claim is None or role not in Participation.Role.values:
                continue
            name = normalize_text(entry.get('actor_name') or '')
            options = list(claim.actors)
            if claim.attributed_to:
                options.append({'name': claim.attributed_to, 'kind': claim.attributed_kind})
            actor = next((item for item in options if normalize_text(item['name']) == name), None)
            if actor is None or (normalize_text(actor['name']), actor['kind'], role) in seen:
                continue
            seen.add((normalize_text(actor['name']), actor['kind'], role))
            participations.append({'actor': actor, 'role': role, 'claim_id': claim.id})

        self.record_run('analyst', started=started, status=AgentRun.Status.OK, input_summary=summary, result=result,
                        output={'propuesta': data, 'decisiones': decisions, 'analisis_aceptados': len(analyses),
                                'participaciones_aceptadas': len(participations)})
        return {'title': title, 'summary': summary_text, 'category': category, 'event_date': event_date,
                'story': {'title': story_title, 'summary': story_summary, 'kind': story_kind},
                'analyses': analyses, 'participations': participations}

    # --- 7. persistence ------------------------------------------------------------------------

    def _actor(self, name, kind, cache):
        name = name.strip()[:255]
        key = (name, kind)
        if key not in cache:
            actor = Actor.objects.filter(name=name, kind=kind).first()
            cache[key] = actor or _validated_save(Actor(name=name, kind=kind), f'el actor «{name}»')
        return cache[key]

    def persist(self, verified, place, analysis):
        auto_publish = bool(getattr(settings, 'INGESTION_AUTO_PUBLISH', False))
        user = self.submission.user
        with transaction.atomic():
            actors = {}
            event_date = analysis['event_date']
            event = _validated_save(Event(
                slug=_unique_slug(Event, analysis['title'], f'ia{self.submission.pk}'),
                title=analysis['title'][:255], summary=analysis['summary'], category=analysis['category'],
                status=Event.Status.PUBLISHED if auto_publish else Event.Status.DRAFT,
                start_date=event_date, end_date=None,
                date_precision=Event.Precision.EXACT if event_date else Event.Precision.UNKNOWN,
                as_of=self.today, origin=Event.Origin.AI_PIPELINE, submitted_by=user), 'el acontecimiento')
            claims = {}
            for item in verified:
                if item.attributed_to:
                    attributed = self._actor(item.attributed_to, item.attributed_kind, actors)
                elif item.kind == 'analysis':
                    lead = item.members[0].document
                    attributed = self._actor(lead.publisher, Actor.Kind.ORGANIZATION, actors)
                else:
                    attributed = None
                claim = _validated_save(Claim(event=event, text=item.text_es, kind=item.kind,
                                              status=Claim.Status.SUPPORTED, attributed_to=attributed), 'una afirmación')
                claims[item.id] = claim
                publishers = item.publishers
                suffix = (' · fuente única (un solo editor)' if publishers <= 1
                          else f' · corroborado por {publishers} editores distintos')
                for member in item.members:
                    _validated_save(Evidence(claim=claim, source=member.document.record.source,
                                             locator=(member.quote.locator + suffix)[:500], excerpt=member.quote.excerpt),
                                    'una evidencia')
            ai_actor = self._actor(AI_ACTOR_NAME, Actor.Kind.OTHER, actors) if analysis['analyses'] else None
            for entry in analysis['analyses']:
                claim = _validated_save(Claim(event=event, text=entry['text'], kind=Claim.Kind.ANALYSIS,
                                              status=Claim.Status.SUPPORTED, attributed_to=ai_actor), 'un análisis')
                cited = [claims[ref] for ref in entry['based_on']]
                locator = ('Síntesis de afirmaciones ' + ', '.join(f'#{item.pk}' for item in cited))[:500]
                sources = []
                for ref in entry['based_on']:
                    for member in next(v for v in verified if v.id == ref).members:
                        if member.document.record.source not in sources:
                            sources.append(member.document.record.source)
                for source in sources:
                    _validated_save(Evidence(claim=claim, source=source, locator=locator, excerpt=''), 'una evidencia')
            for entry in analysis['participations']:
                actor = self._actor(entry['actor']['name'], entry['actor']['kind'], actors)
                _validated_save(Participation(event=event, actor=actor, role=entry['role'], claim=claims[entry['claim_id']],
                                              note='Papel propuesto por el análisis asistido por IA según la afirmación citada.'),
                                'una participación')
            if place:
                found = place['result']
                osm_source = Source.objects.filter(url=found.osm_url).first() or _validated_save(Source(
                    url=found.osm_url, title=_truncate(f'OpenStreetMap: {found.display_name or found.query}', Source, 'title'),
                    creator='Colaboradores de OpenStreetMap (vía Nominatim)', accessed_at=self.today,
                    rights_note=ATTRIBUTION), 'la fuente geográfica')
                _validated_save(Location(event=event, label=_truncate(place['query'], Location, 'label'),
                                         longitude=found.longitude, latitude=found.latitude,
                                         precision=Location.Precision.APPROXIMATE,
                                         note=LOCATION_NOTE.format(mention=place['mention']), source=osm_source,
                                         source_locator=found.locator), 'la ubicación')
            story = self.submission.target_story
            if story is None:
                spec = analysis['story']
                story = _validated_save(TimelineStory(
                    slug=_unique_slug(TimelineStory, spec['title'], f'ia{self.submission.pk}'), title=spec['title'][:255],
                    summary=spec['summary'], kind=spec['kind'], as_of=self.today,
                    origin=TimelineStory.Origin.AI_PIPELINE, created_by=user), 'la cronología')
            order = (story.entries.aggregate(value=Max('order'))['value'] or 0) + 1
            _validated_save(TimelineEntry(story=story, event=event, order=order), 'la entrada de la cronología')

            notes = ' '.join(self.notes)
            self.submission.event = event
            self.submission.story = story
            self.submission.status = Status.PUBLISHED if auto_publish else Status.REVIEW
            self.submission.step_detail = (('Publicado automáticamente. ' if auto_publish else
                                            'Borrador listo para revisión del equipo. ') + notes)[:255]
            self.submission.error = ''
            self.submission.finished_at = timezone.now()
            self.submission.save(update_fields=['event', 'story', 'status', 'step_detail', 'error', 'finished_at', 'updated_at'])
