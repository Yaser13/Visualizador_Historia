from django.contrib import admin
from django.urls import include, path

from accounts.urls import auth_urlpatterns
from accounts.views import profile
from stories.views import stories_index, story_detail

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/stories/", stories_index, name="story-list"),
    path("api/stories/<slug:slug>/", story_detail, name="story-detail"),
    path("api/auth/", include(auth_urlpatterns)),
    path("api/profile/", profile, name="profile"),
    path("api/submissions/", include("ingestion.urls")),
]
