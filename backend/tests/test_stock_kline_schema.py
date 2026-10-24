"""个股研究 K 线合同校验，不访问数据库或外部 Provider。"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.market import DataStatus
from app.schemas.stock import KLineBar, KLineInterval, KLineSeries


def make_bar(**changes: object) -> KLineBar:
    """构造合法行情，允许测试覆盖单个异常字段。"""

    return KLineBar.model_validate({
        "timestamp": datetime(2026, 10, 19, 16, tzinfo=timezone.utc),
        "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000,
        **changes,
    })


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 0, -1])
def test_reject_invalid_prices(field: str, value: float) -> None:
    """四个价格字段均必须是有限正数。"""

    with pytest.raises(ValidationError):
        make_bar(**{field: value})


@pytest.mark.parametrize("changes", [
    {"low": 101}, {"close": 106}, {"open": 106}, {"high": 94},
    {"volume": -1}, {"volume": float("inf")}, {"volume": float("nan")},
    {"timestamp": "invalid-date"},
])
def test_reject_inconsistent_bar(changes: dict[str, object]) -> None:
    """拒绝高低价矛盾、无效成交量及无法解析的时间。"""

    with pytest.raises(ValidationError):
        make_bar(**changes)


def test_flat_bar_and_zero_volume_remain_valid() -> None:
    """平价行情与零成交量是合法样本，不补造波动或成交量。"""

    bar = make_bar(open=100, high=100, low=100, close=100, volume=0)
    assert bar.high == bar.low == 100
    assert bar.volume == 0


@pytest.mark.parametrize("minutes", [0, -1])
def test_reject_duplicate_or_reversed_time(minutes: int) -> None:
    """后一个样本必须晚于前一个样本。"""

    first = make_bar()
    second = make_bar(timestamp=first.timestamp + timedelta(minutes=minutes))
    with pytest.raises(ValidationError, match="strictly increasing"):
        KLineSeries(interval=KLineInterval.ONE_DAY, data_status=DataStatus.DELAYED, bars=[first, second])


def test_reject_mixed_timezone_awareness() -> None:
    """不把无时区日期猜成某一市场时间。"""

    with pytest.raises(ValidationError, match="comparable timezone"):
        KLineSeries(interval="1d", data_status="delayed", bars=[
            make_bar(), make_bar(timestamp=datetime(2026, 10, 20, 16)),
        ])


def test_compare_absolute_time_across_offsets() -> None:
    """不同时区表达的同一时刻仍属于重复样本。"""

    first = make_bar()
    same_instant = first.timestamp.astimezone(timezone(timedelta(hours=8)))
    with pytest.raises(ValidationError, match="strictly increasing"):
        KLineSeries(interval="1d", data_status="delayed", bars=[first, make_bar(timestamp=same_instant)])


@pytest.mark.parametrize("count", [0, 1, 3])
def test_accept_valid_series_without_reordering(count: int) -> None:
    """空序列、单根及合法递增序列均保留原始行情与状态。"""

    bars = [make_bar(timestamp=datetime(2026, 10, 19 + index, 16, tzinfo=timezone.utc)) for index in range(count)]
    series = KLineSeries(interval="1d", data_status="delayed", bars=bars)
    assert series.bars == bars
    assert series.data_status == DataStatus.DELAYED
