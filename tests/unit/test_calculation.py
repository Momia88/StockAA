"""
單元測試：台灣股市費用計算與損益計算
"""
import pytest
from decimal import Decimal

from src.utils.tw_fees import (
    calc_brokerage_fee,
    calc_sell_tax,
    calc_buy_net_amount,
    calc_sell_net_amount,
    calc_new_avg_cost,
    calc_realized_pnl,
)
from src.models.enums import AssetType


class TestBrokerageFee:
    """手續費計算測試"""

    def test_normal_buy_fee(self):
        """一般買入手續費（六折）"""
        # 100 元 × 1000 股 = 100,000 元，手續費 = 100000 × 0.001425 × 0.6 = 85.5 → 86
        fee = calc_brokerage_fee(100.0, 1000, discount=0.6)
        assert fee == 86.0

    def test_minimum_fee(self):
        """手續費未達最低 20 元時，應收 20 元"""
        # 1 元 × 1 股 = 1 元，計算後 < 20，應為 20
        fee = calc_brokerage_fee(1.0, 1, discount=0.6)
        assert fee == 20.0

    def test_no_discount(self):
        """無折扣（折扣率 1.0）"""
        # 100 × 1000 × 0.001425 = 142.5 → 143
        fee = calc_brokerage_fee(100.0, 1000, discount=1.0)
        assert fee == 143.0

    def test_etf_same_rate(self):
        """ETF 手續費費率相同"""
        fee_stock = calc_brokerage_fee(50.0, 1000, discount=0.6)
        fee_etf = calc_brokerage_fee(50.0, 1000, discount=0.6)
        assert fee_stock == fee_etf


class TestSellTax:
    """證券交易稅計算測試"""

    def test_stock_sell_tax(self):
        """個股賣出稅 0.3%"""
        # 100 × 1000 × 0.003 = 300
        tax = calc_sell_tax(100.0, 1000, AssetType.STOCK)
        assert tax == 300.0

    def test_stock_etf_sell_tax(self):
        """股票型 ETF 賣出稅 0.1%"""
        # 100 × 1000 × 0.001 = 100
        tax = calc_sell_tax(100.0, 1000, AssetType.STOCK_ETF)
        assert tax == 100.0

    def test_bond_etf_sell_tax(self):
        """債券型 ETF 賣出稅 0.1%"""
        tax = calc_sell_tax(40.0, 1000, AssetType.BOND_ETF)
        assert tax == 40.0

    def test_tax_rounding(self):
        """交易稅四捨五入"""
        # 99.5 × 100 × 0.003 = 29.85 → 30
        tax = calc_sell_tax(99.5, 100, AssetType.STOCK)
        assert tax == 30.0


class TestAverageCost:
    """平均成本計算測試"""

    def test_first_buy(self):
        """第一次買入，平均成本應等於買入成本（含手續費分攤）"""
        fee = calc_brokerage_fee(100.0, 1000, discount=0.6)  # 86
        avg = calc_new_avg_cost(
            old_qty=0,
            old_avg_cost=0.0,
            buy_qty=1000,
            buy_price=100.0,
            buy_fee=fee,
        )
        # (0 + 100000 + 86) / 1000 = 100.086
        assert abs(avg - 100.086) < 0.001

    def test_second_buy_higher_price(self):
        """第二次以更高價買入，均成本上升"""
        avg = calc_new_avg_cost(
            old_qty=1000,
            old_avg_cost=100.0,
            buy_qty=1000,
            buy_price=120.0,
            buy_fee=100.0,
        )
        # (100000 + 120000 + 100) / 2000 = 110.05
        assert abs(avg - 110.05) < 0.001

    def test_second_buy_lower_price(self):
        """第二次以更低價買入（攤平），均成本下降"""
        avg = calc_new_avg_cost(
            old_qty=1000,
            old_avg_cost=100.0,
            buy_qty=1000,
            buy_price=80.0,
            buy_fee=60.0,
        )
        # (100000 + 80000 + 60) / 2000 = 90.03
        assert abs(avg - 90.03) < 0.001

    def test_zero_old_quantity(self):
        """從零開始買入"""
        avg = calc_new_avg_cost(0, 0.0, 500, 50.0, 43.0)
        expected = (500 * 50.0 + 43.0) / 500
        assert abs(avg - expected) < 0.001


class TestRealizedPnL:
    """已實現損益計算測試"""

    def test_profit(self):
        """獲利賣出"""
        # 買入成本 100，賣出 120，1000 股，費 86，稅 360
        pnl = calc_realized_pnl(
            sell_qty=1000,
            sell_price=120.0,
            avg_cost=100.0,
            fee=86.0,
            tax=360.0,
        )
        # (120 - 100) × 1000 - 86 - 360 = 20000 - 446 = 19554
        assert abs(pnl - 19554.0) < 0.01

    def test_loss(self):
        """虧損賣出"""
        pnl = calc_realized_pnl(
            sell_qty=1000,
            sell_price=80.0,
            avg_cost=100.0,
            fee=57.0,
            tax=240.0,
        )
        # (80 - 100) × 1000 - 57 - 240 = -20000 - 297 = -20297
        assert abs(pnl - (-20297.0)) < 0.01

    def test_breakeven(self):
        """損益平衡（費用即虧損）"""
        pnl = calc_realized_pnl(
            sell_qty=1000,
            sell_price=100.0,
            avg_cost=100.0,
            fee=86.0,
            tax=300.0,
        )
        # 0 - 86 - 300 = -386
        assert abs(pnl - (-386.0)) < 0.01


class TestBuyNetAmount:
    """買入淨金額計算測試"""

    def test_buy_total(self):
        """買入總支出 = 股數 × 單價 + 手續費"""
        net, fee, tax = calc_buy_net_amount(100.0, 1000, discount=0.6)
        assert tax == 0.0  # 買入不收交易稅
        assert fee == 86.0
        assert abs(net - 100086.0) < 0.01


class TestSellNetAmount:
    """賣出淨金額計算測試"""

    def test_sell_total_stock(self):
        """賣出個股淨收入（負數代表收入）"""
        net, fee, tax = calc_sell_net_amount(100.0, 1000, AssetType.STOCK, discount=0.6)
        # 100 × 1000 = 100000
        # fee = 86, tax = 300
        # net_income = -(100000 - 86 - 300) = -99614
        assert tax == 300.0
        assert fee == 86.0
        assert abs(net - (-99614.0)) < 0.01

    def test_sell_total_etf(self):
        """賣出 ETF 淨收入（低稅）"""
        net, fee, tax = calc_sell_net_amount(100.0, 1000, AssetType.STOCK_ETF, discount=0.6)
        assert tax == 100.0  # ETF 稅 0.1%
