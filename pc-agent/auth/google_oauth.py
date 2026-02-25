"""Google OAuth 2.0 모듈.

InstalledAppFlow를 사용하여 브라우저 기반 Google 로그인을 수행한다.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from google_auth_oauthlib.flow import InstalledAppFlow

from . import AuthError
from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

SCOPES = ["openid", "email", "profile"]
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuth:
    """Google OAuth 2.0 인증 클라이언트."""

    def __init__(self, client_secret_path: str | None = None) -> None:
        if client_secret_path is None:
            if getattr(sys, "frozen", False):
                base = Path(sys.executable).parent
            else:
                base = Path(__file__).resolve().parent.parent
            client_secret_path = str(base / "client_secret.json")
        self._client_secret_path = client_secret_path

    def sign_in(self) -> dict[str, str]:
        """브라우저 팝업으로 Google 로그인 후 사용자 정보를 반환한다.

        Returns:
            {"id_token": str, "email": str, "name": str}

        Raises:
            AuthError: 로그인 실패 시.
        """
        try:
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
            flow = InstalledAppFlow.from_client_secrets_file(
                self._client_secret_path,
                SCOPES,
            )
            creds = flow.run_local_server(
                port=8080,
                open_browser=True,
                prompt="consent",
                success_message=(
                    "ProgressEye 로그인 성공! 이 창을 닫고 앱으로 돌아가세요."
                ),
            )
        except FileNotFoundError as exc:
            raise AuthError("client_secret.json 파일을 찾을 수 없습니다.") from exc
        except OSError as exc:
            raise AuthError("브라우저 로그인 서버 시작에 실패했습니다.") from exc
        except Exception as exc:
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
        email = str(userinfo.get("email", ""))
        name = str(userinfo.get("name", ""))

        log.info("Google 로그인 성공")
        return {
            "id_token": id_token,
            "email": email,
            "name": name,
        }

    def _fetch_userinfo(
        self, access_token: str | None, id_token: str
    ) -> dict[str, Any]:
        """사용자 정보를 조회한다.

        userinfo endpoint 실패 시 id_token payload를 fallback으로 사용한다.
        """
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
                    "Google userinfo 조회 실패, id_token fallback 사용: %s", exc
                )
            except ValueError as exc:
                log.warning(
                    "Google userinfo 응답 파싱 실패, id_token fallback 사용: %s", exc
                )

        payload = self._decode_jwt_payload(id_token)
        if payload:
            return payload
        return {}

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict[str, Any]:
        """JWT payload를 검증 없이 디코딩한다."""
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
