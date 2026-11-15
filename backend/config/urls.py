from django.contrib import admin
from django.urls import path
from stories.views import story_detail

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/stories/<slug:slug>/", story_detail, name="story-detail"),
]
