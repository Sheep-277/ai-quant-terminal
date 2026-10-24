from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.market import MarketCode, get_market_context
from app.schemas.market import Direction
from app.schemas.monitor import (
    MonitorEvent,
    MonitorProvenance,
    MonitorResponse,
    MonitorSignal,
    MonitorSignalSeverity,
    MonitorSource,
    MonitorStreamHealth,
    MonitorStreamStatus,
)
from app.tools.registry import call_tool


MONITOR_FIXTURES = {
    MarketCode.US: {
        "latency_ms": 82,
        "reconnect_attempts": 0,
        "quant": {
            "symbol": "NVDA",
            "closes": [float(value) for value in range(100, 131)],
            "fundamentals": {"roe": 0.18, "roic": 0.12, "gross_margin": 0.42},
            "entry_conditions": [{"field": "momentum_20d", "operator": "gt", "value": 0.08}],
        },
        "signals": [
            ("AMD", "半导体板块波动率放大", Direction.WARNING, MonitorSignalSeverity.INFO, 0.71, ["sector volatility percentile > 80"]),
        ],
        "events": [
            (MonitorSource.AI_PATH, "芯片出口新闻聚类", "AI PATH 已把新闻标题与半导体板块波动进行关联。", Direction.WARNING, 0.78),
            (MonitorSource.RISK_ENGINE, "组合半导体敞口偏高", "Risk Engine 标记半导体敞口接近当前模拟组合上限。", Direction.WARNING, 0.84),
        ],
    },
    MarketCode.HK: {
        "latency_ms": 180,
        "reconnect_attempts": 1,
        "quant": {
            "symbol": "00700.HK",
            "closes": [float(value) for value in range(80, 111)],
            "fundamentals": {"roe": 0.14, "roic": 0.1, "gross_margin": 0.36},
            "entry_conditions": [{"field": "momentum_20d", "operator": "gt", "value": 0.06}],
        },
        "signals": [
            ("03690.HK", "平台经济标的回撤扩大", Direction.NEGATIVE, MonitorSignalSeverity.WARNING, 0.69, ["drawdown > 5%"]),
        ],
        "events": [
            (MonitorSource.AI_PATH, "互联网新闻情绪改善", "AI PATH 识别到平台经济相关新闻情绪边际改善。", Direction.POSITIVE, 0.72),
        ],
    },
    MarketCode.CN: {
        "latency_ms": 145,
        "reconnect_attempts": 0,
        "quant": {
            "symbol": "300750.SZ",
            "closes": [
                100.0,
                101.0,
                99.0,
                104.0,
                96.0,
                106.0,
                94.0,
                108.0,
                92.0,
                110.0,
                90.0,
                112.0,
                88.0,
                114.0,
                86.0,
                116.0,
                84.0,
                118.0,
                82.0,
                120.0,
                80.0,
                122.0,
                78.0,
                124.0,
                76.0,
                126.0,
                74.0,
                128.0,
                72.0,
                130.0,
                70.0,
            ],
            "fundamentals": {"roe": 0.12, "roic": 0.08, "gross_margin": 0.28},
            "entry_conditions": [{"field": "momentum_20d", "operator": "gt", "value": 0.05}],
            "exit_conditions": [{"field": "volatility_20d", "operator": "gt", "value": 0.45}],
        },
        "signals": [
            ("600519.SH", "白酒权重股短期动量转弱", Direction.NEGATIVE, MonitorSignalSeverity.WARNING, 0.66, ["momentum_20d < 0"]),
        ],
        "events": [
            (MonitorSource.FAST_PATH, "涨停股票已排除", "FAST PATH 根据 A 股交易规则排除了不可买入的涨停标的。", Direction.WARNING, 1.0),
            (MonitorSource.AI_PATH, "政策新闻映射到新能源链", "AI PATH 把政策新闻映射到新能源车供应链观察池。", Direction.POSITIVE, 0.69),
        ],
    },
}


def get_mock_monitor_stream(market: MarketCode) -> MonitorResponse:
    """生成实时监控 Mock 响应，当前不连接真实行情流或消息队列。"""

    context = get_market_context(market)
    fixture = MONITOR_FIXTURES[market]
    timestamp = datetime.now(timezone.utc)

    return MonitorResponse(
        market=market,
        timestamp=timestamp,
        timezone=context.timezone,
        currency=context.currency,
        provenance=MonitorProvenance(
            transport="rest_polling",
            stream_source="mock",
            signal_source="mock",
            event_source="mock",
            heartbeat_basis="mock_clock",
        ),
        stream=MonitorStreamHealth(
            status=MonitorStreamStatus.CONNECTED,
            latency_ms=fixture["latency_ms"],
            last_heartbeat_at=timestamp - timedelta(seconds=2),
            reconnect_attempts=fixture["reconnect_attempts"],
            data_status="mock",
        ),
        signals=_build_signals(
            timestamp=timestamp,
            market=market,
            quant=fixture["quant"],
            rows=fixture["signals"],
        ),
        events=_build_events(
            timestamp=timestamp,
            market=market,
            rows=fixture["events"],
        ),
    )


