from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.factor_value_repository import FactorValueRepository
from app.models.factor_value import FactorValue
from app.schemas.stock import StockFactorSnapshot


@dataclass(frozen=True)
class StockFactorReadSnapshot:
    """个股因子值只读快照。"""

    factor_snapshot: StockFactorSnapshot
    source: str
    available_factors: tuple[str, ...]
    missing_factors: tuple[str, ...]


EXPECTED_FACTOR_NAMES = (
    "momentum_20d",
    "trend_strength",
    "volatility_20d",
    "quality_score",
    "composite_score",
)


def get_stock_factor_read_snapshot(
    session: Session,
    market: MarketCode,
    symbol: str,
) -> StockFactorReadSnapshot | None:
    """从数据库读取最新因子快照；无数据时返回 None，让调用方回退 Quant Pipeline。"""

    normalized_symbol = symbol.strip().upper()
    factor_values = FactorValueRepository(session).list_latest_by_market_symbol(market.value, normalized_symbol)
    if not factor_values:
        return None

    factor_map = {factor.factor_name: factor for factor in factor_values}
    available_factors = tuple(factor_name for factor_name in EXPECTED_FACTOR_NAMES if factor_name in factor_map)
    missing_factors = tuple(factor_name for factor_name in EXPECTED_FACTOR_NAMES if factor_name not in factor_map)

    return StockFactorReadSnapshot(
        factor_snapshot=StockFactorSnapshot(
            momentum_20d=_factor_to_float(factor_map.get("momentum_20d")),
            trend_strength=_factor_to_float(factor_map.get("trend_strength")),
            volatility_20d=_factor_to_float(factor_map.get("volatility_20d")),
            quality_score=_factor_to_float(factor_map.get("quality_score")),
            composite_score=_factor_to_float(factor_map.get("composite_score")),
        ),
        source="database",
        available_factors=available_factors,
        missing_factors=missing_factors,
    )


def _factor_to_float(factor: FactorValue | None) -> float | None:
    """把数据库因子值转换成 API 使用的 float，并保留缺失值。"""

    if factor is None or factor.factor_value is None:
        return None
    return float(factor.factor_value)
