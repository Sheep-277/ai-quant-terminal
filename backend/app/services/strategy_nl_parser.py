import re

from app.schemas.strategy import (
    RiskConstraint,
    StrategyCondition,
    StrategyConditionField,
    StrategyConditionOperator,
    StrategyNaturalLanguageParseRequest,
    StrategyNaturalLanguageParseResponse,
    StrategyNaturalLanguageParseResult,
    StrategyParseSource,
)


PERCENT_FIELDS = {
    StrategyConditionField.MOMENTUM_20D,
    StrategyConditionField.ROE,
}

FIELD_PATTERNS: tuple[tuple[re.Pattern[str], StrategyConditionField], ...] = (
    (re.compile(r"(20\s*日动量|20d\s*momentum|momentum_20d|动量)", re.IGNORECASE), StrategyConditionField.MOMENTUM_20D),
    (re.compile(r"(roe|净资产收益率)", re.IGNORECASE), StrategyConditionField.ROE),
    (re.compile(r"(成交量比率|量比|volume\s*ratio)", re.IGNORECASE), StrategyConditionField.VOLUME_RATIO),
    (re.compile(r"(rsi|相对强弱)", re.IGNORECASE), StrategyConditionField.RSI_14),
    (re.compile(r"(pe\s*ttm|市盈率|pe)", re.IGNORECASE), StrategyConditionField.PE_TTM),
)

BETWEEN_PATTERN = re.compile(
    r"(?:在|介于|between)\s*([-+]?\d+(?:\.\d+)?)\s*(%)?\s*(?:到|至|和|-|and)\s*([-+]?\d+(?:\.\d+)?)\s*(%)?\s*(?:之间|区间)?",
    re.IGNORECASE,
)

COMPARISON_PATTERNS: tuple[tuple[re.Pattern[str], StrategyConditionOperator], ...] = (
    (re.compile(r"(不低于|大于等于|至少|>=|at\s+least|not\s+below)", re.IGNORECASE), StrategyConditionOperator.GREATER_THAN_OR_EQUAL),
    (re.compile(r"(不高于|小于等于|至多|<=|at\s+most|not\s+above)", re.IGNORECASE), StrategyConditionOperator.LESS_THAN_OR_EQUAL),
    (re.compile(r"(大于|高于|超过|>|above|greater\s+than|higher\s+than)", re.IGNORECASE), StrategyConditionOperator.GREATER_THAN),
    (re.compile(r"(小于|低于|跌破|<|below|less\s+than|under)", re.IGNORECASE), StrategyConditionOperator.LESS_THAN),
)

NUMBER_PATTERN = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*(%)?")
EXIT_KEYWORDS = ("退出", "卖出", "止盈", "止损", "离场", "exit", "sell", "stop loss", "take profit")
SENTENCE_SPLIT_PATTERN = re.compile(r"[，,。；;\n]+")


def parse_strategy_natural_language(request: StrategyNaturalLanguageParseRequest) -> StrategyNaturalLanguageParseResponse:
    """把用户输入的中文策略描述解析为可编辑条件，当前只走确定性规则路径。"""

    entry_conditions: list[StrategyCondition] = []
    exit_conditions: list[StrategyCondition] = []
    risk_constraints: list[RiskConstraint] = []
    warnings: list[str] = []

    for sentence in _split_sentences(request.text):
        risk_constraint = _parse_risk_constraint(sentence)
        if risk_constraint is not None:
            risk_constraints.append(risk_constraint)
            continue

        condition = _parse_condition(sentence)
        if condition is None:
            warnings.append(f"未识别条件：{sentence}")
            continue

        if _is_exit_sentence(sentence):
            exit_conditions.append(condition)
        else:
            entry_conditions.append(condition)

    if not entry_conditions and not exit_conditions and not risk_constraints:
        raise ValueError("could not parse any strategy condition from text")

    parsed_count = len(entry_conditions) + len(exit_conditions) + len(risk_constraints)
    confidence = parsed_count / (parsed_count + len(warnings))

    return StrategyNaturalLanguageParseResponse(
        market=request.market,
        source=StrategyParseSource.RULE_BASED,
        confidence=round(confidence, 2),
        requires_user_confirmation=request.require_user_confirmation,
        raw_text=request.text,
        result=StrategyNaturalLanguageParseResult(
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            risk_constraints=risk_constraints,
            warnings=warnings,
        ),
    )


