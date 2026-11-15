"""Worker for the news-submission queue (contract §3).

    python backend/manage.py process_submissions            # polling every 5 s
    python backend/manage.py process_submissions --once     # drain the queue and exit
    python backend/manage.py process_submissions --id 12    # process one queued submission

Submissions are claimed with a conditional update (``queued`` → ``fetching``),
so two workers never process the same submission.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from ingestion.models import NewsSubmission
from ingestion.pipeline.runner import claim_submission, process_next, process_submission


class Command(BaseCommand):
    help = 'Procesa los envíos de noticias en cola con el flujo de agentes.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Procesa la cola actual y termina.')
        parser.add_argument('--id', type=int, dest='submission_id', help='Procesa solo el envío indicado (debe estar en cola).')
        parser.add_argument('--interval', type=float, default=5.0, help='Segundos entre consultas a la cola (por defecto 5).')
        parser.add_argument('--max', type=int, default=0, dest='max_count', help='Máximo de envíos a procesar (0 = sin límite).')

    def report(self, submission):
        style = self.style.SUCCESS if submission.status in ('review', 'published') else self.style.ERROR
        detail = submission.error or submission.step_detail
        self.stdout.write(style(f'Envío #{submission.pk}: {submission.status} — {detail}'))

    def handle(self, *args, submission_id=None, once=False, interval=5.0, max_count=0, **options):
        if submission_id is not None:
            if not NewsSubmission.objects.filter(pk=submission_id).exists():
                raise CommandError(f'No existe el envío #{submission_id}.')
            if not claim_submission(submission_id):
                raise CommandError(f'El envío #{submission_id} no está en cola (o lo está procesando otro trabajador).')
            self.report(process_submission(NewsSubmission.objects.get(pk=submission_id)))
            return
        processed = 0
        if not once:
            self.stdout.write(f'Esperando envíos (cada {interval:g} s). Ctrl+C para salir.')
        try:
            while not max_count or processed < max_count:
                submission = process_next()
                if submission is not None:
                    processed += 1
                    self.report(submission)
                    continue
                if once:
                    break
                time.sleep(interval if interval > 0 else 5.0)
        except KeyboardInterrupt:
            self.stdout.write('Trabajador detenido.')
        if once:
            self.stdout.write(f'Procesados: {processed}.')

