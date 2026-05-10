import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gearshare_core.settings')

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

# IMPORTANT: Import your routing AFTER get_asgi_application() is called to prevent AppRegistryNotReady errors
import users.routing

application = ProtocolTypeRouter({
    # Django's traditional HTTP routing
    "http": django_asgi_app,
    
    # NEW: The WebSocket routing!
    "websocket": AuthMiddlewareStack(
        URLRouter(
            users.routing.websocket_urlpatterns
        )
    ),
})