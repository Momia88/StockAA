"""
台灣股市費用計算工具
"""
from decimal import ROUND_HALF_UP, Decimal

from ..models.enums import AssetType

# 常數
BROKERAGE_RATE = Decimal("0.001425")   # 手續費率 0.1425%
MIN_BROKERAGE_FEE = Decimal("20")      # 最低手續費 20 元
SELL_TAX_STOCK = Decimal("0.003")      # 個股交易稅 0.3%
SELL_TAX_ETF = Decimal("0.001")        # ETF 交易稅 0.1%


def calc_brokerage_fee(
    price: float,
    quantity: int,
    discount: float = 0.6,
) -> float:
    """
    計算手續費（買賣雙向）

    Args:
        price: 交易單價（元/股）
        quantity: 交易股數
        discount: 手續費折扣（0.6 = 六折）

    Returns:
        手續費（元，四捨五入至整數）
    """
    amount = Decimal(str(price)) * Decimal(str(quantity))
    fee = amount * BROKERAGE_RATE * Decimal(str(discount))
    fee = max(fee, MIN_BROKERAGE_FEE)
    return float(fee.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calc_sell_tax(
    price: float,
    quantity: int,
    asset_type: AssetType,
) -> float:
    """
    計算證券交易稅（僅賣出時收）

    Args:
        price: 賣出單價（元/股）
        quantity: 賣出股數
        asset_type: 資產類型（個股 0.3%，ETF 0.1%）

    Returns:
        交易稅（元，四捨五入至整數）
    """
    amount = Decimal(str(price)) * Decimal(str(quantity))
    tax_rate = (
        SELL_TAX_ETF
        if asset_type in (AssetType.STOCK_ETF, AssetType.BOND_ETF)
        else SELL_TAX_STOCK
    )
    tax = amount * tax_rate
    return float(tax.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calc_buy_net_amount(
    price: float,
    quantity: int,
    discount: float = 0.6,
) -> tuple[float, float, float]:
    """
    計算買入的淨支出金額

    Returns:
        (淨支出金額, 手續費, 交易稅=0)
    """
    amount = price * quantity
    fee = calc_brokerage_fee(price, quantity, discount)
    net = amount + fee
    return round(net, 2), round(fee, 2), 0.0


def calc_sell_net_amount(
    price: float,
    quantity: int,
    asset_type: AssetType,
    discount: float = 0.6,
) -> tuple[float, float, float]:
    """
    計算賣出的淨收入金額

    Returns:
        (淨收入金額為負數, 手續費, 交易稅)
    """
    amount = price * quantity
    fee = calc_brokerage_fee(price, quantity, discount)
    tax = calc_sell_tax(price, quantity, asset_type)
    net = -(amount - fee - tax)  # 負數代表收入
    return round(net, 2), round(fee, 2), round(tax, 2)


def calc_new_avg_cost(
    old_qty: int,
    old_avg_cost: float,
    buy_qty: int,
    buy_price: float,
    buy_fee: float,
) -> float:
    """
    計算買入後的新平均成本（平均成本法）

    新平均成本 = (舊持倉成本總額 + 本次買入含手續費) / 新總持股數
    """
    old_total_cost = Decimal(str(old_avg_cost)) * Decimal(str(old_qty))
    new_buy_cost = Decimal(str(buy_price)) * Decimal(str(buy_qty)) + Decimal(str(buy_fee))
    new_qty = old_qty + buy_qty
    if new_qty == 0:
        return 0.0
    new_avg = (old_total_cost + new_buy_cost) / Decimal(str(new_qty))
    return float(new_avg.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def calc_realized_pnl(
    sell_qty: int,
    sell_price: float,
    avg_cost: float,
    fee: float,
    tax: float,
) -> float:
    """
    計算賣出的已實現損益

    已實現損益 = (賣出單價 - 平均成本) × 股數 - 手續費 - 交易稅
    """
    gross = (Decimal(str(sell_price)) - Decimal(str(avg_cost))) * Decimal(str(sell_qty))
    pnl = gross - Decimal(str(fee)) - Decimal(str(tax))
    return float(pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
