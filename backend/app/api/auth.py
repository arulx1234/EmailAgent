from dataclasses import dataclass
import json
import logging
import os
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest, Response
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from ..config import settings


logger = logging.getLogger(__name__)

# Google may return previously granted scopes in addition to the requested
# scopes. OAuthlib otherwise raises Warning and aborts the token exchange.
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.modify",
    GMAIL_COMPOSE_SCOPE,
]

SESSION_COOKIE = "ai_mail_session"
OAUTH_STATE_COOKIE = "ai_mail_oauth_state"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
AUTH_DB_FILE = Path(__file__).resolve().parents[2] / ".auth_sessions.sqlite3"


@dataclass
class UserSession:
    credentials: Credentials
    profile: dict[str, str]
    expires_at: float


oauth_flows: dict[str, Flow] = {}
user_sessions: dict[str, UserSession] = {}


def _initialize_auth_store() -> None:
    with sqlite3.connect(AUTH_DB_FILE, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_flows (
                state TEXT PRIMARY KEY,
                code_verifier TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                credentials_json TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            "DELETE FROM oauth_flows WHERE expires_at <= ?",
            (time.time(),),
        )
        connection.execute(
            "DELETE FROM user_sessions WHERE expires_at <= ?",
            (time.time(),),
        )


def _store_oauth_flow(state: str, flow: Flow) -> None:
    if not flow.code_verifier:
        raise RuntimeError("Google OAuth did not create a PKCE verifier.")

    expires_at = time.time() + 600
    with sqlite3.connect(AUTH_DB_FILE, timeout=10) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO oauth_flows (state, code_verifier, expires_at)
            VALUES (?, ?, ?)
            """,
            (state, flow.code_verifier, expires_at),
        )
    oauth_flows[state] = flow


def _pop_oauth_flow(state: str) -> Flow | None:
    flow = oauth_flows.pop(state, None)
    if flow is not None:
        with sqlite3.connect(AUTH_DB_FILE, timeout=10) as connection:
            connection.execute("DELETE FROM oauth_flows WHERE state = ?", (state,))
        return flow

    with sqlite3.connect(AUTH_DB_FILE, timeout=10) as connection:
        row = connection.execute(
            """
            SELECT code_verifier, expires_at
            FROM oauth_flows
            WHERE state = ?
            """,
            (state,),
        ).fetchone()
        connection.execute("DELETE FROM oauth_flows WHERE state = ?", (state,))

    if row is None or row[1] <= time.time():
        return None

    flow = create_google_flow()
    flow.code_verifier = row[0]
    return flow


def _store_user_session(session_id: str, session: UserSession) -> None:
    with sqlite3.connect(AUTH_DB_FILE, timeout=10) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO user_sessions
                (session_id, credentials_json, profile_json, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                session_id,
                session.credentials.to_json(),
                json.dumps(session.profile),
                session.expires_at,
            ),
        )
    user_sessions[session_id] = session


def _load_user_session(session_id: str) -> UserSession | None:
    with sqlite3.connect(AUTH_DB_FILE, timeout=10) as connection:
        row = connection.execute(
            """
            SELECT credentials_json, profile_json, expires_at
            FROM user_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        return None

    credentials = Credentials.from_authorized_user_info(
        json.loads(row[0]),
        SCOPES,
    )
    session = UserSession(
        credentials=credentials,
        profile=json.loads(row[1]),
        expires_at=row[2],
    )
    user_sessions[session_id] = session
    return session


_initialize_auth_store()


def create_google_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                settings.google_redirect_uri,
            ],
        }
    }

    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )


def _cookie_secure() -> bool:
    return settings.google_redirect_uri.startswith("https://")


