from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import CreateExpenseCommand, DateRangeQuery
from app.application.exceptions import NotFoundError
from app.application.use_cases.base import UseCase
from app.domain.entities.expense import Expense
from app.domain.uow import UnitOfWork


class CreateExpenseUseCase(UseCase[CreateExpenseCommand, Expense]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreateExpenseCommand) -> Expense:
        with self.uow as uow:
            expenses = self.require(uow.expenses, "expenses")
            categories = self.require(uow.expense_categories, "expense_categories")

            if request.category_id is not None and categories.get_by_id(request.category_id) is None:
                raise NotFoundError(f"Expense category id={request.category_id} not found")

            if request.amount is not None:
                amount = request.amount
            else:
                if request.quantity is None or request.unit_price is None:
                    raise ValueError(
                        "Either amount must be provided, or both quantity and unit_price must be provided"
                    )
                amount = request.unit_price * Decimal(request.quantity)

            expense = Expense(
                expense_name=request.expense_name.strip(),
                amount=amount,
                category_id=request.category_id,
                quantity=request.quantity,
                unit_price=request.unit_price,
                remarks=request.remarks,
                created_by_user_id=request.created_by_user_id,
            )
            return expenses.add(expense)


class ListExpensesByDateRangeUseCase(UseCase[DateRangeQuery, list[Expense]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: DateRangeQuery) -> list[Expense]:
        with self.uow as uow:
            expenses = self.require(uow.expenses, "expenses")
            return expenses.list_by_date_range(request.start, request.end, request.limit)