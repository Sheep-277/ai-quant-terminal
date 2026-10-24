from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.signal_repository import SignalRepository
from app.models.signal import Signal
from app.schemas.market import DataStatus, Direction
from app.schemas.monitor import (
    MonitorEvent,
    MonitorResponse,
    MonitorSignal,
    MonitorSignalSeverity,
    MonitorSource,
)


def get_monitor_signal_read_snapshot(
    session: Session,
    market: MarketCode,
    fallback: MonitorResponse,
) -> MonitorResponse | None:
    """用 signals 表替换监控页信号集；缺少信号时返回 None 让调用方回退 Mock。"""

    signals = SignalRepository(session).list_latest_by_market(market.value)
    if not signals:
        return None

    latest_signal_time = max(signal.triggered_at for signal in signals)
    return fallback.model_copy(
        update={
            "timestamp": latest_signal_time,
            # 仅替换信号和心跳口径，不能把原有 Mock 连接状态标成数据库或真实行情。
            "provenance": fallback.provenance.model_copy(
                update={
                    "signal_source": "database",
                    "event_source": "mixed",
                    "heartbeat_basis": "latest_signal",
                }
            ),
            "stream": fallback.stream.model_copy(
                update={
                    "last_heartbeat_at": latest_signal_time,
                    "data_status": DataStatus.DELAYED,
                }
            ),
            "signals": [_signal_to_monitor_signal(signal) for signal in signals],
            "events": [*_append_database_signal_event(fallback, signals)],
        }
    )


def _signal_to_monitor_signal(signal: Signal) -> MonitorSignal:
    """把持久化量化信号转换成实时监控页可展示的信号卡片。"""

    return MonitorSignal(
        signal_id=f"db-signal-{signal.id}",
        market=MarketCode(signal.market),
        symbol=signal.symbol,
        title=_localize_signal_title(signal.signal_type),
        direction=Direction(signal.direction),
        severity=MonitorSignalSeverity(signal.severity),
        score=signal.score,
        triggered_at=signal.triggered_at,
        source=signal.source,
        # 已落库只代表存储位置；没有可信上游口径的其他来源不能标成真实行情计算。
        data_origin="seed" if signal.source == "mock_seed" else "unknown",
        evidence=[*signal.evidence, f"source={signal.source}"],
    )


def _append_database_signal_event(
    fallback: MonitorResponse,
    signals: list[Signal],
) -> list[MonitorEvent]:
    """在事件流中补充数据库信号读取事件，方便前端观察数据来源。"""

    latest_signal_time = max(signal.triggered_at for signal in signals)
    latest_signal = _get_latest_signal(signals)
    highest_severity = _get_highest_severity(signals)
    source_status_summary = _build_source_status_summary(fallback)
    warning_count = sum(1 for signal in signals if signal.severity == MonitorSignalSeverity.WARNING.value)
    critical_count = sum(1 for signal in signals if signal.severity == MonitorSignalSeverity.CRITICAL.value)
    database_event = MonitorEvent(
        event_id=f"event-{fallback.market.value.lower()}-db-signals",
        market=fallback.market,
        source=MonitorSource.FAST_PATH,
        title="本地信号读取完成",
        summary=(
            f"信息：已从 signals 表读取 {len(signals)} 条本地量化信号，"
            f"最新触发标的为 {latest_signal.symbol}，最高严重程度为 {highest_severity}。"
        ),
        impact=Direction.NEUTRAL,
        confidence=1.0,
        created_at=latest_signal_time,
    )
    source_status_event = MonitorEvent(
        event_id=f"event-{fallback.market.value.lower()}-db-source-status",
        market=fallback.market,
        source=MonitorSource.PROVIDER,
        title="监控数据源状态",
        summary=source_status_summary,
        impact=Direction.NEUTRAL,
        confidence=1.0,
        created_at=latest_signal_time,
    )
    risk_event = MonitorEvent(
        event_id=f"event-{fallback.market.value.lower()}-db-risk-summary",
        market=fallback.market,
        source=MonitorSource.RISK_ENGINE,
        title="本地信号风险复核完成",
        summary=(
            "警告："
            f"数据库信号集中包含 {warning_count} 条 warning 和 {critical_count} 条 critical，"
            f"当前最高严重程度为 {highest_severity}，实时监控页应优先查看高严重程度信号。"
        ),
        impact=_get_risk_event_impact(highest_severity),
        confidence=1.0,
        created_at=latest_signal_time,
    )
    return [*fallback.events, database_event, source_status_event, risk_event]


def _build_source_status_summary(fallback: MonitorResponse) -> str:
    """生成数据源边界摘要，避免把本地数据库信号误读为实时推送。"""

    return (
        "信息：连接状态来自 Mock Monitor，"
        f"连接状态={fallback.stream.status.value}，"
        "传输方式=REST 轮询，"
        "信号来源=数据库 signals 表，"
        "心跳时间=数据库最新信号时间，"
        "当前未连接真实 WebSocket 推送。"
    )


def _get_latest_signal(signals: list[Signal]) -> Signal:
    """返回最新触发的信号；时间相同则保留数据库读取顺序中的最后一条。"""

    return max(enumerate(signals), key=lambda item: (item[1].triggered_at, item[0]))[1]


def _get_highest_severity(signals: list[Signal]) -> str:
    """按 info < warning < critical 计算当前信号集中最高严重程度。"""

    severity_rank = {
        MonitorSignalSeverity.INFO.value: 1,
        MonitorSignalSeverity.WARNING.value: 2,
        MonitorSignalSeverity.CRITICAL.value: 3,
    }
    return max((signal.severity for signal in signals), key=lambda severity: severity_rank.get(severity, 0))


def _get_risk_event_impact(highest_severity: str) -> Direction:
    """把最高严重程度转换为事件流影响方向，供前端使用红涨绿跌以外的风险色。"""

    if highest_severity in {MonitorSignalSeverity.WARNING.value, MonitorSignalSeverity.CRITICAL.value}:
        return Direction.WARNING
    return Direction.NEUTRAL


def _localize_signal_title(signal_type: str) -> str:
    """把量化信号代码转换为监控页面标题。"""

    title_map = {
        "momentum_strength": "20日动量增强",
        "momentum_weakness": "20日动量转弱",
        "trend_above_ema": "价格站上 EMA 趋势线",
        "trend_below_ema": "价格跌破 EMA 趋势线",
        "volatility_elevated": "20日年化波动率升高",
        "composite_score_high": "综合因子评分较高",
        "composite_score_low": "综合因子评分较低",
    }
    return title_map.get(signal_type, signal_type)