def get_current_session(request: FastAPIRequest) -> UserSession:
    session_id = request.cookies.get(SESSION_COOKIE)
    session = (
        user_sessions.get(session_id or "")
        or (_load_user_session(session_id) if session_id else None)
    )
    if session is None or session.expires_at <= time.time():
        if session_id:
            user_sessions.pop(session_id, None)
            with sqlite3.connect(AUTH_DB_FILE, timeout=10) as connection:
                connection.execute(
                    "DELETE FROM user_sessions WHERE session_id = ?",
                    (session_id,),
                )
        raise HTTPException(
            status_code=401,
            detail="Gmail is not connected. Please connect your Google account first.",
        )

    return session


def get_current_credentials(request: FastAPIRequest) -> Credentials:
    return get_current_session(request).credentials


@router.get("/google")
def google_login():
    if not settings.google_client_id:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID is not configured.",
        )

    if not settings.google_client_secret:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_SECRET is not configured.",
        )

    flow = create_google_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    _store_oauth_flow(state, flow)

    response = RedirectResponse(url=authorization_url)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
    )
    return response


@router.get("/google/callback")
def google_callback(
    code: str,
    state: str,
    request: FastAPIRequest,
):
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Authorization code was not provided.",
        )

    if not state or request.cookies.get(OAUTH_STATE_COOKIE) != state:
        response = RedirectResponse(
            url=(
                f"{settings.frontend_url.rstrip('/')}/settings"
                "?gmail=error&reason=state"
            ),
            status_code=303,
        )
        response.delete_cookie(OAUTH_STATE_COOKIE, samesite="lax")
        return response

    flow = _pop_oauth_flow(state)
    if flow is None:
        response = RedirectResponse(
            url=(
                f"{settings.frontend_url.rstrip('/')}/settings"
                "?gmail=error&reason=expired"
            ),
            status_code=303,
        )
        response.delete_cookie(OAUTH_STATE_COOKIE, samesite="lax")
        return response

    callback_stage = "token exchange"
    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        if not credentials.token:
            raise ValueError("Google did not return an access token.")
        granted_scopes = set(credentials.scopes or [])
        required_scopes = set(SCOPES)
        if not required_scopes.issubset(granted_scopes):
            raise ValueError("Google did not grant all requested Gmail scopes.")

        callback_stage = "Google profile lookup"
        profile_request = Request(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"},
        )
        with urlopen(profile_request, timeout=15) as google_response:
            google_profile = json.loads(google_response.read().decode("utf-8"))

        email = google_profile.get("email") or ""
        if not email:
            raise ValueError("Google did not return an account email.")

        profile = {
            "name": google_profile.get("name")
            or email.split("@")[0].replace(".", " ").title(),
            "email": email,
            "picture": google_profile.get("picture") or "",
        }
        session_id = secrets.token_urlsafe(32)
        callback_stage = "session storage"
        _store_user_session(
            session_id,
            UserSession(
                credentials=credentials,
                profile=profile,
                expires_at=time.time() + SESSION_TTL_SECONDS,
            ),
        )

        response = RedirectResponse(
            url=f"{settings.frontend_url.rstrip('/')}/settings?gmail=connected",
            status_code=303,
        )
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
        )
        response.delete_cookie(OAUTH_STATE_COOKIE, samesite="lax")
        return response
    except Exception as exc:
        logger.error(
            "Google sign-in failed during %s (%s)",
            callback_stage,
            type(exc).__name__,
        )
        response = RedirectResponse(
            url=(
                f"{settings.frontend_url.rstrip('/')}/settings"
                "?gmail=error&reason=exchange"
            ),
            status_code=303,
        )
        response.delete_cookie(OAUTH_STATE_COOKIE, samesite="lax")
        return response


@router.get("/me")
def get_current_user_profile(
    request: FastAPIRequest,
) -> dict[str, str]:
    return get_current_session(request).profile


@router.post("/logout", status_code=204)
def logout(request: FastAPIRequest) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        user_sessions.pop(session_id, None)
        with sqlite3.connect(AUTH_DB_FILE, timeout=10) as connection:
            connection.execute(
                "DELETE FROM user_sessions WHERE session_id = ?",
                (session_id,),
            )

    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
    )
    return response
