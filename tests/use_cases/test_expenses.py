from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import CreateExpenseCategoryCommand, CreateExpenseCommand
from app.application.use_cases.expenses import CreateExpenseUseCase
from app.application.use_cases.master_data import CreateExpenseCategoryUseCase


def test_create_expense(uow):
    category = CreateExpenseCategoryUseCase(uow).execute(
        CreateExpenseCategoryCommand(name="Fuel", description="Transport and fuel")
    )

    expense = CreateExpenseUseCase(uow).execute(
        CreateExpenseCommand(
            expense_name="Fuel for delivery",
            category_id=category.id,
            amount=Decimal("1500.00"),
            remarks="Delivery run",
        )
    )

    assert expense.id is not None
    assert expense.expense_name == "Fuel for delivery"
    assert expense.amount == Decimal("1500.00")
    assert expense.category_id == category.id