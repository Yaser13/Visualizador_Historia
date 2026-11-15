"""Submission API, services and admin actions (docs/api/CONTRATO_USUARIOS_INGESTA.md §1-§2).

All records are SYNTHETIC test data with example.org URLs; nothing calls the network or OpenAI.
"""
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from stories.models import Claim, Event, Evidence, Source, TimelineEntry, TimelineStory

from .models import AgentRun, FetchedDocument, NewsSubmission
from .services import SubmissionError, normalize_url, publish_submission, reject_submission, retry_submission

User = get_user_model()
# Password hashing speed is irrelevant here; the hasher choice does not change the API behaviour.
FAST_HASHERS = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


def post_json(client, url, data=None, **extra):
    return client.post(url, data=json.dumps(data or {}), content_type='application/json', **extra)


def make_user(username, display_name, **extra):
    user = User.objects.create_user(username, f'{username}@example.org', 'Clave-Sintetica-2026', **extra)
    Profile.objects.create(user=user, display_name=display_name)
    return user


def make_review_submission(user, slug='hito-ia-sintetico', story=None):
    """Mimics the pipeline output: draft AI event with a supported, evidenced fact, submission in review."""
    source = Source.objects.create(title='Nota sintética', creator='Medio ficticio', url=f'https://example.org/{slug}',
                                   published_at=date(2026, 11, 10))
    event = Event.objects.create(slug=slug, title='Hito sintético generado', summary='Resumen sintético.', category='diplomacia',
                                 status=Event.Status.DRAFT, start_date=date(2026, 11, 9), date_precision='exact',
                                 as_of=date(2026, 11, 15), origin=Event.Origin.AI_PIPELINE, submitted_by=user)
    claim = Claim.objects.create(event=event, text='Hecho sintético verificado.', kind=Claim.Kind.FACT, status=Claim.Status.SUPPORTED)
    Evidence.objects.create(claim=claim, source=source, locator='Párrafo 1', excerpt='Cita literal sintética.')
    if story is None:
        story = TimelineStory.objects.create(slug=f'historia-{slug}', title='Historia sintética', summary='Resumen.',
                                             origin=TimelineStory.Origin.AI_PIPELINE, created_by=user)
    submission = NewsSubmission.objects.create(user=user, url=source.url, normalized_url=normalize_url(source.url),
                                               status=NewsSubmission.Status.REVIEW, event=event, story=story)
    FetchedDocument.objects.create(submission=submission, source=source, role=FetchedDocument.Role.SUBMITTED,
                                   http_status=200, content_type='text/html', title='Nota sintética',
                                   publisher='Medio ficticio', text='Cita literal sintética.', content_hash='0' * 64)
    AgentRun.objects.create(submission=submission, agent=AgentRun.Agent.EXTRACTOR, model='modelo-de-prueba',
                            status=AgentRun.Status.OK, output={'claims': 1}, finished_at=timezone.now())
    return submission


@FAST_HASHERS
class NormalizeUrlTests(TestCase):
    def test_removes_fragment_and_utm_parameters(self):
        self.assertEqual(normalize_url('HTTPS://Example.org/a/b?utm_source=x&id=7&UTM_Medium=y&q=a%20b#parte'),
                         'https://example.org/a/b?id=7&q=a%20b')
        self.assertEqual(normalize_url('http://example.org'), 'http://example.org/')
        self.assertEqual(normalize_url('https://example.org/x?utm_campaign=1'), 'https://example.org/x')


