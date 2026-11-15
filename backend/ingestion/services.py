"""State transitions for news submissions, shared by the API and the Django admin.

Contract: docs/api/CONTRATO_USUARIOS_INGESTA.md §2. The agent pipeline (``ingestion/pipeline/``)
owns the ``queued → … → review`` steps; this module owns creation and the human decisions.
"""
from datetime import datetime, time
from urllib.parse import unquote_plus, urlsplit, urlunsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from stories.models import Event, TimelineEntry

from .models import NOTE_MAX_LENGTH, NewsSubmission

URL_MAX_LENGTH = 1000
_url_validator = URLValidator(schemes=['http', 'https'])


class SubmissionError(Exception):
    """A transition or request that is not allowed; ``status`` is the HTTP status to answer with."""

    def __init__(self, message, status=400, field=None):
        super().__init__(message)
        self.message, self.status, self.field = message, status, field


class DailyLimitExceeded(SubmissionError):
    def __init__(self, limit):
        super().__init__(f'Has alcanzado el límite de {limit} envíos por día. Inténtalo de nuevo mañana.', status=429)


def normalize_url(url):
    """Lowercase scheme and host, drop the fragment and every ``utm_*`` query parameter."""
    parts = urlsplit(url.strip())
    # Filter the raw ``key=value`` pairs so the remaining parameters keep their original encoding.
    query = '&'.join(pair for pair in parts.query.split('&')
                     if pair and not unquote_plus(pair.split('=', 1)[0]).lower().startswith('utm_'))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '/', query, ''))


def validate_submission_url(url):
    """Return the stripped URL or raise ``SubmissionError`` (field ``url``)."""
    if not isinstance(url, str) or not url.strip():
        raise SubmissionError('Este campo es obligatorio.', field='url')
    url = url.strip()
    if len(url) > URL_MAX_LENGTH:
        raise SubmissionError(f'La URL no puede superar {URL_MAX_LENGTH} caracteres.', field='url')
    try:
        _url_validator(url)
    except ValidationError as error:
        raise SubmissionError('Introduce una URL válida que empiece por http:// o https://.', field='url') from error
    if urlsplit(url).username or urlsplit(url).password:
        raise SubmissionError('La URL no puede incluir usuario ni contraseña.', field='url')
    return url


def active_submission(user, normalized_url):
    return (NewsSubmission.objects.filter(user=user, normalized_url=normalized_url)
            .exclude(status__in=NewsSubmission.TERMINAL_STATUSES).first())


def submissions_today(user):
    start = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    return NewsSubmission.objects.filter(user=user, created_at__gte=start).count()


def create_submission(user, url, note='', target_story=None):
    """Create a queued submission. Returns ``(submission, created)``.

    An active submission with the same normalized URL is returned instead of creating a duplicate
    (and does not count toward the daily limit).
    """
    url = validate_submission_url(url)
    if len(note) > NOTE_MAX_LENGTH:
        raise SubmissionError(f'Máximo {NOTE_MAX_LENGTH} caracteres.', field='note')
    normalized = normalize_url(url)
    if len(normalized) > URL_MAX_LENGTH:
        raise SubmissionError(f'La URL no puede superar {URL_MAX_LENGTH} caracteres.', field='url')
    existing = active_submission(user, normalized)
    if existing is not None:
        return existing, False
    limit = settings.INGESTION_DAILY_LIMIT
    if submissions_today(user) >= limit:
        raise DailyLimitExceeded(limit)
    try:
        with transaction.atomic():
            submission = NewsSubmission.objects.create(
                user=user, url=url, normalized_url=normalized, note=note, target_story=target_story,
                status=NewsSubmission.Status.QUEUED, step_detail='En cola para su procesamiento.')
    except IntegrityError:
        # Concurrent duplicate: the partial unique constraint kept a single active submission.
        existing = active_submission(user, normalized)
        if existing is None:
            raise
        return existing, False
    return submission, True


def _locked(submission):
    return NewsSubmission.objects.select_for_update().select_related('event', 'story', 'target_story').get(pk=submission.pk)


def publish_submission(submission, reviewer, note=''):
    """Staff decision: ``review`` → ``published``; the event becomes ``published`` and joins its story."""
    if not reviewer.is_staff:
        raise SubmissionError('Solo el equipo editorial puede publicar envíos.', status=403)
    with transaction.atomic():
        current = _locked(submission)
        if current.status != NewsSubmission.Status.REVIEW:
            raise SubmissionError(f'Solo se pueden publicar envíos pendientes de revisión (estado actual: {current.get_status_display()}).')
        event = current.event
        if event is None:
            raise SubmissionError('El envío no tiene un acontecimiento que publicar.')
        story = current.story or current.target_story
        if story is None:
            raise SubmissionError('El envío no tiene una cronología donde publicar el acontecimiento.')
        Event.objects.filter(pk=event.pk).update(status=Event.Status.PUBLISHED, updated_at=timezone.now())
        if not TimelineEntry.objects.filter(story=story, event=event).exists():
            last = TimelineEntry.objects.filter(story=story).aggregate(last=Max('order'))['last'] or 0
            TimelineEntry.objects.create(story=story, event=event, order=last + 1)
        current.status = NewsSubmission.Status.PUBLISHED
        current.story = story
        current.reviewed_by = reviewer
        current.review_note = note
        current.step_detail = 'Publicado tras la revisión editorial.'
        current.save(update_fields=['status', 'story', 'reviewed_by', 'review_note', 'step_detail', 'updated_at'])
    return current


def reject_submission(submission, reviewer, note):
    """Staff decision: ``review`` → ``rejected``; the event stays unpublished (``draft``)."""
    if not reviewer.is_staff:
        raise SubmissionError('Solo el equipo editorial puede rechazar envíos.', status=403)
    note = (note or '').strip()
    if not note:
        raise SubmissionError('Indica el motivo del rechazo.', field='note')
    with transaction.atomic():
        current = _locked(submission)
        if current.status != NewsSubmission.Status.REVIEW:
            raise SubmissionError(f'Solo se pueden rechazar envíos pendientes de revisión (estado actual: {current.get_status_display()}).')
        if current.event_id:
            Event.objects.filter(pk=current.event_id).update(status=Event.Status.DRAFT, updated_at=timezone.now())
        current.status = NewsSubmission.Status.REJECTED
        current.reviewed_by = reviewer
        current.review_note = note
        current.step_detail = 'Rechazado tras la revisión editorial.'
        current.save(update_fields=['status', 'reviewed_by', 'review_note', 'step_detail', 'updated_at'])
    return current


def retry_submission(submission, user):
    """Owner action: ``failed`` → ``queued`` (the pipeline picks it up again)."""
    if submission.user_id != user.pk:
        raise SubmissionError('Solo quien hizo el envío puede reintentarlo.', status=403)
    with transaction.atomic():
        current = _locked(submission)
        if current.status != NewsSubmission.Status.FAILED:
            raise SubmissionError('Solo se pueden reintentar envíos con error.')
        if active_submission(current.user, current.normalized_url) is not None:
            raise SubmissionError('Ya tienes otro envío en curso con esta URL.')
        current.status = NewsSubmission.Status.QUEUED
        current.error = ''
        current.step_detail = 'En cola para un nuevo intento.'
        current.started_at = None
        current.finished_at = None
        current.save(update_fields=['status', 'error', 'step_detail', 'started_at', 'finished_at', 'updated_at'])
    return current
