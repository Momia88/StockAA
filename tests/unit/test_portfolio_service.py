"""
整合測試：PortfolioService 買入/賣出/股利流程
"""
import pytest
from datetime import date

from src.models.enums import AssetType, Exchange
from src.utils.exceptions import (
    AssetNotFoundError,
    InsufficientHoldingsError,
    InvalidTransactionError,
)


class TestBuyOperation:
    """買入操作測試"""

    def test_first_buy_creates_asset(self, portfolio_service, db_session):
        """首次買入應建立 Asset 記錄"""
        asset, tx = portfolio_service.buy(
            ticker="2330",
            name="台積電",
            asset_type=AssetType.STOCK,
            exchange=Exchange.TWSE,
            price=600.0,
            quantity=1000,
            trade_date=date(2024, 1, 1),
        )
        assert asset.ticker == "2330"
        assert asset.quantity == 1000
        assert asset.avg_cost > 600.0  # 含手續費分攤，成本略高於買入價
        assert asset.first_buy_date == date(2024, 1, 1)
        assert tx.action.value == "BUY"
        assert tx.fee > 0
        assert tx.tax == 0.0  # 買入不收交易稅

    def test_second_buy_updates_avg_cost(self, portfolio_service, db_session):
        """第二次買入應更新平均成本"""
        # 第一次買入 1000 股 @600
        asset, _ = portfolio_service.buy(
            ticker="2330", name="台積電",
            asset_type=AssetType.STOCK, exchange=Exchange.TWSE,
            price=600.0, quantity=1000, trade_date=date(2024, 1, 1),
        )
        first_avg = asset.avg_cost
        db_session.commit()

        # 第二次買入 1000 股 @700（價格較高）
        asset, _ = portfolio_service.buy(
            ticker="2330", name="台積電",
            asset_type=AssetType.STOCK, exchange=Exchange.TWSE,
            price=700.0, quantity=1000, trade_date=date(2024, 2, 1),
        )
        db_session.commit()

        assert asset.quantity == 2000
        assert asset.avg_cost > first_avg  # 均價上升
        assert asset.avg_cost < 700.0      # 但低於第二次買入價

    def test_buy_invalid_quantity(self, portfolio_service):
        """買入股數 <= 0 應拋出例外"""
        with pytest.raises(InvalidTransactionError):
            portfolio_service.buy(
                ticker="2330", name="台積電",
                asset_type=AssetType.STOCK, exchange=Exchange.TWSE,
                price=600.0, quantity=0, trade_date=date(2024, 1, 1),
            )

    def test_buy_invalid_price(self, portfolio_service):
        """買入價格 <= 0 應拋出例外"""
        with pytest.raises(InvalidTransactionError):
            portfolio_service.buy(
                ticker="2330", name="台積電",
                asset_type=AssetType.STOCK, exchange=Exchange.TWSE,
                price=-1.0, quantity=1000, trade_date=date(2024, 1, 1),
            )

    def test_buy_fee_minimum(self, portfolio_service, db_session):
        """少量買入時手續費應達最低 20 元"""
        asset, tx = portfolio_service.buy(
            ticker="2330", name="台積電",
            asset_type=AssetType.STOCK, exchange=Exchange.TWSE,
            price=1.0, quantity=1, trade_date=date(2024, 1, 1),
        )
        assert tx.fee == 20.0  # 最低手續費

    def test_etf_buy(self, portfolio_service, db_session):
        """ETF 買入正常運作"""
        asset, tx = portfolio_service.buy(
            ticker="0050", name="元大台灣50",
            asset_type=AssetType.STOCK_ETF, exchange=Exchange.TWSE,
            price=185.0, quantity=2000, trade_date=date(2024, 1, 15),
        )
        assert asset.asset_type == AssetType.STOCK_ETF
        assert asset.quantity == 2000


