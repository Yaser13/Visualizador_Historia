"""Ingestion of user-submitted news (contract: docs/api/CONTRATO_USUARIOS_INGESTA.md §1).

Field names, choices and lowercase values are a shared contract with ``ingestion/pipeline/``.
"""
from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

NOTE_MAX_LENGTH = 1000
DOCUMENT_TEXT_MAX_LENGTH = 200_000


class NewsSubmission(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'queued', 'En cola'
        FETCHING = 'fetching', 'Descargando la noticia'
        RESEARCHING = 'researching', 'Buscando cobertura independiente'
        EXTRACTING = 'extracting', 'Extrayendo afirmaciones'
        VERIFYING = 'verifying', 'Verificando citas'
        GEOLOCATING = 'geolocating', 'Localizando lugares'
        ANALYZING = 'analyzing', 'Redactando el análisis'
        REVIEW = 'review', 'Pendiente de revisión'
        PUBLISHED = 'published', 'Publicado'
        REJECTED = 'rejected', 'Rechazado'
        FAILED = 'failed', 'Error'

    # A user may hold only one non-terminal submission per normalized URL.
    TERMINAL_STATUSES = (Status.PUBLISHED, Status.REJECTED, Status.FAILED)
    # Steps executed by the agent pipeline, in order.
    PIPELINE_STATUSES = (Status.FETCHING, Status.RESEARCHING, Status.EXTRACTING, Status.VERIFYING,
                         Status.GEOLOCATING, Status.ANALYZING)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='news_submissions')
    url = models.URLField(max_length=1000)
    normalized_url = models.URLField(max_length=1000, help_text='URL sin fragmento ni parámetros utm_*.')
    note = models.TextField(blank=True, validators=[MaxLengthValidator(NOTE_MAX_LENGTH)])
    target_story = models.ForeignKey('stories.TimelineStory', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='targeted_submissions')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    step_detail = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    event = models.ForeignKey('stories.Event', on_delete=models.SET_NULL, null=True, blank=True, related_name='submissions')
    story = models.ForeignKey('stories.TimelineStory', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='result_submissions')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_submissions')
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'envío de noticia'
        verbose_name_plural = 'envíos de noticias'
        constraints = [
            models.UniqueConstraint(fields=['user', 'normalized_url'],
                                    condition=~Q(status__in=['published', 'rejected', 'failed']),
                                    name='submission_unique_active_url',
                                    violation_error_message='Ya tienes un envío en curso con esta URL.'),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at'], name='submission_status_created'),
            models.Index(fields=['user', 'created_at'], name='submission_user_created'),
        ]

    @property
    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES

    def __str__(self):
        return f'#{self.pk} {self.normalized_url} ({self.status})'


class FetchedDocument(models.Model):
    class Role(models.TextChoices):
        SUBMITTED = 'submitted', 'Enviada por el usuario'
        RELATED = 'related', 'Cobertura relacionada'

    submission = models.ForeignKey(NewsSubmission, on_delete=models.CASCADE, related_name='documents')
    source = models.ForeignKey('stories.Source', on_delete=models.PROTECT, related_name='fetched_documents')
    role = models.CharField(max_length=10, choices=Role.choices)
    fetched_at = models.DateTimeField(default=timezone.now)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=500, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    published_at = models.DateField(null=True, blank=True, help_text='Solo si consta en los metadatos o en el texto.')
    language = models.CharField(max_length=16, blank=True)
    text = models.TextField(blank=True, validators=[MaxLengthValidator(DOCUMENT_TEXT_MAX_LENGTH)])
    content_hash = models.CharField(max_length=64, blank=True, help_text='sha256 hexadecimal del texto.')
    fetch_error = models.TextField(blank=True)

    class Meta:
        ordering = ['fetched_at', 'pk']
        verbose_name = 'documento descargado'
        verbose_name_plural = 'documentos descargados'
        constraints = [models.UniqueConstraint(fields=['submission', 'source'], name='fetched_document_unique_source')]

    def __str__(self):
        return self.title or str(self.source)


class AgentRun(models.Model):
    class Agent(models.TextChoices):
        RESEARCHER = 'researcher', 'Investigador'
        EXTRACTOR = 'extractor', 'Extractor'
        VERIFIER = 'verifier', 'Verificador'
        GEOLOCATOR = 'geolocator', 'Geolocalizador'
        ANALYST = 'analyst', 'Analista'

    class Status(models.TextChoices):
        OK = 'ok', 'Correcto'
        ERROR = 'error', 'Error'
        SKIPPED = 'skipped', 'Omitido'

    submission = models.ForeignKey(NewsSubmission, on_delete=models.CASCADE, related_name='agent_runs')
    agent = models.CharField(max_length=12, choices=Agent.choices)
    model = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices)
    input_summary = models.TextField(blank=True, help_text='Resumen corto de la entrada, sin claves ni secretos.')
    output = models.JSONField(default=dict, blank=True)
    tokens_in = models.PositiveIntegerField(null=True, blank=True)
    tokens_out = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['started_at', 'pk']
        verbose_name = 'ejecución de agente'
        verbose_name_plural = 'ejecuciones de agentes'
        indexes = [models.Index(fields=['submission', 'started_at'], name='agent_run_submission_started')]

    def __str__(self):
        return f'{self.get_agent_display()} · {self.status}'