def _split_sentences(text: str) -> list[str]:
    """按中文和英文标点拆分策略描述，保留非空片段。"""

    return [sentence.strip() for sentence in SENTENCE_SPLIT_PATTERN.split(text) if sentence.strip()]


def _parse_condition(sentence: str) -> StrategyCondition | None:
    """解析单句条件，识别字段、比较符和数值。"""

    field = _detect_field(sentence)
    if field is None:
        return None

    between_match = BETWEEN_PATTERN.search(sentence)
    if between_match is not None:
        value = _normalize_value(field, float(between_match.group(1)), between_match.group(2))
        upper_value = _normalize_value(field, float(between_match.group(3)), between_match.group(4))
        return StrategyCondition(
            field=field,
            operator=StrategyConditionOperator.BETWEEN,
            value=value,
            upper_value=upper_value,
            description=sentence,
        )

    operator = _detect_operator(sentence)
    if operator is None:
        return None

    number_match = NUMBER_PATTERN.search(sentence)
    if number_match is None:
        return None

    return StrategyCondition(
        field=field,
        operator=operator,
        value=_normalize_value(field, float(number_match.group(1)), number_match.group(2)),
        description=sentence,
    )


def _parse_risk_constraint(sentence: str) -> RiskConstraint | None:
    """解析常见风险约束，例如最大回撤和止损。"""

    normalized_sentence = sentence.lower()
    if not any(
        keyword in normalized_sentence
        for keyword in ("最大回撤", "回撤", "止损", "流动性", "maximum drawdown", "drawdown", "stop loss", "liquidity")
    ):
        return None

    number_match = NUMBER_PATTERN.search(sentence)
    if number_match is None:
        return None

    value = float(number_match.group(1))
    has_percent = number_match.group(2) == "%"

    if "止损" in normalized_sentence or "stop loss" in normalized_sentence:
        return RiskConstraint(stop_loss=_normalize_percent_like_value(value, has_percent))
    if "流动性" in normalized_sentence or "liquidity" in normalized_sentence:
        return RiskConstraint(min_liquidity=value)
    return RiskConstraint(max_drawdown=_normalize_percent_like_value(value, has_percent))


def _detect_field(sentence: str) -> StrategyConditionField | None:
    """从句子中识别当前 Strategy Lab 支持的指标字段。"""

    for pattern, field in FIELD_PATTERNS:
        if pattern.search(sentence):
            return field
    return None


def _detect_operator(sentence: str) -> StrategyConditionOperator | None:
    """从句子中识别比较符。"""

    for pattern, operator in COMPARISON_PATTERNS:
        if pattern.search(sentence):
            return operator
    return None


def _normalize_value(field: StrategyConditionField, value: float, percent_mark: str | None) -> float:
    """把中文百分比输入转换为内部数值，比例型字段默认按百分比理解。"""

    if percent_mark == "%" or field in PERCENT_FIELDS:
        return value / 100
    return value


def _normalize_percent_like_value(value: float, has_percent: bool) -> float:
    """风险约束常用百分比表达，带百分号或大于 1 时转为小数。"""

    if has_percent or value > 1:
        return value / 100
    return value


def _is_exit_sentence(sentence: str) -> bool:
    """识别该条件是否属于出场规则。"""

    normalized_sentence = sentence.lower()
    return any(keyword in normalized_sentence for keyword in EXIT_KEYWORDS)