@FAST_HASHERS
class SubmissionCreateTests(TestCase):
    def setUp(self):
        self.user = make_user('autor', 'Autora Sintética')
        self.client.force_login(self.user)
        self.url = reverse('submission-list')

    def test_requires_session(self):
        anonymous = Client()
        self.assertEqual(post_json(anonymous, self.url, {'url': 'https://example.org/n'}).status_code, 401)
        self.assertEqual(anonymous.get(self.url).status_code, 401)

    def test_create_returns_202_with_contract_fields(self):
        response = post_json(self.client, self.url, {'url': 'https://example.org/noticia?utm_source=red#top', 'note': 'Nota.'})
        self.assertEqual(response.status_code, 202)
        submission = response.json()['submission']
        self.assertEqual(set(submission), {'id', 'url', 'note', 'status', 'status_label', 'step_detail', 'error', 'created_at',
                                           'updated_at', 'story_slug', 'event_title', 'submitted_by'})
        self.assertEqual(submission['status'], 'queued')
        self.assertEqual(submission['status_label'], 'En cola')
        self.assertEqual(submission['submitted_by'], 'Autora Sintética')
        stored = NewsSubmission.objects.get(pk=submission['id'])
        self.assertEqual(stored.normalized_url, 'https://example.org/noticia')
        self.assertEqual(stored.url, 'https://example.org/noticia?utm_source=red#top')

    def test_only_http_and_https(self):
        for url in ('ftp://example.org/a', 'javascript:alert(1)', 'file:///etc/passwd', 'no es url', '', 'https://usuario:clave@example.org/'):
            response = post_json(self.client, self.url, {'url': url})
            self.assertEqual(response.status_code, 400, url)
            self.assertIn('url', response.json()['errors'])
        self.assertFalse(NewsSubmission.objects.exists())

    def test_unknown_target_story(self):
        response = post_json(self.client, self.url, {'url': 'https://example.org/a', 'target_story': 'no-existe'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('target_story', response.json()['errors'])
        story = TimelineStory.objects.create(slug='existente', title='T', summary='S')
        response = post_json(self.client, self.url, {'url': 'https://example.org/a', 'target_story': 'existente'})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(NewsSubmission.objects.get().target_story, story)

    def test_active_duplicate_returns_existing_with_200(self):
        first = post_json(self.client, self.url, {'url': 'https://example.org/dup#a'})
        second = post_json(self.client, self.url, {'url': 'https://example.org/dup?utm_medium=x'})
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['submission']['id'], first.json()['submission']['id'])
        self.assertEqual(NewsSubmission.objects.count(), 1)
        # Once terminal, the same URL can be submitted again.
        NewsSubmission.objects.update(status=NewsSubmission.Status.FAILED)
        self.assertEqual(post_json(self.client, self.url, {'url': 'https://example.org/dup'}).status_code, 202)

    def test_database_enforces_single_active_submission(self):
        NewsSubmission.objects.create(user=self.user, url='https://example.org/x', normalized_url='https://example.org/x')
        with self.assertRaises(IntegrityError), transaction.atomic():
            NewsSubmission.objects.create(user=self.user, url='https://example.org/x', normalized_url='https://example.org/x')
        NewsSubmission.objects.create(user=self.user, url='https://example.org/x', normalized_url='https://example.org/x',
                                      status=NewsSubmission.Status.REJECTED)

    @override_settings(INGESTION_DAILY_LIMIT=2)
    def test_daily_limit_returns_429(self):
        for index in range(2):
            self.assertEqual(post_json(self.client, self.url, {'url': f'https://example.org/n{index}'}).status_code, 202)
        response = post_json(self.client, self.url, {'url': 'https://example.org/n3'})
        self.assertEqual(response.status_code, 429)
        self.assertIn('límite', response.json()['detail'])
        # Submissions from previous days do not count.
        NewsSubmission.objects.update(created_at=timezone.now() - timedelta(days=2))
        self.assertEqual(post_json(self.client, self.url, {'url': 'https://example.org/n3'}).status_code, 202)


@FAST_HASHERS
class SubmissionReadTests(TestCase):
    def setUp(self):
        self.owner = make_user('duena', 'Dueña Sintética')
        self.other = make_user('ajeno', 'Usuario Ajeno')
        self.staff = make_user('editora', 'Editora', is_staff=True)
        self.submission = make_review_submission(self.owner)
        NewsSubmission.objects.create(user=self.other, url='https://example.org/otro', normalized_url='https://example.org/otro')

    def test_list_only_own_unless_staff_all(self):
        self.client.force_login(self.owner)
        items = self.client.get(reverse('submission-list')).json()['submissions']
        self.assertEqual([item['id'] for item in items], [self.submission.pk])
        self.assertEqual(len(self.client.get(reverse('submission-list') + '?all=1').json()['submissions']), 1)
        self.client.force_login(self.staff)
        self.assertEqual(len(self.client.get(reverse('submission-list')).json()['submissions']), 0)
        everything = self.client.get(reverse('submission-list') + '?all=1').json()['submissions']
        self.assertEqual(len(everything), 2)
        review = self.client.get(reverse('submission-list') + '?all=1&status=review').json()['submissions']
        self.assertEqual([item['id'] for item in review], [self.submission.pk])

    def test_other_users_get_404(self):
        self.client.force_login(self.other)
        for name in ('submission-detail', 'submission-retry'):
            response = (self.client.get if name == 'submission-detail' else self.client.post)(reverse(name, args=[self.submission.pk]))
            self.assertEqual(response.status_code, 404, name)
            self.assertEqual(response.json(), {'detail': 'Envío no encontrado.'})

    def test_detail_with_documents_runs_and_draft_preview(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('submission-detail', args=[self.submission.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()['submission']
        self.assertEqual(data['documents'], [{'title': 'Nota sintética', 'url': 'https://example.org/hito-ia-sintetico',
                                              'publisher': 'Medio ficticio', 'role': 'submitted', 'published_at': None,
                                              'fetched_at': data['documents'][0]['fetched_at'], 'fetch_error': ''}])
        self.assertEqual(data['agent_runs'][0]['agent'], 'extractor')
        self.assertEqual(set(data['agent_runs'][0]), {'agent', 'status', 'model', 'finished_at', 'error'})
        self.assertEqual(data['story_slug'], 'historia-hito-ia-sintetico')
        self.assertEqual(data['event_title'], 'Hito sintético generado')
        self.assertEqual(data['review_note'], '')
        preview = data['preview']
        self.assertEqual(preview['origin'], 'ai_pipeline')
        self.assertEqual(preview['submitted_by'], 'Dueña Sintética')
        self.assertEqual(preview['claims'][0]['sources'][0]['locator'], 'Párrafo 1')
        # The draft is still invisible publicly.
        self.assertEqual(Client().get(reverse('story-detail', args=['historia-hito-ia-sintetico'])).status_code, 404)
        self.client.force_login(self.staff)
        self.assertIsNotNone(self.client.get(reverse('submission-detail', args=[self.submission.pk])).json()['submission']['preview'])

    def test_preview_null_without_event(self):
        self.client.force_login(self.other)
        submission = NewsSubmission.objects.get(user=self.other)
        self.assertIsNone(self.client.get(reverse('submission-detail', args=[submission.pk])).json()['submission']['preview'])


@FAST_HASHERS
class SubmissionTransitionTests(TestCase):
    def setUp(self):
        self.owner = make_user('duena', 'Dueña Sintética')
        self.staff = make_user('editora', 'Editora', is_staff=True)
        self.submission = make_review_submission(self.owner)

    def test_publish_requires_staff(self):
        self.client.force_login(self.owner)
        response = post_json(self.client, reverse('submission-publish', args=[self.submission.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(post_json(self.client, reverse('submission-reject', args=[self.submission.pk]), {'note': 'x'}).status_code, 403)
        self.assertEqual(post_json(Client(), reverse('submission-publish', args=[self.submission.pk])).status_code, 401)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'review')

    def test_publish_makes_event_public_with_origin_and_submitter(self):
        self.client.force_login(self.staff)
        response = post_json(self.client, reverse('submission-publish', args=[self.submission.pk]), {'note': 'Comprobado.'})
        self.assertEqual(response.status_code, 200)
        data = response.json()['submission']
        self.assertEqual(data['status'], 'published')
        self.assertEqual(data['review_note'], 'Comprobado.')
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.reviewed_by, self.staff)
        self.assertEqual(self.submission.event.status, Event.Status.PUBLISHED)
        self.assertTrue(TimelineEntry.objects.filter(story=self.submission.story, event=self.submission.event, order=1).exists())
        public = Client().get(reverse('story-detail', args=['historia-hito-ia-sintetico']))
        self.assertEqual(public.status_code, 200)
        story = public.json()
        self.assertEqual(story['origin'], 'ai_pipeline')
        self.assertEqual(story['events'][0]['origin'], 'ai_pipeline')
        self.assertEqual(story['events'][0]['submitted_by'], 'Dueña Sintética')
        listed = {item['slug']: item for item in Client().get(reverse('story-list')).json()['stories']}
        self.assertEqual(listed['historia-hito-ia-sintetico']['origin'], 'ai_pipeline')
        # Publishing twice is not allowed.
        again = post_json(self.client, reverse('submission-publish', args=[self.submission.pk]))
        self.assertEqual(again.status_code, 400)
        self.assertEqual(TimelineEntry.objects.filter(event=self.submission.event).count(), 1)

    def test_publish_appends_to_target_story(self):
        story = TimelineStory.objects.create(slug='destino', title='Destino', summary='S')
        other = make_review_submission(self.owner, slug='otro-hito', story=story)
        TimelineEntry.objects.create(story=story, event=self.submission.event, order=4)
        NewsSubmission.objects.filter(pk=other.pk).update(story=None, target_story=story)
        publish_submission(other, self.staff)
        self.assertEqual(TimelineEntry.objects.get(story=story, event=other.event).order, 5)
        other.refresh_from_db()
        self.assertEqual(other.story, story)

    def test_reject_requires_note_and_keeps_event_unpublished(self):
        self.client.force_login(self.staff)
        missing = post_json(self.client, reverse('submission-reject', args=[self.submission.pk]), {'note': '  '})
        self.assertEqual(missing.status_code, 400)
        self.assertIn('note', missing.json()['errors'])
        response = post_json(self.client, reverse('submission-reject', args=[self.submission.pk]), {'note': 'Fuente insuficiente.'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['submission']['status'], 'rejected')
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.event.status, Event.Status.DRAFT)
        self.assertEqual(Client().get(reverse('story-detail', args=['historia-hito-ia-sintetico'])).status_code, 404)

    def test_publish_and_reject_only_from_review(self):
        NewsSubmission.objects.filter(pk=self.submission.pk).update(status=NewsSubmission.Status.EXTRACTING)
        with self.assertRaises(SubmissionError):
            publish_submission(self.submission, self.staff)
        with self.assertRaises(SubmissionError):
            reject_submission(self.submission, self.staff, 'motivo')

    def test_retry_only_failed_and_only_owner(self):
        self.client.force_login(self.owner)
        self.assertEqual(post_json(self.client, reverse('submission-retry', args=[self.submission.pk])).status_code, 400)
        NewsSubmission.objects.filter(pk=self.submission.pk).update(status=NewsSubmission.Status.FAILED, error='Fallo de red sintético.')
        self.client.force_login(self.staff)
        self.assertEqual(post_json(self.client, reverse('submission-retry', args=[self.submission.pk])).status_code, 403)
        self.client.force_login(self.owner)
        response = post_json(self.client, reverse('submission-retry', args=[self.submission.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['submission']['status'], 'queued')
        self.assertEqual(response.json()['submission']['error'], '')

    def test_retry_blocked_by_another_active_submission(self):
        NewsSubmission.objects.filter(pk=self.submission.pk).update(status=NewsSubmission.Status.FAILED)
        NewsSubmission.objects.create(user=self.owner, url=self.submission.url, normalized_url=self.submission.normalized_url)
        with self.assertRaises(SubmissionError):
            retry_submission(self.submission, self.owner)

    def test_admin_actions_reuse_services(self):
        self.client.force_login(User.objects.create_superuser('admin', 'admin@example.org', 'Clave-Sintetica-2026'))
        changelist = reverse('admin:ingestion_newssubmission_changelist')
        self.assertEqual(self.client.get(changelist + '?status__exact=review').status_code, 200)
        # Reject without a review note is refused; the submission stays in review.
        self.client.post(changelist, {'action': 'reject_selected', '_selected_action': [self.submission.pk]})
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'review')
        self.client.post(changelist, {'action': 'publish_selected', '_selected_action': [self.submission.pk]})
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'published')
        self.assertEqual(self.submission.event.status, Event.Status.PUBLISHED)


@FAST_HASHERS
class NoEmailExposureTests(TestCase):
    def test_public_and_submission_payloads_never_include_email_or_username(self):
        owner = make_user('usuario-secreto', 'Nombre Público')
        submission = make_review_submission(owner)
        publish_submission(submission, make_user('editora', 'Editora', is_staff=True))
        anonymous = Client()
        payloads = [anonymous.get(reverse('story-list')).content.decode(),
                    anonymous.get(reverse('story-detail', args=['historia-hito-ia-sintetico'])).content.decode()]
        other = make_user('mirona', 'Mirona')
        anonymous.force_login(other)
        payloads.append(anonymous.get(reverse('submission-list')).content.decode())
        anonymous.force_login(User.objects.get(username='editora'))
        payloads.append(anonymous.get(reverse('submission-list') + '?all=1').content.decode())
        payloads.append(anonymous.get(reverse('submission-detail', args=[submission.pk])).content.decode())
        for payload in payloads:
            self.assertNotIn('@example.org', payload)
            self.assertNotIn('usuario-secreto', payload)
        self.assertIn('Nombre Público', payloads[1])


@FAST_HASHERS
class SettingsTests(TestCase):
    def test_cookie_settings(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertFalse(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')
        self.assertTrue(settings.INGESTION_USER_AGENT)

    def test_env_file_parser_never_overrides_existing_variables(self):
        from config.settings import load_env_file
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            lines = ['# comentario', 'export GEO_TEST_A="uno"', 'GEO_TEST_B=dos # nota', 'GEO_TEST_C=ya',
                     'linea-invalida', "GEO_TEST_D='con # almohadilla'"]
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            with patch.dict(os.environ, {'GEO_TEST_C': 'entorno'}):
                load_env_file(path)
                self.assertEqual(os.environ['GEO_TEST_A'], 'uno')
                self.assertEqual(os.environ['GEO_TEST_B'], 'dos')
                self.assertEqual(os.environ['GEO_TEST_C'], 'entorno')
                self.assertEqual(os.environ['GEO_TEST_D'], 'con # almohadilla')
            load_env_file(Path(directory) / 'no-existe')
