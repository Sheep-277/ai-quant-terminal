from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from app.api.v1.strategy import build_strategy_draft_response, build_strategy_lab_response, parse_strategy_text
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.seed import seed_development_data
from app.db.session import create_database_engine, get_engine, get_session_factory
from app.main import app
from app.schemas.strategy import (
    PositionRule,
    RebalanceFrequency,
    StrategyCondition,
    StrategyConditionField,
    StrategyConditionOperator,
    StrategyDraftCreateRequest,
    StrategyNaturalLanguageParseRequest,
    StrategyNaturalLanguageParseResponse,
    StrategyNaturalLanguageParseResult,
    StrategyParseSource,
    StrategyUniverse,
    UniverseType,
)
from app.services.strategy_nl_parser import parse_strategy_natural_language


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_strategy_database_reads_by_default(monkeypatch: pytest.MonkeyPatch):
    """大多数接口测试验证默认 Mock 行为，避免本地 .env 影响测试结果。"""

    monkeypatch.setenv("ENABLE_STRATEGY_DATABASE_READS", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_strategy_lab_defaults_to_us() -> None:
    # 不传 market 时应返回默认美股策略实验室数据。
    response = client.get("/api/v1/strategy/lab")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "US"
    assert payload["default_universe"]["market"] == "US"
    assert payload["default_universe"]["symbols"]
    assert payload["drafts"][0]["status"] == "draft"


def test_strategy_lab_supports_all_v1_markets() -> None:
    # Strategy Lab 必须和全局市场切换保持一致，覆盖 US / HK / CN。
    expected_universes = {
        "US": "NASDAQ 100",
        "HK": "Hang Seng TECH",
        "CN": "CSI 300",
    }

    for market, universe_name in expected_universes.items():
        response = client.get("/api/v1/strategy/lab", params={"market": market})

        assert response.status_code == 200
        payload = response.json()
        draft = payload["drafts"][0]
        assert payload["market"] == market
        assert payload["default_universe"]["name"] == universe_name
        assert draft["universe"]["market"] == market
        assert draft["entry_conditions"]
        assert draft["exit_conditions"]
        assert draft["position_rule"]["max_holdings"] > 0
        assert draft["risk_constraints"]


def test_strategy_lab_draft_requires_user_confirmation_before_backtest() -> None:
    # AI 生成策略只能先进入草案态，后续回测前必须由用户确认。
    response = client.get("/api/v1/strategy/lab", params={"market": "US"})

    assert response.status_code == 200
    payload = response.json()
    draft = payload["drafts"][0]
    assert draft["created_by"] == "agent"
    assert draft["status"] == "draft"
    assert draft["parameters"]["paper_trading_enabled"] is False
    assert draft["parameters"]["live_trading_enabled"] is False


def test_strategy_lab_draft_exposes_mock_provider_metadata() -> None:
    # 策略实验室需要显式暴露 Mock 数据来源，后续才能平滑切换到真实 Provider。
    response = client.get("/api/v1/strategy/lab", params={"market": "HK"})

    assert response.status_code == 200
    payload = response.json()
    parameters = payload["drafts"][0]["parameters"]
    assert parameters["data_mode"] == "mock"
    assert parameters["provider"] == "MockMarketDataProvider"
    assert parameters["provider_ready"] is False
    assert parameters["universe_source"] == "mock_index_universe"
    assert parameters["market"] == "HK"
    assert parameters["market_timezone"] == "Asia/Hong_Kong"
    assert parameters["live_trading_enabled"] is False


def test_strategy_lab_contains_engine_evaluation() -> None:
    # Strategy Lab 应返回确定性 Strategy Engine 的规则评估摘要，供后续回测确认使用。
    response = client.get("/api/v1/strategy/lab", params={"market": "US"})

    assert response.status_code == 200
    payload = response.json()
    evaluation = payload["drafts"][0]["parameters"]["strategy_evaluation"]
    assert evaluation["entry_matched"] is True
    assert evaluation["exit_matched"] is False
    assert evaluation["entry_evaluations"]
    assert evaluation["exit_evaluations"]
    assert all(item["reason"] == "matched" for item in evaluation["entry_evaluations"])


def test_strategy_lab_can_use_database_drafts(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    response = build_strategy_lab_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_STRATEGY_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.market == MarketCode.US
    assert len(response.drafts) == 1
    assert response.drafts[0].strategy_id == "mock-us-momentum-quality-v1"
    assert response.drafts[0].parameters["data_mode"] == "mock"


def test_strategy_lab_marks_fallback_when_database_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_database_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    monkeypatch.setattr("app.api.v1.strategy.get_strategy_read_snapshot", raise_database_error)

    response = build_strategy_lab_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_STRATEGY_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.market == MarketCode.US
    assert response.drafts
    assert response.drafts[0].parameters["data_status"] == "unavailable"
    assert response.drafts[0].parameters["fallback_active"] is True
    assert "RuntimeError" in response.drafts[0].parameters["fallback_reason"]
    assert "Mock Strategy Lab" in response.drafts[0].parameters["fallback_reason"]


def test_strategy_lab_rejects_unknown_market() -> None:
    # 未支持市场必须返回参数校验错误，避免策略隐式套用错误市场规则。
    response = client.get("/api/v1/strategy/lab", params={"market": "EU"})

    assert response.status_code == 422


def test_create_strategy_draft_returns_mock_draft() -> None:
    # 创建策略草案只返回 Mock 草案回执，不触发回测或模拟交易。
    request = _build_strategy_draft_request(symbols=[" nvda ", "aapl"])

    response = client.post("/api/v1/strategies", json=request.model_dump(mode="json"))

    assert response.status_code == 202
    payload = response.json()
    assert payload["strategy_id"] == "mock-us-momentum-quality-draft-draft"
    assert payload["status"] == "draft"
    assert payload["created_by"] == "user"
    assert payload["universe"]["symbols"] == ["NVDA", "AAPL"]
    assert payload["parameters"]["paper_trading_enabled"] is False
    assert payload["parameters"]["data_mode"] == "mock"
    assert payload["parameters"]["provider"] == "MockMarketDataProvider"
    assert payload["parameters"]["provider_ready"] is False
    assert payload["parameters"]["universe_source"] == "user_request"
    assert payload["parameters"]["live_trading_enabled"] is False


def test_create_strategy_draft_can_write_database(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    response = build_strategy_draft_response(
        _build_strategy_draft_request(symbols=["msft", "nvda"]),
        Settings(
            DATABASE_URL=database_url,
            ENABLE_STRATEGY_DATABASE_WRITES=True,
            _env_file=None,
        ),
    )

    assert response.strategy_id == "mock-us-momentum-quality-draft-draft"
    assert response.universe.symbols == ["MSFT", "NVDA"]
    assert response.parameters["storage_source"] == "database"

    lab_response = build_strategy_lab_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_STRATEGY_DATABASE_READS=True,
            _env_file=None,
        ),
    )
    strategy_ids = {draft.strategy_id for draft in lab_response.drafts}
    assert "mock-us-momentum-quality-draft-draft" in strategy_ids


def test_create_strategy_draft_marks_fallback_when_database_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_database_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    monkeypatch.setattr("app.api.v1.strategy.create_strategy_draft_record", raise_database_error)

    response = build_strategy_draft_response(
        _build_strategy_draft_request(symbols=["msft", "nvda"]),
        Settings(
            DATABASE_URL=database_url,
            ENABLE_STRATEGY_DATABASE_WRITES=True,
            _env_file=None,
        ),
    )

    assert response.strategy_id == "mock-us-momentum-quality-draft-draft"
    assert response.universe.symbols == ["MSFT", "NVDA"]
    assert response.parameters["data_status"] == "unavailable"
    assert response.parameters["fallback_active"] is True
    assert response.parameters["storage_source"] == "mock_fallback"
    assert "RuntimeError" in response.parameters["fallback_reason"]
    assert "未持久化 Mock 草案" in response.parameters["fallback_reason"]


def test_create_strategy_draft_rejects_market_mismatch() -> None:
    # HTTP 层应复用 schema 校验，市场不一致时直接返回 422。
    request = _build_strategy_draft_request().model_dump(mode="json")
    request["universe"]["market"] = "HK"

    response = client.post("/api/v1/strategies", json=request)

    assert response.status_code == 422


def test_strategy_draft_create_request_normalizes_symbols() -> None:
    # 创建策略草案前先规范化证券代码，后续 Provider Adapter 才能稳定转换。
    request = _build_strategy_draft_request(symbols=[" nvda ", "aapl"])

    assert request.universe.symbols == ["NVDA", "AAPL"]


def test_strategy_draft_create_request_rejects_market_mismatch() -> None:
    # 策略请求和股票池必须属于同一市场，不能用美股请求跑港股股票池。
    with pytest.raises(ValidationError, match="universe.market must match request market"):
        _build_strategy_draft_request(market="US", universe_market="HK")


def test_strategy_condition_between_requires_valid_upper_value() -> None:
    # 区间条件必须同时有下界和更大的上界，否则策略规则没有确定含义。
    with pytest.raises(ValidationError, match="upper_value is required"):
        StrategyCondition(
            field=StrategyConditionField.MOMENTUM_20D,
            operator=StrategyConditionOperator.BETWEEN,
            value=0.02,
            upper_value=None,
            description="20 日动量区间",
        )

    with pytest.raises(ValidationError, match="upper_value must be greater"):
        StrategyCondition(
            field=StrategyConditionField.MOMENTUM_20D,
            operator=StrategyConditionOperator.BETWEEN,
            value=0.16,
            upper_value=0.02,
            description="20 日动量区间",
        )


def test_strategy_natural_language_parse_request_normalizes_text() -> None:
    # 自然语言解析入口先清理用户输入，后续解析器只处理有效文本。
    request = StrategyNaturalLanguageParseRequest(
        market="CN",
        text="  ROE 大于 15%，20 日动量在 2% 到 16% 之间  ",
    )

    assert request.text == "ROE 大于 15%，20 日动量在 2% 到 16% 之间"
    assert request.require_user_confirmation is True


def test_strategy_natural_language_parse_request_rejects_market_mismatch() -> None:
    # 自然语言解析也必须显式绑定市场，不能用 A 股请求解析港股股票池。
    with pytest.raises(ValidationError, match="universe.market must match request market"):
        StrategyNaturalLanguageParseRequest(
            market="CN",
            text="筛选腾讯和美团中 ROE 较高的标的",
            universe=StrategyUniverse(
                market="HK",
                universe_type=UniverseType.CUSTOM,
                name="HK Watchlist",
                symbols=["00700.HK", "03690.HK"],
            ),
        )


def test_strategy_natural_language_parse_result_rejects_empty_output() -> None:
    # 解析失败不能伪装成有效结果，前端应展示错误或要求用户改写。
    with pytest.raises(ValidationError, match="at least one structured rule"):
        StrategyNaturalLanguageParseResult()


def test_strategy_natural_language_parse_response_keeps_user_confirmation_boundary() -> None:
    # 解析响应只给出可确认的结构化条件，不会绕过用户直接创建策略。
    response = StrategyNaturalLanguageParseResponse(
        market="US",
        source=StrategyParseSource.RULE_BASED,
        confidence=0.82,
        raw_text="20 日动量大于 10%，RSI 高于 75 时退出",
        result=StrategyNaturalLanguageParseResult(
            entry_conditions=[
                StrategyCondition(
                    field=StrategyConditionField.MOMENTUM_20D,
                    operator=StrategyConditionOperator.GREATER_THAN,
                    value=0.1,
                    description="20 日动量大于 10%",
                )
            ],
            exit_conditions=[
                StrategyCondition(
                    field=StrategyConditionField.RSI_14,
                    operator=StrategyConditionOperator.GREATER_THAN,
                    value=75,
                    description="RSI 高于 75 时退出",
                )
            ],
        ),
    )

    assert response.source == StrategyParseSource.RULE_BASED
    assert response.requires_user_confirmation is True
    assert response.result.entry_conditions[0].field == StrategyConditionField.MOMENTUM_20D


def test_strategy_natural_language_parser_extracts_entry_and_exit_conditions() -> None:
    # 规则解析器先覆盖 Strategy Lab 当前支持的常见中文指标表达。
    response = parse_strategy_natural_language(
        StrategyNaturalLanguageParseRequest(
            market="US",
            text="ROE 大于 15%，20 日动量在 2% 到 16% 之间，RSI 高于 75 时退出",
        )
    )

    assert response.source == StrategyParseSource.RULE_BASED
    assert response.confidence == 1
    assert [condition.field for condition in response.result.entry_conditions] == [
        StrategyConditionField.ROE,
        StrategyConditionField.MOMENTUM_20D,
    ]
    assert response.result.entry_conditions[0].value == 0.15
    assert response.result.entry_conditions[1].operator == StrategyConditionOperator.BETWEEN
    assert response.result.entry_conditions[1].value == 0.02
    assert response.result.entry_conditions[1].upper_value == 0.16
    assert response.result.exit_conditions[0].field == StrategyConditionField.RSI_14
    assert response.result.exit_conditions[0].value == 75


def test_strategy_natural_language_parser_extracts_pe_volume_and_risk_rules() -> None:
    # 估值、量比和风险约束会分别进入入场条件和 risk_constraints。
    response = parse_strategy_natural_language(
        StrategyNaturalLanguageParseRequest(
            market="CN",
            text="PE TTM 小于 35，成交量比率大于 1.5，最大回撤不超过 16%，止损 7%",
        )
    )

    assert response.result.entry_conditions[0].field == StrategyConditionField.PE_TTM
    assert response.result.entry_conditions[0].operator == StrategyConditionOperator.LESS_THAN
    assert response.result.entry_conditions[0].value == 35
    assert response.result.entry_conditions[1].field == StrategyConditionField.VOLUME_RATIO
    assert response.result.entry_conditions[1].value == 1.5
    assert response.result.risk_constraints[0].max_drawdown == 0.16
    assert response.result.risk_constraints[1].stop_loss == 0.07


def test_strategy_natural_language_parser_supports_english_demo_text() -> None:
    # 英文界面的示例文本也应进入同一套结构化规则，避免 en-US 演示失败。
    response = parse_strategy_natural_language(
        StrategyNaturalLanguageParseRequest(
            market="US",
            text=(
                "ROE above 18%, 20D momentum between 2% and 16%, "
                "exit when RSI is above 78, maximum drawdown under 16%, stop loss 7%"
            ),
        )
    )

    assert response.confidence == 1
    assert [condition.field for condition in response.result.entry_conditions] == [
        StrategyConditionField.ROE,
        StrategyConditionField.MOMENTUM_20D,
    ]
    assert response.result.entry_conditions[0].operator == StrategyConditionOperator.GREATER_THAN
    assert response.result.entry_conditions[0].value == 0.18
    assert response.result.entry_conditions[1].operator == StrategyConditionOperator.BETWEEN
    assert response.result.entry_conditions[1].value == 0.02
    assert response.result.entry_conditions[1].upper_value == 0.16
    assert response.result.exit_conditions[0].field == StrategyConditionField.RSI_14
    assert response.result.exit_conditions[0].value == 78
    assert response.result.risk_constraints[0].max_drawdown == 0.16
    assert response.result.risk_constraints[1].stop_loss == 0.07


def test_strategy_natural_language_parser_reports_unrecognized_text() -> None:
    # 混合输入中无法识别的片段保留为 warning，便于前端提醒用户确认。
    response = parse_strategy_natural_language(
        StrategyNaturalLanguageParseRequest(
            market="HK",
            text="ROE 不低于 12%，偏好品牌影响力强的公司",
        )
    )

    assert response.confidence == 0.5
    assert response.result.entry_conditions[0].operator == StrategyConditionOperator.GREATER_THAN_OR_EQUAL
    assert response.result.warnings == ["未识别条件：偏好品牌影响力强的公司"]


def test_strategy_natural_language_parser_rejects_fully_unrecognized_text() -> None:
    # 完全无法结构化的输入不能返回空结果。
    with pytest.raises(ValueError, match="could not parse any strategy condition"):
        parse_strategy_natural_language(
            StrategyNaturalLanguageParseRequest(
                market="US",
                text="找一些看起来不错的公司",
            )
        )


def test_parse_strategy_text_route_returns_structured_preview() -> None:
    # 路由层只返回解析预览，不保存草案，也不进入回测。
    response = parse_strategy_text(
        StrategyNaturalLanguageParseRequest(
            market="CN",
            text="ROE 大于 18%，20 日动量在 2% 到 16% 之间，RSI 高于 78 时退出",
        )
    )

    assert response.market == MarketCode.CN
    assert response.source == StrategyParseSource.RULE_BASED
    assert response.requires_user_confirmation is True
    assert response.result.entry_conditions[0].field == StrategyConditionField.ROE
    assert response.result.entry_conditions[0].value == 0.18
    assert response.result.entry_conditions[1].operator == StrategyConditionOperator.BETWEEN
    assert response.result.exit_conditions[0].field == StrategyConditionField.RSI_14


def test_parse_strategy_text_route_rejects_unrecognized_text() -> None:
    # 解析失败应返回 422，避免前端把后端异常当作空策略。
    with pytest.raises(HTTPException) as exc_info:
        parse_strategy_text(
            StrategyNaturalLanguageParseRequest(
                market="US",
                text="找一些看起来不错的公司",
            )
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "strategy_natural_language_parse_failed"


def _build_strategy_draft_request(
    *,
    market: str = "US",
    universe_market: str = "US",
    symbols: list[str] | None = None,
) -> StrategyDraftCreateRequest:
    """构造最小合法策略草案请求，便于测试不同校验边界。"""

    return StrategyDraftCreateRequest(
        market=market,
        name="Momentum Quality Draft",
        description="筛选动量和质量都较强的标的。",
        universe=StrategyUniverse(
            market=universe_market,
            universe_type=UniverseType.CUSTOM,
            name="User Watchlist",
            symbols=symbols or ["NVDA", "AAPL"],
        ),
        entry_conditions=[
            StrategyCondition(
                field=StrategyConditionField.MOMENTUM_20D,
                operator=StrategyConditionOperator.GREATER_THAN,
                value=0.1,
                description="20 日动量大于 10%",
            )
        ],
        exit_conditions=[
            StrategyCondition(
                field=StrategyConditionField.RSI_14,
                operator=StrategyConditionOperator.GREATER_THAN,
                value=75,
                description="RSI 过热时退出",
            )
        ],
        position_rule=PositionRule(max_holdings=10, max_position_weight=0.1),
        rebalance_frequency=RebalanceFrequency.WEEKLY,
    )
