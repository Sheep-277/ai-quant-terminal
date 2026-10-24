from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.backtest_repository import BacktestRepository
from app.models.backtest import Backtest, BacktestTrade as BacktestTradeModel, EquityCurvePoint as EquityCurvePointModel
from app.schemas.backtest import (
    BacktestDataMode,
    BacktestPerformance,
    BacktestResponse,
    BacktestStatus,
    BacktestTrade,
    EquityCurvePoint,
)


@dataclass(frozen=True)
class BacktestReadSnapshot:
    """回测结果只读快照，标记当前数据来自数据库。"""

    response: BacktestResponse
    source: str


def get_latest_backtest_snapshot(session: Session, market: MarketCode) -> BacktestReadSnapshot | None:
    """读取当前市场最近一条已完成回测；没有数据时返回 None，让调用方回退 Mock。"""

    repository = BacktestRepository(session)
    backtests = repository.list_by_market(market.value, status=BacktestStatus.COMPLETED.value, limit=1)
    if not backtests:
        return None

    backtest = backtests[0]
    return BacktestReadSnapshot(
        response=_backtest_to_response(
            backtest,
            equity_curve=repository.list_equity_curve(backtest.backtest_id),
            trades=repository.list_trades(backtest.backtest_id),
        ),
        source="database",
    )


def get_backtest_snapshot_by_id(session: Session, backtest_id: str) -> BacktestReadSnapshot | None:
    """按 backtest_id 读取回测结果；不存在时返回 None。"""

    repository = BacktestRepository(session)
    backtest = repository.get_by_backtest_id(backtest_id)
    if backtest is None:
        return None

    return BacktestReadSnapshot(
        response=_backtest_to_response(
            backtest,
            equity_curve=repository.list_equity_curve(backtest.backtest_id),
            trades=repository.list_trades(backtest.backtest_id),
        ),
        source="database",
    )


def _backtest_to_response(
    backtest: Backtest,
    *,
    equity_curve: list[EquityCurvePointModel],
    trades: list[BacktestTradeModel],
) -> BacktestResponse:
    """把数据库回测记录转换为前端使用的 BacktestResponse。"""

    return BacktestResponse(
        backtest_id=backtest.backtest_id,
        strategy_id=backtest.strategy_id,
        market=MarketCode(backtest.market),
        status=BacktestStatus(backtest.status),
        data_mode=BacktestDataMode(backtest.data_mode),
        timestamp=_to_utc(backtest.updated_at),
        timezone=backtest.timezone,
        currency=backtest.currency,
        benchmark=backtest.benchmark,
        start_date=backtest.start_date,
        end_date=backtest.end_date,
        performance=BacktestPerformance(
            initial_capital=float(backtest.initial_capital),
            final_value=float(backtest.final_value),
            total_return=float(backtest.total_return),
            annualized_return=float(backtest.annualized_return),
            benchmark_return=float(backtest.benchmark_return),
            maximum_drawdown=float(backtest.maximum_drawdown),
            sharpe_ratio=None if backtest.sharpe_ratio is None else float(backtest.sharpe_ratio),
            win_rate=float(backtest.win_rate),
            trade_count=backtest.trade_count,
        ),
        equity_curve=[_equity_point_to_schema(point) for point in equity_curve],
        trades=[_trade_to_schema(trade) for trade in trades],
        assumptions=list(backtest.assumptions),
    )


def _equity_point_to_schema(point: EquityCurvePointModel) -> EquityCurvePoint:
    """把数据库权益曲线点转换为 API schema。"""

    return EquityCurvePoint(
        timestamp=_to_utc(point.point_timestamp),
        equity=float(point.equity),
        benchmark_equity=float(point.benchmark_equity),
        drawdown=float(point.drawdown),
    )


def _trade_to_schema(trade: BacktestTradeModel) -> BacktestTrade:
    """把数据库回测成交转换为 API schema。"""

    return BacktestTrade(
        timestamp=_to_utc(trade.trade_timestamp),
        market=MarketCode(trade.market),
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
        price=float(trade.price),
        fee=float(trade.fee),
        slippage=float(trade.slippage),
    )


def _to_utc(value: datetime) -> datetime:
    """把数据库中的无时区时间补成 UTC，保持 API 响应时间语义明确。"""

    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return value.replace(tzinfo=timezone.utc)
