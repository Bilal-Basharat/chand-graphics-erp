from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str
    """Plain text. The one message this app sends is a password a person
    has to read and retype, and plain text is what survives every client
    intact."""


class EmailSender(ABC):
    """
    Abstract outgoing-mail contract.

    Infrastructure provides the concrete implementation.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this installation can send mail at all.

        Callers check before offering the user something that would fail:
        an unconfigured mail server is a setup state, not an error to be
        discovered mid-request.
        """
        raise NotImplementedError

    @abstractmethod
    def send(self, message: EmailMessage) -> None:
        """Deliver `message`, raising `EmailDeliveryError` if it cannot."""
        raise NotImplementedError
