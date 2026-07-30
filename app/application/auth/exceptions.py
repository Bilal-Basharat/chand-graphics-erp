from __future__ import annotations


class AuthenticationError(Exception):
    """Base authentication error."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when email or password is invalid."""


class InactiveAccountError(AuthenticationError):
    """Raised when the user exists but is inactive."""


class AuthenticationRequiredError(AuthenticationError):
    """Raised when an operation requires a signed-in user."""

class AuthorizationError(Exception):
    """Base authorization error."""


class PermissionDeniedError(AuthorizationError):
    """Raised when the signed-in user does not have the required permission."""

class LoginThrottledError(AuthenticationError):
    """Raised when too many failed sign-in attempts were made recently."""