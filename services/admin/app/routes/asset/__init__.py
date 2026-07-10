from .batches import router as batches_router
from .card_types import router as card_types_router
from .cards import router as cards_router
from .redemptions import router as redemptions_router

asset_routers = [
    card_types_router,
    batches_router,
    cards_router,
    redemptions_router,
]

__all__ = ["asset_routers"]
