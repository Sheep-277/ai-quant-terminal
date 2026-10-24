from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.repositories.backtest_repository import BacktestRepository
from app.models.backtest import Backtest, BacktestTrade, EquityCurvePoint
from app.schemas.backtest import BacktestResponse


def save_backtest_result(session: Session, response: BacktestResponse) -> Backtest:
    """把回测响应快照保存到数据库，包含主表、权益曲线和模拟成交。"""

    repository = BacktestRepository(session)
    saved_backtest = repository.save_backtest(_response_to_backtest(response))
    session.flush()
    repository.replace_equity_curve(
        saved_backtest,
        [_response_point_to_model(point, source="mock_result") for point in response.equity_curve],
    )
    repository.replace_trades(
        saved_backtest,
        [_response_trade_to_model(trade, source="mock_result") for trade in response.trades],
    )
    session.commit()
    session.refresh(saved_backtest)
    return saved_backtest


def _response_to_backtest(response: BacktestResponse) -> Backtest:
    """把 API 回测响应主信息转换成 backtests 表记录。"""

    performance = response.performance
    return Backtest(
        backtest_id=response.backtest_id,
        strategy_id=response.strategy_id,
        market=response.market.value,
        status=response.status.value,
        data_mode=response.data_mode.value,
        timezone=response.timezone,
        currency=response.currency,
        benchmark=response.benchmark,
        start_date=response.start_date,
        end_date=response.end_date,
        initial_capital=_decimal(performance.initial_capital),
        final_value=_decimal(performance.final_value),
        total_return=_decimal(performance.total_return),
        annualized_return=_decimal(performance.annualized_return),
        benchmark_return=_decimal(performance.benchmark_return),
        maximum_drawdown=_decimal(performance.maximum_drawdown),
        sharpe_ratio=None if performance.sharpe_ratio is None else _decimal(performance.sharpe_ratio),
        win_rate=_decimal(performance.win_rate),
        trade_count=performance.trade_count,
        assumptions=response.assumptions,
        source="mock_result",
    )


def _response_point_to_model(point, *, source: str) -> EquityCurvePoint:
    """把 API 权益曲线点转换成 equity_curve_points 表记录。"""

    return EquityCurvePoint(
        backtest_pk=0,
        backtest_id="",
        point_timestamp=_to_naive_datetime(point.timestamp),
        equity=_decimal(point.equity),
        benchmark_equity=_decimal(point.benchmark_equity),
        drawdown=_decimal(point.drawdown),
        source=source,
    )


def _response_trade_to_model(trade, *, source: str) -> BacktestTrade:
    """把 API 回测成交转换成 backtest_trades 表记录。"""

    return BacktestTrade(
        backtest_pk=0,
        backtest_id="",
        trade_timestamp=_to_naive_datetime(trade.timestamp),
        market=trade.market.value,
        symbol=trade.symbol.strip().upper(),
        side=trade.side,
        quantity=trade.quantity,
        price=_decimal(trade.price),
        fee=_decimal(trade.fee),
        slippage=_decimal(trade.slippage),
        source=source,
    )


def _decimal(value: float) -> Decimal:
    """把响应中的浮点数转换为 Decimal，减少金融数值落库时的二进制浮点误差。"""

    return Decimal(str(value))


def _to_naive_datetime(value: datetime) -> datetime:
    """统一去除时区信息，匹配当前项目 DateTime 字段的存储方式。"""

    return value.replace(tzinfo=None)
