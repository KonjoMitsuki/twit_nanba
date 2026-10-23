"""Google OIDC login, signed sessions, and a two-person allowlist."""

import os
import secrets
from urllib.parse import urlsplit

import httpx
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth", tags=["authentication"])
oauth = OAuth()


def allowed_emails():
    return {
        value.strip().casefold()
        for value in os.getenv("GOOGLE_ALLOWED_EMAILS", "").split(",")
        if value.strip()
    }


def configured():
    return bool(
        os.getenv("GOOGLE_CLIENT_ID")
        and os.getenv("GOOGLE_CLIENT_SECRET")
        and len(os.getenv("SESSION_SECRET", "")) >= 32
        and len(allowed_emails()) == 2
    )


def require_user(request: Request):
    if not configured():
        raise HTTPException(
            503, "Googleログインを設定してください。画面はデモで確認できます"
        )
    user = request.session.get("user")
    if not user or user.get("email", "").casefold() not in allowed_emails():
        raise HTTPException(401, "ログインしてください")
    return user


def require_csrf(request: Request):
    require_user(request)
    token = request.session.get("csrf", "")
    if not token or not secrets.compare_digest(
        request.headers.get("X-CSRF-Token", ""), token
    ):
        raise HTTPException(403, "画面を再読み込みしてから操作してください")


def google_client():
    oauth.register(
        "google",
        overwrite=True,
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
            "code_challenge_method": "S256",
        },
    )
    return oauth.create_client("google")


@router.get("/login")
async def login(request: Request):
    if not configured():
        raise HTTPException(
            503, "Google OAuthと2人の許可メールアドレスを設定してください"
        )
    # Fixed registered URI avoids an untrusted Host header controlling the callback.
    callback = os.getenv("GOOGLE_REDIRECT_URI", "")
    if not callback:
        raise HTTPException(503, "GOOGLE_REDIRECT_URIを設定してください")
    return await google_client().authorize_redirect(request, callback)


@router.get("/callback")
async def callback(request: Request):
    if not configured():
        raise HTTPException(503, "Googleログインが未設定です")
    try:
        # Authlib checks state, signature, issuer, audience, expiry and nonce.
        token = await google_client().authorize_access_token(request)
        info = token.get("userinfo", {})
        email = str(info.get("email", "")).casefold()
        if (
            not info.get("sub")
            or info.get("email_verified") is not True
            or email not in allowed_emails()
        ):
            request.session.clear()
            raise HTTPException(403, "許可されたアカウントでログインしてください")
        request.session.clear()
        request.session["user"] = {
            "id": info["sub"],
            "email": email,
            "name": info.get("name", email),
        }
        request.session["csrf"] = secrets.token_urlsafe(32)
    except (AuthlibBaseError, httpx.HTTPError, ValueError, KeyError) as error:
        request.session.clear()
        raise HTTPException(
            401, "認証を完了できませんでした。もう一度ログインしてください"
        ) from error
    return RedirectResponse("/analytics", status_code=303)


@router.get("/me")
def me(request: Request):
    return {"user": require_user(request), "csrf": request.session["csrf"]}


@router.post("/logout")
def logout(request: Request):
    require_csrf(request)
    request.session.clear()
    return {"ok": True}


async def protect_api(request: Request, call_next):
    """Protect the existing collector controls too when authentication is enabled."""
    from fastapi.responses import JSONResponse

    path = request.url.path
    if path.startswith("/api/") and path != "/api/health":
        enabled = bool(
            os.getenv("GOOGLE_CLIENT_ID")
            or os.getenv("GOOGLE_CLIENT_SECRET")
            or os.getenv("GOOGLE_ALLOWED_EMAILS")
        )
        if enabled or path.startswith("/api/analytics"):
            try:
                require_user(request)
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    require_csrf(request)
                    origin = request.headers.get("origin")
                    expected = urlsplit(os.getenv("GOOGLE_REDIRECT_URI", ""))
                    if origin and origin != f"{expected.scheme}://{expected.netloc}":
                        raise HTTPException(403, "同じサイトから操作してください")
            except HTTPException as error:
                return JSONResponse(
                    {"detail": error.detail}, status_code=error.status_code
                )
    response = await call_next(request)
    if path.startswith(("/api/", "/auth/")):
        response.headers["Cache-Control"] = "no-store"
    return response
