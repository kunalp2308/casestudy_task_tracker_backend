import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..auth import create_access_token, create_oauth_state, get_current_user, verify_oauth_state
from ..config import settings
from ..database import get_db
from ..services import commit_or_409, get_role_by_name


router = APIRouter(prefix="/auth", tags=["auth"])


def _frontend_callback_url(error: str | None = None, access_token: str | None = None) -> str:
    base_url = settings.frontend_origin.rstrip('/')
    if access_token:
        return f"{base_url}/?access_token={quote(access_token)}"
    if error:
        return f"{base_url}?auth_error={quote(error)}"
    return base_url


def _ensure_google_configured():
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google SSO is not configured",
        )


def _exchange_code_for_token(code: str) -> dict:
    request_body = urlencode(
        {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = Request(
        settings.google_token_url,
        data=request_body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authorization code exchange failed",
        ) from exc


def _fetch_google_profile(access_token: str) -> dict:
    request = Request(
        settings.google_userinfo_url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to fetch Google profile",
        ) from exc


def _assign_login_roles(db: Session, user: models.User, is_new_user: bool):
    admin_role = get_role_by_name(db, "admin")
    read_only_role = get_role_by_name(db, "individual read only user")
    email = user.email.lower()

    should_be_admin = email in settings.google_admin_email_set

    if should_be_admin:
        if admin_role and admin_role not in user.roles:
            user.roles.append(admin_role)
    elif is_new_user and read_only_role:
        user.roles.append(read_only_role)


def _upsert_google_user(db: Session, profile: dict) -> models.User:
    email = profile.get("email")
    google_sub = profile.get("sub")
    full_name = profile.get("name") or email
    avatar_url = profile.get("picture")
    email_verified = profile.get("email_verified")

    if not email or not google_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google profile is incomplete")
    if email_verified is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google email is not verified")

    user = (
        db.query(models.User)
        .options(selectinload(models.User.roles))
        .filter(models.User.google_sub == google_sub)
        .first()
    )
    if user is None:
        user = (
            db.query(models.User)
            .options(selectinload(models.User.roles))
            .filter(models.User.email == email)
            .first()
        )

    is_new_user = user is None
    if is_new_user:
        user = models.User(
            full_name=full_name,
            email=email,
            google_sub=google_sub,
            avatar_url=avatar_url,
            is_active=True,
        )
        db.add(user)
    else:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        user.full_name = full_name
        user.email = email
        user.google_sub = user.google_sub or google_sub
        user.avatar_url = avatar_url

    _assign_login_roles(db, user, is_new_user)
    commit_or_409(db, "Unable to store Google user")
    db.refresh(user)
    return user


@router.get("/google/login")
def google_login():
    _ensure_google_configured()
    state = create_oauth_state()
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
            "include_granted_scopes": "true",
        }
    )
    return RedirectResponse(f"{settings.google_authorization_url}?{params}")


@router.get("/google/callback")
def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if error:
        return RedirectResponse(_frontend_callback_url(error=error))
    if not code or not state:
        return RedirectResponse(_frontend_callback_url(error="Google callback is missing code or state"))

    try:
        _ensure_google_configured()
        verify_oauth_state(state)
        token_payload = _exchange_code_for_token(code)
        profile = _fetch_google_profile(token_payload["access_token"])
        user = _upsert_google_user(db, profile)
        access_token = create_access_token(user)
        return RedirectResponse(_frontend_callback_url(access_token=access_token))
    except HTTPException as exc:
        return RedirectResponse(_frontend_callback_url(error=str(exc.detail)))


@router.get("/me", response_model=schemas.UserRead)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user
