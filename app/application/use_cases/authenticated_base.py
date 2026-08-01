from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar

from app.application.auth.session import CurrentUserSession
from app.application.use_cases.base import UseCase

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class AuthenticatedUseCase(UseCase[RequestT, ResponseT], ABC, Generic[RequestT, ResponseT]):
    """
    Base class for use cases that require a signed-in user.
    """

    def __init__(self, current_user_session: CurrentUserSession | None = None) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        self.current_user_session = current_user_session

    def current_user_id(self) -> int:
        return self.current_user_session.require_user_id()