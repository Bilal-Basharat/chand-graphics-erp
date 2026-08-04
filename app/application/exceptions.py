from __future__ import annotations


class ApplicationError(Exception):
    """Base class for application-level errors."""


class DuplicateEntityError(ApplicationError):
    """Raised when a record already exists and should remain unique."""


class NotFoundError(ApplicationError):
    """Raised when a required record does not exist."""


class EntityInUseError(ApplicationError):
    """Raised when a record cannot be deleted because documents reference it.

    Deleting it would leave those documents pointing at nothing, so the
    caller is told what is holding the record instead.
    """