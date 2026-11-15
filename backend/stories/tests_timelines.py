"""Tests for updatable timelines (docs/api/CONTRATO_CRONOLOGIAS.md).

All timeline content here is SYNTHETIC test data written to temporary files;
it does not describe real events and uses example.org URLs.
"""
import copy
import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse

from .categories import EVENT_CATEGORIES
from .models import Actor, Claim, Event, Evidence, Location, Participation, Source, TimelineEntry, TimelineStory

MODELS = (TimelineStory, TimelineEntry, Event, Claim, Evidence, Source, Actor, Location, Participation)


def sample_event(slug, start, category='conflicto', coordinates=(10.0, 20.0), title=None):
    return {
        'slug': slug,
        'title': title or f'Hito sintético {slug}',
        'category': category,
        'start_date': start,
        'end_date': None,
        'date_precision': 'exact',
        'summary': 'Texto sintético de prueba.',
        'claims': [
            {'key': 'c1', 'kind': 'fact', 'text': f'Hecho sintético {slug}.', 'attributed_to': None,
             'evidence': [{'source': 'informe', 'locator': 'Párrafo 1'}]},
            {'key': 'c2', 'kind': 'statement', 'text': f'Declaración sintética {slug}.', 'attributed_to': 'gobierno',
             'evidence': [{'source': 'informe', 'locator': 'Párrafo 2'}]},
        ],
        'location': {'label': 'Ciudad ficticia', 'coordinates': list(coordinates),
                     'note': 'Referencia aproximada sintética; no es posición de fuerzas.',
                     'source': 'gazetteer', 'source_locator': 'Ficha de la ciudad — coordenadas'},
        'participations': [{'actor': 'gobierno', 'role': 'participant', 'claim': 'c1', 'note': ''}],
    }


def sample_timeline(as_of='2026-11-15', events=None):
    return {
        'schema_version': 1,
        'story': {'slug': 'cronologia-prueba', 'title': 'Cronología sintética', 'summary': 'Datos sintéticos de prueba.', 'kind': 'conflict'},
        'as_of': as_of,
        'sources': {
            'informe': {'url': 'https://example.org/informe', 'title': 'Informe sintético', 'creator': 'Entidad ficticia',
                        'published_at': '2024-05-01', 'rights_note': 'Ejemplo de prueba.'},
            'gazetteer': {'url': 'https://example.org/gazetteer', 'title': 'Nomenclátor sintético', 'creator': 'Entidad ficticia',
                          'published_at': None, 'rights_note': ''},
        },
        'actors': {'gobierno': {'name': 'Gobierno ficticio', 'kind': 'country', 'country_code': 'zz'}},
        'events': events if events is not None else [
            sample_event('prueba-segundo', '2024-06-10', category='negociacion'),
            sample_event('prueba-primero', '2024-01-05'),
        ],
    }


class TimelineFileMixin:
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def write(self, data, name='cronologia.json'):
        path = Path(self._tmp.name) / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return str(path)

    def load(self, data, *args):
        out = StringIO()
        call_command('load_timeline', self.write(data), *args, stdout=out)
        return out.getvalue()

    def counts(self):
        return [model.objects.count() for model in MODELS]

    def assert_load_fails(self, data, *fragments):
        before = self.counts()
        with self.assertRaises(CommandError) as ctx:
            self.load(data)
        for fragment in fragments:
            self.assertIn(fragment, str(ctx.exception))
        self.assertEqual(before, self.counts(), 'un error debe revertir todo el archivo')
        return str(ctx.exception)


