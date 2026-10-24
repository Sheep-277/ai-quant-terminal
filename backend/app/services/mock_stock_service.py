from datetime import datetime, timedelta, timezone

from app.core.market import MarketCode, get_market_context
from app.providers.base import ProviderBar, ProviderStatus
from app.providers.factory import get_market_data_provider
from app.quant.indicators import calculate_macd, calculate_rsi
from app.quant.pipeline import QuantPipelineInput, QuantPipelineResult, run_quant_pipeline
from app.quant.signals import SignalDirection
from app.schemas.market import DataStatus, Direction
from app.schemas.stock import (
    CashFlowMetrics,
    FactorDataStatus,
    FundamentalDataStatus,
    KLineBar,
    KLineInterval,
    KLineSeries,
    MarketDataSourceStatus,
    SignalDataStatus,
    ProfitabilityMetrics,
    StockAssetType,
    StockProfile,
    StockFactorSnapshot,
    StockQuantSignal,
    StockQuote,
    StockResearchResponse,
    TechnicalIndicators,
    ValuationMetrics,
)
from app.services.kline_read_service import KLineReadSnapshot
from app.services.stock_factor_read_service import StockFactorReadSnapshot
from app.services.stock_fundamental_read_service import StockFundamentalReadSnapshot
from app.services.stock_read_service import StockReadSnapshot, build_provider_quote_data_source
from app.services.stock_signal_read_service import StockSignalReadSnapshot


def get_default_stock_symbol(market: MarketCode) -> str:
    """根据市场返回默认研究标的，供接口层在未传 symbol 时使用。"""

    return get_market_data_provider().get_default_stock_symbol(market)


