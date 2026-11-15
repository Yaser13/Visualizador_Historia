"""Session authentication and profile API (contract: docs/api/CONTRATO_USUARIOS_INGESTA.md §2).

Session cookies + CSRF: every unsafe method needs the ``X-CSRFToken`` header (no ``csrf_exempt``).
"""
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.views.csrf import csrf_failure as default_csrf_failure
from django.views.decorators.csrf import ensure_csrf_cookie

from .http import api_view, detail, json_body, json_response, text_field, validation_error
from .models import BIO_MAX_LENGTH, Profile, get_profile

User = get_user_model()

GENERIC_LOGIN_ERROR = 'Usuario o contraseña incorrectos.'
PROFILE_FIELDS = ('display_name', 'bio', 'country', 'organization', 'language')


def profile_data(profile):
    return {field: getattr(profile, field) for field in PROFILE_FIELDS}


def user_data(user):
    """Private ``user`` object: only returned to the user themself."""
    return {'id': user.pk, 'username': user.username, 'email': user.email, 'is_staff': user.is_staff,
            'profile': profile_data(get_profile(user))}


def csrf_failure(request, reason=''):
    """JSON 403 for API calls; Django's default HTML page elsewhere (admin)."""
    if request.path.startswith('/api/'):
        return detail('Falta el token CSRF o no es válido. Recarga la página e inténtalo de nuevo.', 403)
    return default_csrf_failure(request, reason=reason)


def password_messages(error):
    return list(error.messages)


@api_view(['GET'])
@ensure_csrf_cookie
def csrf(request):
    return json_response({'csrfToken': get_token(request)})


@api_view(['POST'])
def register(request):
    data = json_body(request)
    errors = {}
    username = text_field(data, 'username', errors, required=True, max_length=150)
    email = text_field(data, 'email', errors, required=True, max_length=254)
    display_name = text_field(data, 'display_name', errors, required=True, max_length=80)
    password = data.get('password')
    if not isinstance(password, str) or not password:
        errors['password'] = ['Este campo es obligatorio.']
    if username and 'username' not in errors:
        try:
            User.username_validator(username)
        except ValidationError:
            errors['username'] = ['Usa solo letras, números y los caracteres @ . + - _ (máximo 150).']
        else:
            if User.objects.filter(username__iexact=username).exists():
                errors['username'] = ['Ese nombre de usuario ya está en uso.']
    if email and 'email' not in errors:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = ['Introduce un correo electrónico válido.']
    if 'password' not in errors:
        try:
            validate_password(password, user=User(username=username, email=email))
        except ValidationError as error:
            errors['password'] = password_messages(error)
    if errors:
        return validation_error(errors)
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=username, email=email, password=password)
            Profile.objects.create(user=user, display_name=display_name)
    except IntegrityError:
        return validation_error({'username': 'Ese nombre de usuario ya está en uso.'})
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return json_response({'user': user_data(user)}, status=201)


@api_view(['POST'])
def login_view(request):
    data = json_body(request)
    username, password = data.get('username'), data.get('password')
    if not isinstance(username, str) or not isinstance(password, str) or not username.strip() or not password:
        return detail(GENERIC_LOGIN_ERROR, 400)
    user = authenticate(request, username=username.strip(), password=password)
    if user is None:
        return detail(GENERIC_LOGIN_ERROR, 400)
    login(request, user)
    return json_response({'user': user_data(user)})


@api_view(['POST'])
def logout_view(request):
    logout(request)
    return HttpResponse(status=204)


@api_view(['GET'])
def me(request):
    if not request.user.is_authenticated:
        return json_response({'authenticated': False})
    return json_response({'authenticated': True, 'user': user_data(request.user)})


@api_view(['POST'], login_required=True)
def change_password(request):
    data = json_body(request)
    old_password, new_password = data.get('old_password'), data.get('new_password')
    errors = {}
    if not isinstance(old_password, str) or not old_password:
        errors['old_password'] = ['Este campo es obligatorio.']
    elif not request.user.check_password(old_password):
        errors['old_password'] = ['La contraseña actual no es correcta.']
    if not isinstance(new_password, str) or not new_password:
        errors['new_password'] = ['Este campo es obligatorio.']
    else:
        try:
            validate_password(new_password, user=request.user)
        except ValidationError as error:
            errors['new_password'] = password_messages(error)
    if errors:
        return validation_error(errors)
    request.user.set_password(new_password)
    request.user.save(update_fields=['password'])
    update_session_auth_hash(request, request.user)
    return HttpResponse(status=204)


@api_view(['GET', 'PATCH'], login_required=True)
def profile(request):
    user = request.user
    if request.method == 'GET':
        return json_response({'user': user_data(user)})
    data = json_body(request)
    errors = {}
    profile_obj = get_profile(user)
    limits = {'display_name': 80, 'bio': BIO_MAX_LENGTH, 'country': 2, 'organization': 120, 'language': 2}
    updates = {}
    for field, limit in limits.items():
        if field in data:
            updates[field] = text_field(data, field, errors, required=field in ('display_name', 'language'), max_length=limit)
    if 'country' in updates and 'country' not in errors:
        updates['country'] = updates['country'].upper()
        if updates['country'] and not (len(updates['country']) == 2 and updates['country'].isascii() and updates['country'].isalpha()):
            errors['country'] = ['Usa un código de país ISO de 2 letras (p. ej. ES).']
    if 'language' in updates and 'language' not in errors and updates['language'] not in Profile.Language.values:
        errors['language'] = ['Idioma no admitido. Valores: es, en.']
    email = None
    if 'email' in data:
        email = text_field(data, 'email', errors, required=True, max_length=254)
        if 'email' not in errors:
            try:
                validate_email(email)
            except ValidationError:
                errors['email'] = ['Introduce un correo electrónico válido.']
    if errors:
        return validation_error(errors)
    for field, value in updates.items():
        setattr(profile_obj, field, value)
    with transaction.atomic():
        profile_obj.save()
        if email is not None and email != user.email:
            user.email = email
            user.save(update_fields=['email'])
    return json_response({'user': user_data(user)})
