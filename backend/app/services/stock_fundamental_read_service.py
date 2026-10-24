from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.financial_repository import FinancialRepository
from app.db.repositories.valuation_snapshot_repository import ValuationSnapshotRepository
from app.models.financial import Financial
from app.models.valuation_snapshot import ValuationSnapshot
from app.schemas.stock import CashFlowMetrics, ProfitabilityMetrics, ValuationMetrics

FundamentalDataCompleteness = Literal["complete", "partial"]


@dataclass(frozen=True)
class StockFundamentalReadSnapshot:
    """个股基本面和估值的只读快照。"""

    valuation: ValuationMetrics
    profitability: ProfitabilityMetrics
    cash_flow: CashFlowMetrics
    source: str
    completeness: FundamentalDataCompleteness
    available_sections: tuple[str, ...]
    missing_sections: tuple[str, ...]


def get_stock_fundamental_read_snapshot(
    session: Session,
    market: MarketCode,
    symbol: str,
) -> StockFundamentalReadSnapshot | None:
    """从数据库读取最新基本面和估值；缺失时返回 None，让调用方回退 Mock。"""

    normalized_symbol = symbol.strip().upper()
    financial = FinancialRepository(session).get_latest_by_market_symbol(market.value, normalized_symbol)
    valuation = ValuationSnapshotRepository(session).get_latest_by_market_symbol(market.value, normalized_symbol)
    if financial is None and valuation is None:
        return None

    return StockFundamentalReadSnapshot(
        valuation=_to_valuation_metrics(valuation),
        profitability=_to_profitability_metrics(financial),
        cash_flow=_to_cash_flow_metrics(financial),
        source="database",
        completeness=_resolve_completeness(financial, valuation),
        available_sections=_resolve_available_sections(financial, valuation),
        missing_sections=_resolve_missing_sections(financial, valuation),
    )


def _resolve_completeness(
    financial: Financial | None,
    valuation: ValuationSnapshot | None,
) -> FundamentalDataCompleteness:
    """判断数据库基本面快照是否覆盖估值、盈利能力和现金流三个区域。"""

    if financial is not None and valuation is not None:
        return "complete"
    return "partial"


def _resolve_available_sections(financial: Financial | None, valuation: ValuationSnapshot | None) -> tuple[str, ...]:
    """返回当前数据库快照已经覆盖的页面指标区域。"""

    sections: list[str] = []
    if valuation is not None:
        sections.append("valuation")
    if financial is not None:
        sections.extend(["profitability", "cash_flow"])
    return tuple(sections)


def _resolve_missing_sections(financial: Financial | None, valuation: ValuationSnapshot | None) -> tuple[str, ...]:
    """返回当前数据库快照缺失、需要调用方继续回退的页面指标区域。"""

    sections: list[str] = []
    if valuation is None:
        sections.append("valuation")
    if financial is None:
        sections.extend(["profitability", "cash_flow"])
    return tuple(sections)


def _to_valuation_metrics(snapshot: ValuationSnapshot | None) -> ValuationMetrics:
    """把估值快照 ORM 转成个股研究响应中的估值指标。"""

    if snapshot is None:
        return ValuationMetrics()

    return ValuationMetrics(
        pe_ttm=_decimal_to_float(snapshot.pe_ttm),
        pb=_decimal_to_float(snapshot.pb),
        ps_ttm=_decimal_to_float(snapshot.ps_ttm),
        pfcf_ttm=_decimal_to_float(snapshot.pfcf_ttm),
    )


def _to_profitability_metrics(financial: Financial | None) -> ProfitabilityMetrics:
    """把基本面 ORM 转成盈利能力指标。"""

    if financial is None:
        return ProfitabilityMetrics()

    return ProfitabilityMetrics(
        roe_ttm=_decimal_to_float(financial.roe),
        roic_ttm=_decimal_to_float(financial.roic),
        gross_margin_ttm=_decimal_to_float(financial.gross_margin),
        operating_margin_ttm=_decimal_to_float(financial.operating_margin),
    )


def _to_cash_flow_metrics(financial: Financial | None) -> CashFlowMetrics:
    """把基本面 ORM 转成现金流指标。"""

    if financial is None:
        return CashFlowMetrics()

    return CashFlowMetrics(
        fcf_ttm=_decimal_to_float(financial.fcf),
        operating_cash_flow_ttm=_decimal_to_float(financial.operating_cash_flow),
        capex_ttm=_decimal_to_float(financial.capex),
    )


def _decimal_to_float(value):
    """把数据库 Decimal 转成 API 使用的 float，并保留 None 表示缺失值。"""

    if value is None:
        return None
    return float(value)
