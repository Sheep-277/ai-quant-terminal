"""回测结果服务入口。

该模块使用中性命名承接回测中心结果与任务回执。
当前底层仍复用 mock_backtest_service 中的实现，后续可以逐步把真实 Provider 回测逻辑迁移到这里。
"""

from app.services.mock_backtest_service import (
    create_backtest_task_receipt,
    get_backtest_result,
    get_mock_backtest_result,
)

__all__ = [
    "create_backtest_task_receipt",
    "get_backtest_result",
    "get_mock_backtest_result",
]
