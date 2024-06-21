import os

import django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from .urls import ws_urlpatterns  # noqa: E402

django_application = get_asgi_application()


application = ProtocolTypeRouter(
    {
        "http": django_application,
        "websocket": URLRouter(ws_urlpatterns),
    }
)