class LoadTimelineCommandTests(TimelineFileMixin, TestCase):
    def test_valid_load_creates_story_events_and_reuses_shared_records(self):
        output = self.load(sample_timeline())
        story = TimelineStory.objects.get(slug='cronologia-prueba')
        self.assertEqual(story.kind, TimelineStory.Kind.CONFLICT)
        self.assertEqual(story.as_of, date(2026, 11, 15))
        self.assertEqual([entry.event.slug for entry in story.entries.order_by('order')], ['prueba-segundo', 'prueba-primero'])
        self.assertEqual([entry.order for entry in story.entries.order_by('order')], [1, 2])
        for event in Event.objects.all():
            self.assertEqual(event.status, Event.Status.REVIEWED)
            self.assertEqual(event.as_of, date(2026, 11, 15))
        self.assertTrue(all(claim.status == Claim.Status.SUPPORTED for claim in Claim.objects.all()))
        self.assertEqual(Source.objects.count(), 2)
        self.assertEqual(Source.objects.get(url='https://example.org/informe').accessed_at, date(2026, 11, 15))
        self.assertEqual(Actor.objects.get().country_code, 'ZZ')
        self.assertEqual(Claim.objects.get(text='Declaración sintética prueba-primero.').attributed_to.name, 'Gobierno ficticio')
        location = Location.objects.get(event__slug='prueba-primero')
        self.assertEqual((location.longitude, location.latitude, location.precision), (10.0, 20.0, 'approximate'))
        self.assertEqual(Participation.objects.count(), 2)
        self.assertIn('Hitos creados: 2', output)

    def test_reload_is_idempotent(self):
        self.load(sample_timeline())
        before = self.counts()
        output = self.load(sample_timeline())
        self.assertEqual(before, self.counts())
        self.assertIn('Hitos creados: 0', output)
        self.assertIn('Hitos omitidos (ya existían): 2', output)

    def test_second_load_adds_only_new_event_without_touching_existing(self):
        self.load(sample_timeline())
        edited = Event.objects.get(slug='prueba-primero')
        edited.title = 'Título revisado manualmente'
        edited.save()
        data = sample_timeline(as_of='2026-12-01')
        data['events'].append(sample_event('prueba-tercero', '2025-03-03', category='acuerdo'))
        output = self.load(data)

        self.assertIn('Hitos creados: 1 (prueba-tercero)', output)
        story = TimelineStory.objects.get(slug='cronologia-prueba')
        self.assertEqual(story.as_of, date(2026, 12, 1))
        self.assertEqual(TimelineEntry.objects.get(event__slug='prueba-tercero').order, 3)
        self.assertEqual(Event.objects.get(slug='prueba-tercero').as_of, date(2026, 12, 1))
        self.assertEqual(Event.objects.get(slug='prueba-primero').title, 'Título revisado manualmente')
        self.assertEqual(Event.objects.get(slug='prueba-primero').as_of, date(2026, 11, 15))
        self.assertEqual(Source.objects.count(), 2)
        self.assertEqual(Actor.objects.count(), 1)

    def test_older_as_of_does_not_regress_story(self):
        self.load(sample_timeline(as_of='2026-11-15'))
        self.load(sample_timeline(as_of='2026-10-01'))
        self.assertEqual(TimelineStory.objects.get().as_of, date(2026, 11, 15))

    def test_dry_run_writes_nothing(self):
        output = self.load(sample_timeline(), '--dry-run')
        self.assertIn('SIMULACIÓN', output)
        self.assertIn('Hitos creados: 2', output)
        self.assertEqual(self.counts(), [0] * len(MODELS))

    def test_unknown_reference_rolls_back_everything(self):
        data = sample_timeline()
        data['events'][1]['claims'][0]['evidence'][0]['source'] = 'inexistente'
        data['events'][1]['participations'][0]['actor'] = 'nadie'
        message = self.assert_load_fails(data, 'events[1].claims[0].evidence[0].source', 'inexistente',
                                         'events[1].participations[0].actor')
        self.assertIn('no se escribió ningún registro', message)

    def test_unknown_category_is_rejected(self):
        data = sample_timeline()
        data['events'][0]['category'] = 'batalla'
        self.assert_load_fails(data, 'events[0].category', 'batalla')

    def test_out_of_range_coordinates_are_rejected(self):
        data = sample_timeline()
        data['events'][1]['location']['coordinates'] = [32.5, 95.0]
        self.assert_load_fails(data, 'events[1].location.coordinates[1]', 'latitud fuera de rango')

    def test_coordinates_need_provenance(self):
        data = sample_timeline()
        del data['events'][0]['location']['source']
        data['events'][0]['location']['source_locator'] = ''
        self.assert_load_fails(data, 'events[0].location.source', 'events[0].location.source_locator')

    def test_event_without_evidenced_fact_is_rejected(self):
        data = sample_timeline()
        data['events'][0]['claims'][0]['evidence'] = []
        self.assert_load_fails(data, 'events[0].claims', 'fact')

    def test_database_validation_error_rolls_back_previous_events(self):
        data = sample_timeline()
        # Passes the structural check, fails URLField validation in full_clean() on the second event.
        data['sources']['otra'] = {'url': 'https://dominio invalido', 'title': 'Mal', 'creator': 'X'}
        data['events'][1]['claims'][0]['evidence'].append({'source': 'otra', 'locator': 'Página 1'})
        self.assert_load_fails(data, 'sources.otra.url')

    def test_slug_owned_by_another_story_is_rejected(self):
        self.load(sample_timeline())
        data = sample_timeline()
        data['story']['slug'] = 'otra-cronologia'
        self.assert_load_fails(data, 'events[0].slug', 'no pertenece a la historia «otra-cronologia»')
        self.assertFalse(TimelineStory.objects.filter(slug='otra-cronologia').exists())

    def test_failed_update_keeps_existing_timeline_intact(self):
        self.load(sample_timeline())
        data = sample_timeline(as_of='2026-12-01')
        data['events'].append(sample_event('prueba-tercero', '2025-03-03', coordinates=(200.0, 10.0)))
        self.assert_load_fails(data, 'events[2].location.coordinates[0]')
        self.assertEqual(TimelineStory.objects.get().as_of, date(2026, 11, 15))

    def test_invalid_json_and_schema_version(self):
        path = Path(self._tmp.name) / 'roto.json'
        path.write_text('{"schema_version": 1,', encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'JSON no válido'):
            call_command('load_timeline', str(path), stdout=StringIO())
        data = sample_timeline()
        data['schema_version'] = 2
        self.assert_load_fails(data, 'schema_version')

    def test_model_rejects_unknown_category(self):
        self.assertIn('clima', EVENT_CATEGORIES)
        event = Event(slug='x', title='X', summary='Y', category='desconocida')
        with self.assertRaises(ValidationError) as ctx:
            event.full_clean()
        self.assertIn('category', ctx.exception.message_dict)
        event.category = 'acuerdo'
        event.full_clean()


