from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_pre_trade_risk_check_route_returns_decision() -> None:
    # HTTP 层只负责接收请求和返回风险结论，具体计算由 risk_service 完成。
    response = client.post(
        "/api/v1/risk/pre-trade-check",
        json={
            "account_id": "paper-us-001",
            "market": "US",
            "symbol": "NVDA",
            "side": "buy",
            "quantity": 1,
            "limit_price": 100,
            "nav": 100_000,
            "cash": 30_000,
            "current_positions": [
                {
                    "market": "US",
                    "symbol": "MSFT",
                    "market_value": 20_000,
                    "side": "long",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "approved"
    assert payload["risk_checked"] is True
    assert payload["symbol"] == "NVDA"
    assert payload["projected_order_value"] == 100


def test_pre_trade_risk_check_route_rejects_live_trading_flag() -> None:
    # 真实交易意图应在 HTTP schema 校验阶段被拒绝。
    response = client.post(
        "/api/v1/risk/pre-trade-check",
        json={
            "account_id": "paper-us-001",
            "market": "US",
            "symbol": "NVDA",
            "side": "buy",
            "quantity": 1,
            "nav": 100_000,
            "cash": 30_000,
            "paper_trading": False,
        },
    )

    assert response.status_code == 422


def test_pre_trade_risk_check_route_rejects_cross_market_positions() -> None:
    # 风险检查不能混用不同市场的持仓口径。
    response = client.post(
        "/api/v1/risk/pre-trade-check",
        json={
            "account_id": "paper-us-001",
            "market": "US",
            "symbol": "NVDA",
            "side": "buy",
            "quantity": 1,
            "nav": 100_000,
            "cash": 30_000,
            "current_positions": [
                {
                    "market": "HK",
                    "symbol": "00700.HK",
                    "market_value": 20_000,
                }
            ],
        },
    )

    assert response.status_code == 422
