from __future__ import annotations

from app.application.auth.commands import EnsureInitialAdminUserCommand
from app.application.use_cases.base import UseCase
from app.domain.entities.user import User
from app.domain.security.password_hasher import PasswordHasher
from app.domain.uow import UnitOfWork


class EnsureInitialAdminUserUseCase(UseCase[EnsureInitialAdminUserCommand, User | None]):
    """
    Create the first admin user only if no users exist yet.

    If the users table already has at least one row, this use case does nothing.
    """

    def __init__(self, uow: UnitOfWork, password_hasher: PasswordHasher) -> None:
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(self, request: EnsureInitialAdminUserCommand) -> User | None:
        email = request.email.strip().lower()
        full_name = request.full_name.strip()
        password = request.password.strip()
        role = request.role.strip() or "admin"

        if not email:
            raise ValueError("email cannot be empty")
        if not full_name:
            raise ValueError("full_name cannot be empty")
        if not password:
            raise ValueError("password cannot be empty")

        with self.uow as uow:
            users = self.require(uow.users, "users")

            # If any user already exists, do not create bootstrap admin again.
            if users.list(limit=1):
                return None

            admin_user = User(
                email=email,
                password_hash=self.password_hasher.hash(password),
                full_name=full_name,
                role=role,
                is_active=True,
            )
            return users.add(admin_user)