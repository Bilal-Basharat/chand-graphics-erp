from enum import StrEnum


class TransactionType(StrEnum):
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"