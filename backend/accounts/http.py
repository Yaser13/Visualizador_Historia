"""Small JSON helpers shared by the session-based APIs (accounts, ingestion)."""
import json
from functools import wraps

from django.http import JsonResponse

UNAUTHENTICATED = 'Inicia sesión para continuar.'
FORBIDDEN = 'No tienes permiso para realizar esta acción.'


def json_response(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})


def detail(message, status):
    return json_response({'detail': message}, status=status)


def validation_error(errors):
    """``400 {"errors": {"campo": ["mensaje"]}}``."""
    return json_response({'errors': {key: list(value) if isinstance(value, (list, tuple)) else [value]
                                     for key, value in errors.items()}}, status=400)


class BadJSON(Exception):
    pass


def json_body(request):
    """Parse a JSON object body; an empty body is ``{}``."""
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BadJSON from error
    if not isinstance(data, dict):
        raise BadJSON
    return data


def api_view(methods, login_required=False, staff_required=False):
    """JSON-only method/auth guard. CSRF stays enforced by ``CsrfViewMiddleware``."""
    allowed = tuple(method.upper() for method in methods)

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in allowed:
                response = detail('Método no permitido.', 405)
                response['Allow'] = ', '.join(allowed)
                return response
            if (login_required or staff_required) and not request.user.is_authenticated:
                return detail(UNAUTHENTICATED, 401)
            if staff_required and not request.user.is_staff:
                return detail(FORBIDDEN, 403)
            try:
                return view(request, *args, **kwargs)
            except BadJSON:
                return detail('El cuerpo de la petición debe ser un objeto JSON válido.', 400)
        return wrapper
    return decorator


def text_field(data, name, errors, *, required=False, max_length=None, label=None):
    """Read a string field, recording Spanish validation messages in ``errors``."""
    value = data.get(name, '')
    if value is None:
        value = ''
    if not isinstance(value, str):
        errors[name] = ['Debe ser un texto.']
        return ''
    value = value.strip()
    if required and not value:
        errors[name] = ['Este campo es obligatorio.']
    elif max_length is not None and len(value) > max_length:
        errors[name] = [f'Máximo {max_length} caracteres.']
    return value