def get_mock_stock_research(
    market: MarketCode,
    symbol: str | None = None,
    stock_read_snapshot: StockReadSnapshot | None = None,
    fundamental_read_snapshot: StockFundamentalReadSnapshot | None = None,
    factor_read_snapshot: StockFactorReadSnapshot | None = None,
    signal_read_snapshot: StockSignalReadSnapshot | None = None,
    kline_read_snapshot: KLineReadSnapshot | None = None,
) -> StockResearchResponse:
    """基于已有读取快照或当前 Provider 构造个股研究响应。"""

    context = get_market_context(market)
    requested_symbol = _normalize_requested_symbol(symbol) or get_default_stock_symbol(market)
    market_data_provider = get_market_data_provider()
    provider_status = market_data_provider.get_provider_status()
    asset_profile = market_data_provider.get_asset_profile(market, requested_symbol)
    # 快照已包含报价及来源，不能再次请求后将两次响应的状态混用。
    if stock_read_snapshot is not None:
        quote = stock_read_snapshot.quote
    else:
        provider_quote = market_data_provider.get_quote(market, requested_symbol)
        quote = StockQuote(
            price=provider_quote["price"],
            change=provider_quote["change"],
            change_percent=provider_quote["change_percent"],
            volume=provider_quote["volume"],
            turnover=provider_quote["turnover"],
            timestamp=provider_quote.get("timestamp"),
            data_status=provider_quote["data_status"],
        )
    # 缺失的报价时间保持为空，不能用读取时间冒充行情更新。
    timestamp = quote.timestamp
    financials = market_data_provider.get_financials(market, requested_symbol)
    valuation = fundamental_read_snapshot.valuation if fundamental_read_snapshot else _build_mock_valuation(financials)
    profitability = (
        fundamental_read_snapshot.profitability if fundamental_read_snapshot else _build_mock_profitability(financials)
    )
    cash_flow = fundamental_read_snapshot.cash_flow if fundamental_read_snapshot else _build_mock_cash_flow(financials)
    provider_bars = (
        []
        if kline_read_snapshot
        else market_data_provider.get_bars(market, requested_symbol, count=40)
    )
    research_notes = market_data_provider.get_research_notes(market, requested_symbol)
    fallback_symbol = research_notes["fallback_symbol"]
    displayed_provider_bars = provider_bars[-30:]
    kline_data_source = _build_kline_data_source(
        kline_read_snapshot,
        quote.data_status,
        provider_status,
        displayed_provider_bars,
    )
    kline = (
        kline_read_snapshot.kline
        if kline_read_snapshot
        else KLineSeries(
            interval=KLineInterval.ONE_DAY,
            data_status=kline_data_source.data_status,
            # 无日期的 Mock K 线单独生成样例日期，不将该日期回填为报价时间。
            bars=_build_kline_bars(timestamp or datetime.now(timezone.utc), displayed_provider_bars),
        )
    )
    # 技术指标、因子和信号统一使用页面实际展示的 K 线，避免来源与计算输入不一致。
    closes = [bar.close for bar in kline.bars]
    technical = _calculate_mock_technical_indicators(closes)
    quant_result = run_quant_pipeline(
        QuantPipelineInput(
            symbol=requested_symbol,
            closes=closes,
            roe=profitability.roe_ttm,
            roic=profitability.roic_ttm,
            gross_margin=profitability.gross_margin_ttm,
        )
    )
    quote_data_source = _build_quote_data_source(stock_read_snapshot, quote.data_status, provider_status)
    fundamental_data_status = _build_fundamental_data_status(fundamental_read_snapshot)
    data_warnings = _build_data_risk_flags(quote_data_source, kline_data_source, fundamental_data_status)
    if fallback_symbol:
        data_warnings = _build_fallback_risk_flags(requested_symbol, fallback_symbol) + data_warnings

    return StockResearchResponse(
        profile=stock_read_snapshot.profile
        if stock_read_snapshot
        else StockProfile(
            market=context.market,
            symbol=asset_profile["symbol"] if asset_profile["symbol"] == requested_symbol else requested_symbol,
            name=asset_profile["name"],
            asset_type=StockAssetType.COMMON_STOCK,
            exchange=asset_profile["exchange"],
            currency=context.currency,
            timezone=context.timezone,
            sector=asset_profile["sector"],
            industry=asset_profile["industry"],
        ),
        quote=quote,
        valuation=valuation,
        profitability=profitability,
        cash_flow=cash_flow,
        fundamental_data_status=fundamental_data_status,
        technical=TechnicalIndicators(
            rsi_14=technical["rsi_14"],
            macd=technical["macd"],
            macd_signal=technical["macd_signal"],
            macd_histogram=technical["macd_histogram"],
        ),
        technical_data_source=_build_quant_derived_data_source(
            kline_data_source,
            "技术指标由 Quant Pipeline 基于当前 K 线确定性计算",
        ),
        factor_snapshot=factor_read_snapshot.factor_snapshot
        if factor_read_snapshot
        else _build_factor_snapshot(quant_result),
        factor_data_status=_build_factor_data_status(factor_read_snapshot),
        quant_signals=signal_read_snapshot.quant_signals if signal_read_snapshot else _build_quant_signals(quant_result),
        signal_data_status=_build_signal_data_status(signal_read_snapshot, quant_result),
        quote_data_source=quote_data_source,
        kline=kline,
        kline_data_source=kline_data_source,
        risk_flags=data_warnings + _build_quant_risk_flags(quant_result),
        # 样例评语不属于当前计算证据；摘要仅保留计算值与标的回退说明。
        summary_points=_build_quant_summary_points(quant_result) + (
            _build_fallback_summary_points(requested_symbol, fallback_symbol)
            if fallback_symbol
            else []
        ),
        summary_data_source=_build_quant_derived_data_source(
            kline_data_source,
            "研究摘要由 Quant Pipeline 基于当前 K 线与基本面输入计算，基本面来源以对应分区标识为准",
        ),
        direction=_resolve_direction(quant_result),
    )


def _normalize_requested_symbol(symbol: str | None) -> str | None:
    """清洗调用方输入的 symbol；这里只做格式归一，不根据 symbol 推断市场。"""

    if symbol is None:
        return None

    normalized_symbol = symbol.strip().upper()
    return normalized_symbol or None


def _build_mock_valuation(financials: dict[str, float | None]) -> ValuationMetrics:
    """把 Provider Mock 财务数据转换为估值指标。"""

    return ValuationMetrics(
        pe_ttm=financials["pe_ttm"],
        pb=financials["pb"],
        ps_ttm=financials["ps_ttm"],
        pfcf_ttm=financials["pfcf_ttm"],
    )


def _build_mock_profitability(financials: dict[str, float | None]) -> ProfitabilityMetrics:
    """把 Provider Mock 财务数据转换为盈利能力指标。"""

    return ProfitabilityMetrics(
        roe_ttm=financials["roe_ttm"],
        roic_ttm=financials["roic_ttm"],
        gross_margin_ttm=financials["gross_margin_ttm"],
        operating_margin_ttm=financials["operating_margin_ttm"],
    )


def _build_mock_cash_flow(financials: dict[str, float | None]) -> CashFlowMetrics:
    """把 Provider Mock 财务数据转换为现金流指标。"""

    return CashFlowMetrics(
        fcf_ttm=financials["fcf_ttm"],
        operating_cash_flow_ttm=financials["operating_cash_flow_ttm"],
        capex_ttm=financials["capex_ttm"],
    )


