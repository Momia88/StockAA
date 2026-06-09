"""
Pytest 設定與共用 Fixtures
"""
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
from src.models.database import create_all_tables


@pytest.fixture(scope="function")
def db_engine():
    """建立記憶體內 SQLite 引擎（每個測試獨立）"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    create_all_tables(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """建立資料庫 Session"""
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def portfolio_service(db_session):
    """PortfolioService 實例（使用六折手續費）"""
    from src.services.portfolio_service import PortfolioService
    return PortfolioService(db_session, brokerage_discount=0.6)


@pytest.fixture
def sample_buy_2330(portfolio_service, db_session):
    """預設已買入 1000 股台積電 @600"""
    asset, tx = portfolio_service.buy(
        ticker="2330",
        name="台積電",
        asset_type=__import__("src.models.enums", fromlist=["AssetType"]).AssetType.STOCK,
        exchange=__import__("src.models.enums", fromlist=["Exchange"]).Exchange.TWSE,
        price=600.0,
        quantity=1000,
        trade_date=date(2024, 1, 15),
        note="初始買入",
    )
    db_session.commit()
    return asset


@pytest.fixture
def sample_buy_0050(portfolio_service, db_session):
    """預設已買入 2000 股元大台灣50 @180"""
    from src.models.enums import AssetType, Exchange
    asset, tx = portfolio_service.buy(
        ticker="0050",
        name="元大台灣50",
        asset_type=AssetType.STOCK_ETF,
        exchange=Exchange.TWSE,
        price=180.0,
        quantity=2000,
        trade_date=date(2024, 2, 1),
    )
    db_session.commit()
    return asset
