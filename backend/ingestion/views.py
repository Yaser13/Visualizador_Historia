"""News submission API (contract: docs/api/CONTRATO_USUARIOS_INGESTA.md §2)."""
from django.db.models import Prefetch

from accounts.http import api_view, detail, json_body, json_response, text_field, validation_error
from accounts.models import public_display_name
from stories.models import TimelineEntry, TimelineStory
from stories.serializers import event_data, event_relations

from .models import AgentRun, FetchedDocument, NewsSubmission
from .services import (SubmissionError, create_submission, publish_submission, reject_submission,
                       retry_submission)

NOT_FOUND = 'Envío no encontrado.'
LIST_LIMIT = 200


def iso(value):
    return value.isoformat() if value else None


def submission_data(submission):
    return {
        'id': submission.pk, 'url': submission.url, 'note': submission.note, 'status': submission.status,
        'status_label': submission.get_status_display(), 'step_detail': submission.step_detail,
        'error': submission.error, 'created_at': iso(submission.created_at), 'updated_at': iso(submission.updated_at),
        'story_slug': submission.story.slug if submission.story_id else None,
        'event_title': submission.event.title if submission.event_id else None,
        'submitted_by': public_display_name(submission.user),
    }


def preview_data(submission):
    """Same event object as ``GET /api/stories/<slug>/``, even for drafts (owner/staff only)."""
    if not submission.event_id:
        return None
    event = event_relations().filter(pk=submission.event_id).first()
    if event is None:
        return None
    entry = TimelineEntry.objects.filter(event=event).order_by('pk').first()
    return event_data(event, event.slug, entry.order if entry else 1)


def submission_detail_data(submission):
    data = submission_data(submission)
    data['documents'] = [{'title': document.title, 'url': document.source.url, 'publisher': document.publisher,
                          'role': document.role, 'published_at': iso(document.published_at),
                          'fetched_at': iso(document.fetched_at), 'fetch_error': document.fetch_error}
                         for document in submission.documents.all()]
    data['agent_runs'] = [{'agent': run.agent, 'status': run.status, 'model': run.model,
                           'finished_at': iso(run.finished_at), 'error': run.error}
                          for run in submission.agent_runs.all()]
    data['preview'] = preview_data(submission)
    data['review_note'] = submission.review_note
    return data


def base_queryset():
    return NewsSubmission.objects.select_related('user__profile', 'story', 'event')


def visible_submission(request, pk):
    """Owner or staff; anyone else gets ``None`` (answered as 404, not 403, to avoid disclosure)."""
    queryset = base_queryset().prefetch_related(
        Prefetch('documents', queryset=FetchedDocument.objects.select_related('source')),
        Prefetch('agent_runs', queryset=AgentRun.objects.only('submission_id', 'agent', 'status', 'model',
                                                               'finished_at', 'error', 'started_at')))
    if not request.user.is_staff:
        queryset = queryset.filter(user=request.user)
    return queryset.filter(pk=pk).first()


def service_error(error):
    if error.field:
        return validation_error({error.field: error.message})
    return detail(error.message, error.status)


@api_view(['GET', 'POST'], login_required=True)
def submissions(request):
    if request.method == 'POST':
        return create(request)
    queryset = base_queryset()
    if not (request.user.is_staff and request.GET.get('all') == '1'):
        queryset = queryset.filter(user=request.user)
    status = request.GET.get('status')
    if status:
        if status not in NewsSubmission.Status.values:
            return validation_error({'status': 'Estado desconocido.'})
        queryset = queryset.filter(status=status)
    return json_response({'submissions': [submission_data(item) for item in queryset[:LIST_LIMIT]]})


def create(request):
    data = json_body(request)
    errors = {}
    note = text_field(data, 'note', errors)
    target = data.get('target_story')
    target_story = None
    if target not in (None, ''):
        if not isinstance(target, str):
            errors['target_story'] = ['Indica el slug de una cronología existente.']
        else:
            target_story = TimelineStory.objects.filter(slug=target.strip()).first()
            if target_story is None:
                errors['target_story'] = ['La cronología indicada no existe.']
    if errors:
        return validation_error(errors)
    try:
        submission, created = create_submission(request.user, data.get('url'), note=note, target_story=target_story)
    except SubmissionError as error:
        return service_error(error)
    submission = base_queryset().get(pk=submission.pk)
    return json_response({'submission': submission_data(submission)}, status=202 if created else 200)


@api_view(['GET'], login_required=True)
def submission_detail(request, pk):
    submission = visible_submission(request, pk)
    if submission is None:
        return detail(NOT_FOUND, 404)
    return json_response({'submission': submission_detail_data(submission)})


def _transition(request, pk, action):
    submission = visible_submission(request, pk)
    if submission is None:
        return detail(NOT_FOUND, 404)
    try:
        action(submission)
    except SubmissionError as error:
        return service_error(error)
    return json_response({'submission': submission_detail_data(visible_submission(request, pk))})


@api_view(['POST'], login_required=True)
def submission_retry(request, pk):
    return _transition(request, pk, lambda submission: retry_submission(submission, request.user))


@api_view(['POST'], staff_required=True)
def submission_publish(request, pk):
    data = json_body(request)
    errors = {}
    note = text_field(data, 'note', errors, max_length=1000)
    if errors:
        return validation_error(errors)
    return _transition(request, pk, lambda submission: publish_submission(submission, request.user, note))


@api_view(['POST'], staff_required=True)
def submission_reject(request, pk):
    data = json_body(request)
    errors = {}
    note = text_field(data, 'note', errors, required=True, max_length=1000)
    if errors:
        return validation_error(errors)
    return _transition(request, pk, lambda submission: reject_submission(submission, request.user, note))
