from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from .api import router
from .views import (
    DockerImageJobCreateView,
    JobDetailView,
    JobListView,
    RawScriptJobCreateView,
    api_token_view,
)

urlpatterns = [
    path("", JobListView.as_view(), name="job/list"),
    path("new-docker/", DockerImageJobCreateView.as_view(), name="job-docker/submit"),
    path("new-raw/", RawScriptJobCreateView.as_view(), name="job-raw/submit"),
    path("<uuid:pk>/", JobDetailView.as_view(), name="job/detail"),
    path("api/v1/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("api-token-auth/", obtain_auth_token, name="api-token-auth"),
    path("api-token-generate/", api_token_view, name="api-token-generate"),
]
