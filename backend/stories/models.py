from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from .categories import EVENT_CATEGORIES, is_valid_category


class Origin(models.TextChoices):
    """Who produced a record: the editorial team or the AI ingestion pipeline."""
    EDITORIAL = 'editorial', 'Editorial'
    AI_PIPELINE = 'ai_pipeline', 'Flujo de agentes de IA'


class Event(models.Model):
    Origin = Origin

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        REVIEWED = 'reviewed', 'Revisado'
        PUBLISHED = 'published', 'Publicado'

    class Precision(models.TextChoices):
        EXACT = 'exact', 'Exacta'
        RANGE = 'range', 'Intervalo'
        APPROXIMATE = 'approximate', 'Aproximada'
        UNKNOWN = 'unknown', 'Desconocida'

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    category = models.CharField(max_length=80)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    date_precision = models.CharField(max_length=12, choices=Precision.choices, default=Precision.UNKNOWN)
    as_of = models.DateField(null=True, blank=True)
    origin = models.CharField(max_length=12, choices=Origin.choices, default=Origin.EDITORIAL)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_events')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(start_date__isnull=True) | Q(end_date__isnull=True) | Q(end_date__gte=F('start_date')), name='event_dates_ordered'),
            models.CheckConstraint(condition=(Q(date_precision='unknown', start_date__isnull=True, end_date__isnull=True) | Q(date_precision='exact', start_date__isnull=False, end_date__isnull=True) | Q(date_precision='exact', start_date__isnull=False, end_date=F('start_date')) | Q(date_precision='range', start_date__isnull=False, end_date__isnull=False) | (Q(date_precision='approximate') & (Q(start_date__isnull=False) | Q(end_date__isnull=False)))), name='event_dates_precision'),
        ]

    def clean(self):
        super().clean()
        if self.category and not is_valid_category(self.category):
            raise ValidationError({'category': f'Categoría desconocida «{self.category}». Valores admitidos: {", ".join(EVENT_CATEGORIES)}.'})

    def __str__(self):
        return self.title


class Source(models.Model):
    title = models.CharField(max_length=500)
    creator = models.CharField(max_length=255)
    url = models.URLField(unique=True, max_length=1000)
    published_at = models.DateField(null=True, blank=True)
    accessed_at = models.DateField(null=True, blank=True)
    rights_note = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Actor(models.Model):
    class Kind(models.TextChoices):
        COUNTRY = 'country', 'País'
        ORGANIZATION = 'organization', 'Organización'
        PERSON = 'person', 'Persona'
        OTHER = 'other', 'Otro'

    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    country_code = models.CharField(max_length=2, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['name', 'kind'], name='actor_name_kind_unique')]

    def __str__(self):
        return self.name


class Claim(models.Model):
    class Kind(models.TextChoices):
        FACT = 'fact', 'Hecho'
        STATEMENT = 'statement', 'Declaración'
        ANALYSIS = 'analysis', 'Análisis'
        OBJECTIVE = 'objective', 'Objetivo declarado'
        ACTION = 'action', 'Acción'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        SUPPORTED = 'supported', 'Respaldada'
        DISPUTED = 'disputed', 'Disputada'
        UNCERTAIN = 'uncertain', 'Incierta'
        REJECTED = 'rejected', 'Rechazada'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='claims')
    text = models.TextField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    attributed_to = models.ForeignKey(Actor, on_delete=models.PROTECT, null=True, blank=True, related_name='attributed_claims')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:80]


class Evidence(models.Model):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='evidence')
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='evidence')
    locator = models.CharField(max_length=500)
    excerpt = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['claim', 'source', 'locator'], name='evidence_unique_locator'), models.CheckConstraint(condition=~Q(locator=''), name='evidence_locator_not_empty')]

    def clean(self):
        super().clean()
        if not self.locator.strip():
            raise ValidationError({'locator': 'Indica un localizador de la fuente.'})

    def __str__(self):
        return f'{self.source}: {self.locator}'


