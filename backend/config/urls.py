from django.contrib import admin
from django.urls import path
from stories.views import stories_index, story_detail

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/stories/", stories_index, name="story-list"),
    path("api/stories/<slug:slug>/", story_detail, name="story-detail"),
]
