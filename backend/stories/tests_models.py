from datetime import date
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from .models import Actor, Claim, Effect, Event, Evidence, Location, Participation, Source


class GeopoliticalModelsTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(slug='foro', title='Foro', summary='Contexto', category='diplomacia')
        self.other = Event.objects.create(slug='otro', title='Otro', summary='Contexto', category='diplomacia')
        self.actor = Actor.objects.create(name='Ejemplo', kind=Actor.Kind.ORGANIZATION)
        self.source = Source.objects.create(title='Fuente', creator='Entidad', url='https://example.org/fuente')
        self.claim = Claim.objects.create(event=self.event, text='Declaración', kind=Claim.Kind.STATEMENT)

    def test_precision_and_ranges(self):
        event = Event(slug='fecha', title='Fecha', summary='Texto', category='clima', date_precision='range', start_date=date(2026, 11, 20), end_date=date(2026, 11, 9))
        with self.assertRaises(ValidationError):
            event.full_clean()
        event.date_precision = 'unknown'
        with self.assertRaises(ValidationError):
            event.full_clean()
        event.start_date = None
        event.end_date = None
        event.full_clean()

    def test_location_coordinates_need_pair_provenance_and_valid_ranges(self):
        location = Location(event=self.event, label='Ciudad', longitude=30.6, latitude=None, precision='approximate', source=self.source, source_locator='Coordenadas')
        with self.assertRaises(ValidationError):
            location.full_clean()
        location.latitude = 91
        with self.assertRaises(ValidationError):
            location.full_clean()
        location.latitude = 36.9
        location.source = None
        with self.assertRaises(ValidationError):
            location.full_clean()
        location.source = self.source
        location.source_locator = '  '
        with self.assertRaises(ValidationError):
            location.full_clean()
        location.source_locator = 'Coordenadas'
        location.full_clean()
        location.save()
        with self.assertRaises(ProtectedError):
            self.source.delete()

    def test_claim_source_and_evidence_protection(self):
        evidence = Evidence(claim=self.claim, source=self.source, locator='  ')
        with self.assertRaises(ValidationError):
            evidence.full_clean()
        evidence.locator = 'Sección 1'
        evidence.full_clean()
        evidence.save()
        duplicate = Evidence(claim=self.claim, source=self.source, locator='Sección 1')
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        with self.assertRaises(ProtectedError):
            self.source.delete()

    def test_cross_event_relations_are_rejected(self):
        participation = Participation(event=self.other, actor=self.actor, role='host', claim=self.claim)
        effect = Effect(event=self.other, description='Resultado', claim=self.claim)
        with self.assertRaises(ValidationError):
            participation.full_clean()
        with self.assertRaises(ValidationError):
            effect.full_clean()

    def test_positive_effect_needs_perspective_and_evidence(self):
        effect = Effect(event=self.event, description='Resultado', claim=self.claim, valence='positive')
        with self.assertRaises(ValidationError):
            effect.full_clean()
        effect.perspective = self.actor
        with self.assertRaises(ValidationError):
            effect.full_clean()
        Evidence.objects.create(claim=self.claim, source=self.source, locator='Párrafo 2')
        effect.full_clean()
        self.assertEqual(Effect(event=self.event, description='Sin evaluación', claim=self.claim).valence, 'unknown')
