from fastapi import APIRouter

from app.schemas.risk import PreTradeRiskCheckRequest, PreTradeRiskCheckResponse
from app.services.risk_service import pre_trade_check


router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/pre-trade-check", response_model=PreTradeRiskCheckResponse)
def create_pre_trade_risk_check(
    request: PreTradeRiskCheckRequest,
) -> PreTradeRiskCheckResponse:
    """执行下单前风险检查，只返回风险结论，不创建订单。"""

    return pre_trade_check(request=request)
