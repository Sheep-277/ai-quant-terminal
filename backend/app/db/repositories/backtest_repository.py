from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.backtest import Backtest, BacktestTrade, EquityCurvePoint


class BacktestRepository:
    """回测 Repository，封装回测结果、权益曲线和模拟成交的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_backtest_id(self, backtest_id: str) -> Backtest | None:
        """根据业务 backtest_id 查询回测主记录。"""

        statement = select(Backtest).where(Backtest.backtest_id == backtest_id.strip())
        return self._session.execute(statement).scalar_one_or_none()

    def list_by_market(self, market: str, *, status: str | None = None, limit: int = 20) -> list[Backtest]:
        """按市场查询最近的回测结果，可选按状态过滤。"""

        statement = select(Backtest).where(Backtest.market == market.upper())
        if status is not None:
            statement = statement.where(Backtest.status == status)
        statement = statement.order_by(Backtest.updated_at.desc(), Backtest.id.desc()).limit(limit)
        return list(self._session.execute(statement).scalars().all())

    def save_backtest(self, backtest: Backtest) -> Backtest:
        """保存回测主记录；backtest_id 已存在时更新绩效摘要。"""

        existing_backtest = self.get_by_backtest_id(backtest.backtest_id)
        if existing_backtest is None:
            self._session.add(backtest)
            return backtest

        existing_backtest.strategy_id = backtest.strategy_id
        existing_backtest.market = backtest.market.upper()
        existing_backtest.status = backtest.status
        existing_backtest.data_mode = backtest.data_mode
        existing_backtest.timezone = backtest.timezone
        existing_backtest.currency = backtest.currency
        existing_backtest.benchmark = backtest.benchmark
        existing_backtest.start_date = backtest.start_date
        existing_backtest.end_date = backtest.end_date
        existing_backtest.initial_capital = backtest.initial_capital
        existing_backtest.final_value = backtest.final_value
        existing_backtest.total_return = backtest.total_return
        existing_backtest.annualized_return = backtest.annualized_return
        existing_backtest.benchmark_return = backtest.benchmark_return
        existing_backtest.maximum_drawdown = backtest.maximum_drawdown
        existing_backtest.sharpe_ratio = backtest.sharpe_ratio
        existing_backtest.win_rate = backtest.win_rate
        existing_backtest.trade_count = backtest.trade_count
        existing_backtest.assumptions = backtest.assumptions
        existing_backtest.source = backtest.source
        return existing_backtest

    def replace_equity_curve(self, backtest: Backtest, points: Sequence[EquityCurvePoint]) -> list[EquityCurvePoint]:
        """替换某次回测的权益曲线点，事务提交由调用方控制。"""

        self._session.execute(delete(EquityCurvePoint).where(EquityCurvePoint.backtest_id == backtest.backtest_id))
        point_list = list(points)
        for point in point_list:
            point.backtest_pk = backtest.id
            point.backtest_id = backtest.backtest_id
        self._session.add_all(point_list)
        return point_list

    def replace_trades(self, backtest: Backtest, trades: Sequence[BacktestTrade]) -> list[BacktestTrade]:
        """替换某次回测的模拟成交记录，事务提交由调用方控制。"""

        self._session.execute(delete(BacktestTrade).where(BacktestTrade.backtest_id == backtest.backtest_id))
        trade_list = list(trades)
        for trade in trade_list:
            trade.backtest_pk = backtest.id
            trade.backtest_id = backtest.backtest_id
        self._session.add_all(trade_list)
        return trade_list

    def list_equity_curve(self, backtest_id: str) -> list[EquityCurvePoint]:
        """按时间升序查询指定回测的权益曲线。"""

        statement = (
            select(EquityCurvePoint)
            .where(EquityCurvePoint.backtest_id == backtest_id.strip())
            .order_by(EquityCurvePoint.point_timestamp.asc(), EquityCurvePoint.id.asc())
        )
        return list(self._session.execute(statement).scalars().all())

    def list_trades(self, backtest_id: str) -> list[BacktestTrade]:
        """按时间升序查询指定回测的模拟成交。"""

        statement = (
            select(BacktestTrade)
            .where(BacktestTrade.backtest_id == backtest_id.strip())
            .order_by(BacktestTrade.trade_timestamp.asc(), BacktestTrade.id.asc())
        )
        return list(self._session.execute(statement).scalars().all())
