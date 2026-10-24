from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Backtest(Base):
    """回测结果主表，保存一次策略回测的身份、区间、状态和绩效摘要。"""

    __tablename__ = "backtests"
    __table_args__ = (
        UniqueConstraint("backtest_id", name="uq_backtests_backtest_id"),
        Index("idx_backtests_strategy_market", "strategy_id", "market"),
        Index("idx_backtests_market_status", "market", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    backtest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    data_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    benchmark: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    final_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    total_return: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    annualized_return: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    benchmark_return: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    maximum_drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assumptions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EquityCurvePoint(Base):
    """回测权益曲线点表，保存策略净值、基准净值和回撤序列。"""

    __tablename__ = "equity_curve_points"
    __table_args__ = (
        UniqueConstraint("backtest_id", "point_timestamp", name="uq_equity_curve_backtest_timestamp"),
        Index("idx_equity_curve_backtest_time", "backtest_id", "point_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    backtest_pk: Mapped[int] = mapped_column(ForeignKey("backtests.id"), nullable=False)
    backtest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    point_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    benchmark_equity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)


class BacktestTrade(Base):
    """回测模拟成交表，记录回测引擎生成的买卖、费用和滑点。"""

    __tablename__ = "backtest_trades"
    __table_args__ = (
        Index("idx_backtest_trades_backtest_time", "backtest_id", "trade_timestamp"),
        Index("idx_backtest_trades_symbol_time", "market", "symbol", "trade_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    backtest_pk: Mapped[int] = mapped_column(ForeignKey("backtests.id"), nullable=False)
    backtest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trade_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    slippage: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