class TimelineApiTests(TimelineFileMixin, TestCase):
    def setUp(self):
        super().setUp()
        call_command('seed_cop31', verbosity=0, stdout=StringIO())
        call_command('seed_conflicto', verbosity=0, stdout=StringIO())
        self.load(sample_timeline())
        TimelineStory.objects.create(slug='vacia', title='Sin hitos', summary='Sin eventos visibles.')

    def test_list_endpoint(self):
        response = self.client.get(reverse('story-list'))
        self.assertEqual(response.status_code, 200)
        stories = response.json()['stories']
        self.assertEqual([item['slug'] for item in stories], ['conflicto-armado', 'geopolitica', 'cronologia-prueba'])
        by_slug = {item['slug']: item for item in stories}
        self.assertEqual(by_slug['cronologia-prueba'], {
            'slug': 'cronologia-prueba', 'title': 'Cronología sintética', 'summary': 'Datos sintéticos de prueba.', 'kind': 'conflict',
            'events_count': 2, 'first_event_date': '2024-01-05', 'last_event_date': '2024-06-10', 'as_of': '2026-11-15'})
        self.assertEqual(by_slug['geopolitica']['kind'], 'diplomacy')
        self.assertEqual(by_slug['geopolitica']['events_count'], 1)
        self.assertEqual(by_slug['conflicto-armado']['kind'], 'conflict')
        self.assertEqual(by_slug['conflicto-armado']['events_count'], 3)
        self.assertNotIn('vacia', by_slug)

    def test_list_counts_only_visible_events(self):
        Event.objects.filter(slug='prueba-primero').update(status=Event.Status.DRAFT)
        item = next(s for s in self.client.get(reverse('story-list')).json()['stories'] if s['slug'] == 'cronologia-prueba')
        self.assertEqual(item['events_count'], 1)
        self.assertEqual(item['first_event_date'], '2024-06-10')

    def test_detail_has_new_fields_and_is_sorted_by_start_date(self):
        response = self.client.get(reverse('story-detail', args=['cronologia-prueba']))
        self.assertEqual(response.status_code, 200)
        story = response.json()
        self.assertEqual((story['kind'], story['as_of'], story['first_event_date'], story['last_event_date']),
                         ('conflict', '2026-11-15', '2024-01-05', '2024-06-10'))
        self.assertEqual([event['id'] for event in story['events']], ['prueba-primero', 'prueba-segundo'])
        first = story['events'][0]
        self.assertEqual(first['date']['start'], '2024-01-05')
        self.assertIsNone(first['date']['end'])
        self.assertEqual((first['date']['start_year'], first['date']['precision']), (2024, 'exact'))
        self.assertTrue(first['date']['label'])
        self.assertEqual(first['place']['coordinates'], [10.0, 20.0])
        self.assertEqual(first['category'], 'conflicto')
        self.assertTrue(first['claims'] and first['sources'] and first['actors'])

    def test_existing_stories_keep_format_and_gain_fields(self):
        news = self.client.get(reverse('story-detail', args=['geopolitica'])).json()
        self.assertEqual(news['kind'], 'diplomacy')
        self.assertEqual(news['events'][0]['id'], 'cop31-apertura')
        self.assertEqual(news['events'][0]['date']['start'], '2026-11-09')
        self.assertEqual(news['events'][0]['date']['end'], '2026-11-20')
        self.assertEqual(news['events'][0]['date']['start_year'], 2026)
        conflict = self.client.get(reverse('story-detail', args=['conflicto-armado'])).json()
        self.assertEqual((conflict['kind'], conflict['as_of']), ('conflict', '2026-11-15'))
        self.assertEqual([e['date']['start'] for e in conflict['events']], ['2022-02-24', '2022-07-22', '2026-11-10'])
        rome = self.client.get(reverse('story-detail', args=['expansion-de-roma']))
        self.assertEqual(rome.status_code, 200)
        self.assertEqual(rome.json()['slug'], 'expansion-de-roma')

    def test_unknown_or_empty_story_returns_404_with_detail(self):
        for slug in ('no-existe', 'vacia'):
            response = self.client.get(reverse('story-detail', args=[slug]))
            self.assertEqual(response.status_code, 404)
            self.assertIn('detail', response.json())

    def test_list_returns_503_without_database(self):
        with patch('stories.views.story_list', side_effect=OperationalError('test')):
            response = self.client.get(reverse('story-list'))
        self.assertEqual(response.status_code, 503)
        self.assertIn('detail', response.json())
        with patch('stories.views.timeline_from_database', side_effect=OperationalError('test')):
            self.assertEqual(self.client.get(reverse('story-detail', args=['cronologia-prueba'])).status_code, 503)

    def test_list_is_read_only(self):
        self.assertEqual(self.client.post(reverse('story-list')).status_code, 405)
