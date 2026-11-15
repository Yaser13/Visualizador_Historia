from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .data import ROME


@require_GET
def story_detail(request, slug):
    if slug != ROME["slug"]:
        return JsonResponse({"detail": "Historia no encontrada."}, status=404)
    return JsonResponse(ROME, json_dumps_params={"ensure_ascii": False})
