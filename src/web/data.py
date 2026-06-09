"""
Streamlit 資料存取層 — 直接使用 Python service layer（不經過 HTTP）
"""
import sys
from pathlib import Path

# 確保專案根目錄在 sys.path
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from typing import Optional

from sqlalchemy.orm import sessionmaker as _sessionmaker
from src.models.database import create_all_tables, get_db_session, get_engine
from src.models.enums import AssetType, Exchange
from src.repositories.asset_repo import AssetRepository
from src.repositories.transaction_repo import TransactionRepository
from src.services.calculation_service import CalculationService, PortfolioSummary
from src.services.portfolio_service import PortfolioService
from src.data_providers.price_manager import PriceManager
from src.utils.config import get_settings
from src.utils.exceptions import AssetNotFoundError

import streamlit as st


@st.cache_resource
def _get_session_factory():
    settings = get_settings()
    engine = get_engine(settings.db_path)
    create_all_tables(engine)
    return _sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_portfolio_summary(include_closed: bool = False, no_price: bool = False) -> PortfolioSummary:
    sf = _get_session_factory()
    settings = get_settings()

    with get_db_session(sf) as session:
        repo = AssetRepository(session)
        assets = repo.get_all() if include_closed else repo.get_all_active()

        prices = {}
        if not no_price and assets:
            mgr = PriceManager(timeout=settings.api_timeout, session_factory=sf)
            tickers = [a.ticker for a in assets]
            try:
                prices = mgr.get_prices_batch(tickers)
            except Exception:
                pass

        calc = CalculationService()
        return calc.build_portfolio_summary(assets, prices, active_only=not include_closed)


def get_transactions(ticker: Optional[str] = None, limit: int = 100):
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = TransactionRepository(session)
        if ticker:
            return repo.get_by_ticker(ticker, limit=limit)
        return repo.get_all()[:limit]


def do_buy(ticker, name, asset_type_str, exchange_str, price, quantity, trade_date, note=None):
    sf = _get_session_factory()
    settings = get_settings()
    with get_db_session(sf) as session:
        svc = PortfolioService(session, brokerage_discount=settings.brokerage_discount)
        atype = AssetType(asset_type_str)
        exch = Exchange(exchange_str)
        asset, tx = svc.buy(
            ticker=ticker, name=name, asset_type=atype, exchange=exch,
            price=price, quantity=quantity, trade_date=trade_date, note=note,
        )
        return asset.avg_cost, asset.quantity, tx.fee


def do_sell(ticker, price, quantity, trade_date, note=None):
    sf = _get_session_factory()
    settings = get_settings()
    with get_db_session(sf) as session:
        svc = PortfolioService(session, brokerage_discount=settings.brokerage_discount)
        asset, tx = svc.sell(
            ticker=ticker, price=price, quantity=quantity,
            trade_date=trade_date, note=note,
        )
        return tx.realized_pnl, tx.fee, tx.tax, asset.quantity


def do_dividend(ticker, dividend_per_share, trade_date, quantity=None, note=None):
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        svc = PortfolioService(session)
        if quantity is None:
            repo = AssetRepository(session)
            a = repo.get_by_ticker(ticker)
            if a is None:
                raise AssetNotFoundError(ticker)
            quantity = a.quantity
        asset, tx = svc.add_dividend(
            ticker=ticker, dividend_per_share=dividend_per_share,
            quantity=quantity, trade_date=trade_date, note=note,
        )
        return dividend_per_share * quantity


def do_split(ticker, split_ratio, trade_date, note=None):
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        svc = PortfolioService(session)
        asset, tx = svc.add_split(
            ticker=ticker, split_ratio=split_ratio,
            trade_date=trade_date, note=note,
        )
        return asset.quantity, asset.avg_cost


def get_asset_tickers() -> list[str]:
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = AssetRepository(session)
        return [a.ticker for a in repo.get_all_active()]