def _build_fundamental_data_status(
    snapshot: StockFundamentalReadSnapshot | None,
) -> FundamentalDataStatus:
    """生成前端可展示的基本面数据来源和完整性状态。"""

    if snapshot is None:
        return FundamentalDataStatus(
            source="mock_provider",
            completeness="mock",
            available_sections=[],
            missing_sections=["valuation", "profitability", "cash_flow"],
        )

    return FundamentalDataStatus(
        source=snapshot.source,
        completeness=snapshot.completeness,
        available_sections=list(snapshot.available_sections),
        missing_sections=list(snapshot.missing_sections),
    )


def _build_factor_data_status(
    snapshot: StockFactorReadSnapshot | None,
) -> FactorDataStatus:
    """生成前端可展示的因子数据来源和完整性状态。"""

    if snapshot is None:
        return FactorDataStatus(
            source="quant_pipeline",
            completeness="computed",
            available_factors=[],
            missing_factors=[],
        )

    completeness = "complete" if not snapshot.missing_factors else "partial"
    return FactorDataStatus(
        source=snapshot.source,
        completeness=completeness,
        available_factors=list(snapshot.available_factors),
        missing_factors=list(snapshot.missing_factors),
    )


def _build_signal_data_status(
    snapshot: StockSignalReadSnapshot | None,
    quant_result: QuantPipelineResult,
) -> SignalDataStatus:
    """生成前端可展示的量化信号数据来源状态。"""

    if snapshot is None:
        return SignalDataStatus(
            source="quant_pipeline",
            completeness="computed",
            signal_count=len(quant_result.signals),
        )

    return SignalDataStatus(
        source=snapshot.source,
        completeness="complete",
        signal_count=len(snapshot.quant_signals),
    )


def _build_quote_data_source(
    snapshot: StockReadSnapshot | None,
    provider_data_status: DataStatus,
    provider_status: ProviderStatus,
) -> MarketDataSourceStatus:
    """生成最新行情的数据来源说明，供前端展示数据源标签。"""

    if snapshot is not None:
        if snapshot.quote_data_source is not None:
            return snapshot.quote_data_source
        return MarketDataSourceStatus(
            source=snapshot.source,
            detail="最新行情来自本地数据库 latest_quotes 表" if snapshot.source == "database" else "最新行情来自已有读取快照",
            fallback_active=snapshot.source == "mock_fallback",
            data_status=snapshot.quote.data_status,
        )

    return build_provider_quote_data_source(provider_data_status, provider_status)


def _build_kline_data_source(
    snapshot: KLineReadSnapshot | None,
    mock_data_status: DataStatus,
    provider_status: ProviderStatus,
    provider_bars: list[ProviderBar],
) -> MarketDataSourceStatus:
    """数据库取自身状态，真实 Provider 取逐条元数据，旧 Mock 沿用市场样例状态。"""

    if snapshot is not None:
        return MarketDataSourceStatus(
            source=snapshot.source,
            detail=snapshot.detail,
            fallback_active=False,
            data_status=snapshot.kline.data_status,
        )

    if provider_status["mode"] == "mock":
        return MarketDataSourceStatus(
            source="mock_provider",
            detail="K 线来自当前 Mock Provider",
            fallback_active=False,
            data_status=mock_data_status,
        )

    # 真实链路只相信本次展示的 K 线元数据，不能从报价成功或 Provider 配置推断成功。
    sources = {bar.get("source") for bar in provider_bars}
    statuses = {bar.get("data_status") for bar in provider_bars}
    fallback_active = bool(sources & {"mock_fallback", "mock_provider"})
    if not provider_bars or None in sources or None in statuses or DataStatus.UNAVAILABLE in statuses:
        data_status = DataStatus.UNAVAILABLE
    elif DataStatus.DELAYED in statuses:
        data_status = DataStatus.DELAYED
    else:
        data_status = DataStatus.REALTIME

    # 混合或缺失来源不冒充某一家供应商；存在样例回退时整体按回退标记。
    active_source = next(iter(sources)) if len(sources) == 1 and None not in sources else "provider"
    if fallback_active:
        detail = "K 线全部或部分来自 Mock Provider 回退"
    elif not provider_bars or None in sources or None in statuses:
        detail = "K 线来源或数据状态缺失，不能确认行情可用性"
    elif active_source == "demo_provider":
        detail = "K 线来自本地 DemoProvider 样例数据"
    else:
        detail = "K 线来源与状态取自当前展示的数据序列"
    return MarketDataSourceStatus(
        source="mock_provider" if fallback_active else active_source,
        detail=detail,
        fallback_active=fallback_active,
        data_status=data_status,
    )


