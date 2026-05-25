import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session, selectinload

from . import models
from .config import settings
from .database import get_db


ALGORITHM = "HS256"
bearer_scheme = HTTPBearer(auto_error=False)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _sign(message: str) -> str:
    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        message.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(signature)


def create_signed_token(payload: dict, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _base64url_encode(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}"
    return f"{signing_input}.{_sign(signing_input)}"


def decode_signed_token(token: str) -> dict:
    try:
        encoded_header, encoded_payload, signature = token.split(".", 2)
        signing_input = f"{encoded_header}.{encoded_payload}"
        if not hmac.compare_digest(_sign(signing_input), signature):
            raise ValueError("Invalid token signature")
        payload = json.loads(_base64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
        )
    return payload


def create_oauth_state() -> str:
    return create_signed_token(
        {"typ": "oauth_state", "nonce": secrets.token_urlsafe(24)},
        timedelta(minutes=settings.oauth_state_expire_minutes),
    )


def verify_oauth_state(state_token: str) -> None:
    payload = decode_signed_token(state_token)
    if payload.get("typ") != "oauth_state":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid oauth state",
        )


def create_access_token(user: models.User) -> str:
    return create_signed_token(
        {
            "typ": "access",
            "sub": str(user.id),
            "email": user.email,
            "name": user.full_name,
            "roles": sorted(role.name for role in user.roles),
        },
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def decode_access_token(token: str) -> dict:
    payload = decode_signed_token(token)
    if payload.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    user = (
        db.query(models.User)
        .options(selectinload(models.User.roles))
        .filter(models.User.id == int(user_id))
        .first()
        if str(user_id).isdigit()
        else None
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active",
        )
    return user


def role_names(user: models.User) -> set[str]:
    return {role.name.lower() for role in user.roles}


def has_any_role(user: models.User, allowed_roles: Iterable[str]) -> bool:
    allowed = {role.lower() for role in allowed_roles}
    return bool(role_names(user) & allowed)


def require_any_role(*allowed_roles: str):
    def dependency(current_user: models.User = Depends(get_current_user)) -> models.User:
        if not has_any_role(current_user, allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return dependency


def can_manage_work(user: models.User) -> bool:
    return has_any_role(user, {"admin", "task creator"})