def _build_signals(
    timestamp: datetime,
    market: MarketCode,
    quant: dict[str, Any],
    rows: list[tuple[str, str, Direction, MonitorSignalSeverity, float, list[str]]],
) -> list[MonitorSignal]:
    """把紧凑 fixture 转成 FAST PATH 结构化信号。"""

    quant_signal = _build_quant_signal(timestamp=timestamp, market=market, quant=quant)
    fixture_signals = [
        MonitorSignal(
            signal_id=f"signal-{market.value.lower()}-{index + 2:03d}",
            market=market,
            symbol=symbol,
            title=title,
            direction=direction,
            severity=severity,
            score=score,
            triggered_at=timestamp - timedelta(seconds=(index + 1) * 18),
            source="mock_fixture",
            data_origin="mock",
            evidence=evidence,
        )
        for index, (symbol, title, direction, severity, score, evidence) in enumerate(rows)
    ]
    return [quant_signal, *fixture_signals]


def _build_quant_signal(
    timestamp: datetime,
    market: MarketCode,
    quant: dict[str, Any],
) -> MonitorSignal:
    """通过 Tool Registry 生成首条 FAST PATH 量化信号。"""

    output = call_tool("run_quant_pipeline", quant)
    signal = output["signals"][0]
    return MonitorSignal(
        signal_id=f"signal-{market.value.lower()}-001",
        market=market,
        symbol=output["symbol"],
        title=_localize_quant_signal_title(signal["code"]),
        direction=Direction(signal["direction"]),
        severity=MonitorSignalSeverity(signal["severity"]),
        score=signal["score"],
        triggered_at=timestamp - timedelta(seconds=18),
        source="mock_quant_pipeline",
        data_origin="mock",
        evidence=[*signal["evidence"], "source=ToolRegistry.run_quant_pipeline"],
    )


def _localize_quant_signal_title(code: str) -> str:
    """把 Quant Pipeline 信号代码转换为前端可读中文标题。"""

    title_map = {
        "momentum_strength": "20日动量增强",
        "momentum_weakness": "20日动量转弱",
        "trend_above_ema": "价格站上 EMA 趋势线",
        "trend_below_ema": "价格跌破 EMA 趋势线",
        "volatility_elevated": "20日年化波动率升高",
        "composite_score_high": "综合因子评分较高",
        "composite_score_low": "综合因子评分较低",
    }
    return title_map.get(code, code)


def _build_events(
    timestamp: datetime,
    market: MarketCode,
    rows: list[tuple[MonitorSource, str, str, Direction, float]],
) -> list[MonitorEvent]:
    """把紧凑 fixture 转成标准化事件，并自动补充数据状态提示。"""

    events = [
        MonitorEvent(
            event_id=f"event-{market.value.lower()}-{index + 1:03d}",
            market=market,
            source=source,
            title=title,
            summary=_build_event_summary(impact=impact, summary=summary),
            impact=impact,
            confidence=confidence,
            created_at=timestamp - timedelta(minutes=index + 1),
        )
        for index, (source, title, summary, impact, confidence) in enumerate(rows)
    ]

    events.append(
        MonitorEvent(
            event_id=f"event-{market.value.lower()}-{len(events) + 1:03d}",
            market=market,
            source=MonitorSource.PROVIDER,
            title="监控连接状态为模拟数据",
            summary="信息：连接状态、延迟和重连次数来自 Mock Monitor，不代表真实行情连接；信号来源以结构化来源标记和逐条证据为准。",
            impact=Direction.NEUTRAL,
            confidence=1.0,
            created_at=timestamp,
        )
    )

    return events


def _build_event_summary(impact: Direction, summary: str) -> str:
    """根据事件影响方向统一增加严重程度前缀。"""

    severity_label = {
        Direction.POSITIVE: "信息",
        Direction.NEUTRAL: "信息",
        Direction.WARNING: "警告",
        Direction.NEGATIVE: "警告",
    }[impact]
    return f"{severity_label}：{summary}"
