from django.db import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .data import ROME
from .serializers import NEWS_SLUG, story_from_database, story_list, timeline_from_database

DATABASE_UNAVAILABLE = 'Base de datos no disponible; ejecuta las migraciones locales.'


def json_response(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})


@require_GET
def stories_index(request):
    try:
        stories = story_list()
    except (OperationalError, ProgrammingError):
        return json_response({'detail': DATABASE_UNAVAILABLE}, status=503)
    return json_response({'stories': stories})


@require_GET
def story_detail(request, slug):
    if slug == ROME['slug']:
        return json_response(ROME)
    try:
        story = story_from_database() if slug == NEWS_SLUG else timeline_from_database(slug)
    except (OperationalError, ProgrammingError):
        return json_response({'detail': DATABASE_UNAVAILABLE}, status=503)
    if story is None:
        if slug == NEWS_SLUG:
            return json_response({'detail': 'No hay noticias revisadas; carga la instantánea local.'}, status=404)
        return json_response({'detail': 'Historia no encontrada o sin hitos revisados con evidencia.'}, status=404)
    return json_response(story)
