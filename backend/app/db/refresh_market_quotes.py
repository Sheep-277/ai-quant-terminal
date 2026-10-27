import argparse
from collections.abc import Sequence
import json

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.core.market import MarketCode
from app.db.session import get_session_factory
from app.providers.factory import get_market_data_provider
from app.services.market_quote_refresh_service import refresh_market_quotes


def main(argv: Sequence[str] | None = None) -> int:
    """默认预览；显式 --apply 才在一个事务中提交成功报价，不执行 init 或 seed。"""
    parser = argparse.ArgumentParser(description="Refresh existing active stocks from the configured real provider.")
    parser.add_argument("--market", choices=[market.value for market in MarketCode], required=True)
    parser.add_argument("--apply", action="store_true", help="Commit valid quotes; default is read-only preview.")
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
        provider = get_market_data_provider(settings)
        with get_session_factory(settings.database_url)() as session:
            # Service 不吞掉数据库错误；任意落库失败会回滚整批，不输出虚假的成功回执。
            with session.begin():
                report = refresh_market_quotes(session, MarketCode(args.market), provider, dry_run=not args.apply)
    except (ProviderError, SQLAlchemyError, ValueError, OSError) as exc:
        print(json.dumps({"market": args.market, "error_type": type(exc).__name__}, ensure_ascii=True))
        return 1
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if not report["items"] or any(item["status"] in ("skipped", "failed") for item in report["items"]):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
