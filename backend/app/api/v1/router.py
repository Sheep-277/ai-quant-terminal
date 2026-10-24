from fastapi import APIRouter

from app.api.v1.ai_research import legacy_router as ai_research_legacy_router
from app.api.v1.ai_research import router as research_router
from app.api.v1.backtest import router as backtest_router
from app.api.v1.market import router as market_router
from app.api.v1.monitor import router as monitor_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.provider import router as provider_router
from app.api.v1.risk import router as risk_router
from app.api.v1.stock import router as stock_router
from app.api.v1.strategy import router as strategy_router


api_router = APIRouter()

# V1 下的业务路由统一在这里聚合，main.py 只负责挂载总入口。
api_router.include_router(market_router)
api_router.include_router(stock_router)
api_router.include_router(strategy_router)
api_router.include_router(backtest_router)
api_router.include_router(portfolio_router)
api_router.include_router(provider_router)
api_router.include_router(risk_router)
api_router.include_router(monitor_router)
api_router.include_router(research_router)
api_router.include_router(ai_research_legacy_router)
