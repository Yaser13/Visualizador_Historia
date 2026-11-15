"""Load a reviewed snapshot without overwriting later editorial changes."""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from stories.models import Actor, Claim, Event, Evidence, Location, Participation, Source


def create_validated(model, lookup, defaults):
    """Validate new records; leave existing records untouched on repeat runs."""
    existing = model.objects.filter(**lookup).first()
    if existing is not None:
        return existing
    obj = model(**lookup, **defaults)
    obj.full_clean()
    obj.save()
    return obj


class Command(BaseCommand):
    help = 'Carga una instantánea documentada de COP31 sin sobrescribir datos existentes.'

    @transaction.atomic
    def handle(self, *args, **options):
        # The snapshot is a one-time import. Never reconstruct missing or edited
        # records in an existing event: doing so would silently undo review.
        if Event.objects.filter(slug='geopolitica').exists():
            self.stdout.write('La noticia ya existe; no se modificaron ni añadieron registros.')
            return
        cutoff = date(2026, 11, 15)
        event = create_validated(Event, {'slug': 'geopolitica'}, {
            'title': 'Comienza la COP31',
            'summary': 'Instantánea documental consultada el 15 de noviembre de 2026. No se actualiza automáticamente.',
            'category': 'clima', 'status': Event.Status.REVIEWED,
            'start_date': date(2026, 11, 9), 'end_date': date(2026, 11, 20),
            'date_precision': Event.Precision.RANGE, 'as_of': cutoff,
        })
        sources = {}
        for key, url, title, creator, published, rights in [
            ('ap', 'https://apnews.com/article/turkey-cop31-summit-climate-change-edd587ab19f3b57848b50f9dc724ba82', 'UN climate summit kicks off in Turkey after a disastrous year of extreme weather', 'Suzan Fraser y Sibi Arasu · Associated Press', date(2026, 11, 9), 'Derechos reservados; se enlaza y resume.'),
            ('agenda', 'https://unfccc.int/sites/default/files/resource/COP%2031%20agenda%20as%20adopted.pdf', 'COP31 Agenda as Adopted', 'Convención Marco de las Naciones Unidas sobre el Cambio Climático', None, 'Se enlaza el documento; condiciones de reproducción no verificadas.'),
            ('about', 'https://unfccc.int/cop31/about', 'About COP31', 'Convención Marco de las Naciones Unidas sobre el Cambio Climático', None, 'Se enlaza el documento; condiciones de reproducción no verificadas.'),
            ('geo', 'https://ungegn.un.org/dashboard/cities/details?id=2881', 'City Details — Antalya', 'UNGEGN / NGA GEOnet Names Server', None, 'Condiciones de reutilización de los datos pendientes de revisión.'),
        ]:
            sources[key] = create_validated(Source, {'url': url}, {'title': title, 'creator': creator, 'published_at': published, 'accessed_at': cutoff, 'rights_note': rights})

        actors = {}
        for key, name, kind, code in [
            ('forum', 'UNFCCC / conferencia de las Partes', 'organization', ''),
            ('turkey', 'Turquía', 'country', 'TR'),
            ('australia', 'Australia', 'country', 'AU'),
            ('african_group', 'Grupo Africano', 'organization', ''),
            ('advisor', 'Iskander Erzini Vernoit', 'person', ''),
        ]:
            actors[key] = create_validated(Actor, {'name': name, 'kind': kind}, {'country_code': code})

        def claim(text, kind, evidence_items, actor=None):
            item = create_validated(Claim, {'event': event, 'text': text, 'kind': kind}, {'status': Claim.Status.SUPPORTED, 'attributed_to': actor})
            for source_key, locator in evidence_items:
                create_validated(Evidence, {'claim': item, 'source': sources[source_key], 'locator': locator}, {})
            return item

        opening = claim('La conferencia climática de la ONU comenzó el 9 de noviembre de 2026 en Antalya, Turquía.', 'fact', [('ap', 'Apertura del artículo'), ('agenda', 'Página 1, encabezado y nota 1')])
        claim('La agenda aprobada incluye adaptación y financiación climática; la conferencia estaba prevista hasta el 20 de noviembre.', 'fact', [('agenda', 'Página 1, encabezado y apartados 6 y 8')])
        claim('Según Iskander Erzini Vernoit, asesor de negociadores africanos citado por AP, propuestas del Grupo Africano recibieron apoyo de numerosos países en desarrollo y fueron cuestionadas por países de la Unión Europea y Canadá.', 'statement', [('ap', 'Climate talks kick off with a tense start')], actors['advisor'])
        claim('Según la UNFCCC, la conferencia aborda adaptación, financiación para países en desarrollo y transición justa.', 'objective', [('about', 'What is COP31 about?')], actors['forum'])
        analysis = claim('Las diferencias descritas sobre financiación ilustran la dificultad de conciliar prioridades en la negociación; su evolución y el resultado final seguían abiertos en la fecha de corte.', 'analysis', [('ap', 'Climate talks kick off with a tense start')])
        del opening, analysis
        for key, text, role, note in [
            ('forum', 'La UNFCCC identifica a la COP31 como foro multilateral de negociación climática.', 'participant', 'Foro de negociación; no se atribuye responsabilidad causal.'),
            ('turkey', 'La UNFCCC identifica a Turquía como país anfitrión de la COP31.', 'host', 'Anfitrión; no implica responsabilidad por todos los resultados.'),
            ('australia', 'La UNFCCC identifica a Australia con la presidencia de las negociaciones de la COP31.', 'participant', 'Presidencia de negociaciones; no se infieren posiciones.'),
        ]:
            support = claim(text, 'fact', [('about', 'Who is hosting COP31?' if key != 'forum' else 'What is COP31?')])
            create_validated(Participation, {'event': event, 'actor': actors[key], 'role': role, 'claim': support}, {'note': note})
        create_validated(Location, {'event': event, 'label': 'Antalya, Turquía'}, {
            'longitude': 30.6897, 'latitude': 36.9125, 'precision': 'approximate',
            'note': 'Punto de referencia de la ciudad de Antalya, no la ubicación exacta del recinto de la conferencia.',
            'source': sources['geo'], 'source_locator': 'City Details — Antalya, coordenadas NGA GEOnet Names Server',
        })
        self.stdout.write(self.style.SUCCESS('Instantánea COP31 disponible; no se sobrescribieron registros existentes.'))
