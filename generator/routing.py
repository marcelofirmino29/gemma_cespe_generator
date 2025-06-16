# generator/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/kahoot/(?P<game_pin>\w+)/$', consumers.KahootConsumer.as_asgi()),
]