from fastapi import APIRouter

from app.api.v1.market_intelligence import router as market_intelligence_router

router = APIRouter()
router.include_router(market_intelligence_router)
