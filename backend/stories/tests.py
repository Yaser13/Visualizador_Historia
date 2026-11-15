from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase
from .models import Actor, Claim, Event, Evidence, Location, Participation, Source
from django.urls import reverse


class StoryApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_cop31', verbosity=0)

    def test_rome_story_has_ordered_sourced_events_in_review(self):
        response = self.client.get(reverse("story-detail", args=["expansion-de-roma"]))
        self.assertEqual(response.status_code, 200)
        story = response.json()
        self.assertEqual(story["slug"], "expansion-de-roma")
        self.assertEqual([item["order"] for item in story["events"]], list(range(1, 6)))
        for item in story["events"]:
            self.assertEqual(item["evidence_status"], "under_review")
            self.assertTrue(item["sources"][0]["locator"])
            place = item["place"]
            if place["coordinates"] is None:
                self.assertEqual(place["precision"], "unknown")
                self.assertIsNone(place["coordinate_source"])
            else:
                longitude, latitude = place["coordinates"]
                self.assertTrue(-180 <= longitude <= 180)
                self.assertTrue(-90 <= latitude <= 90)
                self.assertEqual(place["precision"], "approximate")
                self.assertTrue(place["coordinate_source"]["url"])
                self.assertTrue(place["coordinate_source"]["locator"])
            self.assertNotEqual(item["date"]["start_year"], 0)
            self.assertLessEqual(item["date"]["start_year"], item["date"]["end_year"])
        sicily = next(item for item in story["events"] if item["id"] == "sicilia")
        self.assertIsNone(sicily["place"]["coordinates"])

    def test_unknown_story_returns_json_404(self):
        response = self.client.get(reverse("story-detail", args=["desconocida"]))
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_endpoint_is_read_only(self):
        self.assertEqual(self.client.post(reverse("story-detail", args=["expansion-de-roma"])).status_code, 405)

    def test_geopolitical_news_has_dated_sources_and_geographic_provenance(self):
        response = self.client.get(reverse("story-detail", args=["geopolitica"]))
        self.assertEqual(response.status_code, 200)
        story = response.json()
        self.assertIn("No se actualiza automáticamente", story["summary"])
        event = story["events"][0]
        self.assertEqual(event["category"], "clima")
        self.assertEqual(event["published_at"], "2026-11-09")
        self.assertEqual(event["as_of"], "2026-11-15")
        self.assertTrue(event["analysis"])
        self.assertIn('Iskander Erzini Vernoit', event['analysis'])
        self.assertIn('citad', event['analysis'])
        self.assertGreaterEqual(len(event["sources"]), 2)
        self.assertTrue(any(source["published_at"] == "2026-11-09" for source in event["sources"]))
        self.assertTrue(any(source["published_at"] is None for source in event["sources"]))
        self.assertTrue(all(source["url"].startswith("https://") and source["locator"] for source in event["sources"]))
        self.assertTrue(all(source['creator'] not in source['publication'] for source in event['sources']))
        self.assertTrue(any(source['publication'] == 'Fecha de publicación desconocida' for source in event['sources']))
        self.assertEqual(event["place"]["coordinates"], [30.6897, 36.9125])
        self.assertEqual(event["place"]["precision"], "approximate")
        self.assertIn("no la ubicación exacta", event["place"]["note"])
        self.assertTrue(event["place"]["coordinate_source"]["url"].startswith("https://"))

        self.assertTrue(all(claim['sources'] for claim in event['claims']))
        self.assertTrue(event['actors'])

    def test_unreviewed_or_unsourced_event_is_not_served(self):
        event = Event.objects.get(slug='geopolitica')
        event.status = Event.Status.DRAFT
        event.save()
        self.assertEqual(self.client.get(reverse('story-detail', args=['geopolitica'])).status_code, 404)
        event.status = Event.Status.REVIEWED
        event.save()
        Evidence.objects.filter(claim__event=event).delete()
        self.assertEqual(self.client.get(reverse('story-detail', args=['geopolitica'])).status_code, 404)

    def test_unavailable_database_returns_actionable_json(self):
        from django.db import OperationalError
        with patch('stories.views.story_from_database', side_effect=OperationalError('test')):
            response = self.client.get(reverse('story-detail', args=['geopolitica']))
        self.assertEqual(response.status_code, 503)
        self.assertIn('migraciones', response.json()['detail'])

    def test_seed_is_idempotent_and_preserves_edits(self):
        event = Event.objects.get(slug='geopolitica')
        event.title = 'Título editado por una persona'
        event.save()
        claim = Claim.objects.filter(event=event).order_by('id').first()
        original_text = claim.text
        claim.text = 'Afirmación revisada manualmente'
        claim.save()
        counts = [model.objects.count() for model in (Event, Source, Claim, Evidence, Actor, Participation, Location)]
        call_command('seed_cop31', verbosity=0)
        event.refresh_from_db()
        claim.refresh_from_db()
        self.assertEqual(event.title, 'Título editado por una persona')
        self.assertEqual(claim.text, 'Afirmación revisada manualmente')
        self.assertFalse(Claim.objects.filter(event=event, text=original_text).exists())
        self.assertEqual(counts, [model.objects.count() for model in (Event, Source, Claim, Evidence, Actor, Participation, Location)])

    def test_unreviewed_or_unsupported_claims_do_not_leak(self):
        event = Event.objects.get(slug='geopolitica')
        Claim.objects.create(event=event, text='Sin pruebas', kind='fact', status='supported')
        draft = Claim.objects.create(event=event, text='En borrador', kind='fact', status='draft')
        Evidence.objects.create(claim=draft, source=Source.objects.first(), locator='Sección de prueba')
        body = self.client.get(reverse('story-detail', args=['geopolitica'])).json()
        self.assertNotIn('Sin pruebas', str(body))
        self.assertNotIn('En borrador', str(body))


class SeedAtomicityTests(TestCase):
    def test_empty_database_returns_clear_404(self):
        response = self.client.get(reverse('story-detail', args=['geopolitica']))
        self.assertEqual(response.status_code, 404)
        self.assertIn('carga la instantánea', response.json()['detail'])

    def test_failure_rolls_back_the_entire_seed(self):
        with patch.object(Location, 'save', side_effect=RuntimeError('fallo de prueba')):
            with self.assertRaises(RuntimeError):
                call_command('seed_cop31', verbosity=0)
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(Source.objects.count(), 0)
