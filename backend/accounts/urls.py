from django.urls import path

from . import views

auth_urlpatterns = [
    path('csrf/', views.csrf, name='auth-csrf'),
    path('register/', views.register, name='auth-register'),
    path('login/', views.login_view, name='auth-login'),
    path('logout/', views.logout_view, name='auth-logout'),
    path('me/', views.me, name='auth-me'),
    path('password/', views.change_password, name='auth-password'),
]
