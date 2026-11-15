"""Create an evidence-linked selection of events without overwriting editorial work."""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from stories.models import Claim, Event, Evidence, Location, Source, TimelineEntry, TimelineStory

CUTOFF = date(2026, 11, 15)


def validated_new(model, **kwargs):
    instance = model(**kwargs)
    instance.full_clean()
    instance.save()
    return instance


class Command(BaseCommand):
    help = 'Carga una selección documental sobre Rusia y Ucrania, sin sobrescribir registros existentes.'

    @transaction.atomic
    def handle(self, *args, **options):
        slug = 'conflicto-armado'
        if TimelineStory.objects.filter(slug=slug).exists():
            self.stdout.write('La cronología ya existe; no se modificaron registros.')
            return
        event_slugs = ('ucrania-invasion-2022', 'ucrania-granos-2022', 'ucrania-conversaciones-2026')
        if Event.objects.filter(slug__in=event_slugs).exists():
            raise CommandError('Existe un hito con el mismo identificador; no se modificaron registros.')
        story = validated_new(TimelineStory, slug=slug, title='Guerra de Rusia contra Ucrania',
                              kind=TimelineStory.Kind.CONFLICT, as_of=CUTOFF,
                              summary='Selección parcial de hitos consultada el 15 de noviembre de 2026; no es exhaustiva ni se actualiza automáticamente.')
        source_specs = {
            'onu': ('https://www.un.org/sg/en/content/highlight/2022-02-24.html', 'Daily Press Briefing Highlights: Ukraine', 'Oficina del Secretario General de Naciones Unidas', date(2022, 2, 24)),
            'ohchr': ('https://ukraine.un.org/sites/default/files/2025-07/2022-12-07%20OHCHR%20Thematic%20Report%20Killings%20-%20ENG.pdf', 'Killings of civilians in Kyiv, Chernihiv and Sumy Regions', 'Oficina del Alto Comisionado de las Naciones Unidas para los Derechos Humanos', date(2022, 12, 7)),
            'faq': ('https://www.un.org/en/black-sea-grain-initiative/faq', 'Black Sea Grain Initiative: Frequently Asked Questions', 'Naciones Unidas', None),
            'signing': ('https://www.un.org/sg/en/content/sg/statements/2022-07-22/secretary-generals-remarks-signing-of-black-sea-grain-initiative', 'Remarks at the signing of Black Sea Grain Initiative', 'Secretario General de las Naciones Unidas', date(2022, 7, 22)),
            'ap': ('https://apnews.com/article/3d878a3e56d5df5bd198a6d20c824d18', 'Russia and Ukraine hold nearly 4 hours of US-mediated talks in Abu Dhabi', 'Associated Press', date(2026, 11, 10)),
            'kyiv': ('https://ungegn.un.org/dashboard/cities/details?id=172', 'City Details — Kyiv', 'UNGEGN / United Nations Cartographic Section', None),
            'istanbul': ('https://ungegn.un.org/dashboard/cities/details?id=2897', 'City Details — İstanbul', 'UNGEGN / NGA GEOnet Names Server', None),
            'abu': ('https://ungegn.un.org/dashboard/cities/details?id=86', 'City Details — Abu Dhabi', 'UNGEGN / United Nations Cartographic Section', None),
        }
        sources = {}
        for key, (url, title, creator, published) in source_specs.items():
            source = Source.objects.filter(url=url).first()
            if source is None:
                source = validated_new(Source, url=url, title=title, creator=creator, published_at=published,
                                       accessed_at=CUTOFF, rights_note='Se enlaza la fuente; condiciones de reutilización pendientes de revisión.')
            sources[key] = source
        milestones = [
            ('ucrania-invasion-2022', 'Invasión a gran escala', 'conflicto', date(2022, 2, 24),
             'El 24 de febrero de 2022 Rusia inició una invasión a gran escala de Ucrania. La ofensiva también alcanzó la región de Kyiv, según la misión de derechos humanos de la ONU.',
             [('onu', 'Ukraine, operaciones militares rusas del 24 de febrero'), ('ohchr', 'Sección IV, Context, ofensiva hacia Kyiv')],
             ('Kyiv, Ucrania', 30.5266, 50.3813, 'Referencia aproximada de la ciudad para la región de Kyiv; no indica el lugar de un ataque, el aeropuerto ni posiciones de fuerzas.', 'kyiv')),
            ('ucrania-granos-2022', 'Iniciativa sobre granos del mar Negro', 'acuerdo', date(2022, 7, 22),
             'Rusia, Ucrania, Turquía y la ONU lanzaron en Estambul una iniciativa para facilitar exportaciones de alimentos desde puertos ucranianos designados. Expiró el 17 de julio de 2023 y no fue un acuerdo general de paz.',
             [('signing', 'Discurso pronunciado en la firma, 22 de julio de 2022'), ('faq', 'What was the Black Sea Grain Initiative?; How long did the agreement last?')],
             ('Estambul, Turquía', 28.9647, 41.0186, 'Referencia aproximada de la ciudad; no indica el lugar exacto de la firma.', 'istanbul')),
            ('ucrania-conversaciones-2026', 'Conversaciones en Abu Dabi', 'negociacion', date(2026, 11, 10),
             'Delegaciones de Rusia y Ucrania mantuvieron conversaciones en Abu Dabi con mediación de Estados Unidos, según Associated Press. La reunión no acredita por sí sola un alto el fuego ni un acuerdo definitivo.',
             [('ap', 'Párrafos iniciales; conversaciones del 10 de noviembre de 2026')],
             ('Abu Dabi, Emiratos Árabes Unidos', 54.3861, 24.4396, 'Referencia aproximada de la ciudad; no indica el recinto exacto de las conversaciones.', 'abu')),
        ]
        for order, (event_slug, title, category, occurred, description, evidence, location) in enumerate(milestones, start=1):
            event = validated_new(Event, slug=event_slug, title=title, summary=description, category=category,
                                  status=Event.Status.REVIEWED, start_date=occurred, date_precision=Event.Precision.EXACT, as_of=CUTOFF)
            claim = validated_new(Claim, event=event, text=description, kind=Claim.Kind.FACT, status=Claim.Status.SUPPORTED)
            for source_key, locator in evidence:
                validated_new(Evidence, claim=claim, source=sources[source_key], locator=locator)
            label, longitude, latitude, note, source_key = location
            validated_new(Location, event=event, label=label, longitude=longitude, latitude=latitude,
                          precision=Location.Precision.APPROXIMATE, note=note, source=sources[source_key], source_locator='City Details — coordenadas')
            validated_new(TimelineEntry, story=story, event=event, order=order)
        self.stdout.write(self.style.SUCCESS('Cronología documental creada; no se sobrescribieron registros.'))