def _build_quant_derived_data_source(
    kline_data_source: MarketDataSourceStatus,
    detail: str,
) -> MarketDataSourceStatus:
    """标记 Quant 派生结果，并继承计算所用 K 线的新鲜度与回退状态。"""

    return MarketDataSourceStatus(
        source="quant_pipeline",
        detail=detail,
        fallback_active=kline_data_source.fallback_active,
        data_status=kline_data_source.data_status,
    )


def _build_fallback_risk_flags(
    requested_symbol: str,
    fallback_symbol: str,
) -> list[str]:
    """为未覆盖的 Mock 标的追加风险提示，避免用户误解为真实标的数据。"""

    fallback_flag = f"{requested_symbol} 暂未覆盖 Mock 数据，当前基础数据回退到 {fallback_symbol}。"
    return [fallback_flag]


def _build_fallback_summary_points(
    requested_symbol: str,
    fallback_symbol: str,
) -> list[str]:
    """为未覆盖的 Mock 标的追加摘要提示，便于前端直接展示回退原因。"""

    fallback_point = f"当前 Mock 股票池尚未覆盖 {requested_symbol}，页面保留该代码但使用 {fallback_symbol} 的示例数据。"
    return [fallback_point]


def _build_kline_bars(
    end_timestamp: datetime,
    provider_bars: list[ProviderBar],
) -> list[KLineBar]:
    """把 Provider 标准 K 线转换为 API KLineBar，并用 offset 推导 Mock 时间。"""

    bars: list[KLineBar] = []
    for provider_bar in provider_bars:
        provider_timestamp = provider_bar.get("timestamp")
        timestamp = _parse_provider_bar_timestamp(provider_timestamp) if provider_timestamp else end_timestamp - timedelta(days=int(provider_bar["offset"]))
        bars.append(
            KLineBar(
                timestamp=timestamp,
                open=float(provider_bar["open"]),
                high=float(provider_bar["high"]),
                low=float(provider_bar["low"]),
                close=float(provider_bar["close"]),
                volume=int(provider_bar["volume"]),
            )
        )

    return bars


def _parse_provider_bar_timestamp(value: object) -> datetime:
    """读取真实 Provider K 线时间戳；无法解析时保持显式失败，避免日期轴展示假日期。"""

    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized_value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized_value)

    raise ValueError("provider bar timestamp must be datetime or ISO string")


def _calculate_mock_technical_indicators(
    closes: list[float],
) -> dict[str, float | None]:
    """基于当前收盘价计算技术指标，空行情保留空值而不是伪造指标。"""

    if not closes:
        return {"rsi_14": None, "macd": None, "macd_signal": None, "macd_histogram": None}

    rsi = calculate_rsi(closes, period=14)[-1]
    macd = calculate_macd(closes)

    return {
        "rsi_14": _round_optional(rsi),
        "macd": _round_optional(macd["macd"][-1]),
        "macd_signal": _round_optional(macd["signal"][-1]),
        "macd_histogram": _round_optional(macd["histogram"][-1]),
    }


def _round_optional(value: float | None) -> float | None:
    """统一处理技术指标小数位和缺失值。"""

    if value is None:
        return None

    return round(value, 4)


def _build_factor_snapshot(quant_result: QuantPipelineResult) -> StockFactorSnapshot:
    """把 Quant Pipeline 因子快照转换为个股研究 API schema。"""

    factors = quant_result.factors
    return StockFactorSnapshot(
        momentum_20d=_round_optional(factors.momentum_20d),
        trend_strength=_round_optional(factors.trend_strength),
        volatility_20d=_round_optional(factors.volatility_20d),
        quality_score=_round_optional(factors.quality_score),
        composite_score=_round_optional(factors.composite_score),
    )


def _build_quant_signals(quant_result: QuantPipelineResult) -> list[StockQuantSignal]:
    """把 Quant Pipeline 结构化信号转换为个股研究 API schema。"""

    return [
        StockQuantSignal(
            code=signal.code,
            title=_localize_signal_title(signal.code),
            direction=Direction(signal.direction.value),
            severity=signal.severity.value,
            score=signal.score,
            evidence=signal.evidence + _build_quant_coverage_warnings(quant_result),
        )
        for signal in quant_result.signals
    ]


