from __future__ import annotations


class ApplicationError(Exception):
    """Base class for application-level errors."""


class DuplicateEntityError(ApplicationError):
    """Raised when a record already exists and should remain unique."""


class NotFoundError(ApplicationError):
    """Raised when a required record does not exist."""


class EmailDeliveryError(ApplicationError):
    """Raised when a message could not be sent.

    Covers both "no mail server is configured" and "the server refused
    it": from the caller's side both mean the same thing — nothing was
    delivered, so nothing else should be treated as done either.
    """


class EntityInUseError(ApplicationError):
    """Raised when a record cannot be deleted because documents reference it.

    Deleting it would leave those documents pointing at nothing, so the
    caller is told what is holding the record instead.
    """