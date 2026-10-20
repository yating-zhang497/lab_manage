from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .config import TOKEN_TTL_DAYS
from .models import Token, User

PBKDF2_ITERATIONS = 200_000


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, salt, expected = password_hash.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), expected)


def create_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        Token(
            user_id=user.id,
            token=token,
            expires_at=utcnow() + timedelta(days=TOKEN_TTL_DAYS),
        )
    )
    db.commit()
    return token


def find_user_by_token(db: Session, token: str) -> User | None:
    row = db.query(Token).filter(Token.token == token).first()
    if row is None:
        return None
    if row.expires_at < utcnow():
        db.delete(row)
        db.commit()
        return None
    return db.get(User, row.user_id)


def revoke_token(db: Session, token: str) -> None:
    db.query(Token).filter(Token.token == token).delete()
    db.commit()
