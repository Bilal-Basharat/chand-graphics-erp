# app/domain/enums/movement_type.py
from enum import Enum

class MovementType(str, Enum):
    """Why an item's count changed, for the changes no document explains.

    Purchases and sales move stock as a side effect of trading and are
    never recorded here. What is left are the three exceptions a shop
    actually has: a miscount put right, goods coming back, and goods
    written off.
    """

    # Manual stock correction (e.g., found missing items, system error fix)
    ADJUSTMENT = "ADJUSTMENT"

    # Customer returned goods (Stock In) OR returned to supplier (Stock Out).
    # Never recorded on its own: a return always names the sale or purchase
    # it reverses, and is written by the return use cases.
    RETURN = "RETURN"

    # Items damaged, expired, or written off (Stock Out)
    DAMAGE = "DAMAGE"
