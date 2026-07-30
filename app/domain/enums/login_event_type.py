from __future__ import annotations

from enum import StrEnum


class LoginEventType(StrEnum):
    SIGN_IN_SUCCESS = "sign_in_success"
    SIGN_IN_FAILURE = "sign_in_failure"
    SIGN_OUT = "sign_out"
    SESSION_RESTORED = "session_restored"