def _localize_signal_title(code: str) -> str:
    """把量化信号码转换成个股研究页面可读的中文标题。"""

    title_map = {
        "momentum_strength": "20 日动量增强",
        "momentum_weakness": "20 日动量转弱",
        "trend_above_ema": "价格站上 EMA 趋势线",
        "trend_below_ema": "价格跌破 EMA 趋势线",
        "volatility_elevated": "20 日年化波动率升高",
        "composite_score_high": "综合因子评分较高",
        "composite_score_low": "综合因子评分较低",
    }
    return title_map.get(code, code)


def _build_quant_summary_points(
    quant_result: QuantPipelineResult,
) -> list[str]:
    """仅把当前 Quant 结果转换为摘要，不混入预置的趋势或估值评语。"""

    factors = quant_result.factors
    return [
        f"20 日动量为 {_format_percent(factors.momentum_20d)}，趋势强度为 {_format_percent(factors.trend_strength)}。",
        f"综合因子评分为 {_format_number(factors.composite_score)}，质量评分为 {_format_number(factors.quality_score)}。",
    ] + _build_quant_coverage_warnings(quant_result)


def _build_quant_coverage_warnings(quant_result: QuantPipelineResult) -> list[str]:
    """说明价格因子的缺失边界，不修改可用因子平均及信号阈值。"""

    factors = quant_result.factors
    missing = [
        label for label, value in (
            ("20 日动量", factors.momentum_20d),
            ("趋势强度", factors.trend_strength),
            ("20 日年化波动率", factors.volatility_20d),
        ) if value is None
    ]
    if not missing:
        return []
    return [
        f"价格因子样本不足或不可用（{'、'.join(missing)}）；"
        "综合因子评分仅基于当前可用因子计算，不代表完整趋势分析。"
    ]


def _build_quant_risk_flags(
    quant_result: QuantPipelineResult,
) -> list[str]:
    """仅展示当前 K 线计算中实际命中的负向或警告信号，并保留数值证据。"""

    return _build_quant_coverage_warnings(quant_result) + [
        f"{_localize_signal_title(signal.code)}：{'；'.join(signal.evidence)}"
        for signal in quant_result.signals
        if signal.direction in (SignalDirection.NEGATIVE, SignalDirection.WARNING)
    ]


def _build_data_risk_flags(
    quote_source: MarketDataSourceStatus,
    kline_source: MarketDataSourceStatus,
    fundamental_status: FundamentalDataStatus,
) -> list[str]:
    """由当前结构化来源状态生成数据限制，不沿用 Provider 的样例业务判断。"""

    flags: list[str] = []
    for label, source in (("最新行情", quote_source), ("K 线", kline_source)):
        if source.fallback_active:
            flags.append(f"{label}读取已回退到样例数据，不能作为真实交易依据。")
        elif source.source in ("mock_provider", "demo_provider"):
            flags.append(f"{label}为样例数据，不能作为真实交易依据。")
        elif source.data_status == DataStatus.UNAVAILABLE:
            flags.append(f"{label}数据不可用，不应据此作出交易判断。")
        elif source.data_status == DataStatus.DELAYED:
            flags.append(f"{label}存在延迟，不代表实时行情。")

    if fundamental_status.source == "mock_provider":
        flags.append("基本面为 Mock 样例，质量评分与综合因子评分包含样例输入。")
    elif fundamental_status.completeness == "partial":
        flags.append("基本面数据不完整，质量评分与综合因子评分应结合缺失项查看。")
    return flags


def _resolve_direction(
    quant_result: QuantPipelineResult,
) -> Direction:
    """根据当前量化信号推导方向，无信号时中性，不沿用样例判断。"""

    if not quant_result.signals:
        return Direction.NEUTRAL

    primary_signal = quant_result.signals[0]
    if primary_signal.direction == SignalDirection.POSITIVE:
        return Direction.POSITIVE
    if primary_signal.direction == SignalDirection.NEGATIVE:
        return Direction.NEGATIVE
    if primary_signal.direction == SignalDirection.WARNING:
        return Direction.NEGATIVE

    return Direction.NEUTRAL


def _format_percent(value: float | None) -> str:
    """把小数比例转换成中文摘要中使用的百分比文本。"""

    if value is None:
        return "暂无数据"

    return f"{value * 100:.2f}%"


def _format_number(value: float | None) -> str:
    """把可选数值转换成稳定的小数文本。"""

    if value is None:
        return "暂无数据"

    return f"{value:.2f}"
