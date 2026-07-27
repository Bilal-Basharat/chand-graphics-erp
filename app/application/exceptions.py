from __future__ import annotations


class ApplicationError(Exception):
    """Base class for application-level errors."""


class DuplicateEntityError(ApplicationError):
    """Raised when a record already exists and should remain unique."""


class NotFoundError(ApplicationError):
    """Raised when a required record does not exist."""