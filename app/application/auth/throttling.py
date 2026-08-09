from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.application.auth.exceptions import LoginThrottledError
from app.config.settings import AppSettings
from app.domain.uow import UnitOfWork
from app.shared.datetimes import now_pkt


@dataclass(slots=True)
class LoginThrottleService:
    """
    Login throttling based on recent failed sign-in attempts.

    Uses the login_audits table, so no separate throttling table is required.
    """

    uow: UnitOfWork
    settings: AppSettings

    def failed_attempts_since(self, email: str, since: datetime) -> int:
        email = email.strip().lower()
        with self.uow as uow:
            audits = self._require_login_audits(uow)
            return audits.count_recent_failed_sign_ins(email=email, since=since)

    def require_not_throttled(self, email: str) -> None:
        email = email.strip().lower()
        since = now_pkt() - timedelta(
            minutes=self.settings.login_lockout_minutes
        )
        failed_attempts = self.failed_attempts_since(email, since)

        if failed_attempts >= self.settings.max_login_attempts:
            raise LoginThrottledError(
                "Too many failed sign-in attempts. Please try again later."
            )

    @staticmethod
    def _require_login_audits(uow):
        audits = getattr(uow, "login_audits", None)
        if audits is None:
            raise RuntimeError("login_audits repository is not initialized")
        return audits