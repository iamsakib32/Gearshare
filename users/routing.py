from django.urls import path
from . import consumers

websocket_urlpatterns = [
    # This URL matches the one we will put in your JavaScript later!
    path('ws/chat/<int:request_id>/', consumers.ChatConsumer.as_asgi()),
]