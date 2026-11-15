from django.urls import path

from . import views

urlpatterns = [
    path('', views.submissions, name='submission-list'),
    path('<int:pk>/', views.submission_detail, name='submission-detail'),
    path('<int:pk>/retry/', views.submission_retry, name='submission-retry'),
    path('<int:pk>/publish/', views.submission_publish, name='submission-publish'),
    path('<int:pk>/reject/', views.submission_reject, name='submission-reject'),
]
