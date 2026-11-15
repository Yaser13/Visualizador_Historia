"""Session auth and profile API (docs/api/CONTRATO_USUARIOS_INGESTA.md §2). Synthetic users only."""
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Profile, get_profile

User = get_user_model()
# Password hashing speed is irrelevant here; the hasher choice does not change the API behaviour.
FAST_HASHERS = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
STRONG_PASSWORD = 'Globo-Sintetico-2026!'


def post_json(client, url, data, **extra):
    return client.post(url, data=json.dumps(data), content_type='application/json', **extra)


def patch_json(client, url, data, **extra):
    return client.patch(url, data=json.dumps(data), content_type='application/json', **extra)


@FAST_HASHERS
class RegisterTests(TestCase):
    def register(self, **overrides):
        data = {'username': 'ana', 'email': 'ana@example.org', 'password': STRONG_PASSWORD, 'display_name': 'Ana P.'}
        data.update(overrides)
        return post_json(self.client, reverse('auth-register'), data)

    def test_register_creates_user_profile_and_session(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        user = response.json()['user']
        self.assertEqual(user['username'], 'ana')
        self.assertEqual(user['email'], 'ana@example.org')
        self.assertFalse(user['is_staff'])
        self.assertEqual(user['profile'], {'display_name': 'Ana P.', 'bio': '', 'country': '', 'organization': '', 'language': 'es'})
        self.assertTrue(Profile.objects.filter(user__username='ana', display_name='Ana P.').exists())
        me = self.client.get(reverse('auth-me')).json()
        self.assertTrue(me['authenticated'])
        self.assertEqual(me['user']['id'], user['id'])

    def test_register_validation_messages_in_spanish(self):
        response = self.register(username='', email='no-es-un-correo', password='123', display_name='')
        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        self.assertEqual(set(errors), {'username', 'email', 'password', 'display_name'})
        self.assertEqual(errors['email'], ['Introduce un correo electrónico válido.'])
        # Django password validators, translated through LANGUAGE_CODE = 'es'.
        self.assertTrue(any('contraseña' in message.lower() for message in errors['password']), errors['password'])
        self.assertFalse(User.objects.exists())

    def test_password_similar_to_username_is_rejected(self):
        response = self.register(username='marianoperez', password='marianoperez1')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json()['errors'])

    def test_username_must_be_unique_case_insensitive(self):
        self.assertEqual(self.register().status_code, 201)
        self.client.post(reverse('auth-logout'))
        response = self.register(username='ANA', email='otra@example.org')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['username'], ['Ese nombre de usuario ya está en uso.'])

    def test_invalid_json_body(self):
        response = self.client.post(reverse('auth-register'), data='[1, 2]', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.json())

    def test_wrong_method(self):
        response = self.client.get(reverse('auth-register'))
        self.assertEqual(response.status_code, 405)
        self.assertIn('detail', response.json())


@FAST_HASHERS
class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('luis', 'luis@example.org', STRONG_PASSWORD)

    def test_login_creates_missing_profile_and_logout(self):
        response = post_json(self.client, reverse('auth-login'), {'username': 'luis', 'password': STRONG_PASSWORD})
        self.assertEqual(response.status_code, 200)
        # Users that predate the accounts app (e.g. superusers) get a profile on first read,
        # with a public name that does not reveal the username.
        self.assertEqual(response.json()['user']['profile']['display_name'], f'Usuario {self.user.pk}')
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertEqual(self.client.post(reverse('auth-logout')).status_code, 204)
        self.assertEqual(self.client.get(reverse('auth-me')).json(), {'authenticated': False})

    def test_login_error_is_generic(self):
        wrong_password = post_json(self.client, reverse('auth-login'), {'username': 'luis', 'password': 'x'})
        unknown_user = post_json(self.client, reverse('auth-login'), {'username': 'nadie', 'password': 'x'})
        self.assertEqual(wrong_password.status_code, 400)
        self.assertEqual(wrong_password.json(), unknown_user.json())
        self.assertEqual(wrong_password.json(), {'detail': 'Usuario o contraseña incorrectos.'})

    def test_inactive_user_gets_generic_error(self):
        self.user.is_active = False
        self.user.save()
        response = post_json(self.client, reverse('auth-login'), {'username': 'luis', 'password': STRONG_PASSWORD})
        self.assertEqual(response.json(), {'detail': 'Usuario o contraseña incorrectos.'})


