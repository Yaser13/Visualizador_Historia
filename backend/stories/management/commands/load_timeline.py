"""Load or extend an editorial timeline from a JSON file (CONTRATO_CRONOLOGIAS §1)."""
from django.core.management.base import BaseCommand, CommandError

from stories.timeline_loader import TimelineLoadError, load_timeline_file


class Command(BaseCommand):
    help = ('Carga una cronología desde un archivo JSON. Crea la historia si falta y añade solo hitos nuevos por slug; '
            'nunca modifica ni borra registros existentes. Con --dry-run valida sin escribir.')

    def add_arguments(self, parser):
        parser.add_argument('path', help='Ruta al archivo JSON (UTF-8) de la cronología.')
        parser.add_argument('--dry-run', action='store_true', help='Valida y simula la carga; revierte la transacción.')

    def handle(self, *args, path, dry_run, **options):
        try:
            result = load_timeline_file(path, dry_run=dry_run)
        except TimelineLoadError as exc:
            lines = '\n'.join(f'  - {error}' for error in exc.errors)
            raise CommandError(f'No se cargó «{path}»; no se escribió ningún registro. Errores:\n{lines}')

        prefix = '[SIMULACIÓN, sin cambios] ' if result.dry_run else ''
        write = self.stdout.write
        write(f'{prefix}Historia «{result.story_slug}»: {"creada" if result.story_created else "existente"}.')
        write(f'  Hitos creados: {len(result.events_created)}' + (f' ({", ".join(result.events_created)})' if result.events_created else ''))
        write(f'  Hitos omitidos (ya existían): {len(result.events_skipped)}' + (f' ({", ".join(result.events_skipped)})' if result.events_skipped else ''))
        write(f'  Fuentes creadas: {result.sources_created}; reutilizadas: {result.sources_reused}')
        write(f'  Actores creados: {result.actors_created}; reutilizados: {result.actors_reused}')
        if result.as_of_updated:
            write('  Fecha de verificación (as_of) de la historia actualizada.')
        for warning in result.warnings:
            self.stdout.write(self.style.WARNING(f'  Aviso: {warning}'))
        message = 'Validación correcta; la transacción se revirtió.' if result.dry_run else 'Carga completada.'
        write(self.style.SUCCESS(message))