class Participation(models.Model):
    class Role(models.TextChoices):
        PARTICIPANT = 'participant', 'Participante'
        HOST = 'host', 'Anfitrión'
        DECLARED_INITIATOR = 'declared_initiator', 'Iniciador declarado'
        AFFECTED = 'affected', 'Afectado'
        OTHER = 'other', 'Otro'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='participations')
    actor = models.ForeignKey(Actor, on_delete=models.PROTECT, related_name='participations')
    role = models.CharField(max_length=20, choices=Role.choices)
    claim = models.ForeignKey(Claim, on_delete=models.PROTECT, related_name='participations')
    note = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.event_id and self.claim_id and self.claim.event_id != self.event_id:
            raise ValidationError({'claim': 'La afirmación debe pertenecer al mismo acontecimiento.'})

    def __str__(self):
        return f'{self.actor} · {self.get_role_display()}'


class Effect(models.Model):
    class Valence(models.TextChoices):
        UNKNOWN = 'unknown', 'Desconocida'
        POSITIVE = 'positive', 'Positiva'
        NEGATIVE = 'negative', 'Negativa'
        MIXED = 'mixed', 'Mixta'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='effects')
    description = models.TextField()
    affected_actor = models.ForeignKey(Actor, on_delete=models.PROTECT, null=True, blank=True, related_name='effects_affected')
    perspective = models.ForeignKey(Actor, on_delete=models.PROTECT, null=True, blank=True, related_name='effects_perspective')
    valence = models.CharField(max_length=10, choices=Valence.choices, default=Valence.UNKNOWN)
    claim = models.ForeignKey(Claim, on_delete=models.PROTECT, related_name='effects')

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(valence='unknown') | Q(perspective__isnull=False), name='effect_valence_requires_perspective')]

    def clean(self):
        super().clean()
        if self.event_id and self.claim_id and self.claim.event_id != self.event_id:
            raise ValidationError({'claim': 'La afirmación debe pertenecer al mismo acontecimiento.'})
        if self.valence != self.Valence.UNKNOWN:
            if not self.perspective_id:
                raise ValidationError({'perspective': 'Indica la perspectiva que sustenta la valoración.'})
            if self.claim_id and not self.claim.evidence.exists():
                raise ValidationError({'claim': 'La valoración requiere una afirmación con evidencia.'})

    def __str__(self):
        return self.description[:80]


class Location(models.Model):
    class Precision(models.TextChoices):
        APPROXIMATE = 'approximate', 'Aproximada'
        UNKNOWN = 'unknown', 'Desconocida'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='locations')
    label = models.CharField(max_length=255)
    longitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    latitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    precision = models.CharField(max_length=12, choices=Precision.choices, default=Precision.UNKNOWN)
    note = models.TextField(blank=True)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, null=True, blank=True, related_name='locations')
    source_locator = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(Q(longitude__isnull=True, latitude__isnull=True, precision='unknown') | (Q(longitude__isnull=False, latitude__isnull=False, longitude__gte=-180, longitude__lte=180, latitude__gte=-90, latitude__lte=90, precision='approximate', source__isnull=False) & ~Q(source_locator=''))), name='location_valid_coordinates')]

    def clean(self):
        super().clean()
        if self.longitude is not None or self.latitude is not None:
            if not self.source_locator.strip():
                raise ValidationError({'source_locator': 'Indica el localizador geográfico.'})

    def __str__(self):
        return self.label


class TimelineStory(models.Model):
    """Editorial grouping of independently sourced and dated events."""
    Origin = Origin

    class Kind(models.TextChoices):
        CONFLICT = 'conflict', 'Conflicto'
        DIPLOMACY = 'diplomacy', 'Diplomacia'
        OTHER = 'other', 'Otro'

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.OTHER)
    as_of = models.DateField(null=True, blank=True, help_text='Fecha de la última verificación editorial de la cronología.')
    origin = models.CharField(max_length=12, choices=Origin.choices, default=Origin.EDITORIAL)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_timeline_stories')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class TimelineEntry(models.Model):
    story = models.ForeignKey(TimelineStory, on_delete=models.CASCADE, related_name='entries')
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='timeline_entries')
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['story', 'order'], name='timeline_entry_unique_order'),
            models.UniqueConstraint(fields=['story', 'event'], name='timeline_entry_unique_event'),
        ]

    def __str__(self):
        return f'{self.story} · {self.event}'