class TestSellOperation:
    """賣出操作測試"""

    def test_sell_partial(self, portfolio_service, db_session, sample_buy_2330):
        """部分賣出：持股減少，均價不變，損益計算正確"""
        asset = sample_buy_2330
        buy_avg = asset.avg_cost

        asset, tx = portfolio_service.sell(
            ticker="2330",
            price=700.0,
            quantity=500,
            trade_date=date(2024, 6, 1),
        )
        db_session.commit()

        assert asset.quantity == 500
        assert abs(asset.avg_cost - buy_avg) < 0.001  # 平均成本不變
        assert tx.realized_pnl > 0  # 獲利賣出

    def test_sell_all(self, portfolio_service, db_session, sample_buy_2330):
        """全部賣出後，持股數應為 0，均價歸零"""
        asset, tx = portfolio_service.sell(
            ticker="2330",
            price=650.0,
            quantity=1000,
            trade_date=date(2024, 6, 1),
        )
        db_session.commit()

        assert asset.quantity == 0
        assert asset.avg_cost == 0.0

    def test_sell_at_loss(self, portfolio_service, db_session, sample_buy_2330):
        """虧損賣出：已實現損益為負數"""
        asset, tx = portfolio_service.sell(
            ticker="2330",
            price=500.0,   # 低於均成本 ~600
            quantity=1000,
            trade_date=date(2024, 6, 1),
        )
        assert tx.realized_pnl < 0

    def test_sell_nonexistent_asset(self, portfolio_service):
        """賣出不存在的股票應拋出例外"""
        with pytest.raises(AssetNotFoundError):
            portfolio_service.sell(
                ticker="9999",
                price=100.0,
                quantity=100,
                trade_date=date(2024, 6, 1),
            )

    def test_sell_insufficient_holdings(self, portfolio_service, db_session, sample_buy_2330):
        """賣出超過持有量應拋出例外"""
        with pytest.raises(InsufficientHoldingsError):
            portfolio_service.sell(
                ticker="2330",
                price=700.0,
                quantity=5000,  # 持有 1000，超量賣出
                trade_date=date(2024, 6, 1),
            )

    def test_stock_sell_tax_03_pct(self, portfolio_service, db_session, sample_buy_2330):
        """個股賣出稅率應為 0.3%"""
        _, tx = portfolio_service.sell(
            ticker="2330",
            price=600.0,
            quantity=1000,
            trade_date=date(2024, 6, 1),
        )
        expected_tax = round(600.0 * 1000 * 0.003)
        assert tx.tax == expected_tax

    def test_etf_sell_tax_01_pct(self, portfolio_service, db_session, sample_buy_0050):
        """ETF 賣出稅率應為 0.1%"""
        _, tx = portfolio_service.sell(
            ticker="0050",
            price=185.0,
            quantity=2000,
            trade_date=date(2024, 6, 1),
        )
        expected_tax = round(185.0 * 2000 * 0.001)
        assert tx.tax == expected_tax


class TestDividend:
    """股利操作測試"""

    def test_cash_dividend(self, portfolio_service, db_session, sample_buy_2330):
        """現金股利應累加到 total_dividend"""
        asset, tx = portfolio_service.add_dividend(
            ticker="2330",
            dividend_per_share=12.0,
            quantity=1000,
            trade_date=date(2024, 7, 1),
        )
        db_session.commit()

        assert abs(asset.total_dividend - 12000.0) < 0.01
        assert tx.action.value == "DIVIDEND"

    def test_stock_dividend_reduces_avg_cost(self, portfolio_service, db_session, sample_buy_2330):
        """股票股利應增加股數且降低均成本"""
        asset = sample_buy_2330
        before_avg = asset.avg_cost
        before_qty = asset.quantity

        asset, tx = portfolio_service.add_stock_dividend(
            ticker="2330",
            bonus_shares=100,
            trade_date=date(2024, 7, 15),
        )
        db_session.commit()

        assert asset.quantity == before_qty + 100
        assert asset.avg_cost < before_avg  # 均成本下降
        # 總成本應不變（cost_basis 驗證）
        assert abs(asset.avg_cost * asset.quantity - before_avg * before_qty) < 1.0

    def test_dividend_nonexistent_asset(self, portfolio_service):
        """對不存在的持倉發放股利應拋出例外"""
        with pytest.raises(AssetNotFoundError):
            portfolio_service.add_dividend(
                ticker="9999",
                dividend_per_share=5.0,
                quantity=1000,
                trade_date=date(2024, 7, 1),
            )


