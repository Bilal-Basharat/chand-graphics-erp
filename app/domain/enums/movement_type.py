# app/domain/enums/movement_type.py
from enum import Enum

class MovementType(str, Enum):
    # Manual stock correction (e.g., found missing items, system error fix)
    ADJUSTMENT = "ADJUSTMENT"
    
    # Customer returned goods (Stock In) OR returned to supplier (Stock Out)
    RETURN = "RETURN"
    
    # Items damaged, expired, or written off (Stock Out)
    DAMAGE = "DAMAGE"
    
    # Moving stock between physical locations/cabinets (if tracked) or branches
    TRANSFER = "TRANSFER"