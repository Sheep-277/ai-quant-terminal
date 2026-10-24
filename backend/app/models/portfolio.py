from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Portfolio(Base):
    """模拟组合账户表，保存账户净值、现金、收益和组合风险摘要。"""

    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_portfolios_account_id"),
        Index("idx_portfolios_market_updated", "market", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(String(80), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    data_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    daily_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    total_return: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    largest_position_weight: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    cash_weight: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Position(Base):
    """模拟持仓表，保存单个账户下每只股票的数量、成本、市值和浮动盈亏。"""

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("account_id", "market", "symbol", name="uq_positions_account_market_symbol"),
        Index("idx_positions_account_weight", "account_id", "weight"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(String(80), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    last_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    unrealized_pnl_percent: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Order(Base):
    """模拟订单表，记录模拟账户中的下单请求、状态和风控结论。"""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_orders_order_id"),
        Index("idx_orders_account_status", "account_id", "status"),
        Index("idx_orders_symbol_time", "market", "symbol", "submitted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    account_id: Mapped[str] = mapped_column(String(80), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    risk_checked: Mapped[bool] = mapped_column(default=False, nullable=False)
    risk_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    risk_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)


class Trade(Base):
    """模拟成交表，记录订单成交后的价格、数量和费用快照。"""

    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("trade_id", name="uq_trades_trade_id"),
        Index("idx_trades_order_time", "order_id", "filled_at"),
        Index("idx_trades_symbol_time", "market", "symbol", "filled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trade_id: Mapped[str] = mapped_column(String(128), nullable=False)
    account_id: Mapped[str] = mapped_column(String(80), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    filled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
