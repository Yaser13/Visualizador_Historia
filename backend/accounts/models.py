from django.conf import settings
from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models

BIO_MAX_LENGTH = 1000


def default_display_name(user):
    """Public fallback name that never reveals the username or the email."""
    full_name = user.get_full_name().strip() if hasattr(user, 'get_full_name') else ''
    return (full_name or f'Usuario {user.pk}')[:80]


class Profile(models.Model):
    class Language(models.TextChoices):
        ES = 'es', 'Español'
        EN = 'en', 'English'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField('nombre público', max_length=80)
    bio = models.TextField('biografía', blank=True, validators=[MaxLengthValidator(BIO_MAX_LENGTH)])
    country = models.CharField('país (ISO 3166-1 alfa-2)', max_length=2, blank=True,
                               validators=[RegexValidator(r'^[A-Z]{2}$', 'Usa un código de país ISO de 2 letras en mayúsculas (p. ej. ES).')])
    organization = models.CharField('organización', max_length=120, blank=True)
    language = models.CharField('idioma', max_length=2, choices=Language.choices, default=Language.ES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'perfil'
        verbose_name_plural = 'perfiles'

    def __str__(self):
        return self.display_name


def get_profile(user):
    """Return the user's profile, creating it for users that predate the accounts app (e.g. superusers)."""
    profile, _ = Profile.objects.get_or_create(user=user, defaults={'display_name': default_display_name(user)})
    return profile


def public_display_name(user):
    """``display_name`` for public serializers; ``None`` without user. Never exposes username/email."""
    if user is None:
        return None
    try:
        return user.profile.display_name
    except Profile.DoesNotExist:
        return default_display_name(user)