@FAST_HASHERS
class CsrfTests(TestCase):
    def setUp(self):
        User.objects.create_user('eva', 'eva@example.org', STRONG_PASSWORD)
        self.client = Client(enforce_csrf_checks=True)

    def test_post_without_token_is_rejected_with_json(self):
        response = post_json(self.client, reverse('auth-login'), {'username': 'eva', 'password': STRONG_PASSWORD})
        self.assertEqual(response.status_code, 403)
        self.assertIn('CSRF', response.json()['detail'])

    def test_csrf_endpoint_sets_readable_cookie_and_token_works(self):
        response = self.client.get(reverse('auth-csrf'))
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies[settings.CSRF_COOKIE_NAME]
        self.assertFalse(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        token = response.json()['csrfToken']
        self.assertTrue(token)
        login = post_json(self.client, reverse('auth-login'), {'username': 'eva', 'password': STRONG_PASSWORD},
                          HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login.status_code, 200)
        session_cookie = login.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(session_cookie['httponly'])
        self.assertEqual(session_cookie['samesite'], 'Lax')
        # Login rotates the CSRF token: the SPA must read the new cookie.
        token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(post_json(self.client, reverse('auth-logout'), {}).status_code, 403)
        self.assertEqual(post_json(self.client, reverse('auth-logout'), {}, HTTP_X_CSRFTOKEN=token).status_code, 204)

    def test_patch_profile_requires_token(self):
        self.client.get(reverse('auth-csrf'))
        token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        post_json(self.client, reverse('auth-login'), {'username': 'eva', 'password': STRONG_PASSWORD}, HTTP_X_CSRFTOKEN=token)
        token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(patch_json(self.client, reverse('profile'), {'bio': 'x'}).status_code, 403)
        self.assertEqual(patch_json(self.client, reverse('profile'), {'bio': 'x'}, HTTP_X_CSRFTOKEN=token).status_code, 200)


@FAST_HASHERS
class ProfileAndPasswordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('rosa', 'rosa@example.org', STRONG_PASSWORD)
        get_profile(self.user)

    def test_requires_session(self):
        self.assertEqual(self.client.get(reverse('profile')).status_code, 401)
        self.assertEqual(post_json(self.client, reverse('auth-password'), {}).status_code, 401)
        self.assertEqual(self.client.get(reverse('profile')).json(), {'detail': 'Inicia sesión para continuar.'})

    def test_get_and_patch_profile(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('profile')).json()['user']['username'], 'rosa')
        response = patch_json(self.client, reverse('profile'), {
            'email': 'rosa@example.net', 'display_name': 'Rosa M.', 'bio': 'Analista sintética.',
            'country': 'es', 'organization': 'Ejemplo', 'language': 'en', 'username': 'ignorado'})
        self.assertEqual(response.status_code, 200)
        user = response.json()['user']
        self.assertEqual(user['email'], 'rosa@example.net')
        self.assertEqual(user['username'], 'rosa')
        self.assertEqual(user['profile'], {'display_name': 'Rosa M.', 'bio': 'Analista sintética.', 'country': 'ES',
                                           'organization': 'Ejemplo', 'language': 'en'})

    def test_patch_profile_validation(self):
        self.client.force_login(self.user)
        response = patch_json(self.client, reverse('profile'), {
            'email': 'mal', 'display_name': '', 'bio': 'x' * 1001, 'country': 'ESP', 'language': 'fr'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()['errors']), {'email', 'display_name', 'bio', 'country', 'language'})
        self.assertEqual(Profile.objects.get(user=self.user).language, 'es')

    def test_change_password_keeps_session(self):
        self.client.force_login(self.user)
        wrong = post_json(self.client, reverse('auth-password'), {'old_password': 'x', 'new_password': 'Otra-Clave-Larga-99'})
        self.assertEqual(wrong.status_code, 400)
        self.assertIn('old_password', wrong.json()['errors'])
        weak = post_json(self.client, reverse('auth-password'), {'old_password': STRONG_PASSWORD, 'new_password': '1234'})
        self.assertEqual(weak.status_code, 400)
        self.assertIn('new_password', weak.json()['errors'])
        response = post_json(self.client, reverse('auth-password'), {'old_password': STRONG_PASSWORD, 'new_password': 'Otra-Clave-Larga-99'})
        self.assertEqual(response.status_code, 204)
        self.assertTrue(self.client.get(reverse('auth-me')).json()['authenticated'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Otra-Clave-Larga-99'))
