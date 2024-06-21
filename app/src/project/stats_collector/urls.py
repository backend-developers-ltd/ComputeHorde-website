from django.urls import path

from .views import ValidatorSystemEventView

urlpatterns = [
    path("v0/validator/<str:validator_ss58_address>/system_events", ValidatorSystemEventView.as_view()),
]
