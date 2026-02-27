"""Google OAuth 2.0 module.

Uses InstalledAppFlow(PKCE) for desktop browser login.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

import base64
import json
import os
import sys
import webbrowser
from typing import Any

import requests
from google_auth_oauthlib.flow import InstalledAppFlow

from . import AuthError
from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

SCOPES = ["openid", "email", "profile"]
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DEFAULT_GOOGLE_CLIENT_ID = (
    "989425742328-gf6rcqd68dualv7cp90ij005j1uefd4b.apps.googleusercontent.com"
)
DEFAULT_GOOGLE_CLIENT_SECRET = (
    "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"
)


class GoogleOAuth:
    """Google OAuth 2.0 auth client."""

    def __init__(self, client_id: str | None = None) -> None:
        self._client_id = self._resolve_client_id(client_id)
        self._client_secret = self._resolve_client_secret()

    def sign_in(self) -> dict[str, str]:
        """Run browser login and return id token + profile."""
        try:
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

            if sys.platform == "win32":
                webbrowser.open = lambda url, new=0, autoraise=True: (  # type: ignore[func-returns-value]
                    not os.startfile(url)
                )

            flow = InstalledAppFlow.from_client_config(
                self._build_pkce_client_config(self._client_id),
                SCOPES,
                autogenerate_code_verifier=True,
            )
            creds = flow.run_local_server(
                port=8080,
                open_browser=True,
                prompt="consent",
                success_message="ProgressEye 로그인 성공! 이 창을 닫고 앱으로 돌아가세요.",
            )
        except OSError as exc:
            raise AuthError("브라우저 로그인 서버 시작에 실패했습니다.") from exc
        except Exception as exc:
            message = str(exc)
            if "client_secret is missing" in message:
                raise AuthError(
                    "현재 OAuth 클라이언트가 client_secret을 요구합니다. "
                    "Google Cloud에서 Desktop app 타입 client_id를 사용하세요."
                ) from exc
            raise AuthError(f"Google 로그인에 실패했습니다: {exc}") from exc

        id_token_raw = getattr(creds, "id_token", None)
        id_token = str(id_token_raw) if id_token_raw else ""
        if not id_token:
            raise AuthError(
                "Google id_token을 받지 못했습니다. openid scope를 확인하세요."
            )

        access_token_raw = getattr(creds, "token", None)
        access_token = str(access_token_raw) if access_token_raw else None
        userinfo = self._fetch_userinfo(access_token, id_token)

        log.info("Google 로그인 성공")
        return {
            "id_token": id_token,
            "email": str(userinfo.get("email", "")),
            "name": str(userinfo.get("name", "")),
        }

    def _fetch_userinfo(
        self, access_token: str | None, id_token: str
    ) -> dict[str, Any]:
        """Fetch user profile from userinfo endpoint with JWT fallback."""
        if access_token:
            try:
                response = requests.get(
                    USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    return data
            except requests.RequestException as exc:
                log.warning(
                    "Google userinfo request failed, fallback to id_token payload: %s",
                    exc,
                )
            except ValueError as exc:
                log.warning(
                    "Google userinfo parse failed, fallback to id_token payload: %s",
                    exc,
                )

        payload = self._decode_jwt_payload(id_token)
        return payload if payload else {}

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict[str, Any]:
        """Decode JWT payload without verification (profile fallback only)."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return {}
            payload_b64 = parts[1]
            padding = "=" * (-len(payload_b64) % 4)
            decoded = base64.urlsafe_b64decode(payload_b64 + padding)
            data = json.loads(decoded.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}

    def _resolve_client_id(self, explicit_client_id: str | None) -> str:
        """Resolve OAuth client_id.

        Priority:
        1) explicit argument
        2) env PROGRESSEYE_GOOGLE_CLIENT_ID
        3) built-in default (for store distribution)
        """
        if explicit_client_id and explicit_client_id.strip():
            return explicit_client_id.strip()

        env_client_id = os.getenv("PROGRESSEYE_GOOGLE_CLIENT_ID", "").strip()
        if env_client_id:
            return env_client_id

        if DEFAULT_GOOGLE_CLIENT_ID:
            log.info("환경변수 미설정: 기본 Google OAuth client_id를 사용합니다.")
            return DEFAULT_GOOGLE_CLIENT_ID

        raise AuthError("Google OAuth client_id가 없습니다.")

    def _build_pkce_client_config(self, client_id: str) -> dict[str, Any]:
        """Build PKCE client config for desktop flow."""
        return {
            "installed": {
                "client_id": client_id,
                "client_secret": self._client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

    def _resolve_client_secret(self) -> str:
        """Resolve OAuth client_secret.

        Google Desktop App type treats client_secret as public —
        it provides no real security. PKCE handles auth code protection.
        See: https://developers.google.com/identity/protocols/oauth2/native-app

        Priority:
        1) env PROGRESSEYE_GOOGLE_CLIENT_SECRET
        2) built-in default (Google considers this public for desktop apps)
        """
        env_client_secret = os.getenv("PROGRESSEYE_GOOGLE_CLIENT_SECRET", "").strip()
        if env_client_secret:
            return env_client_secret

        if DEFAULT_GOOGLE_CLIENT_SECRET:
            log.info("환경변수 미설정: 기본 Google OAuth client_secret을 사용합니다.")
            return DEFAULT_GOOGLE_CLIENT_SECRET

        return ""