class TestSplit:
    """股票分割/合併測試"""

    def test_two_for_one_split(self, portfolio_service, db_session, sample_buy_2330):
        """2:1 分割：股數加倍，均成本減半，總成本不變"""
        asset = sample_buy_2330
        before_qty = asset.quantity      # 1000
        before_avg = asset.avg_cost

        asset, tx = portfolio_service.add_split(
            ticker="2330",
            split_ratio=2.0,
            trade_date=date(2024, 8, 1),
            note="2:1 股票分割",
        )
        db_session.commit()

        assert asset.quantity == before_qty * 2              # 2000
        assert abs(asset.avg_cost - before_avg / 2) < 0.01  # 均成本減半
        # 成本總額不變：avg_cost × qty ≈ 原本的 avg_cost × qty
        assert abs(asset.avg_cost * asset.quantity - before_avg * before_qty) < 1.0
        assert tx.action.value == "SPLIT"
        assert tx.quantity == before_qty  # delta = +1000

    def test_reverse_split(self, portfolio_service, db_session, sample_buy_2330):
        """1:2 反向合併：股數減半，均成本加倍"""
        asset = sample_buy_2330
        before_qty = asset.quantity      # 1000
        before_avg = asset.avg_cost

        asset, tx = portfolio_service.add_split(
            ticker="2330",
            split_ratio=0.5,
            trade_date=date(2024, 8, 1),
        )
        db_session.commit()

        assert asset.quantity == 500
        assert abs(asset.avg_cost - before_avg * 2) < 0.01
        assert tx.quantity == -500  # delta = -500

    def test_split_nonexistent_asset(self, portfolio_service):
        """對不存在的持倉執行分割應拋出例外"""
        with pytest.raises(AssetNotFoundError):
            portfolio_service.add_split(
                ticker="9999", split_ratio=2.0, trade_date=date(2024, 8, 1)
            )

    def test_split_invalid_ratio(self, portfolio_service, db_session, sample_buy_2330):
        """比例 <= 0 應拋出例外"""
        with pytest.raises(InvalidTransactionError):
            portfolio_service.add_split(
                ticker="2330", split_ratio=-1.0, trade_date=date(2024, 8, 1)
            )


class TestAverageCostMethod:
    """平均成本法專項測試（多次交易場景）"""

    def test_three_buys_avg_cost(self, portfolio_service, db_session):
        """三次買入，驗證平均成本計算"""
        # 買入 1: 1000 股 @100
        portfolio_service.buy(
            ticker="TEST", name="測試股",
            asset_type=AssetType.STOCK, exchange=Exchange.TWSE,
            price=100.0, quantity=1000, trade_date=date(2024, 1, 1),
        )
        db_session.commit()
        # 買入 2: 1000 股 @120
        portfolio_service.buy(
            ticker="TEST", name="測試股",
            asset_type=AssetType.STOCK, exchange=Exchange.TWSE,
            price=120.0, quantity=1000, trade_date=date(2024, 2, 1),
        )
        db_session.commit()
        # 買入 3: 2000 股 @80（攤平）
        asset, _ = portfolio_service.buy(
            ticker="TEST", name="測試股",
            asset_type=AssetType.STOCK, exchange=Exchange.TWSE,
            price=80.0, quantity=2000, trade_date=date(2024, 3, 1),
        )
        db_session.commit()

        assert asset.quantity == 4000
        # 均價約 = (100000 + fee1 + 120000 + fee2 + 160000 + fee3) / 4000
        # 大約在 95~96 之間（含手續費）
        assert 95.0 < asset.avg_cost < 97.0

    def test_sell_does_not_change_avg_cost(self, portfolio_service, db_session, sample_buy_2330):
        """賣出不應改變平均成本（平均成本法特性）"""
        asset = sample_buy_2330
        before_avg = asset.avg_cost

        asset, _ = portfolio_service.sell(
            ticker="2330",
            price=650.0,
            quantity=500,
            trade_date=date(2024, 6, 1),
        )
        db_session.commit()

        assert abs(asset.avg_cost - before_avg) < 0.001
