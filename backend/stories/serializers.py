"""Read-only presentation of reviewed, source-linked database records."""
from django.db.models import Count, F, Max, Min, Prefetch, Q

from .models import Claim, Event, Evidence, TimelineStory

NEWS_SLUG = 'geopolitica'


def source_data(evidence):
    source = evidence.source
    return {
        'title': source.title,
        'creator': source.creator,
        'url': source.url,
        'published_at': source.published_at.isoformat() if source.published_at else None,
        'publication': f"Publicada el {source.published_at.isoformat()}" if source.published_at else 'Fecha de publicación desconocida',
        'locator': evidence.locator,
        'rights_note': source.rights_note,
    }


def date_label(event):
    months = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
    start, end = event.start_date, event.end_date
    if start is None and end is None:
        return 'Fecha desconocida'
    if start and end and start.year == end.year and start.month == end.month and start != end:
        label = f'{start.day}–{end.day} {months[start.month - 1]} {start.year}'
    else:
        def format_date(d):
            return f'{d.day} {months[d.month - 1]} {d.year}'
        dates = [start] if start == end else [start, end]
        label = ' – '.join(format_date(d) for d in dates if d is not None)
    return f'Aproximadamente {label}' if event.date_precision == 'approximate' else label


def event_queryset():
    return (Event.objects.filter(status__in=[Event.Status.REVIEWED, Event.Status.PUBLISHED])
            .prefetch_related(Prefetch('claims', queryset=Claim.objects.filter(status=Claim.Status.SUPPORTED).select_related('attributed_to').prefetch_related('evidence__source').order_by('id')),
                              'locations__source', 'participations__actor', 'effects__affected_actor', 'effects__perspective'))


def event_data(event, identifier, order):
    claims = [item for item in event.claims.all() if item.evidence.all()]
    facts = [item for item in claims if item.kind == Claim.Kind.FACT]
    if not facts:
        return None
    seen, sources = set(), []
    for item in claims:
        for evidence in item.evidence.all():
            if evidence.source_id not in seen:
                seen.add(evidence.source_id)
                sources.append(source_data(evidence))
    locations = list(event.locations.all())
    location = locations[0] if locations else None
    place = None
    if location:
        coordinates = None if location.longitude is None or location.latitude is None else [location.longitude, location.latitude]
        place = {'label': location.label, 'coordinates': coordinates, 'precision': location.precision,
                 'note': location.note, 'coordinate_source': {'url': location.source.url, 'locator': location.source_locator} if location.source else None}
    visible_claim_ids = {item.id for item in claims}
    participants = [{'name': item.actor.name, 'kind': item.actor.kind, 'role': item.role, 'note': item.note, 'claim_id': item.claim_id}
                    for item in event.participations.all() if item.claim_id in visible_claim_ids]
    effects = [{'description': item.description, 'affected_actor': item.affected_actor.name if item.affected_actor else None,
                'perspective': item.perspective.name if item.perspective else None, 'valence': item.valence, 'claim_id': item.claim_id}
               for item in event.effects.all() if item.claim_id in visible_claim_ids and (item.valence == 'unknown' or item.perspective_id)]
    return {
            'id': identifier, 'order': order, 'title': event.title, 'category': event.category,
            'description': ' '.join(item.text for item in facts[:2]),
            'analysis': ' '.join(item.text for item in claims if item.kind in (Claim.Kind.STATEMENT, Claim.Kind.ANALYSIS)),
            'published_at': min((source['published_at'] for source in sources if source['published_at']), default=None),
            'as_of': event.as_of.isoformat() if event.as_of else None,
            'date': {'start': event.start_date.isoformat() if event.start_date else None,
                     'end': event.end_date.isoformat() if event.end_date else None,
                     'start_year': event.start_date.year if event.start_date else None,
                     'end_year': event.end_date.year if event.end_date else None,
                     'precision': event.date_precision, 'label': date_label(event)},
            'place': place, 'evidence_status': 'supported', 'sources': sources,
            'claims': [{'id': item.pk, 'text': item.text, 'kind': item.kind, 'status': item.status,
                        'attributed_to': item.attributed_to.name if item.attributed_to else None,
                        'sources': [source_data(evidence) for evidence in item.evidence.all()]} for item in claims],
            'actors': participants, 'effects': effects,
    }


def event_date_bounds(events):
    """First and last ``date.start`` (ISO) among serialized events, ignoring unknown dates."""
    starts = [item['date']['start'] for item in events if item['date']['start']]
    return (min(starts), max(starts)) if starts else (None, None)


def story_from_database():
    event = event_queryset().filter(slug=NEWS_SLUG).first()
    if event is None:
        return None
    data = event_data(event, 'cop31-apertura', 1)
    if data is None:
        return None
    first, last = event_date_bounds([data])
    return {'slug': event.slug, 'title': event.title, 'summary': event.summary,
            'kind': TimelineStory.Kind.DIPLOMACY, 'as_of': data['as_of'],
            'first_event_date': first, 'last_event_date': last, 'events': [data]}


def timeline_from_database(slug):
    story = TimelineStory.objects.filter(slug=slug).first()
    if story is None:
        return None
    entries = list(story.entries.select_related('event').order_by(F('event__start_date').asc(nulls_last=True), 'order', 'pk'))
    event_map = {event.pk: event for event in event_queryset().filter(pk__in=[entry.event_id for entry in entries])}
    events = []
    for entry in entries:
        event = event_map.get(entry.event_id)
        if event is not None:
            data = event_data(event, event.slug, entry.order)
            if data is not None:
                events.append(data)
    if not events:
        return None
    first, last = event_date_bounds(events)
    return {'slug': story.slug, 'title': story.title, 'summary': story.summary, 'kind': story.kind,
            'as_of': story.as_of.isoformat() if story.as_of else None,
            'first_event_date': first, 'last_event_date': last, 'events': events}


def visible_events():
    """Events that ``event_data`` would serve: reviewed/published with a supported, evidenced fact."""
    evidenced_facts = Evidence.objects.filter(claim__kind=Claim.Kind.FACT, claim__status=Claim.Status.SUPPORTED).values('claim__event_id')
    return Event.objects.filter(status__in=[Event.Status.REVIEWED, Event.Status.PUBLISHED], pk__in=evidenced_facts)


def story_list():
    """Summaries for GET /api/stories/, newest ``last_event_date`` first."""
    visible = visible_events().values('pk')
    in_visible = Q(entries__event__in=visible)
    stories = (TimelineStory.objects.exclude(slug=NEWS_SLUG)
               .annotate(events_count=Count('entries', filter=in_visible, distinct=True),
                         first_event=Min('entries__event__start_date', filter=in_visible),
                         last_event=Max('entries__event__start_date', filter=in_visible))
               .filter(events_count__gt=0))
    items = [{'slug': story.slug, 'title': story.title, 'summary': story.summary, 'kind': story.kind,
              'events_count': story.events_count,
              'first_event_date': story.first_event.isoformat() if story.first_event else None,
              'last_event_date': story.last_event.isoformat() if story.last_event else None,
              'as_of': story.as_of.isoformat() if story.as_of else None} for story in stories]
    news = story_from_database()
    if news is not None:
        items.append({'slug': news['slug'], 'title': news['title'], 'summary': news['summary'], 'kind': news['kind'],
                      'events_count': len(news['events']), 'first_event_date': news['first_event_date'],
                      'last_event_date': news['last_event_date'], 'as_of': news['as_of']})
    items.sort(key=lambda item: item['slug'])
    items.sort(key=lambda item: item['last_event_date'] or '', reverse=True)
    return items
