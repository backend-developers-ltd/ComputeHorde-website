from django.conf import settings
from django.contrib.admin.sites import site as admin_site
from django.urls import include, path
from fingerprint.views import FingerprintView

from .core.consumers import ValidatorConsumer
from .core.views import SignupView

urlpatterns = [
    path("admin/", admin_site.urls),
    path("redirect/", FingerprintView.as_view(), name="fingerprint"),
    path("accounts/signup/", SignupView.as_view(), name="account_signup"),
    path("accounts/", include("allauth.urls")),
    path("", include("project.core.urls")),
]

if settings.DEBUG_TOOLBAR:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
    ]

ws_urlpatterns = [
    path("ws/v0/", ValidatorConsumer.as_asgi()),
]
