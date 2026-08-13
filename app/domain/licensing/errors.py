from __future__ import annotations


class LicenseError(Exception):
    """Base class for licensing failures the user is told about."""


class InvalidLicenseError(LicenseError):
    """A licence key was rejected — unreadable, unsigned, or not ours.

    Raised only where the user is *offering* a key and needs to know why
    it was refused. Simply reading the stored licence never raises: it
    returns a `LicenseState` carrying the reason, because a screen that
    reports "revoked" is more useful than one that crashes.
    """


class FeatureNotLicensedError(LicenseError):
    """The current licence does not include the feature being used."""
