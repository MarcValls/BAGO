"""bago.api.routes — HTTP route modules."""

from .chat import router as chat_router
from .generate import router as generate_router
from .embed import router as embed_router
from .models import router as models_router
from .bago import router as bago_router

__all__ = [
    "chat_router", "generate_router", "embed_router",
    "models_router", "bago_router",
]
