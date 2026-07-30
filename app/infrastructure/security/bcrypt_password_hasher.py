from __future__ import annotations

import bcrypt

from app.domain.security.password_hasher import PasswordHasher


class BcryptPasswordHasher(PasswordHasher):
    """
    bcrypt-based password hasher.
    """

    def hash(self, plain_text_password: str) -> str:
        if not plain_text_password:
            raise ValueError("plain_text_password cannot be empty")

        hashed = bcrypt.hashpw(
            plain_text_password.encode("utf-8"),
            bcrypt.gensalt(),
        )
        return hashed.decode("utf-8")

    def verify(self, plain_text_password: str, hashed_password: str) -> bool:
        if not plain_text_password or not hashed_password:
            return False

        return bcrypt.checkpw(
            plain_text_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )