"""Sign up, log in, log out, refresh and "who am I", using httpOnly cookies.

Two cookies:
- access_token: short-lived JWT, sent to every /api route.
- refresh_token: long-lived random token, sent only to /api/auth. Its SHA-256 hash is
  stored in refresh_tokens, and it is rotated (old one revoked) on every refresh.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import RefreshToken, User
from .security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    read_access_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_PATH = "/api/auth"


# ---------- schemas ----------


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("full_name")
    @classmethod
    def blank_name_is_none(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    is_verified: bool
    created_at: datetime


# ---------- cookie + session helpers ----------


def _set_cookie(response: Response, name: str, value: str, max_age: int, path: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=path,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )


def _start_session(db: Session, user: User, request: Request, response: Response) -> None:
    """Issue a fresh access + refresh token pair as cookies and store the refresh hash."""
    settings = get_settings()
    refresh = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh),
            user_agent=(request.headers.get("user-agent") or "")[:500] or None,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    _set_cookie(response, ACCESS_COOKIE, create_access_token(user.id), settings.access_token_minutes * 60, "/api")
    _set_cookie(response, REFRESH_COOKIE, refresh, settings.refresh_token_days * 86400, REFRESH_PATH)


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)


def current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Dependency for any route that needs a signed-in user."""
    user_id = read_access_token(access_token) if access_token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


# ---------- routes ----------


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name)
    user.last_login_at = datetime.now(UTC)
    db.add(user)
    try:
        db.flush()  # assigns user.id; the unique index catches a signup race
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from None
    _start_session(db, user, request, response)
    db.commit()
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Same message for "no such email" and "wrong password".
    if not verify_password(user.password_hash if user else None, body.password) or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    user.last_login_at = datetime.now(UTC)
    _start_session(db, user, request, response)
    db.commit()
    return user


@router.post("/refresh", response_model=UserOut, responses={401: {"description": "Refresh token missing, expired or revoked"}})
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | JSONResponse:
    row = (
        db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token)))
        if refresh_token
        else None
    )
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        # Return (not raise) so the cookie-clearing headers reach the browser.
        failed = JSONResponse({"detail": "Session expired, please log in again"}, status.HTTP_401_UNAUTHORIZED)
        _clear_cookies(failed)
        return failed
    row.revoked_at = now  # rotate: each refresh token works once
    user = db.get(User, row.user_id)
    _start_session(db, user, request, response)
    db.commit()
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Response:
    if refresh_token:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(refresh_token), RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    _clear_cookies(response)
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user

