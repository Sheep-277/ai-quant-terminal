from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.session import get_db_session
from app.schemas.stock import StockResearchQuery, StockResearchResponse
from app.services.mock_stock_service import get_default_stock_symbol, get_mock_stock_research
from app.services.kline_read_service import get_kline_read_snapshot
from app.services.stock_factor_read_service import get_stock_factor_read_snapshot
from app.services.stock_fundamental_read_service import get_stock_fundamental_read_snapshot
from app.services.stock_read_service import get_stock_read_snapshot
from app.services.stock_signal_read_service import get_stock_signal_read_snapshot


router = APIRouter(prefix="/stock", tags=["stock"])


def parse_stock_research_query(
    market: MarketCode = Query(default=MarketCode.US, description="当前市场代码：US / HK / CN"),
    symbol: str | None = Query(default=None, description="股票代码；不传时按市场使用默认 Mock 标的"),
) -> StockResearchQuery:
    """把 HTTP query 参数转换为 schema，并让校验失败稳定返回 422。"""

    try:
        return StockResearchQuery(market=market, symbol=symbol)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error


@router.get("/research", response_model=StockResearchResponse)
def get_stock_research(
    query: Annotated[StockResearchQuery, Depends(parse_stock_research_query)],
) -> StockResearchResponse:
    """返回个股研究页所需的结构化 Mock 数据。"""

    return build_stock_research_response(query, get_settings())


def build_stock_research_response(query: StockResearchQuery, settings: Settings) -> StockResearchResponse:
    """根据配置构造个股研究响应；开启数据库读取时优先使用本地股票研究表。"""

    if not settings.enable_stock_database_reads:
        return get_mock_stock_research(market=query.market, symbol=query.symbol)

    resolved_symbol = query.symbol or get_default_stock_symbol(query.market)
    session_generator = get_db_session(settings)
    session = next(session_generator)
    try:
        snapshot = get_stock_read_snapshot(session, query.market, resolved_symbol)
        fundamental_snapshot = get_stock_fundamental_read_snapshot(session, query.market, resolved_symbol)
        factor_snapshot = get_stock_factor_read_snapshot(session, query.market, resolved_symbol)
        signal_snapshot = get_stock_signal_read_snapshot(session, query.market, resolved_symbol)
        kline_snapshot = get_kline_read_snapshot(session, query.market, resolved_symbol)
        return get_mock_stock_research(
            market=query.market,
            symbol=query.symbol,
            stock_read_snapshot=snapshot,
            fundamental_read_snapshot=fundamental_snapshot,
            factor_read_snapshot=factor_snapshot,
            signal_read_snapshot=signal_snapshot,
            kline_read_snapshot=kline_snapshot,
        )
    finally:
        session_generator.close()
